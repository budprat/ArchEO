"""Lightweight in-memory rate limiting middleware for FastAPI.

Uses a sliding window counter per client IP. No external dependencies required.
"""

import time
import threading
from collections import defaultdict
from typing import Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class _SlidingWindowCounter:
    """Thread-safe sliding window rate counter per IP."""

    def __init__(self, max_requests: int, window_seconds: int):
        self._max_requests = max_requests
        self._window = window_seconds
        self._lock = threading.Lock()
        # IP -> list of request timestamps
        self._requests: dict = defaultdict(list)

    def is_allowed(self, client_ip: str) -> Tuple[bool, int]:
        """Check if a request from this IP is allowed.

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        now = time.monotonic()
        cutoff = now - self._window

        with self._lock:
            # Remove expired entries
            timestamps = self._requests[client_ip]
            self._requests[client_ip] = [
                t for t in timestamps if t > cutoff
            ]
            timestamps = self._requests[client_ip]

            if len(timestamps) >= self._max_requests:
                return False, 0

            timestamps.append(now)
            remaining = self._max_requests - len(timestamps)
            return True, remaining

    def cleanup(self):
        """Remove entries for IPs that have no recent requests."""
        now = time.monotonic()
        cutoff = now - self._window
        with self._lock:
            empty_keys = [
                ip for ip, ts in self._requests.items()
                if not ts or all(t <= cutoff for t in ts)
            ]
            for key in empty_keys:
                del self._requests[key]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that enforces per-IP rate limiting.

    Args:
        app: The FastAPI application
        max_requests: Maximum number of requests per window
        window_seconds: Time window in seconds (default 60 = 1 minute)
    """

    def __init__(self, app, max_requests: int = 30, window_seconds: int = 60):
        super().__init__(app)
        self._counter = _SlidingWindowCounter(max_requests, window_seconds)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        # Start a background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True
        )
        self._cleanup_thread.start()

    def _cleanup_loop(self):
        """Periodically clean up expired entries."""
        while True:
            time.sleep(self._window_seconds * 2)
            self._counter.cleanup()

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting for health check endpoints
        if request.url.path in ("/health", "/health/ready", "/health/live"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = self._counter.is_allowed(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "code": "TooManyRequests",
                    "message": (
                        f"Rate limit exceeded: {self._max_requests} requests "
                        f"per {self._window_seconds} seconds. Please retry later."
                    ),
                },
                headers={
                    "Retry-After": str(self._window_seconds),
                    "X-RateLimit-Limit": str(self._max_requests),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
