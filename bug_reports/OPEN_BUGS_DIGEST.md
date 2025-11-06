# Open Bugs Digest

Updated: 2025-11-06 03:16:17Z (UTC)

Purpose: Snapshot of open issues with priorities, suggested owners, and references to full reports.

## P0 — Blockers

- DB schema mismatch: `runs.metadata` vs `run_metadata`
  - Owner: Backend
  - Action: Alembic migration to rename; run upgrade and verify exports
  - Reports: BUG_REPORT_20251105T111630Z.md, BUG_REPORT_20251105T170226Z.md
  - Status: [ ] TODO

- Worker dependencies missing (PyMuPDF/fitz, extract_msg, langextract)
  - Owner: Infra/Worker
  - Action: Install in worker image; choose single source for langextract
  - Reports: BUG_REPORT_20251105T111630Z.md
  - Status: [ ] TODO

## P1 — Major

- Cross-imports (worker imports `api.*`) — guardrail violation
  - Owner: Backend/Infra
  - Action: Extract shared infra (db/models/storage) to `infra/`; API→Worker via RQ strings
  - Reports: BUG_REPORT_20251105T113653Z.md, BUG_REPORT_20251105T112000Z.md
  - Status: [ ] TODO

- Worker mutates API-owned entities (runs/documents)
  - Owner: Backend
  - Action: Worker emits progress only; API updates run/document state
  - Reports: BUG_REPORT_20251105T113842Z.md
  - Status: [ ] TODO

- SSE DB session lifecycle in `/v1/runs/{id}/stream`
  - Owner: Backend
  - Action: Use dedicated DB session inside generator; close on exit
  - Reports: BUG_REPORT_20251105T170226Z.md
  - Status: [ ] TODO

- LangExtract installation source unification
  - Owner: Infra/Worker
  - Action: Pick PyPI or pinned Git tag; remove the other
  - Reports: BUG_REPORT_20251105T125718Z.md
  - Status: [ ] TODO

- UI “Recent Runs” lists cases (misleading)
  - Owner: Frontend
  - Action: Add runs-by-case endpoint and render real runs; or rename temporarily
  - Reports: BUG_REPORT_20251106T011941Z.md
  - Status: [ ] TODO

## P2 — Minor / Docs / Ops

- MinIO CORS for presigned PUTs not documented
  - Owner: Ops/Infra
  - Action: Document CORS policy and quick verification
  - Reports: BUG_REPORT_20251105T130411Z.md
  - Status: [ ] TODO

- MinIO public endpoint replacement robustness
  - Owner: Backend
  - Action: Use `urllib.parse` to rebuild URLs when swapping endpoint
  - Reports: BUG_REPORT_20251106T031335Z.md
  - Status: [ ] TODO

- UI long text truncation (table overflow)
  - Owner: Frontend
  - Action: CSS ellipsis + tooltip/expand for full text
  - Reports: BUG_REPORT_20251106T012024Z.md
  - Status: [ ] TODO

- Presign flow clarity (filename mapping)
  - Owner: Frontend/Docs
  - Action: Document current presign behavior and storage key schema
  - Reports: BUG_REPORT_20251105T125656Z.md
  - Status: [ ] TODO

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

## Notes

- Guardrails to enforce in all fixes:
  - No API ↔ Worker cross-imports; use shared `infra/*` and RQ string enqueues
  - Worker read-only for clients/cases/runs/documents; writes events/artifacts only
  - Storage keys include `clients/{client_id}/cases/{case_id}/runs/{run_id}/…`
  - Auth/secrets safe for production (no default creds)

