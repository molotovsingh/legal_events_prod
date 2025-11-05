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

## Pre-Discovery Check (before systematic bug hunting)

**When to run**: Before Phase 2 testing, integration sprints, major feature work, or scheduled bug discovery sessions.

**Quick health check (2 minutes)**:
```bash
# Count active (non-archived) bug reports
ls bug_reports/BUG_REPORT_*.md 2>/dev/null | wc -l

# Check severity distribution
grep -h "^- Severity:" bug_reports/BUG_REPORT_*.md 2>/dev/null | sort | uniq -c
```

**Stop and fix first if**:
- ≥3 P0 blockers open → Address blockers before finding more issues
- ≥5 P1 major issues unassigned → Assign DRIs and clear backlog
- ≥15 total open reports → Run housekeeping sprint to close/archive resolved bugs
- Any P0 older than 48h → Escalate and resolve before new discovery

**Proceed with discovery if**:
- <3 P0 blockers (or all P0s actively being worked)
- Active DRIs making progress on P1s
- Team has capacity to handle new findings
- Bug fix rate > bug discovery rate (sustainable)

**Document the decision**:
- Add note to STATUS.md: "Pre-discovery check: X open bugs (P0:Y, P1:Z, P2:W), proceeding with [testing/pausing]"
- If pausing: Assign DRIs to top P0/P1 items, schedule a fix sprint, and set a reassessment date
- If proceeding: Note capacity and triage plan for new findings

Note: These thresholds are guidance, not hard gates. A DRI may override by adding a brief rationale in STATUS.md (e.g., customer priority, timeboxed discovery, or release commitments).

Open vs archived: Only non-archived files at `bug_reports/BUG_REPORT_*.md` are considered “open.” Archived reports live in `bug_reports/archive/YYYY/` and are excluded from counts.

**Why this matters**: Prevents bug debt accumulation, forces prioritization, keeps active bug list manageable, and avoids rediscovering known issues.

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

### Labels (rubric)
- Severity: `severity:P0`, `severity:P1`, `severity:P2`
- Area: `area:api`, `area:worker`, `area:core`, `area:infra`, `area:frontend`
- Status: `status:ready-to-archive` (when Resolution + Verification are present)

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

## Archiving via Git Version Manager (GVM)
- Signal: DRI adds “Resolution” + “Verification” sections to the report, and applies label `status:ready-to-archive` to the linked issue/PR.
- Expected GVM actions:
  - Move the report to `bug_reports/archive/<year>/` (preserve filename).
  - Optionally append an entry to an index (e.g., `bug_reports/INDEX.md`).
  - Close the linked issue and remove the label.
- Conventions GVM can rely on:
  - File pattern: `BUG_REPORT_YYYYMMDDTHHMMSSZ.md` (UTC)
  - Archive path: `bug_reports/archive/YYYY/`
  - Sections: Summary, Evidence, Repro, Impact, Fix Plan, Resolution, Verification
  - Labels: severity (P0/P1/P2), area (api/worker/core/infra/frontend), `status:ready-to-archive`

## Templates (optional but recommended)
- `.github/pull_request_template.md` with guardrails + DoD checklist.
- `.github/ISSUE_TEMPLATE/bug_report.md` mapping to this structure.
- `CONTRIBUTING.md` linking to this constitution and guardrails.
