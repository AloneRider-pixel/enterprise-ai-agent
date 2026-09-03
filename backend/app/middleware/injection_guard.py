"""
Prompt injection protection middleware.
Scans incoming requests for prompt injection attempts.
"""
import logging
import re
from typing import List, Tuple

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


# Injection detection patterns
INJECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("ignore_previous", re.compile(
        r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?|rules?)",
        re.IGNORECASE
    )),
    ("new_identity", re.compile(
        r"you\s+are\s+(now\s+)?(a|an)\s+",
        re.IGNORECASE
    )),
    ("disregard_rules", re.compile(
        r"disregard\s+(your|all|the)\s+(instructions?|rules?|guidelines?|system)",
        re.IGNORECASE
    )),
    ("system_override", re.compile(
        r"(system|assistant)\s*:\s*",
        re.IGNORECASE
    )),
    ("forget_everything", re.compile(
        r"forget\s+(everything|all|your\s+(memory|instructions?|rules?))",
        re.IGNORECASE
    )),
    ("pretend_mode", re.compile(
        r"pretend\s+(you\s+)?(are|have|can|you're)",
        re.IGNORECASE
    )),
    ("reveal_prompt", re.compile(
        r"(reveal|show|display|print)\s+(your\s+)?(system\s+)?(prompt|instructions?)",
        re.IGNORECASE
    )),
    ("act_as", re.compile(
        r"act\s+as\s+(if\s+)?(you\s+are|a|an)\s+",
        re.IGNORECASE
    )),
    ("jailbreak", re.compile(
        r"(DAN|jailbreak|do\s+anything\s+now|bypass|override)\s*",
        re.IGNORECASE
    )),
    ("no_restrictions", re.compile(
        r"(without|no)\s+(restrictions?|limitations?|rules?|guidelines?)",
        re.IGNORECASE
    )),
]


class InjectionGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that scans request bodies for prompt injection attempts.
    
    Operates at the API level as a first line of defense.
    The agent's input_guard node provides a second layer.
    """

    def __init__(self, app, block_injection: bool = False):
        super().__init__(app)
        self.block_injection = block_injection  # If True, block; if False, just log

    async def dispatch(self, request: Request, call_next):
        """Check request body for injection patterns."""
        # Only check POST requests with JSON body
        if request.method != "POST":
            return await call_next(request)
        
        # Skip for non-chat endpoints
        if "/api/chat" not in request.url.path:
            return await call_next(request)
        
        try:
            # Read body
            body = await request.body()
            
            if body:
                # Try to parse as JSON
                try:
                    import json
                    data = json.loads(body)
                    text_to_check = ""
                    
                    # Extract text fields to check
                    if isinstance(data, dict):
                        text_to_check = data.get("message", "") or data.get("query", "")
                    elif isinstance(data, str):
                        text_to_check = data
                    
                    if text_to_check:
                        injection_type, confidence = self._detect_injection(text_to_check)
                        
                        if injection_type:
                            logger.warning(
                                f"Prompt injection detected: type={injection_type}, "
                                f"confidence={confidence:.2f}, path={request.url.path}"
                            )
                            
                            if self.block_injection and confidence > 0.8:
                                return JSONResponse(
                                    status_code=400,
                                    content={
                                        "detail": "Request blocked: potential prompt injection detected.",
                                        "injection_type": injection_type,
                                    },
                                )
                except json.JSONDecodeError:
                    pass
            
            # Recreate request with body for downstream processing
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            
            request._receive = receive
            
        except Exception as e:
            logger.error(f"Injection guard error: {e}")
        
        return await call_next(request)

    def _detect_injection(self, text: str) -> Tuple[str, float]:
        """
        Detect injection patterns in text.
        Returns (injection_type, confidence) or (None, 0.0) if clean.
        """
        matches = []
        
        for pattern_name, pattern in INJECTION_PATTERNS:
            if pattern.search(text):
                matches.append(pattern_name)
        
        if not matches:
            return None, 0.0
        
        # Confidence based on number and severity of matches
        confidence = min(1.0, len(matches) * 0.4)
        
        return matches[0], confidence
