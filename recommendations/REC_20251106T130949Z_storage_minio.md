# Recommendation — MinIO CORS & Public Endpoint Robustness

Date: 2025-11-06
Timestamp: 20251106T130949Z (UTC)

## Summary
Document and apply CORS for presigned PUTs; rebuild presigned URLs using `urllib.parse` when swapping to public endpoint.

## Rationale
- Prevents browser upload failures (preflight/Origin headers).
- Robust URL rewriting avoids malformed links.

## Steps
1) Docs: provide mc/boto3 JSON CORS and curl preflight snippet.
2) Code: parse presigned URL; replace scheme/netloc using urlparse/urlunparse; handle http/https.

## Risks
- Misconfigured CORS; test with Origin header.

## Validation
- Upload from UI succeeds; preflight returns 204.

## Rollback
- Revert URL rewriting; keep CORS docs.
