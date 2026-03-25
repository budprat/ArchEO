"""
Tests for OpenEO AI Authentication module.

ABOUTME: Tests OIDC authentication, middleware, and rate limiting.
Follows TDD principles - these tests drive the implementation.
"""

import os
import pytest
import base64
from datetime import datetime
from unittest.mock import MagicMock, patch

# Set test environment
os.environ["OPENEO_DEV_MODE"] = "true"
os.environ["PYTEST_CURRENT_TEST"] = "test"


class TestOIDCUser:
    """Tests for OIDCUser dataclass."""

    def test_oidc_user_creation(self):
        """Test creating an OIDCUser instance."""
        from openeo_ai.auth.oidc import OIDCUser

        user = OIDCUser(
            user_id="test-user-123",
            oidc_sub="oidc:sub:123",
            email="test@example.com",
            name="Test User",
            roles=["user", "admin"],
        )

        assert user.user_id == "test-user-123"
        assert user.oidc_sub == "oidc:sub:123"
        assert user.email == "test@example.com"
        assert user.name == "Test User"
        assert "user" in user.roles
        assert "admin" in user.roles
        assert isinstance(user.authenticated_at, datetime)

    def test_oidc_user_to_dict(self):
        """Test OIDCUser serialization to dict."""
        from openeo_ai.auth.oidc import OIDCUser

        user = OIDCUser(
            user_id="test-user-123",
            oidc_sub="oidc:sub:123",
            email="test@example.com",
        )

        data = user.to_dict()

        assert data["user_id"] == "test-user-123"
        assert data["oidc_sub"] == "oidc:sub:123"
        assert data["email"] == "test@example.com"
        assert "authenticated_at" in data

    def test_oidc_user_from_openeo_user(self):
        """Test creating OIDCUser from openeo-fastapi User."""
        from openeo_ai.auth.oidc import OIDCUser
        import uuid

        # Create mock openeo-fastapi User
        mock_user = MagicMock()
        mock_user.user_id = uuid.uuid4()
        mock_user.oidc_sub = "oidc:test:456"

        oidc_user = OIDCUser.from_openeo_user(mock_user)

        assert oidc_user.user_id == str(mock_user.user_id)
        assert oidc_user.oidc_sub == "oidc:test:456"


class TestCreateDevUser:
    """Tests for development user creation."""

    def test_create_dev_user(self):
        """Test creating a development user."""
        from openeo_ai.auth.oidc import create_dev_user

        user = create_dev_user("test-dev")

        assert user.user_id is not None
        assert user.oidc_sub == "dev:test-dev"
        assert user.email == "test-dev@dev.local"
        assert "Test Dev" in user.name

    def test_create_dev_user_deterministic(self):
        """Test that same username produces same user_id."""
        from openeo_ai.auth.oidc import create_dev_user

        user1 = create_dev_user("consistent-user")
        user2 = create_dev_user("consistent-user")

        assert user1.user_id == user2.user_id

    def test_create_dev_user_different_usernames(self):
        """Test that different usernames produce different user_ids."""
        from openeo_ai.auth.oidc import create_dev_user

        user1 = create_dev_user("user-one")
        user2 = create_dev_user("user-two")

        assert user1.user_id != user2.user_id


class TestRateLimiter:
    """Tests for rate limiting functionality."""

    def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests under limit."""
        from openeo_ai.auth.middleware import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for i in range(5):
            allowed, remaining = limiter.is_allowed("test-user")
            assert allowed, f"Request {i+1} should be allowed"
            assert remaining == 5 - (i + 1)

    def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over limit."""
        from openeo_ai.auth.middleware import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Use up the limit
        for _ in range(3):
            limiter.is_allowed("test-user")

        # Next request should be blocked
        allowed, remaining = limiter.is_allowed("test-user")
        assert not allowed
        assert remaining == 0

    def test_rate_limiter_different_users(self):
        """Test that rate limits are per-user."""
        from openeo_ai.auth.middleware import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # User 1 uses their limit
        limiter.is_allowed("user-1")
        limiter.is_allowed("user-1")
        allowed1, _ = limiter.is_allowed("user-1")

        # User 2 should still have their limit
        allowed2, remaining = limiter.is_allowed("user-2")

        assert not allowed1, "User 1 should be rate limited"
        assert allowed2, "User 2 should not be rate limited"
        assert remaining == 1

    def test_rate_limiter_retry_after(self):
        """Test retry_after calculation."""
        from openeo_ai.auth.middleware import RateLimiter

        limiter = RateLimiter(max_requests=1, window_seconds=60)

        # Use up the limit
        limiter.is_allowed("test-user")

        retry_after = limiter.get_retry_after("test-user")
        assert 0 < retry_after <= 60


class TestAuthMiddleware:
    """Tests for authentication middleware."""

    @pytest.mark.asyncio
    async def test_middleware_adds_timing_header(self):
        """Test that middleware adds X-Process-Time header."""
        from openeo_ai.auth.middleware import AuthMiddleware
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(AuthMiddleware, rate_limit=False)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Process-Time" in response.headers

    @pytest.mark.asyncio
    async def test_middleware_rate_limit_headers(self):
        """Test that middleware adds rate limit headers."""
        from openeo_ai.auth.middleware import AuthMiddleware
        from starlette.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(AuthMiddleware, rate_limit=True)

        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_basic_auth_dev_mode(self):
        """Test Basic Auth in dev mode."""
        from openeo_ai.auth.oidc import get_current_user

        # Create Basic Auth header
        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
        auth_header = f"Basic {credentials}"

        with patch("openeo_ai.auth.oidc._get_authenticator") as mock_auth:
            # Mock the authenticator
            mock_user = MagicMock()
            mock_user.user_id = "test-uuid"
            mock_user.oidc_sub = "dev:testuser"
            mock_auth.return_value.validate.return_value = mock_user

            user = await get_current_user(auth_header)

            assert user.oidc_sub == "dev:testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_missing_header(self):
        """Test that missing auth header raises 401."""
        from openeo_ai.auth.oidc import get_current_user
        from fastapi import HTTPException

        with patch("openeo_ai.auth.oidc._get_authenticator") as mock_auth:
            mock_auth.return_value.validate.side_effect = HTTPException(
                status_code=401, detail="Missing auth"
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user("")

            assert exc_info.value.status_code == 401


class TestOptionalUser:
    """Tests for get_optional_user dependency."""

    @pytest.mark.asyncio
    async def test_optional_user_returns_none_without_header(self):
        """Test that optional user returns None without auth header."""
        from openeo_ai.auth.oidc import get_optional_user

        user = await get_optional_user(None)
        assert user is None

    @pytest.mark.asyncio
    async def test_optional_user_returns_user_with_header(self):
        """Test that optional user returns user with valid header."""
        from openeo_ai.auth.oidc import get_optional_user

        credentials = base64.b64encode(b"testuser:testpass").decode("utf-8")
        auth_header = f"Basic {credentials}"

        with patch("openeo_ai.auth.oidc._get_authenticator") as mock_auth:
            mock_user = MagicMock()
            mock_user.user_id = "test-uuid"
            mock_user.oidc_sub = "dev:testuser"
            mock_auth.return_value.validate.return_value = mock_user

            user = await get_optional_user(auth_header)

            assert user is not None
            assert user.oidc_sub == "dev:testuser"
