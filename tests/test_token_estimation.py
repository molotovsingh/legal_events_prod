"""
Integration tests for /v1/estimate-tokens endpoint

Tests pre-run token estimation and cost calculation functionality.
v0.12.0 - Token counting and cost estimation feature
"""

import pytest
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
            "model": "openai/gpt-4",
            "files": []
        }
        response = client.post("/v1/estimate-tokens", json=payload)
        assert response.status_code == 400
        assert "No files provided" in response.json()["detail"]

    def test_endpoint_requires_valid_provider(self):
        """Endpoint should validate provider/model combination."""
        # TODO: Add test once we have MinIO test fixtures
        pass

    # TODO: Add comprehensive endpoint tests
    # These require MinIO test fixtures with uploaded files

    # def test_successful_estimation_single_file(self):
    #     """Test successful token estimation for a single PDF."""
    #     # 1. Upload test PDF to MinIO
    #     # 2. Get storage_key from upload response
    #     # 3. Call /v1/estimate-tokens with storage_key
    #     # 4. Verify response structure and token counts
    #     pass

    # def test_successful_estimation_multiple_files(self):
    #     """Test estimation for multiple files."""
    #     pass

    # def test_estimation_with_classification_enabled(self):
    #     """Test estimation includes classification tokens when enabled."""
    #     pass

    # def test_estimation_with_classification_disabled(self):
    #     """Test estimation excludes classification tokens when disabled."""
    #     pass

    # def test_cost_calculation_accuracy(self):
    #     """Test that USD cost calculation matches model catalog pricing."""
    #     pass

    # def test_per_document_breakdown(self):
    #     """Test that per-document token counts are included."""
    #     pass

    # def test_pricing_metadata_included(self):
    #     """Test that pricing information is returned for transparency."""
    #     pass

    # def test_missing_storage_key_returns_error(self):
    #     """Test error handling when storage_key doesn't exist in MinIO."""
    #     pass

    # def test_tokenizer_unavailable_returns_400(self):
    #     """Test error when tokenizer is not available for selected model."""
    #     pass

    # def test_docling_extraction_failure_handled(self):
    #     """Test error handling when Docling extraction fails."""
    #     pass


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
