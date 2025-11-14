#!/bin/bash
# Run integration tests with proper MinIO configuration

export MINIO_ENDPOINT="localhost:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="generate-strong-password"
export MINIO_BUCKET="legal-documents"

# Run pytest with the given arguments (or default to all token estimation tests)
python3 -m pytest "${@:-tests/test_token_estimation.py}" -v --tb=short
