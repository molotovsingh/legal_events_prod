"""
Providers Endpoint Integration Tests

Tests the unified GET /v1/providers endpoint to verify:
- All fields present in response
- Filtering works correctly (enabled, recommended_only)
- Response metadata (count, timestamp)
- Backward compatibility (name vs display_name)
- Runtime validation (is_working field)

This validates Phase 3 P1 fix: Unified /v1/providers handler
"""

import pytest
import httpx
from datetime import datetime

API_URL = "http://localhost:8000"
TIMEOUT = 30.0


class TestProvidersEndpoint:
    """Test unified /v1/providers endpoint"""

    @pytest.mark.asyncio
    async def test_providers_default_query(self):
        """GET /v1/providers (default) should return enabled providers only"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

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

    @pytest.mark.asyncio
    async def test_providers_all_fields_present(self):
        """Each provider should have all required fields"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

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

    @pytest.mark.asyncio
    async def test_providers_backward_compatibility(self):
        """'name' and 'display_name' should have same value"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

            for provider in data["providers"]:
                assert provider["name"] == provider["display_name"], \
                    f"Backward compatibility broken: name != display_name for {provider['provider_id']}"

    @pytest.mark.asyncio
    async def test_providers_enabled_filter(self):
        """enabled=true should only return enabled providers"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers?enabled=true")
            assert resp.status_code == 200
            data = resp.json()

            for provider in data["providers"]:
                assert provider["enabled"] is True, \
                    f"Provider {provider['provider_id']} should be enabled"

    @pytest.mark.asyncio
    async def test_providers_all_filter(self):
        """enabled=false should allow disabled providers in results"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Get all providers by setting enabled to false or None
            # Note: This depends on catalog having disabled providers
            resp = await client.get(f"{API_URL}/v1/providers?enabled=false")
            assert resp.status_code == 200
            # Just verify it doesn't error - disabled providers may not exist

    @pytest.mark.asyncio
    async def test_providers_recommended_filter(self):
        """recommended_only=true should only return recommended providers"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers?recommended_only=true")
            assert resp.status_code == 200
            data = resp.json()

            for provider in data["providers"]:
                assert provider["recommended"] is True, \
                    f"Provider {provider['provider_id']} should be recommended"

    @pytest.mark.asyncio
    async def test_providers_combined_filters(self):
        """enabled=true&recommended_only=true should work together"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers?enabled=true&recommended_only=true")
            assert resp.status_code == 200
            data = resp.json()

            for provider in data["providers"]:
                assert provider["enabled"] is True
                assert provider["recommended"] is True

    @pytest.mark.asyncio
    async def test_providers_runtime_validation(self):
        """is_working field should reflect runtime provider status"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

            # At least one provider should be working in production
            working_providers = [p for p in data["providers"] if p["is_working"]]
            assert len(working_providers) > 0, "No providers are working (is_working=true)"

            # Verify is_working is boolean
            for provider in data["providers"]:
                assert isinstance(provider["is_working"], bool), \
                    f"is_working should be boolean for {provider['provider_id']}"

    @pytest.mark.asyncio
    async def test_providers_field_types(self):
        """Verify correct data types for all fields"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

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

    @pytest.mark.asyncio
    async def test_providers_count_accuracy(self):
        """count field should match actual provider list length"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

            assert data["count"] == len(data["providers"]), \
                "count field doesn't match providers list length"

    @pytest.mark.asyncio
    async def test_providers_non_empty(self):
        """Should return at least one enabled provider"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers?enabled=true")
            assert resp.status_code == 200
            data = resp.json()

            assert data["count"] > 0, "No enabled providers found"
            assert len(data["providers"]) > 0, "Empty providers list"

    @pytest.mark.asyncio
    async def test_providers_supports_runtime_model_field(self):
        """Verify supports_runtime_model field exists (was missing in old handler)"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/providers")
            assert resp.status_code == 200
            data = resp.json()

            # This field was missing in Handler 1, present in Handler 2
            # Unified handler should include it
            for provider in data["providers"]:
                assert "supports_runtime_model" in provider, \
                    f"Critical field 'supports_runtime_model' missing for {provider['provider_id']}"
