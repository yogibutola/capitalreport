# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A document Q&A and report generation system (RAG) built on FastAPI + MongoDB + Google Cloud AI services, with a secondary pickleball league management feature.

## Commands

### Backend (Python/FastAPI)

```bash
# Run in development mode (hot reload, port 8000)
./run_debug.sh

# Install dependencies
poetry install

# Export requirements and build Docker image
./build.sh

# Run tests
python -m pytest tests/
# Run a single test file
python -m pytest tests/test_autoslot_logic.py
# Run a single test
python -m pytest tests/test_autoslot_logic.py::TestClassName::test_method_name
```

### Frontend (Angular)

```bash
cd frontend
npm install
ng serve          # Dev server on port 4200
ng build          # Production build → dist/
ng test           # Unit tests via Vitest
ng e2e            # Playwright end-to-end tests
```

### Docker

```bash
docker-compose up   # Start full stack (backend + dependencies)
docker-compose down
```

## Architecture

### Core RAG Pipeline (Document Q&A)

**Upload flow:**
1. `POST /api/v1/upload-files/` → [upload_documents.py](app/api/v1/routers/upload_documents.py)
2. `Orchestrator.process_file()` → [orchestrator.py](app/services/orchestrator.py)
3. `DataExtractor` extracts text from PDF/DOCX/XLSX/TXT
4. `TextSplitter` chunks into 2000-char segments with page/filename/GCS URL metadata
5. `EmbedData` generates embeddings via Vertex AI `text-embedding-004`
6. `MongoDBStore` saves text + embeddings to a per-document MongoDB collection
7. `GCPStore` uploads the original file to GCS bucket `capitalreport_file_storage`

**Query flow:**
1. `GET /api/v1/prahn_kijiye/` → [prashn_kijiye.py](app/api/v1/routers/prashn_kijiye.py)
2. `PrashnUttarAgent.prashn_kijiye()` → retrieves top-k similar chunks from MongoDB
3. Gemini-2.5-flash generates the answer using retrieved context
4. Report generation via `GET /api/v1/generate_report/` uses Gemini vision directly on the PDF

### Pickleball League Management (Secondary Feature)

Located entirely under `app/api/v1/routers/pickleball/`, `app/services/pb_*`, `app/store/mongo/pb_*`, `app/vo/pb/`.

Key business rules in [pb_league_service.py](app/services/pb_league_service.py):
- Auto-slotting only runs on even rounds
- Withdrawn players are excluded from auto-slot assignment
- Promotion/relegation logic moves players between groups after each round

### Layer Responsibilities

| Layer | Path | Role |
|-------|------|------|
| Routers | `app/api/v1/routers/` | HTTP handlers, request/response models |
| Services | `app/services/` | Business logic, orchestration |
| Store | `app/store/` | Data persistence (MongoDB, GCS, ChromaDB) |
| Agents | `app/agents/` | AI model interactions (Gemini, Vertex AI) |
| VO | `app/vo/` | Pydantic value objects / data models |

### Key Configuration

Environment is loaded from `.env` (not committed). Required variables:
- `GOOGLE_API_KEY` — Gemini API key
- `GOOGLE_APPLICATION_CREDENTIALS` — path to GCP service account JSON
- `GOOGLE_CLOUD_PROJECT` — GCP project ID
- `GOOGLE_CLOUD_LOCATION` — GCP region (e.g., `us-central1`)

MongoDB connection string is configured in the store layer. GCS bucket is `capitalreport_file_storage`.

### API Structure

All routes are versioned under `/api/v1/`. The FastAPI app is defined in [app/main.py](app/main.py) and CORS is enabled for `localhost:4200`.
