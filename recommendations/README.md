# Recommendations

Updated: 2025-11-06 (UTC)

Purpose
- Collect high‑impact, actionable recommendations to harden the system, shrink images, and align the codebase with guardrails.
- Each item is scoped so it can be implemented as an independent PR.

How To Use
- Pick from the list below. For larger items, create a short design/plan in the PR and link back here.
- Prefer one PR per recommendation to keep review fast and safe.

Index (timestamped notes)
- REC_20251106T130949Z_docker_hardening.md — Multi‑stage builds, non‑root user, .dockerignore
- REC_20251106T130949Z_db_migrations_enum.md — Alembic enums and migration strategy
- REC_20251106T130949Z_sse_alignment.md — SSE dependency alignment and endpoint hygiene
- REC_20251106T130949Z_guardrails_architecture.md — infra/ package and ownership boundaries
- REC_20251106T130949Z_storage_minio.md — MinIO CORS and public endpoint robustness
- REC_20251106T130949Z_docling_ocr_memory.md — Docling OCR memory mitigations
- REC_20251106T130949Z_anthropic_sdk_audit.md — Anthropic SDK tool/JSON reliability

High‑Impact (Security & Image Size)
1) Multi‑stage Docker builds (api, worker)
   - Builder stage: install compilers (gcc, libpq‑dev), build wheels (pip wheel -r requirements.txt), build git deps (langextract) into /wheels
   - Final stage: python:3.12‑slim; install from /wheels; do NOT include build tools
   - Outcome: Smaller images, reduced attack surface

2) Run containers as non‑root
   - Add user appuser; switch with USER appuser; COPY with --chown=appuser:appuser
   - Ensure writable paths for logs/temp/migrations
   - Outcome: Better runtime isolation

3) Move DB enum/type bootstrapping into Alembic
   - Replace inline Python in docker‑compose with an Alembic migration that creates enums idempotently
   - Compose command becomes: alembic upgrade head && uvicorn ...
   - Outcome: Cleaner compose, schema managed by migrations

Operational & Maintainability
4) Add .dockerignore to trim build context
   - Exclude: .git, .env, __pycache__/, *.pyc, .pytest_cache/, research/, large artifacts
   - Outcome: Faster, safer builds

5) Consolidate shared layers into a base image (optional)
   - Build my‑project‑base with Python + dependencies; FROM it in api/worker
   - Outcome: Faster rebuilds across services

6) depends_on health for worker
   - Use long‑form with condition: service_healthy for postgres/redis/minio (like api)
   - Outcome: Worker starts only when deps are ready

7) Isolate dev‑only settings
   - Remove --reload from base compose; keep in docker‑compose.override.yml only
   - Outcome: Prod‑like runs are not slowed by reload

Dependencies & Streaming (SSE)
8) Align SSE dependency set
   - Test branch with FastAPI 0.118.x + sse‑starlette 3.0.2; let FastAPI manage Starlette
   - Avoid GZip on SSE; consider client disconnect handling
   - Outcome: More reliable streaming and cleanup

9) Pin LangExtract source
   - Use a tagged release or commit for the Git install; document version
   - Outcome: Reproducible builds

Architecture & Guardrails
10) Create infra/ shared package and remove cross‑imports
   - Move DB session/models/storage helpers to infra/*
   - API enqueues worker via RQ string names; worker imports infra/* only
   - Outcome: Clear service boundaries, easier scaling

11) Ownership: API writes runs/documents; Worker writes events/artifacts
   - Shift run/document status updates to API via progress messages/internal endpoints
   - Outcome: Data contracts enforced

12) SSE DB session lifecycle
   - Open/close a dedicated session inside the SSE generator
   - Outcome: Prevents session disposal errors during long streams

Storage
13) MinIO CORS configuration doc + preflight script
   - Provide mc/boto3 JSON CORS example and curl test including Origin header
   - Outcome: Browser PUT to presigned URLs works reliably

14) Robust public endpoint rewriting for presigned URLs
   - Use urllib.parse to swap netloc/scheme; handle http/https correctly
   - Outcome: Valid presigned URLs in diverse deployments

Database
15) Enum migration strategy
   - Document the TEXT→update→new enum→cast back pattern; consider helper libs (alembic‑postgresql‑enum)
   - Outcome: Safe enum value renames under Alembic

16) Complete runs.metadata→run_metadata migration
   - Ensure Alembic migration exists and has been applied everywhere
   - Outcome: Model/schema alignment; no reserved attribute issues

Core Pipeline & Providers
17) Docling OCR memory mitigation
   - Default OCR off for programmatic PDFs; prefer RapidOCR; process long docs in chunks; consider explicit cleanup between batches; pin known good versions
   - Outcome: Fewer OOMs; smoother large‑batch runs

18) Anthropic SDK audit for tool/JSON reliability
   - Use tool forcing for strict JSON; set tool_choice none to prevent chaining; enforce tool_result ordering; pin SDK version
   - Outcome: Consistent structured outputs

Tracking & Process
- For each item, open a PR linked to a bug report or design note
- Validate with ./start.sh test and a small end‑to‑end document run
- Update bug_reports/OPEN_BUGS_DIGEST.md as items land
