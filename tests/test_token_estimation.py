"""
Integration tests for /v1/estimate-tokens endpoint

Tests pre-run token estimation and cost calculation functionality.
v0.12.0 - Token counting and cost estimation feature
"""

import os
import pytest

# Ensure required env vars are set before importing the app to avoid lifespan errors
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_tests")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_integration.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestEstimateTokensEndpoint:
    """Test /v1/estimate-tokens API endpoint."""

    def test_endpoint_exists(self):
        """Endpoint should be registered in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "/v1/estimate-tokens" in schema["paths"]
        assert "post" in schema["paths"]["/v1/estimate-tokens"]

    def test_endpoint_requires_files(self):
        """Endpoint should return 400 if no files provided."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": []
        }
        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 400
        assert "No files provided" in response.json()["detail"]

    def test_successful_estimation_single_file(self, uploaded_sample_1page):
        """Test successful token estimation for a single PDF."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "doc_extractor": "docling",
            "files": [uploaded_sample_1page.model_dump()],
            "enable_classification": False
        }

        response = client.post("/v1/estimate-tokens", json=payload)

        # Should succeed
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()

        # Verify response structure
        assert "per_document" in data
        assert "totals" in data
        assert "pricing" in data

        # Verify per-document breakdown
        assert len(data["per_document"]) == 1
        doc = data["per_document"][0]
        assert doc["filename"] == "sample_1page.pdf"
        assert doc["event_input_tokens"] > 0
        assert doc["classification_input_tokens"] is None  # Classification disabled

        # Verify totals
        totals = data["totals"]
        assert totals["event_input_tokens"] > 0
        assert totals["classification_input_tokens"] == 0
        assert totals["total_input_tokens"] == totals["event_input_tokens"]

        # Verify cost calculation
        assert totals["cost_input_usd"] is not None
        assert totals["cost_input_usd"] > 0
        assert totals["currency"] == "USD"

    def test_successful_estimation_multiple_files(self, uploaded_sample_files):
        """Test estimation for multiple files."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [f.model_dump() for f in uploaded_sample_files],
            "enable_classification": False
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Should have 2 documents
        assert len(data["per_document"]) == 2

        # Verify each document has token counts
        for doc in data["per_document"]:
            assert doc["event_input_tokens"] > 0
            assert doc["classification_input_tokens"] is None

        # Verify totals are sum of individual documents
        total_event_tokens = sum(d["event_input_tokens"] for d in data["per_document"])
        assert data["totals"]["event_input_tokens"] == total_event_tokens

    def test_estimation_with_classification_enabled(self, uploaded_sample_1page):
        """Test estimation includes classification tokens when enabled."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [uploaded_sample_1page.model_dump()],
            "enable_classification": True,
            "classification_model": "meta-llama/llama-3.3-70b-instruct"
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Verify classification tokens are included
        doc = data["per_document"][0]
        assert doc["classification_input_tokens"] is not None
        assert doc["classification_input_tokens"] > 0

        # Verify totals include classification
        totals = data["totals"]
        assert totals["classification_input_tokens"] > 0
        assert totals["total_input_tokens"] == (
            totals["event_input_tokens"] + totals["classification_input_tokens"]
        )

        # Verify pricing includes both event and classification
        assert "event" in data["pricing"]
        assert "classification" in data["pricing"]

    def test_estimation_with_classification_disabled(self, uploaded_sample_1page):
        """Test estimation excludes classification tokens when disabled."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [uploaded_sample_1page.model_dump()],
            "enable_classification": False
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Classification should be zero
        assert data["totals"]["classification_input_tokens"] == 0
        assert data["per_document"][0]["classification_input_tokens"] is None

    def test_cost_calculation_accuracy(self, uploaded_sample_1page):
        """Test that USD cost calculation matches model catalog pricing."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [uploaded_sample_1page.model_dump()]
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Verify cost is calculated correctly
        tokens = data["totals"]["event_input_tokens"]
        cost_per_1m = data["pricing"]["event"]["cost_input_per_1m"]

        # Recalculate cost manually
        expected_cost = (tokens / 1_000_000.0) * cost_per_1m

        # Allow small floating point tolerance
        actual_cost = data["totals"]["cost_input_usd"]
        assert abs(actual_cost - expected_cost) < 0.000001

    def test_per_document_breakdown(self, uploaded_sample_files):
        """Test that per-document token counts are included."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [f.model_dump() for f in uploaded_sample_files]
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Each document should have its own breakdown
        assert len(data["per_document"]) == len(uploaded_sample_files)

        for i, doc in enumerate(data["per_document"]):
            assert doc["filename"] == uploaded_sample_files[i].filename
            assert doc["event_input_tokens"] > 0

    def test_pricing_metadata_included(self, uploaded_sample_1page):
        """Test that pricing information is returned for transparency."""
        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [uploaded_sample_1page.model_dump()],
            "enable_classification": True,
            "classification_model": "meta-llama/llama-3.3-70b-instruct"
        }

        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 200

        data = response.json()

        # Verify pricing metadata structure
        assert "pricing" in data
        assert "event" in data["pricing"]
        assert "classification" in data["pricing"]

        # Verify event pricing
        event_pricing = data["pricing"]["event"]
        assert "cost_input_per_1m" in event_pricing
        assert event_pricing["cost_input_per_1m"] is not None

        # Verify classification pricing
        cls_pricing = data["pricing"]["classification"]
        assert "cost_input_per_1m" in cls_pricing
        assert cls_pricing["cost_input_per_1m"] is not None

    def test_missing_storage_key_returns_error(self, invalid_storage_key):
        """Test error handling when storage_key doesn't exist in MinIO."""
        from api.schemas import FileRef

        payload = {
            "provider": "openrouter",
            "model": "meta-llama/llama-3.3-70b-instruct",
            "files": [
                FileRef(
                    filename="nonexistent.pdf",
                    storage_key=invalid_storage_key,
                    size_bytes=1000
                ).model_dump()
            ]
        }

        # Should raise an error (either HTTP error or exception)
        try:
            response = client.post("/v1/estimate-tokens", json=payload)
            # If we get a response, it should be an error status
            assert response.status_code >= 400, f"Expected error status, got {response.status_code}"
        except Exception as e:
            # Exception is also acceptable for missing storage key
            assert "storage" in str(e).lower() or "download" in str(e).lower() or "failed" in str(e).lower()

    def test_unsupported_provider_model_combination(self, uploaded_sample_1page):
        """Test error when provider/model combination is unsupported."""
        payload = {
            "provider": "unsupported_provider",
            "model": "unsupported/model",
            "files": [uploaded_sample_1page.model_dump()]
        }

        # Should raise ValueError or return 400/500
        try:
            response = client.post("/v1/estimate-tokens", json=payload)
            assert response.status_code >= 400, f"Expected error status, got {response.status_code}"
        except ValueError as e:
            # ValueError for unsupported provider is acceptable
            assert "unsupported_provider" in str(e).lower() or "unknown provider" in str(e).lower()


class TestClassifiersEndpoint:
    """Test /v1/classifiers API endpoint."""

    def test_endpoint_exists(self):
        """Endpoint should be registered in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "/v1/classifiers" in schema["paths"]
        assert "get" in schema["paths"]["/v1/classifiers"]

    def test_classifiers_list_returns_models(self):
        """Endpoint should return list of classification models."""
        response = client.get("/v1/classifiers")
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "models" in data
        assert "count" in data
        assert "timestamp" in data
        assert isinstance(data["models"], list)
        assert data["count"] >= 0

    def test_classifiers_include_recommended_models(self):
        """Response should include recommended classification models."""
        response = client.get("/v1/classifiers")
        data = response.json()

        # Should have at least one recommended model
        recommended = [m for m in data["models"] if m.get("recommended")]
        assert len(recommended) > 0

    def test_classifiers_have_required_fields(self):
        """Each classifier should have required fields."""
        response = client.get("/v1/classifiers")
        data = response.json()

        for model in data["models"]:
            assert "model_id" in model
            assert "display_name" in model
            assert "provider" in model
            assert "recommended" in model
            assert model["provider"] == "openrouter"  # All should be OpenRouter

    def test_classifiers_count_matches_array_length(self):
        """Count field should match number of models in array."""
        response = client.get("/v1/classifiers")
        data = response.json()
        assert data["count"] == len(data["models"])


# TODO: Add fixtures for testing
# class TestFixtures:
#     """Setup test fixtures for token estimation tests."""
#
#     @pytest.fixture
#     def sample_pdf(self):
#         """Provide a sample PDF file for testing."""
#         # Return path to tests/fixtures/sample.pdf
#         pass
#
#     @pytest.fixture
#     def uploaded_file_storage_key(self, sample_pdf):
#         """Upload sample PDF to MinIO and return storage_key."""
#         # 1. Upload sample.pdf to MinIO
#         # 2. Return storage_key
#         pass
#
#     @pytest.fixture
#     def known_token_counts(self):
#         """Provide ground truth token counts for test documents."""
#         # Return dict mapping document -> expected token counts
#         pass


# TODO: Add performance tests
# - Test estimation speed (should be < 5 seconds per document)
# - Test memory usage (no leaks when processing many files)
# - Test concurrent requests (endpoint should handle parallel calls)

# TODO: Add edge case tests
# - Very large PDFs (100+ pages)
# - Encrypted/password-protected PDFs
# - Corrupted PDF files
# - Non-PDF files (should fail gracefully)
# - Unicode/special characters in extracted text
