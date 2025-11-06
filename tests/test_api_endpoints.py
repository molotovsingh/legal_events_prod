"""
API Endpoint Tests
Tests all HTTP endpoints for correct behavior, error handling, and validation
"""

import pytest
import httpx
import uuid
from typing import Dict, Any

API_URL = "http://localhost:8000"
TIMEOUT = 30.0


def get_unique_ref_code() -> str:
    """Generate unique reference code for tests"""
    return f"TEST_{uuid.uuid4().hex[:8].upper()}"


class TestHealthEndpoints:
    """Test health and status endpoints"""

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """GET / should return API information"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/")
            assert resp.status_code == 200
            data = resp.json()
            assert "name" in data
            assert "version" in data
            assert "docs" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """GET /health should return component status"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert data["status"] in ["healthy", "degraded", "unhealthy"]
            assert "components" in data
            assert "database" in data["components"]
            assert "storage" in data["components"]
            assert "queue" in data["components"]

    @pytest.mark.asyncio
    async def test_health_timestamp(self):
        """Health check should include timestamp"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/health")
            data = resp.json()
            assert "timestamp" in data


class TestClientEndpoints:
    """Test client management endpoints"""

    @pytest.mark.asyncio
    async def test_create_client_success(self):
        """POST /v1/clients should create a new client"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/clients",
                json={
                    "name": "Test Client",
                    "reference_code": get_unique_ref_code(),
                    "notes": "Test notes"
                }
            )
            assert resp.status_code in [200, 201]
            data = resp.json()
            assert "id" in data
            assert data["name"] == "Test Client"

    @pytest.mark.asyncio
    async def test_create_client_missing_reference_code(self):
        """POST /v1/clients without reference_code should fail"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/clients",
                json={"name": "Test Client"}
            )
            # Should fail validation
            assert resp.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_client_duplicate_reference_code(self):
        """POST /v1/clients with duplicate reference_code should fail"""
        ref_code = get_unique_ref_code()

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create first client
            resp1 = await client.post(
                f"{API_URL}/v1/clients",
                json={"name": "Client 1", "reference_code": ref_code}
            )
            assert resp1.status_code in [200, 201]

            # Try to create second with same reference_code
            resp2 = await client.post(
                f"{API_URL}/v1/clients",
                json={"name": "Client 2", "reference_code": ref_code}
            )
            # Should fail due to duplicate constraint
            assert resp2.status_code in [400, 409]

    @pytest.mark.asyncio
    async def test_list_clients(self):
        """GET /v1/clients should return client list"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/clients")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_client_by_id(self):
        """GET /v1/clients/{id} should return client details"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Create a client first
            create_resp = await client.post(
                f"{API_URL}/v1/clients",
                json={"name": "Test Client", "reference_code": get_unique_ref_code()}
            )
            client_id = create_resp.json()["id"]

            # Get the client
            get_resp = await client.get(f"{API_URL}/v1/clients/{client_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["id"] == client_id
            assert data["name"] == "Test Client"

    @pytest.mark.asyncio
    async def test_get_client_not_found(self):
        """GET /v1/clients/{id} with invalid ID should return 404"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/clients/99999")
            assert resp.status_code == 404


class TestCaseEndpoints:
    """Test case management endpoints"""

    async def create_test_client(self, client: httpx.AsyncClient) -> int:
        """Helper to create a test client"""
        resp = await client.post(
            f"{API_URL}/v1/clients",
            json={"name": "Test Client", "reference_code": get_unique_ref_code()}
        )
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_create_case_success(self):
        """POST /v1/cases should create a new case"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            client_id = await self.create_test_client(client)

            resp = await client.post(
                f"{API_URL}/v1/cases",
                json={
                    "name": "Test Case",
                    "description": "Test case description",
                    "client_id": client_id,
                    "retention_days": 90
                }
            )
            assert resp.status_code in [200, 201]
            data = resp.json()
            assert "id" in data
            assert data["name"] == "Test Case"
            assert data["client_id"] == client_id

    @pytest.mark.asyncio
    async def test_create_case_invalid_client(self):
        """POST /v1/cases with invalid client_id should fail"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/cases",
                json={
                    "name": "Test Case",
                    "client_id": 99999
                }
            )
            # Should fail validation or return 404
            assert resp.status_code in [400, 404, 422]

    @pytest.mark.asyncio
    async def test_list_cases_by_client(self):
        """GET /v1/clients/{id}/cases should return cases for client"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            client_id = await self.create_test_client(client)

            # Create a case
            await client.post(
                f"{API_URL}/v1/cases",
                json={"name": "Case 1", "client_id": client_id}
            )

            # List cases
            resp = await client.get(f"{API_URL}/v1/clients/{client_id}/cases")
            assert resp.status_code == 200
            data = resp.json()
            assert isinstance(data, list)


class TestRunEndpoints:
    """Test run management endpoints"""

    async def create_test_case(self, client: httpx.AsyncClient) -> int:
        """Helper to create a test case"""
        client_resp = await client.post(
            f"{API_URL}/v1/clients",
            json={"name": "Test Client", "reference_code": get_unique_ref_code()}
        )
        client_id = client_resp.json()["id"]

        case_resp = await client.post(
            f"{API_URL}/v1/cases",
            json={"name": "Test Case", "client_id": client_id}
        )
        return case_resp.json()["id"]

    @pytest.mark.asyncio
    async def test_create_run_success(self):
        """POST /v1/runs should create a new run"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 2}
            )
            assert resp.status_code in [200, 201]
            data = resp.json()
            assert "run_id" in data
            assert "upload_urls" in data
            assert len(data["upload_urls"]) == 2
            assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_create_run_generates_presigned_urls(self):
        """POST /v1/runs should generate presigned URLs"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            assert resp.status_code in [200, 201]
            data = resp.json()
            urls = data["upload_urls"]
            assert len(urls) > 0
            # URLs should be presigned MinIO URLs
            for url in urls:
                assert "minio" in url.lower() or "s3" in url.lower() or "http" in url

    @pytest.mark.asyncio
    async def test_get_run_details(self):
        """GET /v1/runs/{id} should return run details"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            create_resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            run_id = create_resp.json()["run_id"]

            resp = await client.get(f"{API_URL}/v1/runs/{run_id}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["run_id"] == run_id
            assert data["status"] == "queued"

    @pytest.mark.asyncio
    async def test_start_run(self):
        """PUT /v1/runs/{id}/start should start processing"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            create_resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            run_id = create_resp.json()["run_id"]

            resp = await client.put(
                f"{API_URL}/v1/runs/{run_id}/start",
                json={"files": [], "idempotency_key": "test-001"}
            )
            assert resp.status_code in [200, 201]
            data = resp.json()
            assert "job_id" in data
            assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_get_run_events(self):
        """GET /v1/runs/{id}/events should return events"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            create_resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            run_id = create_resp.json()["run_id"]

            resp = await client.get(f"{API_URL}/v1/runs/{run_id}/events")
            assert resp.status_code == 200
            data = resp.json()
            assert "events" in data
            assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_get_run_artifacts(self):
        """GET /v1/runs/{id}/artifacts should return artifacts"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            create_resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            run_id = create_resp.json()["run_id"]

            resp = await client.get(f"{API_URL}/v1/runs/{run_id}/artifacts")
            assert resp.status_code == 200
            data = resp.json()
            assert "artifacts" in data
            assert isinstance(data["artifacts"], list)

    @pytest.mark.asyncio
    async def test_export_run_csv(self):
        """GET /v1/runs/{id}/export?fmt=csv should return CSV"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            case_id = await self.create_test_case(client)

            create_resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": case_id, "file_count": 1}
            )
            run_id = create_resp.json()["run_id"]

            resp = await client.get(f"{API_URL}/v1/runs/{run_id}/export?fmt=csv")
            # May return 404 if no events, but should not error
            assert resp.status_code in [200, 404]


class TestSSEStreamEndpoint:
    """Test Server-Sent Events streaming endpoint"""

    async def create_test_run(self, client: httpx.AsyncClient) -> int:
        """Helper to create a test run"""
        client_resp = await client.post(
            f"{API_URL}/v1/clients",
            json={"name": "Test Client", "reference_code": get_unique_ref_code()}
        )
        client_id = client_resp.json()["id"]

        case_resp = await client.post(
            f"{API_URL}/v1/cases",
            json={"name": "Test Case", "client_id": client_id}
        )
        case_id = case_resp.json()["id"]

        run_resp = await client.post(
            f"{API_URL}/v1/runs",
            json={"case_id": case_id, "file_count": 1}
        )
        return run_resp.json()["run_id"]

    @pytest.mark.asyncio
    async def test_sse_stream_connection(self):
        """GET /v1/runs/{id}/stream should establish SSE connection"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            run_id = await self.create_test_run(client)

            # Connect to stream
            async with client.stream(
                "GET",
                f"{API_URL}/v1/runs/{run_id}/stream",
                timeout=5.0
            ) as resp:
                assert resp.status_code == 200
                # Read first line
                async for line in resp.aiter_lines():
                    if line.startswith("data:") or line.startswith("event:"):
                        # Got at least one event
                        break

    @pytest.mark.asyncio
    async def test_sse_stream_handles_client_disconnect(self):
        """SSE stream should handle client disconnect gracefully"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            run_id = await self.create_test_run(client)

            # Connect and immediately disconnect
            async with client.stream(
                "GET",
                f"{API_URL}/v1/runs/{run_id}/stream",
                timeout=2.0
            ) as resp:
                assert resp.status_code == 200
                # Don't read anything, just exit context


class TestModelCatalogEndpoint:
    """Test model catalog endpoints"""

    @pytest.mark.asyncio
    async def test_list_models(self):
        """GET /v1/models should return model catalog"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/models")
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data
            assert isinstance(data["models"], list)

    @pytest.mark.asyncio
    async def test_filter_models_by_provider(self):
        """GET /v1/models?provider=X should filter by provider"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/models?provider=openai")
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data

    @pytest.mark.asyncio
    async def test_filter_recommended_models(self):
        """GET /v1/models?recommended=true should filter recommended"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/models?recommended=true")
            assert resp.status_code == 200
            data = resp.json()
            assert "models" in data


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_invalid_json_request(self):
        """POST with invalid JSON should return 400"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/clients",
                content=b"invalid json {",
                headers={"Content-Type": "application/json"}
            )
            assert resp.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """Long-running requests should be handled"""
        # This test is informational - actual timeout behavior depends on deployment
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/clients")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_non_existent_endpoint(self):
        """Requests to non-existent endpoints should return 404"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/nonexistent")
            assert resp.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
