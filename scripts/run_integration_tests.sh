#!/bin/bash
# Run integration tests with required environment configuration for a clean env

set -euo pipefail

# Minimal app secrets and services
export JWT_SECRET_KEY="test_secret_key_for_tests"
export DATABASE_URL="sqlite:///./test_integration.db"  # file-based SQLite for multi-threaded TestClient
export REDIS_URL="redis://localhost:6379/15"           # use a test DB; processor tolerates errors

# MinIO configuration (tests/fixtures may stub as needed)
export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="generate-strong-password"
export MINIO_BUCKET="legal-documents"

# Run pytest with the given arguments (or default to token estimation tests)
if [ "$#" -eq 0 ]; then
  python3 -m pytest tests/test_token_estimation.py -v --tb=short
else
  python3 -m pytest "$@" -v --tb=short
fi
