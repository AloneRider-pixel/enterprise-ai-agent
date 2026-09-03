"""
Structured logging middleware.
Provides JSON-formatted request/response logging with timing.
"""
import logging
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every request with structured JSON output.
    Includes request ID, timing, status code, and user information.
    """

    async def dispatch(self, request: Request, call_next):
        """Process the request with structured logging."""
        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.time()
        
        # Log request
        log_data = {
            "event": "request_start",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params) if request.query_params else None,
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", ""),
        }
        logger.info("Request started", extra=log_data)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Log response
            response_log = {
                "event": "request_complete",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(latency_ms, 2),
            }
            
            if response.status_code >= 400:
                logger.warning("Request completed with error", extra=response_log)
            else:
                logger.info("Request completed", extra=response_log)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{latency_ms:.0f}ms"
            
            return response
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                "Request failed",
                extra={
                    "event": "request_error",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "latency_ms": round(latency_ms, 2),
                },
            )
            raise
