# Recommendation — Docker Desktop / Engine Security (macOS)

Date: 2025-11-06
Timestamp: 20251106T131524Z (UTC)

## Summary
Keep Docker Desktop (macOS), Docker Engine, and Docker Compose current to mitigate recent critical/high CVEs, and enable hardening settings.

## Rationale
- Recent CVEs (unauthenticated API access, AuthZ bypass, path traversal, container breakout) are mitigated in latest Desktop/Engine/Compose bundles.
- Hardening settings reduce blast radius of container compromise.

## Actions (Do Now)
1) Update Docker Desktop (bundles Engine + Compose on macOS)
- Target: Desktop ≥ 4.44.3; Engine ≥ 27.1.0; Compose ≥ 2.40.2
- How: Docker Desktop → Check for Updates (or `brew upgrade --cask docker`)

2) Verify versions
- Engine: `docker version` → Server Version ≥ 27.1.0
- Compose: `docker compose version` → Version ≥ 2.40.2
- Desktop: About → Version ≥ 4.44.3

3) Harden settings
- Enable Enhanced Container Isolation (Settings → Security)
- Ensure daemon is not exposed on tcp:// without TLS
- Prefer runtime secrets and avoid env secrets being logged; rotate logs

## Usage Hygiene (Per Project)
- Avoid untrusted remote Compose files; don’t run `docker compose -f https://...`
- Don’t mount `/var/run/docker.sock`; avoid privileged containers; run as non‑root user in images
- Use multi‑stage builds; pin base images; apply `.dockerignore`
- Gate startup with health checks (`depends_on` with `service_healthy`)

## Verification
- `docker version`, `docker compose version`
- Optional: `trivy image <image>` or `docker scout cves <image>`

## Rollback
- N/A (security updates). If issues arise, consult Docker Desktop release notes and downgrade temporarily with Homebrew cask versions.
