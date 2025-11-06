# Recommendation — Docker Hardening (Multi‑Stage, Non‑Root, .dockerignore)

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Shrink images and reduce attack surface by using multi‑stage builds, running as a non‑root user, and trimming build context with .dockerignore. Apply to both `api` and `worker`.

## Rationale
- Build tools (gcc, libpq‑dev) are not needed at runtime; removing them reduces CVE exposure and image size.
- Non‑root mitigates container breakout risk.
- Smaller contexts speed builds and prevent accidental inclusion of secrets.

## Steps
1) Multi‑stage builds
- Stage 1 (builder): python:3.12; install gcc, libpq‑dev; `pip wheel -r requirements.txt -w /wheels`; build git deps (langextract) into /wheels.
- Stage 2 (final): python:3.12‑slim; `pip install --no-index --find-links=/wheels /wheels/*`.
- Keep runtime libs only (api: libpq5; worker: tesseract‑ocr, poppler‑utils, MuPDF runtime).

2) Non‑root user
- `RUN useradd --create-home appuser && mkdir -p /app/logs /app/temp`
- `USER appuser` and `COPY --chown=appuser:appuser ...`

3) .dockerignore
- Exclude: .git, .env, __pycache__/, *.pyc, .pytest_cache/, research/, large artifacts.

## Risks
- Native deps: ensure worker keeps OCR/PDF runtime libs; PyMuPDF needs MuPDF runtime present.

## Validation
- Build with `--no-cache`; compare image sizes.
- Smoke test: `./start.sh start` → health ok; upload + process a doc.

## Rollback
- Switch back to single‑stage Dockerfile backups if needed.
