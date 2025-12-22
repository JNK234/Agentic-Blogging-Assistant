# ABOUTME: User authentication component using Supabase Auth with Google OAuth
# ABOUTME: Provides login/logout UI and session management for Streamlit app

import streamlit as st
import os
from typing import Optional, Dict, Any
import logging
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in parent directory
ROOT_DIR = Path(__file__).parent.parent.parent
ENV_PATH = ROOT_DIR / '.env'
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)

# Initialize Supabase client
@st.cache_resource
def init_supabase_client():
    """Initialize Supabase client for frontend authentication."""
    try:
        from supabase import create_client
    except ImportError:
        st.error("supabase package not installed. Run: pip install supabase")
        st.stop()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not key:
        st.error("Supabase credentials not configured in environment")
        st.stop()

    return create_client(url, key)

def login_with_google():
    """Display Google login button."""
    st.markdown("### Sign in to Quibo")
    st.markdown("Use your Google account to access the blogging assistant.")

    if st.button("Sign in with Google", type="primary", use_container_width=True):
        supabase = init_supabase_client()
        try:
            # Use callback page to handle OAuth flow
            redirect_url = os.getenv("REDIRECT_URL", "http://localhost:8501/callback")

            # Start OAuth flow - this returns a URL that we need to open
            auth_url = supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": redirect_url
                }
            })

            if auth_url:
                st.success("Opening Google sign-in page...")
                # Open the OAuth URL in a new tab/window
                st.markdown(f"""
                <script>
                window.open('{auth_url}', '_blank');
                </script>
                """, unsafe_allow_html=True)
                st.info("If the page didn't open, click here: ")
                st.markdown(f"[Continue to Google Sign-In]({auth_url})")

        except Exception as e:
            logger.error(f"OAuth error: {e}")
            st.error(f"Authentication failed: {str(e)}")

def handle_oauth_callback():
    """Handle OAuth callback and extract session."""
    import streamlit as st
    import time
    supabase = init_supabase_client()

    # Check if there's already a session
    try:
        # Try to get existing session (may need multiple attempts)
        for attempt in range(5):
            logger.info(f"Attempt {attempt + 1}: Checking for session...")
            session = supabase.auth.get_session()
            if session and session.user:
                st.session_state["user"] = session.user
                st.session_state["session"] = session
                logger.info(f"Session found on attempt {attempt + 1}: {session.user.email}")
                return True
            else:
                logger.info(f"Attempt {attempt + 1}: No session found")
            time.sleep(1)  # Wait a bit before retrying
    except Exception as e:
        logger.warning(f"Session extraction failed: {e}")

    return False

def logout():
    """Sign out the current user."""
    supabase = init_supabase_client()
    try:
        supabase.auth.sign_out()
        # Clear all user data from session state
        st.session_state.pop("user", None)
        st.session_state.pop("session", None)
        st.session_state.pop("user_profile", None)

        # Clear project-related state
        keys_to_clear = [k for k in st.session_state.keys() if k not in ["api_app_state"]]
        for key in keys_to_clear:
            st.session_state.pop(key, None)

        st.success("You have been signed out successfully.")
        st.rerun()
    except Exception as e:
        logger.error(f"Logout error: {e}")
        st.error(f"Logout failed: {str(e)}")

def get_current_user() -> Optional[Dict[str, Any]]:
    """Get the currently authenticated user."""
    return st.session_state.get("user")

def require_auth():
    """Decorator-like function to require authentication."""
    import time

    # Check for OAuth callback first (try multiple times)
    for attempt in range(3):
        if handle_oauth_callback():
            logger.info("OAuth callback successful on attempt " + str(attempt + 1))
            time.sleep(1)  # Give it a moment to stabilize
            st.rerun()

    # Check if user is authenticated
    user = get_current_user()

    if not user:
        # Show login UI if not authenticated
        login_with_google()

        # Show additional info in expander
        with st.expander("Why sign in?"):
            st.markdown("""
            - ✨ Save and manage multiple blog projects
            - 🔒 Keep your work private and secure
            - 📊 Track costs and usage over time
            - 🔄 Resume projects from any device
            - 🔗 Integration with your Google account
            """)

        st.info("👆 Click 'Sign in with Google' above to continue")
        st.stop()

    return user

def show_user_profile():
    """Display user profile in sidebar."""
    user = get_current_user()
    if not user:
        return

    with st.sidebar:
        st.markdown("---")

        # Avatar and name
        avatar_url = user.user_metadata.get("avatar_url") if user.user_metadata else None
        full_name = user.user_metadata.get("full_name") if user.user_metadata else user.email

        if avatar_url:
            st.image(avatar_url, width=50)

        st.markdown(f"**{full_name}**")
        st.caption(user.email)

        if st.button("Sign out", type="secondary"):
            logout()
