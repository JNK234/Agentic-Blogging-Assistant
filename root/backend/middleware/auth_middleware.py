# ABOUTME: JWT token verification middleware for user authentication
# ABOUTME: Validates Supabase Auth tokens and extracts user info

import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from supabase import create_client
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate Supabase JWT tokens and authenticate users.
    Extracts user info and makes it available in request.state.user
    """

    def __init__(self, app):
        super().__init__(app)
        self.supabase_url = os.getenv("SUPABASE_URL")
        # Support both SUPABASE_ANON_KEY and SUPABASE_KEY for compatibility
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

        if not self.supabase_url or not self.supabase_anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check and public endpoints
        if request.url.path in ["/health", "/models", "/personas"]:
            return await call_next(request)

        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Try X-User-ID header for API key auth compatibility
            user_id = request.headers.get("X-User-ID")
            if user_id:
                request.state.user = {"id": user_id, "email": request.headers.get("X-User-Email")}
                return await call_next(request)

            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )

        token = auth_header.replace("Bearer ", "")

        try:
            # Verify token with Supabase
            supabase = create_client(self.supabase_url, self.supabase_anon_key)
            user = supabase.auth.get_user(token)

            if not user or not user.user:
                raise HTTPException(status_code=401, detail="Invalid token")

            # Add user info to request state
            request.state.user = {
                "id": user.user.id,
                "email": user.user.email,
                "user_metadata": user.user.user_metadata
            }

        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=401,
                detail=f"Token verification failed: {str(e)}"
            )

        return await call_next(request)
