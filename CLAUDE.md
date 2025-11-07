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

## Event-Driven Architecture (v0.4.0+)

### Overview
The system has been upgraded to use event-driven communication between Worker and API services, ensuring strict service boundary compliance and enabling independent scaling.

### Worker → API Communication Pattern
- **Worker:** Processes documents, emits status events via Redis pub/sub
- **API:** Subscribes to worker events, updates API-owned entities (runs/documents)
- **Result:** Clean service boundaries, no direct database mutations across services

### Key Components

#### 1. Event System (`infra/worker_events.py`)
- `WorkerEventEmitter`: Worker-side component that publishes events to Redis
- `WorkerEventConsumer`: API-side component that subscribes to events
- `WorkerEvent`: Event dataclass with JSON serialization
- Supports run lifecycle events: `RUN_STARTED`, `RUN_COMPLETED`, `RUN_FAILED`
- Supports document lifecycle events: `DOCUMENT_STARTED`, `DOCUMENT_COMPLETED`, `DOCUMENT_FAILED`
- Persists events in Redis with 7-day expiry for audit trail

#### 2. Event Processor (`api/event_processor.py`)
- `APIEventProcessor`: Runs in background thread consuming Redis events
- Updates Run/Document status based on worker events
- Maintains timing metadata (total_seconds, docling_seconds, extractor_seconds)
- Tracks cost estimates (cost_usd)
- Handles all lifecycle transitions with proper error handling

#### 3. Refactored Worker Tasks (`worker/tasks_refactored.py`)
- **CANONICAL implementation** for worker processing
- **Old `worker/tasks.py` is deprecated** - use `tasks_refactored.py` exclusively
- Emits events instead of directly mutating Run/Document status
- READ-ONLY access to clients, cases, runs, documents
- WRITE-ONLY access to events, artifacts (worker's primary output)
- All job routing via `infra/queue.py` automatically uses refactored tasks

### Operational Changes
- Event processor auto-starts on API startup (lifespan context manager)
- Event processor gracefully shuts down on API shutdown
- Job enqueuing automatically routes to `worker.tasks_refactored`
- No changes needed to API endpoints - all backward compatible

### Monitoring & Debugging
```bash
# Monitor live event stream
redis-cli SUBSCRIBE "worker:events"

# Check event history for a specific run
redis-cli LRANGE "worker:events:history:123" 0 -1

# Check queue status
redis-cli LLEN "rq:queue:default"
redis-cli LLEN "rq:queue:failed"
```

### What Changed in v0.4.0
- ✅ Added `infra/worker_events.py` - Redis pub/sub event system
- ✅ Added `api/event_processor.py` - Background event consumer thread
- ✅ Added `worker/tasks_refactored.py` - Service boundary compliant tasks
- ✅ Updated `api/main.py` - Event processor lifecycle management
- ✅ Updated `infra/queue.py` - Job routing to refactored tasks
- ✅ Added `docs/SERVICE_BOUNDARIES.md` - Comprehensive architecture guide
- ✅ Marked `worker/tasks.py` as deprecated (kept for reference only)

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