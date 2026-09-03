"""
FastAPI authentication dependencies.
Used for protecting routes with JWT authentication.
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.utils import decode_access_token

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Extract and verify the current user from the JWT token.
    Returns user payload with sub (user_id), email, and role.
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return {
        "user_id": payload["sub"],
        "email": payload["email"],
        "role": payload.get("role", "user"),
    }


async def get_current_admin_user(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Verify the current user has admin privileges.
    """
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[dict]:
    """
    Extract user from token if present, otherwise return None.
    Used for endpoints that work with or without auth.
    """
    if credentials is None:
        return None
    
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        return None
    
    return {
        "user_id": payload["sub"],
        "email": payload["email"],
        "role": payload.get("role", "user"),
    }
