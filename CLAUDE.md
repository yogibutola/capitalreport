# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Two features share one FastAPI backend and one Angular frontend:

1. **Document Q&A / report generation (RAG)** — upload PDF/DOCX/XLSX/TXT, ask questions, generate reports. Uses MongoDB for vector storage, GCS for original files, and Google Gemini / Vertex AI for embeddings and generation.
2. **Pickleball league management** — clubs create leagues, players register, matches are scored, and players are promoted/relegated between groups each round. This is where nearly all recent development activity is.

The two features are independent except for the shared `app.main:app`, MongoDB server, and Angular shell. The frontend `package.json` is even named `pickleball-league-app`.

## Commands

### Backend (Python 3.12 / FastAPI, Poetry)

```bash
poetry install
./run_debug.sh                      # uvicorn --reload on :8000; sets GOOGLE_* env, expects credentials.json in repo root
python -m pytest tests/              # tests are unittest-style but run under pytest
python -m pytest tests/test_autoslot_logic.py::TestClassName::test_method_name
```

`run_debug.sh` does **not** set `MONGO_URI`; export it yourself (e.g. `mongodb://localhost:27017/?directConnection=true`) or the stores raise `RuntimeError` on first use.

### Frontend (Angular 21 + SSR)

```bash
cd frontend
npm install
npm start            # ng serve on :4200, proxies /api -> http://localhost:8000 via proxy.conf.json
npm run build        # SSR build -> dist/pickleball-league-app/{browser,server}
npm test             # Vitest (via ng test)
npm run e2e          # Playwright
```

The frontend talks to the backend only through relative `/api/...` URLs. In dev that goes through `proxy.conf.json`; in SSR/prod through the Express proxy in [frontend/src/server.ts](frontend/src/server.ts), which forwards `/api` to `$BACKEND_URL` (default `http://localhost:8000`).

### Docker / local full stack

```bash
docker compose -f docker-compose-local.yml up --build   # Dockerfile.combined: backend :8000 + SSR frontend :4000 + mongo, one image (supervisord)
docker compose up                                        # docker-compose.yml: prebuilt image capitalreport:v1.0.0 + separately-built frontend
```

`build.sh` = `poetry lock` + `poetry export -f requirements.txt --without-hashes` + `docker compose -f docker-compose-local.yml up --build`. **`requirements.txt` is the source of truth for the Docker images** (the Dockerfiles `pip install -r requirements.txt`, they do not use Poetry) — regenerate it after changing `pyproject.toml`.

**Note (from prior debugging):** `docker-compose.yml` runs a pre-baked image `capitalreport:v1.0.0`; `--build` does not rebuild it. If new backend routes 404, rebuild that image tag manually.

### Deploy

[cloudbuild.yaml](cloudbuild.yaml) builds backend ([Dockerfile](Dockerfile), gunicorn on `$PORT`/8080) and frontend ([frontend/Dockerfile](frontend/Dockerfile)) images, pushes to Artifact Registry, deploys both to Cloud Run, then wires `BACKEND_URL` (frontend) and `CORS_ORIGINS` (backend) between the two services. Secrets `MONGO_URI` and `GOOGLE_API_KEY` come from Secret Manager. Header comment in the file has the one-time setup.

## Architecture

### Layer layout (both features)

| Layer | Path | Role |
|-------|------|------|
| Routers | `app/api/v1/routers/` | HTTP handlers, request/response models, per-router `get_*` dependency factories |
| Services | `app/services/` | Business logic |
| Store | `app/store/` | Persistence: `mongo_db_store.py` (RAG), `mongo/pb_*` (pickleball), `gcp_file_store.py`, `chroma_db_store.py` |
| Agents | `app/agents/` | AI model calls |
| VO | `app/vo/` | Pydantic models (`app/vo/pb/` for pickleball) |

Everything is wired manually in [app/main.py](app/main.py) and in each router's `get_orchestrator()` / `get_*_service()` function — there is no DI container. Routers are mounted under `/api/v1`.

MongoDB uses **two databases on one server**: `document_embeddings` (RAG, [app/store/mongo_db_store.py](app/store/mongo_db_store.py)) and `pickleball` (leagues, [app/store/mongo/pb_mongo_db_store.py](app/store/mongo/pb_mongo_db_store.py)). Both read `MONGO_URI` from the environment.

### RAG pipeline

Active code path: routers → [app/services/orchestrator.py](app/services/orchestrator.py) → `DataExtractor` / `TextSplitter` (2000-char chunks with page/filename/GCS-URL metadata) / `EmbedData` (`text-embedding-004`) → `MongoDBStore` + `GCPStore` (bucket `capitalreport_file_storage`). Query/report agents live in [app/agents/vertex/](app/agents/vertex/) and use `gemini-2.5-flash` (report generation runs Gemini vision directly on the PDF).

- Upload: `POST /api/v1/upload-files/`
- Query: `GET /api/v1/prahn_kijiye/` (note the spelling) and `/ask_question/`
- Report: `GET /api/v1/generate_report/`

The large `app/agents/genaiway/**` tree and `get_orchestrator()` in `main.py` are **experimental / mostly unused scratch code** — the mounted routers import from `app/services/` and `app/agents/vertex/`. Don't assume `genaiway` modules are live.

### Pickleball league logic

Core rules in [app/services/pb_league_service.py](app/services/pb_league_service.py):
- Rounds are numbered 1..N; `play_day = (round_num + 1) // 2` (two rounds per play day). Auto-slotting only runs on **even** rounds.
- Withdrawn players (matched by email + play_day in `league.withdrawals`) are excluded from the next round's slotting.
- On group completion, `process_group_promotion_relegation` moves the top player up a group and the bottom player down for the next round; boundary groups are special-cased.
- `update_league_with_round_details` splits match data out of the league document into a separate `match` collection before saving.

Auth ([app/utils/security.py](app/utils/security.py), [app/api/v1/deps.py](app/api/v1/deps.py)): JWT via `OAuth2PasswordBearer(tokenUrl="/api/v1/signin")`. `SECRET_KEY` is currently hardcoded — do not rely on it being secure; move it to env before any real deployment.

### Frontend

Angular standalone components, signals, SSR enabled. Routes in [frontend/src/app/app.routes.ts](frontend/src/app/app.routes.ts); `/admin/*` routes are behind `adminGuard`. `AdminService` ([frontend/src/app/admin/admin.ts](frontend/src/app/admin/admin.ts)) is a singleton whose `leagues` signal is cached — components that can switch clubs must refetch in `ngOnInit`. Prettier config (100 cols, single quotes) is in `frontend/package.json`.

## Repo hygiene notes

- The repo root has many ad-hoc `verify_*.py` and `test_*.py` / `debug_*.py` scripts — these are one-off manual checks, not part of the `tests/` suite.
- `credentials.json/` is a directory in the tree; the actual GCP key file `credentials.json` and `.env` are gitignored and must be supplied locally.
- `.venv/`, `.idea/`, `.pytest_cache/` are checked in but ignored — don't edit them.
