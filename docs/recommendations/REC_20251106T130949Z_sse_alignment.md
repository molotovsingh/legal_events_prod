# Recommendation — SSE Dependency Alignment & Hygiene

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Align FastAPI/Starlette/`sse-starlette` versions and harden the SSE endpoint.

## Rationale
- FastAPI 0.118.x fixes StreamingResponse cleanup; `sse-starlette` 3.0.2 fixes multi‑loop issues.

## Steps
1) In a branch, bump: FastAPI → 0.118.x; `sse-starlette` → 3.0.2 (let FastAPI resolve Starlette).
2) SSE endpoint: avoid compression; consider client disconnect checks; dedicate DB session in generator.

## Risks
- Version drift; test end‑to‑end streaming.

## Validation
- `GET /v1/runs/{id}/stream` updates during processing.
- No premature cleanup; no buffering via reverse proxy.

## Rollback
- Revert dependency bumps; keep endpoint hygiene.
