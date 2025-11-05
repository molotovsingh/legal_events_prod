Title: <Short description> (Link bug report: bug_reports/BUG_REPORT_YYYYMMDDTHHMMSSZ.md)

Summary
- What does this change fix or improve?
- Linked bug report: `bug_reports/<file>`

Checklist — Guardrails & Scope
- [ ] Single-issue PR (scoped; no unrelated changes)
- [ ] No API ↔ Worker cross-imports (API uses string-based RQ enqueues)
- [ ] Worker respects ownership (read-only for clients/cases/runs/docs; writes events/artifacts only)
- [ ] Storage keys consistent (clients/{client_id}/cases/{case_id}/runs/{run_id}/…)
- [ ] Auth/secrets safe (no default creds in prod; secrets via env/manager)

Migrations (if applicable)
- [ ] Alembic migration included
- [ ] `alembic upgrade head` verified locally
- [ ] Downgrade path considered/tested or explicitly N/A

Verification
- [ ] Repro steps from report pass locally
- [ ] `./start.sh test` passes, key endpoints healthy
- [ ] Logs/screenshots attached (if helpful)
- [ ] Regression test added or intentionally deferred (explain)

Build & CI
- [ ] Docker builds succeed (api/worker)
- [ ] CI checks pass (lint/tests/build/import rules)

Release Notes
- Ops/migration steps (if any):
```
<commands or notes>
```

