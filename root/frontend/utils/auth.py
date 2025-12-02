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
    Get authentication headers for Cloud Run requests.

    This function provides two layers of authentication:
    1. X-API-Key: Application-level API key validation
    2. Authorization: GCP identity token for Cloud Run IAM (if service account configured)

    Args:
        target_audience: The Cloud Run service URL (used for identity token)

    Returns:
        Dictionary of headers to include in requests
    """
    headers = {}

    # Layer 1: API Key (always added if configured)
    api_key = os.getenv('QUIBO_API_KEY', '')
    if api_key:
        headers['X-API-Key'] = api_key

    # Layer 2: GCP Identity Token (for Cloud Run IAM)
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
