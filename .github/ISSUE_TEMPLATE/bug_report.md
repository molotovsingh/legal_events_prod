---
name: Bug report
about: Report a bug following our workflow
title: "[BUG] <short title>"
labels: bug
assignees: ''
---

Summary
- What is broken or incorrect?
- Link to local report (if created): `bug_reports/BUG_REPORT_YYYYMMDDTHHMMSSZ.md`

Scope & Severity
- Area: (api / worker / core / infra / frontend)
- Severity: (P0 blocker / P1 major / P2 minor)
- DRI (owner): @

Reproduction
1. Steps to reproduce (minimal, exact)
2. Expected result
3. Actual result

Evidence
- Logs/screenshots/tracebacks (if helpful)

Guardrails Check (must consider)
- [ ] No API ↔ Worker cross-imports in proposed fix
- [ ] Worker remains read-only for clients/cases/runs/docs; writes events/artifacts only
- [ ] Storage keys include `clients/{client_id}/cases/{case_id}/runs/{run_id}/…` consistently
- [ ] Auth/secrets safe (no default creds in prod; secrets via env/manager)

Proposed Fix (3–5 lines)
- Brief plan, blast radius, migrations/rollback if any

Links
- Related bug report(s):
- Related PR(s):

Notes
- Any constraints, environment details, or follow-ups

