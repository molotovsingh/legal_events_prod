- this is a child of the POC (proof of concept) located in the docling_langextract_testing directory (v0.10.1)
  - Set POC_DIR environment variable to reference the parent POC: `export POC_DIR=~/docling_langextract_testing`
  - Or configure the path in your development environment
- always ask in case of any gaps or clarity, avoid assuming things that can be easily cleared from user or from researching the internet. Refer to the parent POC as well
- **CRITICAL:** For ANY external library/tool/service issues: WebSearch FIRST for latest documentation/API before attempting fixes. Do not trial-and-error with external deps.

---

## Guardrails Architecture (v0.2.0+)

This system implements production-grade microservice guardrails:

### Service Boundaries ✅
- **API Service:** Owns clients, cases, runs, documents (CRUD)
- **Worker Service:** Owns events, artifacts (write-only via processing)
- **Communication:** Redis queues + PostgreSQL database only
- **No Cross-Imports:** API never imports worker code, uses string-based RQ enqueues
- **Enforced:** Dockerfiles copied service-specific code only

### Data Contracts ✅
- **API Read/Write:** clients, cases, runs, documents
- **Worker Read-Only:** clients, cases, runs, documents
- **Worker Write-Only:** events, artifacts
- **Field Ownership:** API owns run.run_metadata (not metadata)

### Immutable Images ✅
- **Production:** docker-compose.yml uses COPY only (immutable)
- **Development:** docker-compose.override.yml provides hot-reload mounts
- **Deployment:** Use `docker compose -f docker-compose.yml up` (production)
- **Development:** Use `docker compose up` (loads override automatically)

### Operational Requirements
- API latency: P95 < 200ms on CRUD operations
- Worker isolation: Killing workers doesn't break API
- Queue monitoring: Track queued/started/failed job counts
- Horizontal scaling: Workers scale stateless (docker compose up --scale worker=N)
- Idempotency: Document processing retries are safe

### Environment Setup
```bash
# Development (with hot-reload)
docker compose up

# Production (immutable images only)
docker compose -f docker-compose.yml up -d

# Scale workers in production
docker compose -f docker-compose.yml up -d --scale worker=3
```

### Import Rules
- **NEVER:** `from worker import ...` in API code
- **ALWAYS:** Use string-based RQ enqueues: `queue.enqueue("worker.tasks.process_run")`
- **NEVER:** `from api import ...` in Worker code
- **ALWAYS:** Use database/Redis for all communication

### What Changed in v0.2.0
- ✅ Removed `COPY worker` from Dockerfile.api
- ✅ Removed `COPY api` from Dockerfile.worker
- ✅ Removed bind mounts from docker-compose.yml (production)
- ✅ Created docker-compose.override.yml for development