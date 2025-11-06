# Recommendation — DB Migrations & Enum Strategy (Alembic)

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Move enum/type bootstrapping into Alembic and adopt a safe enum value change pattern.

## Rationale
- Avoids brittle inline scripts in docker‑compose.
- Enum value renames need transactional patterns or helper libs.

## Steps
1) New migration: create custom enums idempotently via `op.execute` DO $$ blocks.
2) Replace compose inline script with `alembic upgrade head && uvicorn ...`.
3) Document enum changes: TEXT → update values → new enum → cast back; consider `alembic-postgresql-enum`.

## Risks
- Running migrations on existing DBs; ensure reversible downgrades where possible.

## Validation
- Fresh DB: upgrade applies cleanly; existing DB: upgrade/downgrade round‑trip in dev.

## Rollback
- Restore compose script temporarily; revert migration.
