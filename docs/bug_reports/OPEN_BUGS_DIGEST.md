# Open Bugs Digest

Updated: 2025-11-11 02:53:14Z (UTC)

Purpose: Snapshot of open issues with priorities, suggested owners, and references to full reports.

---

## ⚠️ OPEN ISSUES (2025-11-12)

**Status:** 6 bugs remain from code audit (P0 critical bugs RESOLVED).

- **P0 Critical:** 0 open ✅
- **P1 Major:** 3 open ⚠️
- **P2 Minor:** 3 open 📝

**Latest Report (2025-11-11):**
- BUG_REPORT_20251111T025314Z.md — Resource leaks, None type errors, shutdown issues
- **P0 bugs RESOLVED (2025-11-12)** — See commit 1c786ef

---

## P0 — Critical

**No open P0 issues** ✅

All P0 critical bugs from the 2025-11-11 audit have been resolved.
See "Recently Resolved (2025-11-12)" section below.

## P1 — Major (NEW)

- **MinioStorage resource leak in process_run** (worker/tasks.py:76–77)
  - Symptom: Storage instance created but never closed; long-running workers accumulate connections
  - Impact: Eventually exhausts MinIO connection pool on sustained processing
  - Fix: Implement MinioStorage.close() method; call in finally block
  - Effort: 30 minutes
  - Report: BUG_REPORT_20251111T025314Z.md

- **Event consumer infinite loop blocks shutdown** (infra/worker_events.py:213–219)
  - Symptom: pubsub.listen() blocks indefinitely; stop() cannot interrupt the loop
  - Impact: Application shutdown delayed >5 seconds; worker thread hangs
  - Fix: Add self.running flag; check in loop before processing; break on stop()
  - Effort: 20 minutes
  - Report: BUG_REPORT_20251111T025314Z.md

- **Silent error swallowing in event consumer** (infra/worker_events.py:216–219)
  - Symptom: Failed event parsing logged but not queued to DLQ; events lost permanently
  - Impact: API/worker state divergence; events processed by neither service
  - Fix: Integrate with Redis DLQ (already exists in api/event_processor.py:31)
  - Effort: 25 minutes
  - Report: BUG_REPORT_20251111T025314Z.md

## P2 — Minor (NEW)

- **Race condition in document status updates** (api/event_processor.py:228–234)
  - Symptom: No locking on concurrent reads/writes; concurrent retry events could lose updates
  - Impact: Document state becomes inconsistent under concurrent retries
  - Fix: Add optimistic locking with version column or row-level lock
  - Effort: 1–2 hours
  - Report: BUG_REPORT_20251111T025314Z.md

- **Cleanup function aborts on storage error** (worker/tasks.py:507–516)
  - Symptom: storage.list_objects() failure causes entire cleanup job to fail
  - Impact: Remaining old runs not cleaned up; disk/storage leak
  - Fix: Wrap per-run storage operations in try/except; continue on error
  - Effort: 20 minutes
  - Report: BUG_REPORT_20251111T025314Z.md

- **Blocking event consumer in application shutdown** (api/main.py + infra/worker_events.py)
  - Symptom: pubsub.listen() blocks thread; shutdown timeout may expire before graceful exit
  - Impact: Slow application shutdown; potential resource leaks on restart
  - Fix: Implement signal-based loop break; reduce blocking time
  - Effort: 30 minutes (refactor)
  - Report: BUG_REPORT_20251111T025314Z.md

---

## Recently Resolved (2025-11-12)

**3 P0 Critical Resource Leaks (commit 1c786ef)**

1. **Redis health check connection leak** ✅
   - Fixed Redis connections not being closed when health check fails
   - Added try/finally block to ensure r.close() always executes
   - Files: api/main.py:238-250
   - Impact: Prevents Redis connection pool exhaustion under sustained health checks

2. **Redis retry endpoint connection leak** ✅
   - Fixed early return on idempotency cache hit bypassing r.close()
   - Moved r.close() to finally block for all code paths
   - Files: api/main.py:1135-1149
   - Impact: Eliminates memory leak on each successful retry attempt

3. **None type error in export generation** ✅
   - Added null checks on case/client queries before attribute access
   - Explicit error logging when foreign key references are missing
   - Files: worker/tasks.py:397-406
   - Impact: Prevents worker crashes when case or client deleted

**Bug report:** bug_reports/BUG_REPORT_20251111T025314Z.md

---

## Recently Resolved (2025-11-08)

**5 Critical Security & Reliability Fixes (commit bda2a16)**

1. **Thread Safety in Storage Singleton** ✅
   - Fixed race condition in get_storage() using threading.Lock()
   - Implements double-checked locking pattern
   - Files: infra/storage.py

2. **Hardcoded MinIO Credentials** ✅
   - Removed default credentials ('minioadmin'/'minioadmin123')
   - Requires explicit MINIO_ACCESS_KEY and MINIO_SECRET_KEY env vars
   - Files: infra/storage.py, setup_minio_cors.py

3. **SSE Streaming Infinite Loop** ✅
   - Added MAX_ITERATIONS limit (1800 = 1 hour)
   - Sends timeout event if exceeded
   - Files: api/main.py

4. **Redis Connection Exception Handling** ✅
   - Added connection validation with SystemExit on failure
   - Files: infra/queue.py

5. **Event Processor Resource Leak** ✅
   - Added redis_conn.close() and context manager support
   - Files: api/event_processor.py

6. **S3Error Exception Handling** ✅
   - Captures error.code and error.message for all operations
   - Files: infra/storage.py

**Bug report retired:** bug_reports/retired/BUG_REPORT_20251107T033224Z.md

---

## P0 — Blockers

- DB schema mismatch: `runs.metadata` vs `run_metadata`
  - Owner: Backend
  - Action: Alembic migration to rename; run upgrade and verify exports
  - Reports: BUG_REPORT_20251105T111630Z.md, BUG_REPORT_20251105T170226Z.md
  - Status: [x] RESOLVED

- Worker dependencies missing (PyMuPDF/fitz, extract_msg, langextract)
  - Owner: Infra/Worker
  - Action: Install in worker image; choose single source for langextract
  - Reports: BUG_REPORT_20251105T111630Z.md
  - Status: [x] RESOLVED (False positive - all dependencies present in requirements.txt)

## P1 — Major

- Event provider import failures (only langextract works)
  - Owner: Backend/Infra
  - Action: Fix import paths (src.core → core), add /v1/providers endpoint, validate on startup
  - Reports: Technical debt (not in bug digest)
  - Status: [x] RESOLVED (Session 2 - fixed import paths, added /v1/providers, added startup validation)

- Cross-imports (worker imports `api.*`) — guardrail violation
  - Owner: Backend/Infra
  - Action: Extract shared infra (db/models/storage) to `infra/`; API→Worker via RQ strings
  - Reports: BUG_REPORT_20251105T113653Z.md, BUG_REPORT_20251105T112000Z.md
  - Status: [x] RESOLVED (v0.4.0 - Event-driven architecture with service boundaries, worker/tasks_refactored.py)

- Worker mutates API-owned entities (runs/documents)
  - Owner: Backend
  - Action: Worker emits progress only; API updates run/document state
  - Reports: BUG_REPORT_20251105T113842Z.md
  - Status: [x] RESOLVED (v0.4.0 - Worker emits events via Redis pub/sub, API event processor updates entities)

- SSE DB session lifecycle in `/v1/runs/{id}/stream`
  - Owner: Backend
  - Action: Use dedicated DB session inside generator; close on exit
  - Reports: BUG_REPORT_20251105T170226Z.md
  - Status: [x] RESOLVED (Session 2 - verified correct implementation)

- LangExtract installation source unification
  - Owner: Infra/Worker
  - Action: Pick PyPI or pinned Git tag; remove the other
  - Reports: BUG_REPORT_20251105T125718Z.md
  - Status: [x] RESOLVED (Session 2 - pinned in requirements.txt, removed from Dockerfiles)

- UI “Recent Runs” lists cases (misleading)
  - Owner: Frontend
  - Action: Add runs-by-case endpoint and render real runs; or rename temporarily
  - Reports: BUG_REPORT_20251106T011941Z.md
  - Status: [x] RESOLVED (Renamed panel to “Browse Cases”)

## P2 — Minor / Docs / Ops

- MinIO CORS for presigned PUTs not documented
  - Owner: Ops/Infra
  - Action: Document CORS policy and quick verification
  - Reports: BUG_REPORT_20251105T130411Z.md
  - Status: [x] RESOLVED (docs/MINIO_CORS_SETUP.md)

- MinIO public endpoint replacement robustness
  - Owner: Backend
  - Action: Use `urllib.parse` to rebuild URLs when swapping endpoint
  - Reports: BUG_REPORT_20251106T031335Z.md
  - Status: [x] RESOLVED (commit 86aca25 - Storage key standardization with validation)

- UI long text truncation (table overflow)
  - Owner: Frontend
  - Action: CSS ellipsis + tooltip/expand for full text
  - Reports: BUG_REPORT_20251106T012024Z.md
  - Status: [x] RESOLVED (commit 214dd16)

- Presign flow clarity (filename mapping)
  - Owner: Frontend/Docs
  - Action: Document current presign behavior and storage key schema
  - Reports: BUG_REPORT_20251105T125656Z.md
  - Status: [x] RESOLVED (Two-step filename-aware presign)

- Docker container resource limits
  - Owner: Infra/Ops
  - Action: Add CPU and memory limits to prevent resource exhaustion
  - Reports: BUG_REPORT_20251107T120000Z.md, BUG_REPORT_20251107T025003Z.md
  - Status: [x] RESOLVED (commit a8caf1a - All services now have resource limits)

## Recently Resolved (2025-11-07)

**7 production-readiness fixes applied:**

1. **JWT Security** (commit 4efdebb)
   - Requires explicit JWT_SECRET_KEY in production environments
   - Fail-fast behavior prevents insecure deployments
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #1)

2. **Pagination Validation** (commit 253b505)
   - Added Query(ge=0, le=1000) validators to API endpoints
   - Prevents DoS attacks via unbounded limit parameters
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #6), BUG_REPORT_20251107T025003Z.md (Issue #6)

3. **Config Validation** (commit 1400833)
   - Added __post_init__ validation for STUCK_DOCUMENT_HOURS (1-72 hour range)
   - Fail-fast on invalid configuration
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #3), BUG_REPORT_20251107T025003Z.md (Issue #5)

4. **Docker Resource Limits** (commit a8caf1a)
   - Added CPU/memory limits to all 6 services
   - Prevents container resource exhaustion
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #10), BUG_REPORT_20251107T025003Z.md (Issue #2)

5. **MinIO Timeout Handling** (commit bd31b7a)
   - Added 30-second timeout with circuit breaker pattern
   - Prevents API hanging on MinIO network issues
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #8), BUG_REPORT_20251107T025003Z.md (Issue #3)

6. **Event Processor Retries** (commit d58290d)
   - Implemented 3-attempt retry with exponential backoff (1s, 2s, 4s)
   - Added Dead Letter Queue (DLQ) in Redis for permanently failed events
   - Reports: BUG_REPORT_20251107T120000Z.md (Issue #4)

7. **Storage Key Standardization** (commit 86aca25)
   - Created infra/storage_keys.py with validation utilities
   - Standardized key generation across 3+ locations
   - Prevents path traversal and key inconsistencies

**Bug reports retired:**
- bug_reports/retired/BUG_REPORT_20251107T120000Z.md
- bug_reports/retired/BUG_REPORT_20251107T025003Z.md

## Recently Resolved (to archive when verified)

- SQLAlchemy `text()` in health checks (API + DB)
  - Reports: BUG_REPORT_20251105T170226Z.md (Resolved section)
  - Status: [ ] Ready to archive after verification

- FIVE_COLUMN_HEADERS import in API exports
  - Reports: BUG_REPORT_20251105T111630Z.md (Resolved via import)
  - Status: [ ] Ready to archive after verification

- Duplicate dependency (python-multipart)
  - Reports: BUG_REPORT_20251105T170226Z.md (Resolved section)
  - Status: [ ] Ready to archive after verification

## Resolved — Commit References

- BUG_REPORT_20251105T125656Z.md (Presigned Upload Key Mismatch)
  - Commit: d3fb9be — fix(storage): resolve presigned upload key mismatch causing worker failures

- BUG_REPORT_20251105T130411Z.md (MinIO CORS Documentation)
  - Commit: 56d90fe — fix: Fix SSE DB session lifecycle and add MinIO CORS documentation (docs/MINIO_CORS_SETUP.md)

- BUG_REPORT_20251106T011941Z.md (UI “Recent Runs” misleading)
  - Commit: 1feb33c — fix(ui): rename misleading "Recent Runs" section to "Browse Cases"

- BUG_REPORT_20251106T012024Z.md (UI long text overflow)
  - Commit: 214dd16 — fix(ui): truncate long event text with hover tooltips

- BUG_REPORT_20251106T033605Z.md (Alembic enum migrations)
  - Commit: 01b3058 — docs(migrations): add comprehensive enum migration patterns guide (docs/ENUM_MIGRATIONS.md)

- BUG_REPORT_20251106T033627Z.md (Docling OCR memory)
  - Commit: 7869ef2 — docs(ocr): add comprehensive OCR memory management guide (docs/OCR_MEMORY_MANAGEMENT.md)

- BUG_REPORT_20251106T033703Z.md (Anthropic SDK audit)
  - Commit: b38a305 — docs(audit): complete Anthropic SDK integration audit (docs/ANTHROPIC_SDK_AUDIT.md)

## Notes

- Guardrails to enforce in all fixes:
  - No API ↔ Worker cross-imports; use shared `infra/*` and RQ string enqueues
  - Worker read-only for clients/cases/runs/documents; writes events/artifacts only
  - Storage keys include `clients/{client_id}/cases/{case_id}/runs/{run_id}/…`
  - Auth/secrets safe for production (no default creds)
