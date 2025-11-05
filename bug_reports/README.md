# Bug Reports

- Purpose: Track investigation notes and actionable defects found during testing and integration.
- Scope: Repository-wide issues impacting correctness, reliability, or operability.

## Naming Convention
- Filename pattern: `BUG_REPORT_YYYYMMDDTHHMMSSZ.md`
- Timezone: UTC (Zulu)
- Example: `BUG_REPORT_20251105T111630Z.md`
- Generate timestamp (Linux/macOS): `date -u +"%Y%m%dT%H%M%SZ"`

## Recommended Sections
- Summary — one paragraph context and impact
- Critical Issues — blockers with file references, symptoms, fixes
- Major Issues — high-impact with mitigations
- Minor Issues / Cleanups — low-risk improvements
- Repro Steps — minimal steps to reproduce
- Suggested Fix Plan — ordered actions with owners, files
- Notes — assumptions, environment, related links

## Workflow
- Create new report in `bug_reports/` using the naming convention.
- Keep bullets concise; include exact file paths and line references when helpful.
- Cross-link PRs or commits that address items.
- Close out by adding a short “Resolution” note at the end with the commit SHA(s).

## Template Snippet
```
# Bug Report — <short title>
Date: <YYYY-MM-DD>
Timestamp: <YYYY-MM-DDTHH:MM:SSZ> (UTC)

## Summary
<one paragraph>

## Critical Issues
- <file:path:line> — <symptom>. Fix: <action>.

## Major Issues
- ...

## Minor Issues / Cleanups
- ...

## Repro Steps
1) ...

## Suggested Fix Plan
1) ...

## Notes
- ...
```
