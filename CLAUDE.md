# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Legal Events Extraction - a production system for extracting legal events from documents (PDFs, emails) using LLM providers. Forked from the POC at `~/docling_langextract_testing` (v0.10.1).

## Common Commands

```bash
# Development (with hot-reload)
docker compose up

# Production (immutable images)
docker compose -f docker-compose.yml up -d

# Scale workers
docker compose -f docker-compose.yml up -d --scale worker=3

# Service management
./start.sh start      # Start all services
./start.sh stop       # Stop all services
./start.sh status     # Check service health
./start.sh logs       # View logs
./start.sh clean      # Clean and restart

# Run tests
pytest tests/ -v                                    # All tests
pytest tests/test_api_endpoints.py -v               # API endpoint tests
pytest tests/test_token_counter.py -v               # Unit tests
./run_integration_tests.sh                          # Integration tests with env setup
./run_integration_tests.sh tests/test_specific.py   # Run specific integration test

# Database migrations
alembic upgrade head                    # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

## Architecture

### Service Boundaries (Microservice Pattern)
- **API Service** (`api/`): Owns clients, cases, runs, documents (CRUD). FastAPI on port 8000.
- **Worker Service** (`worker/`): Owns events, artifacts (write-only). Background processing via RQ.
- **Communication**: Redis queues + PostgreSQL only. No cross-imports between API and Worker.

### Core Engine (Private Package)
The extraction pipeline has been separated into a private package: `legal-events-core`
located at `~/legal-events-core/`. This protects proprietary extraction logic from
outsourced developers who only need access to the application layer.

```bash
# Install core engine for development
pip install -e ~/legal-events-core

# For production (from private git repo)
pip install git+ssh://git@github.com/your-org/legal-events-core.git
```

### Key Directories
```
api/                # FastAPI application
├── main.py         # REST endpoints
├── schemas.py      # Pydantic models
├── auth.py         # JWT authentication
└── event_processor.py  # Consumes worker events

worker/             # Background job processing
├── tasks_refactored.py  # CANONICAL task implementation (use this, not tasks.py)
└── main.py         # Worker entry point

infra/              # Shared infrastructure
├── models.py       # SQLAlchemy ORM models
├── database.py     # Database session management
├── storage.py      # MinIO/S3 storage client
├── queue.py        # Redis/RQ job queue
└── worker_events.py # Redis pub/sub for worker→API events

frontend/           # Static web UI (served via nginx)
```

### Event-Driven Worker → API Communication
Workers emit events via Redis pub/sub (`worker:events`). API's `event_processor.py` subscribes and updates Run/Document status. This maintains strict service boundaries.

### Provider System (v0.11.0+)
Single registry in `core/providers.py`. All providers use standardized `config.model` field.

**Adding a new provider:**
1. Create config class in `core/config.py` with `model` field
2. Create adapter in `core/myprovider_adapter.py`
3. Register in `core/providers.py:PROVIDERS`
4. Add to `core/config.py:load_provider_config()` registry

**Default provider:** `openrouter` with model `meta-llama/llama-3.3-70b-instruct`

## Import Rules

```python
# NEVER in API code:
from worker import ...  # Use string-based RQ enqueues instead
queue.enqueue("worker.tasks_refactored.process_run", ...)

# NEVER in Worker code:
from api import ...  # Use database/Redis for all communication
```

## Environment Variables

Required (at least one LLM provider):
- `OPENROUTER_API_KEY` (recommended)
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`

Security:
- `JWT_SECRET_KEY` - Required in production (generate with `openssl rand -hex 32`)
- `APP_ENV` - `development`, `staging`, or `production`

See `.env.example` for full configuration options.

## Key Endpoints

- `GET /health` - Basic health check
- `GET /v1/workers/status` - Detailed worker health with heartbeat detection
- `GET /v1/providers` - List available LLM providers
- `POST /v1/runs` - Create extraction run
- `GET /v1/runs` - List runs with pagination
- `POST /v1/estimate-tokens` - Pre-run cost estimation

## Monitoring

```bash
# Live event stream
redis-cli SUBSCRIBE "worker:events"

# Event history for a run
redis-cli LRANGE "worker:events:history:<run_id>" 0 -1

# Queue status
redis-cli LLEN "rq:queue:default"
redis-cli LLEN "rq:queue:failed"
```

## Working with this Codebase

- **CRITICAL:** For external library issues, WebSearch FIRST for latest docs before attempting fixes
- Always ask for clarification on gaps rather than assuming
- Refer to the parent POC at `~/docling_langextract_testing` for context
- `worker/tasks.py` is deprecated - use `worker/tasks_refactored.py`
- Working providers: OpenRouter, Anthropic, OpenAI (3/5 validated)
