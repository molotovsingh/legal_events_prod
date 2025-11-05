# Contributing Guide

Welcome! This guide explains how we capture, triage, and fix bugs while respecting our service guardrails.

## Quick Start
- Report bugs in `bug_reports/` using the timestamped pattern: `BUG_REPORT_YYYYMMDDTHHMMSSZ.md` (UTC).
- Follow the simple workflow in: `bug_reports/BUG_WORKFLOW_CONSTITUTION.md`.
- Use the PR checklist: `.github/pull_request_template.md`.

## Guardrails (must follow)
- API ↔ Worker: No cross-imports. API enqueues worker tasks via string names (RQ) and shares only neutral libraries.
- Ownership: Worker is read-only for Clients/Cases/Runs/Documents; Worker writes Events/Artifacts only.
- Storage tenancy: Object keys include `clients/{client_id}/cases/{case_id}/runs/{run_id}/…` consistently.
- Security: No default creds in production; enable auth when required; secrets via env/secrets manager.

## Bug Workflow (human-friendly)
See `bug_reports/BUG_WORKFLOW_CONSTITUTION.md` for the one-page flow:
- **Pre-Discovery Check** → Check active bugs before systematic bug hunting
- Capture → Triage → Reproduce → Plan → Implement → Verify → Ship → Close
- Severity: P0 blocker / P1 major / P2 minor; one DRI per bug
- Definition of Done in PR template

## Before Bug Discovery (Important!)
Before starting Phase 2 testing or systematic bug hunting:
```bash
# Quick check: how many active bugs?
ls bug_reports/BUG_REPORT_*.md 2>/dev/null | wc -l
```

**Stop and fix first if**:
- ≥3 P0 blockers open
- ≥5 P1 major issues unassigned
- ≥15 total open reports
- Any P0 older than 48h

See `bug_reports/BUG_WORKFLOW_CONSTITUTION.md` → "Pre-Discovery Check" for full details.

## Branching & Commits
- Branches: `fix/<area>-<short-slug>` (e.g., `fix/worker-langextract-import`)
- Commits: prefix with the report ID (e.g., `BR-20251105T113902Z unify storage keys`)

## Migrations
- Use Alembic; include up/down; test locally before merge.

## Running Locally
- Dev: `docker compose up`
- Prod-like: `docker compose -f docker-compose.yml up -d`
- Health check: `./start.sh test`

Thanks for contributing and keeping the guardrails intact!

