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

---

## Technical Debt (v0.3.0 Sprint)

### Event Provider Import Failures
**Issue:** Only `langextract` (Gemini) provider is fully working. Other providers (OpenRouter, Anthropic, OpenAI, DeepSeek) defined in `core/event_extractor_catalog.py` fail to register due to import path issues.

**Root Cause:** Factory callables use `src.core.*` import paths that fail to resolve in worker runtime context.

**Files Affected:**
- `core/event_extractor_catalog.py` (Lines 51-132) - Defines 7 providers, only langextract works
- `core/extractor_factory.py` (Lines 229-234) - Import failures silently fail with warnings
- `frontend/index.html` - Dropdown shows providers that don't work (temporary workaround: langextract is now default option)

**Fix for v0.3.0:**
1. Change factory_callable import paths from `src.core.*` to absolute/relative imports
2. Add startup validation that fails loudly if enabled providers can't load
3. Create `/v1/providers` API endpoint to expose available providers dynamically
4. Update frontend to fetch provider list from API instead of hardcoding

**Workaround (Current - v0.2.0):**
- UI dropdown manually updated to show langextract as working option
- Other providers listed but will error if selected (marked as future work)