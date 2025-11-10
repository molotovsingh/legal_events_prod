"""
Providers Endpoint Unit Tests

Tests the unified GET /v1/providers endpoint using FastAPI TestClient (in-process).
No external server required - tests run against the app directly.

Tests verify:
- All fields present in response
- Filtering works correctly (enabled, recommended_only)
- Response metadata (count, timestamp)
- Backward compatibility (name vs display_name)
- Runtime validation (is_working field)

This validates Phase 3 P1 fix: Unified /v1/providers handler
"""

import os
import pytest
from datetime import datetime
from unittest.mock import MagicMock

# Set required environment variables BEFORE importing app
# This prevents RuntimeError during app initialization
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-minio-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-minio-secret-key")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_BUCKET", "test-legal-documents")
os.environ.setdefault("MINIO_SECURE", "false")

from fastapi.testclient import TestClient

# Import the FastAPI app AFTER setting environment variables
from api.main import app

# Create test client (runs in-process, no external server needed)
client = TestClient(app)


class TestProvidersEndpoint:
    """Test unified /v1/providers endpoint"""

    def test_providers_default_query(self):
        """GET /v1/providers (default) should return enabled providers only"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # Verify top-level response structure
        assert "providers" in data
        assert "count" in data
        assert "timestamp" in data
        assert isinstance(data["providers"], list)
        assert data["count"] == len(data["providers"])

        # Verify timestamp is valid ISO format
        try:
            datetime.fromisoformat(data["timestamp"])
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {data['timestamp']}")

    def test_providers_all_fields_present(self):
        """Each provider should have all required fields"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        required_fields = [
            "provider_id",
            "display_name",
            "name",  # Backward compatibility alias
            "enabled",
            "supports_runtime_model",
            "recommended",
            "notes",
            "documentation_url",
            "is_working",
            "models"
        ]

        for provider in data["providers"]:
            for field in required_fields:
                assert field in provider, f"Missing field '{field}' in provider {provider.get('provider_id')}"

    def test_providers_backward_compatibility(self):
        """'name' and 'display_name' should have same value"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["name"] == provider["display_name"], \
                f"Backward compatibility broken: name != display_name for {provider['provider_id']}"

    def test_providers_enabled_filter(self):
        """enabled=true should only return enabled providers"""
        response = client.get("/v1/providers?enabled=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["enabled"] is True, \
                f"Provider {provider['provider_id']} should be enabled"

    def test_providers_all_filter(self):
        """enabled=false should allow disabled providers in results"""
        # Get all providers by setting enabled to false or None
        # Note: This depends on catalog having disabled providers
        response = client.get("/v1/providers?enabled=false")
        assert response.status_code == 200
        # Just verify it doesn't error - disabled providers may not exist

    def test_providers_recommended_filter(self):
        """recommended_only=true should only return recommended providers"""
        response = client.get("/v1/providers?recommended_only=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["recommended"] is True, \
                f"Provider {provider['provider_id']} should be recommended"

    def test_providers_combined_filters(self):
        """enabled=true&recommended_only=true should work together"""
        response = client.get("/v1/providers?enabled=true&recommended_only=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["enabled"] is True
            assert provider["recommended"] is True

    def test_providers_runtime_validation(self):
        """is_working field should reflect runtime provider status"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # At least one provider should be working in production
        working_providers = [p for p in data["providers"] if p["is_working"]]
        assert len(working_providers) > 0, "No providers are working (is_working=true)"

        # Verify is_working is boolean
        for provider in data["providers"]:
            assert isinstance(provider["is_working"], bool), \
                f"is_working should be boolean for {provider['provider_id']}"

    def test_providers_field_types(self):
        """Verify correct data types for all fields"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            # String fields
            assert isinstance(provider["provider_id"], str)
            assert isinstance(provider["display_name"], str)
            assert isinstance(provider["name"], str)
            assert isinstance(provider["notes"], str)

            # Boolean fields
            assert isinstance(provider["enabled"], bool)
            assert isinstance(provider["supports_runtime_model"], bool)
            assert isinstance(provider["recommended"], bool)
            assert isinstance(provider["is_working"], bool)

            # Optional string (can be None)
            assert provider["documentation_url"] is None or isinstance(provider["documentation_url"], str)

            # List field
            assert isinstance(provider["models"], list)

    def test_providers_count_accuracy(self):
        """count field should match actual provider list length"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == len(data["providers"]), \
            "count field doesn't match providers list length"

    def test_providers_non_empty(self):
        """Should return at least one enabled provider"""
        response = client.get("/v1/providers?enabled=true")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] > 0, "No enabled providers found"
        assert len(data["providers"]) > 0, "Empty providers list"

    def test_providers_supports_runtime_model_field(self):
        """Verify supports_runtime_model field exists (was missing in old handler)"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # This field was missing in Handler 1, present in Handler 2
        # Unified handler should include it
        for provider in data["providers"]:
            assert "supports_runtime_model" in provider, \
                f"Critical field 'supports_runtime_model' missing for {provider['provider_id']}"

    def test_providers_response_structure(self):
        """Verify response has correct top-level structure"""
        response = client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # Should have exactly these three keys
        assert set(data.keys()) == {"providers", "count", "timestamp"}

    def test_providers_error_handling(self):
        """Verify error handling for invalid query parameters"""
        # Test with invalid boolean value
        response = client.get("/v1/providers?enabled=invalid")
        # FastAPI should handle validation errors with 422
        assert response.status_code in [200, 422]  # May coerce or reject
