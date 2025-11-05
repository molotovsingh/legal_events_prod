# Bug Workflow Constitution (Human-Friendly)

Date: 2025-11-05
Owners: Project maintainers

## Purpose
- Provide a simple, repeatable way to capture, triage, fix, and close bugs.
- Keep changes guardrail-compliant and easy to review.

## Scope
- Applies to all services (api, worker, core, infra, frontend) and deployment assets.

## Roles
- DRI (Directly Responsible Individual): exactly one owner per bug.
- Reviewer: verifies guardrails, correctness, and minimal scope.

## Severity & SLA
- P0 Blocker: system unusable/data risk → fix within 24–48h.
- P1 Major: core features degraded → fix within 3–5 days.
- P2 Minor: cosmetic/low-risk → batch with next release.

## One-Page Flow
1) Spot it → capture immediately in `bug_reports`.
2) Capture fast → add 5 bullets: What, Where, Repro, Impact, First guess.
3) Triage (5 min) → set Severity, Area (api/worker/core/infra/frontend), Guardrails status, DRI.
4) Reproduce minimally → exact steps, expected vs actual, logs/screenshots if helpful.
5) Plan fix (3–5 lines) → confirm against Guardrails (below).
6) Implement small → single-scope branch/PR; link the report.
7) Verify → rerun repro; `./start.sh test`; sanity-check logs/artifacts; add tiny regression test if low effort.
8) Ship → merge, rebuild, run migrations (if any), monitor.
9) Close → update report with Resolution (commits/PR), Verification, Follow-ups. For P0 add one-line RCA.

## Guardrails Quick-Check (must pass)
- API ↔ Worker: no cross-imports; use string-based RQ enqueues.
- Ownership: Worker is read-only for Clients/Cases/Runs/Documents; Worker writes Events/Artifacts only.
- Storage tenancy: object keys consistently include `clients/{client_id}/cases/{case_id}/runs/{run_id}/…`.
- Security: no default creds in prod; auth enabled when required; secrets via env/secret manager.

## Artifacts & Naming
- Bug report files: `bug_reports/BUG_REPORT_YYYYMMDDTHHMMSSZ.md` (UTC).
- Branches: `fix/<area>-<short-slug>` (e.g., `fix/worker-langextract-import`).
- Commits: prefix with report ID (e.g., `BR-20251105T113902Z unify storage keys`).

## PR Definition of Done
- Links the bug report; scope is minimal (one issue per PR).
- Guardrails checklist ticked.
- Repro passes locally in Docker; migrations noted if present.
- CI passes (lint/tests/build; import rules; alembic heads consistent).

## Triage Cadence
- Daily 10-minute triage: new/changed P0–P1 first, assign DRI.
- Weekly housekeeping: batch P2s and close verified reports.

## Templates (optional but recommended)
- `.github/pull_request_template.md` with guardrails + DoD checklist.
- `.github/ISSUE_TEMPLATE/bug_report.md` mapping to this structure.
- `CONTRIBUTING.md` linking to this constitution and guardrails.

