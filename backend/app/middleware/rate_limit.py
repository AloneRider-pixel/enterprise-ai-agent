"""
Rate limiting middleware using Redis sliding window.
Protects the API from abuse and ensures fair usage.
"""
import logging
import time

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.redis_client import redis_client

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using Redis sliding window algorithm.
    
    Limits requests per user based on JWT token.
    Falls back to IP-based limiting for unauthenticated requests.
    """

    def __init__(self, app, max_requests: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        """Process the request with rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path in ("/api/health", "/health", "/docs", "/openapi.json"):
            return await call_next(request)

        # Get user identifier
        user_id = self._get_user_id(request)
        
        # Check rate limit
        result = await redis_client.check_rate_limit(
            user_id=user_id,
            max_requests=self.max_requests,
            window_seconds=self.window_seconds,
        )
        
        if not result["allowed"]:
            logger.warning(
                f"Rate limit exceeded for {user_id}: "
                f"{result['request_count']} requests in window"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": int(result["reset_at"] - time.time()),
                },
                headers={
                    "X-RateLimit-Limit": str(self.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(result["reset_at"])),
                    "Retry-After": str(int(result["reset_at"] - time.time())),
                },
            )
        
        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(result["remaining"])
        response.headers["X-RateLimit-Reset"] = str(int(result["reset_at"]))
        
        return response

    def _get_user_id(self, request: Request) -> str:
        """Extract user ID from auth header or fall back to IP."""
        # Try to get from auth header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Decode JWT without full validation (just get the sub claim)
            try:
                import jwt
                from app.config import settings
                token = auth_header.split(" ")[1]
                payload = jwt.decode(
                    token,
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_exp": False},
                )
                return f"user:{payload.get('sub', 'unknown')}"
            except Exception:
                pass
        
        # Fall back to client IP
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"
