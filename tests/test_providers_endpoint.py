"""
Providers Endpoint Unit Tests

Tests the unified GET /v1/providers endpoint using FastAPI TestClient (in-process).
No external services required - fully isolated with stubs and fixtures.

Tests verify:
- All fields present in response
- Filtering works correctly (enabled, recommended_only)
- Response metadata (count, timestamp)
- Backward compatibility (name vs display_name)
- Runtime validation (is_working field)

This validates Phase 3 P1 fix: Unified /v1/providers handler
"""

import os
import sys
import pytest
from datetime import datetime
from unittest.mock import MagicMock, Mock
from typing import Generator


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Set all required environment variables BEFORE any module imports.
    Session-scoped and autouse ensures this runs first.
    """
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests")
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
    os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
    os.environ.setdefault("MINIO_ACCESS_KEY", "test-minio-access-key")
    os.environ.setdefault("MINIO_SECRET_KEY", "test-minio-secret-key")
    os.environ.setdefault("MINIO_BUCKET", "test-legal-documents")
    os.environ.setdefault("MINIO_SECURE", "false")


@pytest.fixture(scope="module")
def mock_dependencies():
    """
    Stub all external service modules BEFORE importing api.main.
    Module-scoped to prevent leaking mocks into other test modules.

    Prevents import-time connections to Redis, MinIO, etc.
    """
    # Save original modules if they exist (for restoration)
    original_modules = {}
    for module_name in ['api.event_processor', 'infra.queue', 'infra.storage']:
        if module_name in sys.modules:
            original_modules[module_name] = sys.modules[module_name]

    # Stub api.event_processor (Redis event consumer)
    event_processor_mock = Mock()
    event_processor_mock.start_event_processor = Mock()
    event_processor_mock.stop_event_processor = Mock()
    sys.modules['api.event_processor'] = event_processor_mock

    # Stub infra.queue (Redis RQ connection)
    # Critical: infra.queue pings Redis at import time
    queue_mock = Mock()
    queue_mock.enqueue_job = Mock(return_value="mock-job-id")
    queue_mock.get_worker_stats = Mock(return_value={"workers": 0, "queued": 0})
    queue_mock.get_redis_connection = Mock()
    sys.modules['infra.queue'] = queue_mock

    # Stub infra.storage.MinioStorage
    # Prevents MinIO connection during storage initialization
    storage_module = Mock()
    fake_storage = Mock()
    fake_storage.ensure_bucket = Mock(return_value=True)
    fake_storage.upload_file = Mock(return_value="mock-storage-key")
    fake_storage.get_presigned_url = Mock(return_value="http://mock-url")
    storage_module.MinioStorage = Mock(return_value=fake_storage)
    sys.modules['infra.storage'] = storage_module

    yield

    # Cleanup: Remove mocked modules
    for module_name in ['api.event_processor', 'infra.queue', 'infra.storage']:
        if module_name in sys.modules:
            del sys.modules[module_name]

    # Restore original modules if they existed
    for module_name, original_module in original_modules.items():
        sys.modules[module_name] = original_module

    # Force reload of api.main to clear cached imports
    # This ensures other test modules get fresh, real implementations
    if 'api.main' in sys.modules:
        import importlib
        importlib.reload(sys.modules['api.main'])


@pytest.fixture(scope="module")
def test_client(setup_test_environment, mock_dependencies):
    """
    Create TestClient AFTER all stubs are in place.
    Import api.main only inside this fixture to ensure mocks are active.
    """
    from fastapi.testclient import TestClient
    from api.main import app

    # Override database dependency to use in-memory SQLite
    from infra.database import get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from infra.models import Base

    # Create in-memory SQLite engine
    test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db() -> Generator:
        """Override get_db to use test database"""
        try:
            db = TestSessionLocal()
            yield db
        finally:
            db.close()

    # Override FastAPI dependency
    app.dependency_overrides[get_db] = override_get_db

    client = TestClient(app)
    yield client

    # Cleanup
    app.dependency_overrides.clear()


class TestProvidersEndpoint:
    """Test unified /v1/providers endpoint"""

    def test_providers_default_query(self, test_client):
        """GET /v1/providers (default) should return enabled providers only"""
        response = test_client.get("/v1/providers")
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

    def test_providers_all_fields_present(self, test_client):
        """Each provider should have all required fields"""
        response = test_client.get("/v1/providers")
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

    def test_providers_backward_compatibility(self, test_client):
        """'name' and 'display_name' should have same value"""
        response = test_client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["name"] == provider["display_name"], \
                f"Backward compatibility broken: name != display_name for {provider['provider_id']}"

    def test_providers_enabled_filter(self, test_client):
        """enabled=true should only return enabled providers"""
        response = test_client.get("/v1/providers?enabled=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["enabled"] is True, \
                f"Provider {provider['provider_id']} should be enabled"

    def test_providers_all_filter(self, test_client):
        """enabled=false should allow disabled providers in results"""
        response = test_client.get("/v1/providers?enabled=false")
        assert response.status_code == 200
        # Just verify it doesn't error - disabled providers may not exist

    def test_providers_recommended_filter(self, test_client):
        """recommended_only=true should only return recommended providers"""
        response = test_client.get("/v1/providers?recommended_only=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["recommended"] is True, \
                f"Provider {provider['provider_id']} should be recommended"

    def test_providers_combined_filters(self, test_client):
        """enabled=true&recommended_only=true should work together"""
        response = test_client.get("/v1/providers?enabled=true&recommended_only=true")
        assert response.status_code == 200
        data = response.json()

        for provider in data["providers"]:
            assert provider["enabled"] is True
            assert provider["recommended"] is True

    def test_providers_runtime_validation(self, test_client):
        """is_working field should reflect runtime provider status"""
        response = test_client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # At least one provider should be working
        working_providers = [p for p in data["providers"] if p["is_working"]]
        assert len(working_providers) > 0, "No providers are working (is_working=true)"

        # Verify is_working is boolean
        for provider in data["providers"]:
            assert isinstance(provider["is_working"], bool), \
                f"is_working should be boolean for {provider['provider_id']}"

    def test_providers_field_types(self, test_client):
        """Verify correct data types for all fields"""
        response = test_client.get("/v1/providers")
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

    def test_providers_count_accuracy(self, test_client):
        """count field should match actual provider list length"""
        response = test_client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] == len(data["providers"]), \
            "count field doesn't match providers list length"

    def test_providers_non_empty(self, test_client):
        """Should return at least one enabled provider"""
        response = test_client.get("/v1/providers?enabled=true")
        assert response.status_code == 200
        data = response.json()

        assert data["count"] > 0, "No enabled providers found"
        assert len(data["providers"]) > 0, "Empty providers list"

    def test_providers_supports_runtime_model_field(self, test_client):
        """Verify supports_runtime_model field exists (was missing in old handler)"""
        response = test_client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # This field was missing in Handler 1, present in Handler 2
        # Unified handler should include it
        for provider in data["providers"]:
            assert "supports_runtime_model" in provider, \
                f"Critical field 'supports_runtime_model' missing for {provider['provider_id']}"

    def test_providers_response_structure(self, test_client):
        """Verify response has correct top-level structure"""
        response = test_client.get("/v1/providers")
        assert response.status_code == 200
        data = response.json()

        # Should have exactly these three keys
        assert set(data.keys()) == {"providers", "count", "timestamp"}

    def test_providers_error_handling(self, test_client):
        """Verify error handling for invalid query parameters"""
        # Test with invalid boolean value
        response = test_client.get("/v1/providers?enabled=invalid")
        # FastAPI should handle validation errors with 422
        assert response.status_code in [200, 422]  # May coerce or reject
