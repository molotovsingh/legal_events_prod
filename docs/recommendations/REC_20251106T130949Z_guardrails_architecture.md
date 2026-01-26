# Recommendation — Guardrails: infra/ Package & Ownership

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Create `infra/` for shared DB/models/storage; remove API↔Worker cross‑imports; enforce ownership: API writes runs/documents, Worker writes events/artifacts.

## Rationale
- Clear service boundaries; easier scaling and testing.

## Steps
1) Move shared code to `infra/` (db session factory, SQLAlchemy models, MinIO client helpers).
2) API enqueues worker via RQ string names only.
3) Worker emits progress; API updates run/document state.

## Risks
- Refactor touches imports; keep PRs small and well‑tested.

## Validation
- End‑to‑end: create run, upload, process; statuses update via API; events/artifacts produced by Worker.

## Rollback
- Revert import paths; keep infra/ staged for later.
