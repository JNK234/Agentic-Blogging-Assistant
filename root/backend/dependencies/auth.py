# ABOUTME: JWT token verification dependency for FastAPI endpoints
# ABOUTME: Validates Supabase Auth tokens and returns clean 401 errors for expiration

import os
import jwt
import logging
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client

logger = logging.getLogger(__name__)

# Initialize Supabase client for token verification
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")
supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")

if not supabase_url or not supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

supabase_client = create_client(supabase_url, supabase_key)
security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to validate Supabase JWT tokens.

    Returns:
        Decoded JWT payload containing user info

    Raises:
        HTTPException(401): If token is missing, expired, or invalid
        HTTPException(500): If there's an auth system error
    """
    token = credentials.credentials

    try:
        # Verify JWT signature and expiration
        # Supabase uses HS256 with JWT_SECRET (not the anon key)
        payload = jwt.decode(
            token,
            supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}  # Supabase-specific audience handling
        )
        return payload

    except jwt.ExpiredSignatureError:
        # Clean 401 for expired tokens - frontend will catch and refresh
        logger.debug("Token expired, returning 401")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        # Invalid token (bad signature, malformed, etc)
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch-all for unexpected errors to prevent crash
        logger.error(f"Auth system error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system error"
        )

async def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """
    Dependency that attempts to validate token but returns None instead of 401 if invalid.

    Used for endpoints that can work with or without authentication.
    """
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False}
        )
        return payload
    except Exception:
        # Return None for any token error (expired, invalid, etc)
        return None
