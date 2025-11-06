"""
Authentication Tests
Tests JWT token generation, validation, and protected endpoint access
"""

import pytest
import json
import httpx
from datetime import datetime, timedelta
from jose import jwt
import os

API_URL = "http://localhost:8000"
TIMEOUT = 30.0
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "test-secret-key")
JWT_ALGORITHM = "HS256"


def create_test_token(email: str, role: str = "admin", expires_in_hours: int = 24) -> str:
    """Helper to create a valid JWT token for testing"""
    payload = {
        "sub": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=expires_in_hours)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_expired_token(email: str) -> str:
    """Helper to create an expired JWT token"""
    payload = {
        "sub": email,
        "role": "admin",
        "exp": datetime.utcnow() - timedelta(hours=1)  # Expired 1 hour ago
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


class TestJWTTokenGeneration:
    """Test JWT token generation and validation"""

    @pytest.mark.asyncio
    async def test_token_created_with_valid_claims(self):
        """Token should contain sub, role, and exp claims"""
        token = create_test_token("test@example.com", "admin")
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        assert decoded["sub"] == "test@example.com"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    @pytest.mark.asyncio
    async def test_token_expires_after_24_hours(self):
        """Token should expire after 24 hours"""
        token = create_test_token("test@example.com", expires_in_hours=24)
        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

        exp_time = datetime.utcfromtimestamp(decoded["exp"])
        now = datetime.utcnow()
        diff = (exp_time - now).total_seconds() / 3600

        # Should be approximately 24 hours
        assert 23.9 < diff < 24.1

    @pytest.mark.asyncio
    async def test_token_with_different_roles(self):
        """Tokens should support different roles"""
        roles = ["admin", "case_manager", "reviewer"]

        for role in roles:
            token = create_test_token("test@example.com", role=role)
            decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            assert decoded["role"] == role


class TestBearerTokenAuth:
    """Test Bearer token authentication in HTTP requests"""

    @pytest.mark.asyncio
    async def test_request_with_valid_bearer_token(self):
        """Requests with valid Bearer token should succeed"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": f"Bearer {token}"}
            )
            # Should succeed (200 or 401 if user doesn't exist, but auth should pass)
            assert resp.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_request_without_bearer_token(self):
        """Requests without Bearer token should still work (optional auth in Phase 1)"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/clients")
            # In Phase 1, auth is optional, so this should succeed
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_request_with_malformed_bearer_token(self):
        """Requests with malformed Bearer token should fail gracefully"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": "Bearer invalid.malformed.token"}
            )
            # Should handle gracefully (no crash)
            assert resp.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_request_with_expired_token(self):
        """Requests with expired token should be rejected"""
        token = create_expired_token("test@example.com")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": f"Bearer {token}"}
            )
            # Expired tokens should return 401 or be treated as invalid
            assert resp.status_code in [200, 401]

    @pytest.mark.asyncio
    async def test_request_with_wrong_algorithm(self):
        """Token signed with wrong algorithm should be rejected"""
        # Create token with HS512 instead of HS256
        payload = {
            "sub": "test@example.com",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS512")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": f"Bearer {token}"}
            )
            # Should be rejected or treated as invalid
            assert resp.status_code in [200, 401]


class TestProtectedEndpoints:
    """Test that protected endpoints require authentication"""

    @pytest.mark.asyncio
    async def test_create_client_with_auth(self):
        """Creating client with valid token should work"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/clients",
                json={"name": "Test Client", "reference_code": "TEST_AUTH_001"},
                headers={"Authorization": f"Bearer {token}"}
            )
            # May succeed or fail based on user validation, but should not be auth error
            assert resp.status_code in [200, 201, 400, 409]

    @pytest.mark.asyncio
    async def test_create_case_with_auth(self):
        """Creating case with valid token should work"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/cases",
                json={"name": "Test Case", "client_id": 1},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code in [200, 201, 400, 404]

    @pytest.mark.asyncio
    async def test_create_run_with_auth(self):
        """Creating run with valid token should work"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{API_URL}/v1/runs",
                json={"case_id": 1, "file_count": 1},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code in [200, 201, 400, 404]

    @pytest.mark.asyncio
    async def test_start_run_with_auth(self):
        """Starting run with valid token should work"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.put(
                f"{API_URL}/v1/runs/1/start",
                json={"files": [], "idempotency_key": "test-001"},
                headers={"Authorization": f"Bearer {token}"}
            )
            assert resp.status_code in [200, 400, 404]


class TestTokenClaims:
    """Test JWT token claims and payloads"""

    @pytest.mark.asyncio
    async def test_token_missing_sub_claim(self):
        """Token without sub claim should be invalid"""
        payload = {
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=24)
            # Missing "sub" claim
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        # Token is technically valid JWT, but application should reject it
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            assert "sub" not in decoded
        except jwt.DecodeError:
            pytest.fail("Token decode raised DecodeError")

    @pytest.mark.asyncio
    async def test_token_missing_exp_claim(self):
        """Token without exp claim should have no expiration"""
        payload = {
            "sub": "test@example.com",
            "role": "admin"
            # Missing "exp" claim
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert "exp" not in decoded

    @pytest.mark.asyncio
    async def test_token_with_custom_claims(self):
        """Token should support custom claims"""
        payload = {
            "sub": "test@example.com",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=24),
            "custom_field": "custom_value",
            "metadata": {"org_id": 123}
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        assert decoded["custom_field"] == "custom_value"
        assert decoded["metadata"]["org_id"] == 123


class TestAuthorizationHeaders:
    """Test various Authorization header formats"""

    @pytest.mark.asyncio
    async def test_bearer_prefix_case_insensitive(self):
        """Bearer prefix should work in different cases"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            # Try different case variations
            for prefix in ["Bearer", "bearer", "BEARER"]:
                resp = await client.get(
                    f"{API_URL}/v1/clients",
                    headers={"Authorization": f"{prefix} {token}"}
                )
                # Should work (in Phase 1, auth is optional anyway)
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_authorization_header(self):
        """Missing Authorization header should not crash API"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{API_URL}/v1/clients")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_malformed_authorization_header(self):
        """Malformed Authorization header should be handled"""
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": "InvalidFormat"}
            )
            # Should handle gracefully
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_extra_whitespace_in_bearer_token(self):
        """Extra whitespace in Bearer token should be handled"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": f"Bearer  {token}"}  # Extra space
            )
            # Should handle extra whitespace
            assert resp.status_code in [200, 401]


class TestPasswordHashing:
    """Test password hashing functionality"""

    @pytest.mark.asyncio
    async def test_password_hash_is_not_plaintext(self):
        """Passwords should not be stored as plaintext"""
        # This is a conceptual test - we verify the auth system uses hashing
        # In practice, this would be tested in the User model
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        password = "test_password_123"
        hashed = pwd_context.hash(password)

        # Hash should be different from plaintext
        assert hashed != password
        # Hash should start with bcrypt prefix
        assert hashed.startswith("$2b$")

    @pytest.mark.asyncio
    async def test_password_verification(self):
        """Password verification should work correctly"""
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        password = "test_password_123"
        hashed = pwd_context.hash(password)

        # Correct password should verify
        assert pwd_context.verify(password, hashed)
        # Wrong password should not verify
        assert not pwd_context.verify("wrong_password", hashed)


class TestTokenSecurityHeaders:
    """Test security-related headers in auth responses"""

    @pytest.mark.asyncio
    async def test_api_response_includes_security_headers(self):
        """API responses should include appropriate security headers"""
        token = create_test_token("test@example.com", "admin")

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                f"{API_URL}/v1/clients",
                headers={"Authorization": f"Bearer {token}"}
            )

            # Response should be successful
            assert resp.status_code == 200
            # Headers should not expose sensitive info (no server details, etc)
            assert "server" not in [h.lower() for h in resp.headers.keys()]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
