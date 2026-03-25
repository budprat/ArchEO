"""
Authentication middleware for OpenEO AI Assistant.

ABOUTME: Provides middleware for request authentication and rate limiting.
Integrates with FastAPI middleware system.
"""

import os
import logging
import time
from typing import Callable, Dict, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Configuration
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))  # seconds


@dataclass
class RateLimitEntry:
    """Track rate limit for a user/IP."""
    count: int = 0
    window_start: float = field(default_factory=time.time)


class RateLimiter:
    """
    Simple in-memory rate limiter.

    For production, consider using Redis-based rate limiting.
    """

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._entries: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """
        Check if request is allowed under rate limit.

        Args:
            key: Unique identifier (user_id or IP)

        Returns:
            tuple: (is_allowed, remaining_requests)
        """
        now = time.time()
        entry = self._entries[key]

        # Reset window if expired
        if now - entry.window_start >= self.window_seconds:
            entry.count = 0
            entry.window_start = now

        # Check limit
        if entry.count >= self.max_requests:
            return False, 0

        entry.count += 1
        remaining = self.max_requests - entry.count

        return True, remaining

    def get_retry_after(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        entry = self._entries.get(key)
        if not entry:
            return 0

        elapsed = time.time() - entry.window_start
        return max(0, int(self.window_seconds - elapsed))


# Global rate limiter instance
_rate_limiter = RateLimiter()


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware for authentication-related processing.

    Handles:
    - Request logging
    - Rate limiting (optional)
    - Request timing
    """

    def __init__(self, app, rate_limit: bool = RATE_LIMIT_ENABLED):
        super().__init__(app)
        self.rate_limit = rate_limit

    async def dispatch(self, request: Request, call_next: Callable):
        """Process the request."""
        start_time = time.time()

        # Extract identifier for rate limiting
        rate_key = self._get_rate_key(request)

        # Check rate limit
        if self.rate_limit and rate_key:
            allowed, remaining = _rate_limiter.is_allowed(rate_key)

            if not allowed:
                retry_after = _rate_limiter.get_retry_after(rate_key)
                logger.warning(f"Rate limit exceeded for {rate_key}")

                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded",
                        "retry_after": retry_after,
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(_rate_limiter.max_requests),
                        "X-RateLimit-Remaining": "0",
                    },
                )

        # Process request
        try:
            response = await call_next(request)

            # Add timing header
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            # Add rate limit headers if enabled
            if self.rate_limit and rate_key:
                _, remaining = _rate_limiter.is_allowed(rate_key)
                # Decrement since we already counted
                remaining = max(0, remaining)
                response.headers["X-RateLimit-Limit"] = str(_rate_limiter.max_requests)
                response.headers["X-RateLimit-Remaining"] = str(remaining)

            return response

        except Exception as e:
            logger.error(f"Request processing error: {e}")
            raise

    def _get_rate_key(self, request: Request) -> Optional[str]:
        """
        Extract rate limit key from request.

        Uses user_id from auth header if available, otherwise client IP.
        """
        # Try to get user ID from state (set by auth dependency)
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"

        # Fall back to client IP
        client_ip = request.client.host if request.client else None
        if client_ip:
            return f"ip:{client_ip}"

        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable):
        """Log request and response details."""
        start_time = time.time()

        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path} "
            f"from {request.client.host if request.client else 'unknown'}"
        )

        response = await call_next(request)

        # Log response
        process_time = time.time() - start_time
        logger.info(
            f"Response: {response.status_code} "
            f"for {request.method} {request.url.path} "
            f"in {process_time:.3f}s"
        )

        return response


def setup_auth_middleware(app, rate_limit: bool = True, logging: bool = True):
    """
    Configure auth middleware for the FastAPI app.

    Args:
        app: FastAPI application instance
        rate_limit: Enable rate limiting
        logging: Enable request logging
    """
    if logging:
        app.add_middleware(RequestLoggingMiddleware)

    if rate_limit:
        app.add_middleware(AuthMiddleware, rate_limit=True)
