# Backend — Content Management System

FastAPI backend for the book summary Kanban app. Connects to Neon PostgreSQL, triggers voice/audio generation jobs in the background.

## Stack

- FastAPI + Python 3.13
- SQLAlchemy 2.0 async (asyncpg)
- Neon PostgreSQL
- Pydantic v2 + pydantic-settings
- pytest + pytest-asyncio

## File Structure

```
backend/
├── main.py                     # App entry, CORS, router mounts, /health
├── config.py                   # Pydantic settings (reads ../.env)
├── database.py                 # asyncpg engine + SessionLocal
├── models.py                   # ORM: Summary, Review, PipelineJob
├── schemas.py                  # Pydantic: SummaryCard, SummaryDetail, KanbanBoard,
│                               #           JobCreate, JobStatus, ReviewOut, etc.
├── requirements.txt
├── pytest.ini                  # asyncio_mode=auto, pythonpath=..
│
├── routers/
│   ├── summaries.py            # GET /api/summaries/kanban
│   │                           # GET /api/summaries/categories
│   │                           # GET /api/summaries/voices
│   │                           # GET /api/summaries/{linear_id}
│   │                           # PATCH /api/summaries/{linear_id}
│   ├── pipeline.py             # POST /api/jobs  (trigger background job)
│   │                           # GET  /api/jobs/{job_id}  (poll status)
│   └── reviews.py              # GET /api/reviews/{linear_id}?language=
│
├── services/
│   ├── voice_service.py        # generate_voice_text() — wraps modules/generate_voice_text
│   └── audio_service.py        # generate_audio() — wraps modules/chapter_audio_processor
│
├── migrations/
│   ├── 001_initial.sql         # Neon schema: summaries, reviews, pipeline_jobs
│   └── migrate_sqlite.py       # One-time SQLite → Neon migration (1418 rows)
│
└── tests/
    ├── conftest.py             # Session-scoped engine.dispose()
    ├── test_database.py
    ├── test_summaries_router.py
    ├── test_pipeline_router.py
    └── test_reviews_router.py
```

## Setup

```bash
# Install dependencies (from content_management_system/ root)
pip install -r backend/requirements.txt

# Run dev server (from content_management_system/ root)
uvicorn backend.main:app --reload --port 8000

# Run tests (from content_management_system/ root)
cd backend && pytest
```

## Environment

`.env` at `content_management_system/` root is loaded by `config.py`. Required vars:

```bash
NEON_CONNECTION_STRING=postgresql://...   # or DATABASE_URL
ELEVENLABS_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
VOICE_TEXTS_DIR=/abs/path/to/voice_texts
AUDIOS_ROOT=/abs/path/to/audios
INPUT_DIR=/abs/path/to/input
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/summaries/kanban` | Board grouped by voice_status (filters: language, category, voice_name, top_150, search) |
| GET | `/api/summaries/categories` | Distinct categories |
| GET | `/api/summaries/voices` | Distinct voice names |
| GET | `/api/summaries/{linear_id}` | Full summary detail |
| PATCH | `/api/summaries/{linear_id}` | Update voice_status / voice_name / voice_id / audio_url |
| POST | `/api/jobs` | Trigger voice_text or audio job |
| GET | `/api/jobs/{job_id}` | Poll job status |
| GET | `/api/reviews/{linear_id}` | Reviews for a summary |
| GET | `/health` | Health check |

## Notes

- `modules/` must be on Python path — `pytest.ini` sets `pythonpath = ..` (parent = `content_management_system/`)
- Sync voice/audio functions run via `asyncio.to_thread` to avoid blocking the event loop
- Job failure path calls `session.rollback()` before updating status (prevents "session in bad state" error)
