# Handoff Notes for New Mac Mini Setup

**Date:** 2026-01-26
**Previous Machine:** iMac
**Target:** New Mac Mini

---

## Repositories to Clone

```bash
# Main application
git clone https://github.com/molotovsingh/legal_events_prod.git ~/legal-events-production

# Private core package (MUST be at this exact path)
git clone https://github.com/molotovsingh/-legal-events-core.git ~/legal-events-core
```

---

## Prerequisites

1. **Docker Desktop** - Required for running services
2. **Environment file** - Copy `.env` from old machine or create from `.env.example`

---

## Docker Path Issue

Docker binary is at `/Applications/Docker.app/Contents/Resources/bin/docker`. If `docker` command not found, either:

```bash
# Option 1: Add to PATH in ~/.zshrc
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Option 2: Use full path
/Applications/Docker.app/Contents/Resources/bin/docker compose up -d
```

---

## Starting the Application

```bash
cd ~/legal-events-production
docker compose up -d
```

Services:
- **API**: http://localhost:8000
- **Frontend**: http://localhost:3000
- **MinIO Console**: http://localhost:9001
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

---

## Recent Changes (This Session)

### Feature: Document Classification Now Runs by Default

**What changed:**
- Removed "Enable Document Classification" checkbox from UI
- Kept classifier model dropdown (users can still pick model)
- Classification always runs with default model `meta-llama/llama-3.3-70b-instruct`

**Files modified:**
- `frontend/index.html` - Removed checkbox
- `frontend/app.js` - Always send `enable_classification: true`
- `api/schemas.py` - Default `enable_classification=True`
- `worker/tasks_refactored.py` - Always run classifier
- `docker-compose.override.yml` - Mount legal-events-core package

### Fix: Broken Imports in legal-events-core

Fixed relative imports in:
- `legal_events_core/adapters/docling_adapter.py`
- `legal_events_core/adapters/langextract_client.py`

---

## Development Setup Notes

The `docker-compose.override.yml` mounts the local `legal-events-core` package and installs it on container startup:

```yaml
volumes:
  - ~/legal-events-core:/app/legal-events-core
command:
  - sh
  - -c
  - |
    pip install -e /app/legal-events-core --quiet
    # ... rest of startup
```

This enables hot-reload of core package changes.

---

## Key Architecture Points

1. **Service Boundaries**: API owns clients/cases/runs/documents. Worker owns events/artifacts.
2. **Communication**: Redis pub/sub for worker→API status updates
3. **Provider**: OpenRouter is the default LLM provider
4. **Default Model**: `meta-llama/llama-3.3-70b-instruct`

---

## Login Credentials (Development)

- **Email**: dev@localhost
- **Password**: devpass123

---

## Useful Commands

```bash
# View logs
docker compose logs -f api
docker compose logs -f worker

# Restart services
docker compose restart api worker

# Health check
curl http://localhost:8000/health

# Run tests
pytest tests/ -v
```

---

## Environment Variables Required

At minimum in `.env`:
- `JWT_SECRET_KEY` - Generate with `openssl rand -hex 32`
- `DATABASE_URL` - PostgreSQL connection string
- `OPENROUTER_API_KEY` - For LLM calls

See `.env.example` for full list.
