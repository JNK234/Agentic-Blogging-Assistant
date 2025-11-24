# ABOUTME: Supabase client configuration and initialization
# ABOUTME: Provides singleton Supabase client instance with environment-based configuration

"""
Supabase client configuration for QuiboAI blogging assistant.
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Singleton client instance
_supabase_client = None


def get_supabase_client():
    """
    Get or create Supabase client instance.

    Returns:
        Supabase client instance

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_KEY not set in environment
    """
    global _supabase_client

    if _supabase_client is None:
        # Import here to avoid issues if supabase package not installed
        try:
            from supabase import create_client, Client
        except ImportError:
            raise ImportError(
                "supabase package not installed. Install with: pip install supabase"
            )

        # Get environment variables
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")

        if not url:
            raise ValueError(
                "SUPABASE_URL not set in environment. "
                "Please set SUPABASE_URL in your .env file."
            )

        if not key:
            raise ValueError(
                "SUPABASE_KEY not set in environment. "
                "Please set SUPABASE_KEY in your .env file."
            )

        # Create client
        _supabase_client = create_client(url, key)
        logger.info(f"Supabase client initialized with URL: {url}")

    return _supabase_client


def reset_supabase_client():
    """
    Reset the singleton client instance.
    Useful for testing or when credentials change.
    """
    global _supabase_client
    _supabase_client = None
    logger.info("Supabase client reset")
