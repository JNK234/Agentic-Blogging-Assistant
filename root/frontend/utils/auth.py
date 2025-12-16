# ABOUTME: Authentication utility for Cloud Run backend access
# ABOUTME: Generates auth headers with API key and GCP identity token

import os
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Root directory for resolving relative paths
ROOT_DIR = Path(__file__).parent.parent.parent

# Optional: Google Auth for Cloud Run IAM authentication
try:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    from google.oauth2.service_account import IDTokenCredentials
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False
    logger.info("google-auth not installed, using API key auth only")


def get_auth_headers(target_audience: Optional[str] = None) -> Dict[str, str]:
    """
    Get authentication headers for API requests.

    This function provides authentication in priority order:
    1. Supabase JWT token (for authenticated users via Google OAuth)
    2. X-API-Key: Application-level API key validation
    3. GCP identity token for Cloud Run IAM (fallback for production)

    Args:
        target_audience: The Cloud Run service URL (used for identity token)

    Returns:
        Dictionary of headers to include in requests
    """
    import streamlit as st
    
    headers = {}

    # Layer 1: API Key (always added if configured)
    api_key = os.getenv('QUIBO_API_KEY', '')
    if api_key:
        headers['X-API-Key'] = api_key

    # Layer 2: Supabase JWT (priority for authenticated users)
    # This is the proper HS256 token that the backend can verify
    try:
        supabase_session = st.session_state.get("supabase_session")
        if supabase_session and supabase_session.get("access_token"):
            token = supabase_session["access_token"]
            headers['Authorization'] = f'Bearer {token}'
            logger.debug(f"Added Supabase JWT to headers (len={len(token)})")
            return headers  # Supabase auth takes priority, return early
    except Exception as e:
        logger.debug(f"No Supabase session available: {e}")

    # Layer 3: GCP Identity Token (fallback for Cloud Run IAM in production)
    if GOOGLE_AUTH_AVAILABLE:
        sa_file = os.getenv('GCP_SERVICE_ACCOUNT_FILE', '')
        # Resolve relative paths against ROOT_DIR
        if sa_file and not os.path.isabs(sa_file):
            sa_file = str(ROOT_DIR / sa_file)
        if sa_file and os.path.exists(sa_file) and target_audience:
            try:
                credentials = IDTokenCredentials.from_service_account_file(
                    sa_file,
                    target_audience=target_audience
                )
                request = Request()
                credentials.refresh(request)
                headers['Authorization'] = f'Bearer {credentials.token}'
                logger.debug("Added GCP identity token to headers")
            except Exception as e:
                logger.warning(f"Failed to generate identity token: {e}")

    return headers


def is_auth_configured() -> bool:
    """Check if authentication is properly configured."""
    api_key = os.getenv('QUIBO_API_KEY', '')
    sa_file = os.getenv('GCP_SERVICE_ACCOUNT_FILE', '')

    if not api_key:
        logger.warning("QUIBO_API_KEY not configured")
        return False

    if sa_file and not os.path.exists(sa_file):
        logger.warning(f"Service account file not found: {sa_file}")
        return False

    return True


def get_auth_headers_with_user(target_audience: Optional[str] = None) -> Dict[str, str]:
    """
    Get authentication headers including Supabase user info for backend requests.

    This extends get_auth_headers by adding user identification headers when
    a user is authenticated via Supabase Auth.

    Args:
        target_audience: The Cloud Run service URL (used for identity token)

    Returns:
        Dictionary of headers including API key, identity token, and user info
    """
    import streamlit as st

    headers = get_auth_headers(target_audience)

    # Add user info if authenticated via Supabase
    if "user" in st.session_state:
        user = st.session_state.user
        headers["X-User-ID"] = str(user.id)
        headers["X-User-Email"] = user.email

    return headers
