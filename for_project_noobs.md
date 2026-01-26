# Legal Events Extraction - For Project Noobs

*A plain-language guide to understanding this codebase, its architecture, and the lessons learned building it.*

---

## What Does This Project Do?

Imagine you're a lawyer drowning in thousands of pages of legal documents - contracts, court filings, correspondence. You need to extract a timeline of "what happened when" from all these documents. That's exactly what this system does.

**In simple terms**: Upload PDFs/emails → AI reads them → Get a structured timeline of legal events

The output is a clean table with:
| No | Date | Event Particulars | Citation | Document Reference |
|----|------|-------------------|----------|-------------------|
| 1 | 2024-03-15 | Contract signed between parties | Clause 3.2 | Agreement.pdf |
| 2 | 2024-04-01 | First payment received | Invoice #1234 | Receipt.pdf |

---

## The Architecture (The Big Picture)

Think of this system like a restaurant:

```
┌─────────────────────────────────────────────────────────────────┐
│                        THE RESTAURANT                            │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │   FRONTEND   │    │     API      │    │   WORKER     │       │
│  │  (The Menu)  │───▶│ (The Waiter) │───▶│ (The Kitchen)│       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                             │                    │               │
│                             ▼                    ▼               │
│                      ┌──────────────┐    ┌──────────────┐       │
│                      │  PostgreSQL  │    │ legal-events │       │
│                      │  (Orders DB) │    │    -core     │       │
│                      └──────────────┘    │ (Secret      │       │
│                                          │  Recipes)    │       │
│                                          └──────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

### The Components

1. **Frontend** (`frontend/`) - The menu customers see
   - Simple HTML/JS interface
   - Upload documents, view results
   - No fancy framework - just vanilla JavaScript

2. **API** (`api/`) - The waiter taking orders
   - FastAPI application (Python's fast web framework)
   - Handles authentication, file uploads, job creation
   - Doesn't do the actual extraction work

3. **Worker** (`worker/`) - The kitchen doing the cooking
   - Background job processor using Redis Queue (RQ)
   - Picks up jobs and processes documents
   - Uses the secret recipes (core engine) to extract events

4. **Core Engine** (`~/legal-events-core/`) - The secret recipes (PRIVATE!)
   - **This is in a SEPARATE repository for IP protection**
   - Contains the LLM prompts, adapters, and extraction logic
   - Outsourced developers can't see this code

5. **Infrastructure** (`infra/`) - The restaurant's utilities
   - Database connections, storage, queues
   - Shared by both API and Worker

---

## Why Is The Core Engine Separate?

Here's a real-world scenario: You hire contractors to build the frontend, but you don't want them seeing your proprietary AI prompts that took months to perfect.

**The Solution**: We extracted the "secret sauce" into a private Python package:

```
YOUR PRIVATE REPOS (only you can see)
├── legal-events-core/          ← The secret recipes
│   └── legal_events_core/
│       ├── adapters/           ← How we talk to different AIs
│       ├── prompts/            ← The magic prompts
│       └── pipeline.py         ← The extraction logic

SHARED WITH CONTRACTORS
├── legal-events-production/    ← The app shell
│   ├── api/                    ← REST API (they can modify)
│   ├── worker/                 ← Job processor (they can modify)
│   ├── frontend/               ← UI (they work here mostly)
│   └── infra/                  ← Database/storage stuff
```

**How it works**:
- Contractors install the core package as a dependency: `pip install -e ~/legal-events-core`
- They can USE the package but can't see its source code
- All they see is: `from legal_events_core import LegalEventsPipeline`

---

## The Data Flow (How a Document Gets Processed)

```
1. User uploads PDF via frontend
         │
         ▼
2. API receives file, stores in MinIO (S3-compatible storage)
         │
         ▼
3. API creates a "Run" record in PostgreSQL
         │
         ▼
4. API pushes job to Redis Queue: "Hey, process Run #123"
         │
         ▼
5. Worker picks up job from Redis
         │
         ▼
6. Worker downloads file from MinIO
         │
         ▼
7. Worker calls legal-events-core:
   ┌─────────────────────────────────────────┐
   │  a. Docling extracts text from PDF      │
   │  b. LLM (via OpenRouter) extracts events│
   │  c. Results formatted into 5 columns    │
   └─────────────────────────────────────────┘
         │
         ▼
8. Worker saves events to PostgreSQL
         │
         ▼
9. Worker emits Redis event: "Run #123 complete!"
         │
         ▼
10. API receives event, updates Run status
         │
         ▼
11. Frontend polls API, shows results to user
```

---

## The Technologies (And Why We Chose Them)

### FastAPI (API Framework)
**What**: Modern Python web framework
**Why**:
- Automatic OpenAPI documentation
- Built-in validation with Pydantic
- Async support (though we use sync for simplicity)
- Type hints make code self-documenting

### Redis + RQ (Job Queue)
**What**: Background job processing
**Why**:
- Document processing takes 10-60 seconds
- Can't make users wait that long
- Workers can be scaled independently
- If a job fails, it can be retried

**The alternative we didn't choose**: Celery (too complex for our needs)

### PostgreSQL (Database)
**What**: Relational database
**Why**:
- ACID compliance (data integrity matters for legal docs)
- Proper foreign key relationships
- Well-understood, battle-tested

### MinIO (Object Storage)
**What**: S3-compatible storage
**Why**:
- Documents can be large (100MB+ PDFs)
- Don't want to bloat the database
- Can be replaced with real S3 in production

### Docling (PDF Processing)
**What**: IBM's document understanding library
**Why**:
- Handles complex PDFs (tables, headers, footers)
- Extracts structured text, not just raw bytes
- Better than PyMuPDF for complex documents

### OpenRouter (LLM Provider)
**What**: API gateway to multiple LLMs
**Why**:
- Access to Llama, Claude, GPT through one API
- Easy to switch models without code changes
- Cost optimization (use cheaper models for simpler docs)

---

## Service Boundaries (The Golden Rule)

**THE RULE**: API and Worker NEVER directly modify each other's data.

```
API owns:                    Worker owns:
├── Clients                  ├── Events (extracted data)
├── Cases                    └── Artifacts (output files)
├── Runs
└── Documents

Communication happens through:
├── Redis Queue (API → Worker: "process this")
└── Redis Pub/Sub (Worker → API: "I'm done")
```

**Why this matters**:
- You can deploy API and Worker separately
- One crashing doesn't corrupt the other's data
- Easier to scale workers without touching API

**The bug we avoided**: Early version had workers directly updating Run status in the database. This caused race conditions when multiple workers processed the same run. Now workers only EMIT events, and API REACTS to them.

---

## Lessons Learned (The Hard Way)

### 1. The "Magic Import" Disaster
**What happened**: Workers imported API code, API imported Worker code. Circular dependency nightmare.

**The fix**: Strict boundary - workers enqueue jobs by STRING name, not by importing the function:
```python
# WRONG (creates circular import)
from worker.tasks import process_run
queue.enqueue(process_run, run_id)

# RIGHT (string-based reference)
queue.enqueue("worker.tasks_refactored.process_run", run_id)
```

### 2. The "Five Column Guarantee"
**What happened**: LLM sometimes returned 3 columns, sometimes 7. Broke the frontend every time.

**The fix**: Pipeline ALWAYS returns exactly 5 columns. If LLM fails, we create a fallback record:
```python
{
    "number": 1,
    "date": "No date available",
    "event_particulars": "Processing failed: [error message]",
    "citation": "No citation available",
    "document_reference": filename
}
```

### 3. The "JWT Token in URL" Security Hole
**What happened**: First version passed JWT tokens in query parameters. These got logged everywhere.

**The fix**: Always use `Authorization: Bearer <token>` header. Never put tokens in URLs.

### 4. The "Provider Config Field" Chaos
**What happened**: Different providers used different field names (`model_name`, `model_id`, `model`). Nightmare to maintain.

**The fix**: v0.11.0 standardized ALL configs to use `config.model`. Single source of truth in `providers.py`.

### 5. The "Streamlit Dependency" Trap
**What happened**: Core pipeline had `import streamlit` for caching. This pulled in 200MB of dependencies for server-side code that never used Streamlit.

**The fix**: Made Streamlit optional:
```python
try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False
```

---

## How to Run This Locally

### Quick Start (Docker)
```bash
# Start everything
docker compose up

# Access the app
open http://localhost:8000
```

### Development Mode (Manual)
```bash
# 1. Install the private core package
pip install -e ~/legal-events-core

# 2. Install app dependencies
pip install -r requirements.txt

# 3. Start infrastructure (Postgres, Redis, MinIO)
docker compose up postgres redis minio -d

# 4. Run database migrations
alembic upgrade head

# 5. Start the API (in one terminal)
uvicorn api.main:app --reload

# 6. Start the worker (in another terminal)
python -m worker.main
```

### Environment Variables
Copy `.env.example` to `.env` and fill in:
- `OPENROUTER_API_KEY` - Get from openrouter.ai
- `JWT_SECRET_KEY` - Generate with `openssl rand -hex 32`

---

## The File Structure Explained

```
legal-events-production/
│
├── api/                      # The waiter (REST API)
│   ├── main.py              # All endpoints live here
│   ├── schemas.py           # Request/response models
│   └── auth.py              # JWT authentication
│
├── worker/                   # The kitchen (background jobs)
│   ├── tasks_refactored.py  # THE job definitions (use this, not tasks.py)
│   └── main.py              # Worker startup
│
├── infra/                    # Shared infrastructure
│   ├── models.py            # Database tables (SQLAlchemy)
│   ├── database.py          # DB connection handling
│   ├── storage.py           # MinIO/S3 client
│   ├── queue.py             # Redis queue helpers
│   └── worker_events.py     # Redis pub/sub for worker→API
│
├── frontend/                 # Simple HTML/JS UI
│   ├── simple.html          # The main page
│   └── simple.js            # All the JavaScript
│
├── tests/                    # Test files
├── scripts/                  # Utility scripts
├── docs/                     # Documentation
│
└── alembic/                  # Database migrations
    └── versions/            # Migration files (auto-generated)
```

---

## Common Tasks

### Adding a New LLM Provider
1. Create adapter in `legal-events-core/legal_events_core/adapters/`
2. Add config class in `legal-events-core/legal_events_core/config.py`
3. Register in `legal-events-core/legal_events_core/providers.py`

### Adding a New API Endpoint
1. Add route in `api/main.py`
2. Add schema in `api/schemas.py` if needed
3. Add tests in `tests/test_api_endpoints.py`

### Running Tests
```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_api_endpoints.py -v

# With coverage
pytest tests/ --cov=api --cov=worker
```

### Database Migration
```bash
# Create a new migration after model changes
alembic revision --autogenerate -m "add user preferences table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

---

## Debugging Tips

### "Worker not processing jobs"
```bash
# Check if worker is connected
redis-cli PING  # Should return PONG

# Check queue length
redis-cli LLEN "rq:queue:default"

# Check for failed jobs
redis-cli LLEN "rq:queue:failed"
```

### "API returns 500 error"
```bash
# Check API logs
docker compose logs api

# Or if running locally
# Look at the terminal where uvicorn is running
```

### "Document extraction fails"
```bash
# Subscribe to worker events
redis-cli SUBSCRIBE "worker:events"

# Then trigger a job and watch the output
```

### "Can't import legal_events_core"
```bash
# Make sure it's installed
pip list | grep legal-events-core

# If not, install it
pip install -e ~/legal-events-core
```

---

## The Future (Phase 2)

The `CoreClient` abstraction in `legal-events-core` is designed for a future where the core engine runs as a separate microservice:

```python
# Phase 1 (now): Direct function calls
client = CoreClient(provider="openrouter")
events = client.process_documents(files)  # Calls pipeline directly

# Phase 2 (future): HTTP calls
client = CoreClient(api_url="https://core.internal/", api_key="...")
events = client.process_documents(files)  # Makes HTTP request
```

This means the worker code won't change when we move to microservices - just the CoreClient implementation.

---

## Questions?

If you're stuck, check:
1. `CLAUDE.md` - Quick reference for common commands
2. `docs/` - Detailed documentation
3. The tests - Often the best documentation of how things work

Happy coding!
