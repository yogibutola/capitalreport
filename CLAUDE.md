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

## Testing expectations

Every code change must add or update tests:

- **Backend** — unittest-style tests in `tests/` (run under pytest), e.g. [tests/test_autoslot_logic.py](tests/test_autoslot_logic.py), [tests/test_promotion_relegation.py](tests/test_promotion_relegation.py).
- **Frontend** — Playwright e2e specs in [frontend/e2e/](frontend/e2e/) (`npm run e2e`), e.g. [frontend/e2e/league-flow.spec.ts](frontend/e2e/league-flow.spec.ts). Add/update Vitest unit specs too where they fit, but note `npm test` currently doesn't compile — use `npm run build` plus `npm run e2e` as the gate.
  - `frontend/e2e/platform-console.spec.ts` requires the backend to run with `SUPERADMIN_EMAILS=platform.admin@test.com`; it seeds via `seed_platform_admin.py`.

Call out in the change summary which tests were added or updated.

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

Three roles, all carried in the JWT `role` claim: `player`, `admin` (**= a club**, not an operator), and `superadmin` (the application/platform admin). `deps.py` has one dependency per tier: `get_current_player`, `get_current_admin`, `get_current_superadmin`.

Access rules on top of the role (helpers in `deps.py`; tests in [tests/test_access_control.py](tests/test_access_control.py)):
- **Identity comes from the token, never the body.** Registration, group creator/voter/author all use `payload["sub"]`; body email fields are accepted but ignored.
- **Club ownership** (`require_club_owner`): a league/tournament's `club_id` is its club's email, and every admin mutation on one (round, slot, delete, draw, score, reopen) checks it against the caller. `get_current_admin` alone is not enough.
- **Self-only** (`require_self`): endpoints keyed by an email in the path (`/player/{email}/matches`, `/player/league/{email}`, `/player/tournaments/{email}`, `/groups/player/{email}`) return only the caller's own data (superadmin excepted).
- League match scores: the match's four players or the owning club. Groups: signed-in members only.
- `GET /tournament/id/{id}` serves anonymous visitors (the flyer share link) via `get_optional_user_payload`, returning event details only — no roster.
- Password-reset links are only logged when `LOG_PASSWORD_RESET_LINKS=true` (set in `run_debug.sh`; never in deployed envs).

### Platform admin console (hidden)

`superadmin` is granted **at sign-in** to any account whose email is in the `SUPERADMIN_EMAILS` env var (comma-separated; [app/utils/security.py](app/utils/security.py) `is_superadmin_email`) — the stored `players` doc keeps its own role. Sign up a normal account, add its email to `SUPERADMIN_EMAILS`, restart the backend.

- Backend: [app/api/v1/routers/pickleball/pb_admin.py](app/api/v1/routers/pickleball/pb_admin.py) → [app/services/pb_platform_service.py](app/services/pb_platform_service.py). Mounted at `/api/v1/platform-console/...` with `include_in_schema=False` (absent from OpenAPI). Lists / creates / deletes clubs and players across the whole system; deleting a club **orphans** its leagues/tournaments, deleting a player purges them from every league/tournament roster (`purge_player` on the league/tournament stores).
- Frontend: route `/x9k2-console` (+ `/x9k2-console/login`), guarded by `superAdminGuard` ([frontend/src/app/auth/super-admin.guard.ts](frontend/src/app/auth/super-admin.guard.ts)). **Intentionally not linked from any nav** and the path is unadvertised. Components in [frontend/src/app/platform/](frontend/src/app/platform/).

### Activity log (observability)

`AuditLogMiddleware` ([app/utils/audit_middleware.py](app/utils/audit_middleware.py)) records every mutating `/api/v1` request into the `audit_log` collection (`PBAuditStore`) — actor email (from the token), action label, status, duration. Sign-ins are recorded explicitly in `PBPlayerService._audit_signin` with the real actor. Surfaced in the console's Activity tab + Metrics header. No-op when `AUDIT_LOG_ENABLED != "true"` or `MONGO_URI` is unset; a write failure never breaks the request. Cloud Run: set `SUPERADMIN_EMAILS` via the `_SUPERADMIN_EMAILS` substitution in [cloudbuild.yaml](cloudbuild.yaml).

### Frontend

Angular standalone components, signals, SSR enabled. Routes in [frontend/src/app/app.routes.ts](frontend/src/app/app.routes.ts); `/admin/*` routes are behind `adminGuard`. `AdminService` ([frontend/src/app/admin/admin.ts](frontend/src/app/admin/admin.ts)) is a singleton whose `leagues` signal is cached — components that can switch clubs must refetch in `ngOnInit`. Prettier config (100 cols, single quotes) is in `frontend/package.json`.

#### Theming (dark + light)

Both themes are one token set in [frontend/src/styles.css](frontend/src/styles.css): `:root` is dark (the original design and the default), `:root[data-theme='light']` redefines the same tokens. **Component CSS must never name a literal colour** — always a token — or it won't follow the toggle; an e2e test asserts every referenced custom property resolves in both themes.

- Colours used at partial alpha go through channel tokens: `rgba(var(--tint-rgb), 0.06)`, not `rgba(255,255,255,0.06)`. `--tint-rgb` flips white→ink, so elevation washes and hairlines invert instead of vanishing on a light page. `--shadow-k` scales every shadow's alpha at once.
- `--ball` (brand lime) deepens to olive in light, and `--ball-ink` flips light to match, so `background: var(--ball); color: var(--ball-ink)` stays legible in both. The legacy lime HSL triplets (`--color-ace-lime` etc.) shift with it.
- `ThemeService` ([frontend/src/app/theme.service.ts](frontend/src/app/theme.service.ts)) resolves stored choice → OS `prefers-color-scheme` → dark, and `App` mirrors it onto `<html data-theme>`. An inline script in [frontend/src/index.html](frontend/src/index.html) applies the stored theme before first paint (SSR renders dark, so without it light users get a flash) — keep its storage key and resolution order in sync with the service.
- `<app-theme-toggle>` ([frontend/src/app/shared/theme-toggle.ts](frontend/src/app/shared/theme-toggle.ts)) is mounted in the signed-in header and both public navs.
- The app is zoneless, so `data-theme` lands on the next tick — e2e assertions about the applied theme must poll, not read once.

## Repo hygiene notes

- The repo root has many ad-hoc `verify_*.py` and `test_*.py` / `debug_*.py` scripts — these are one-off manual checks, not part of the `tests/` suite.
- `credentials.json/` is a directory in the tree; the actual GCP key file `credentials.json` and `.env` are gitignored and must be supplied locally.
- `.venv/`, `.idea/`, `.pytest_cache/` are checked in but ignored — don't edit them.
