# ABOUTME: Supabase OAuth authentication component using streamlit-supabase-auth
# ABOUTME: Provides Google OAuth login/logout functionality for Streamlit app

import streamlit as st
from streamlit_supabase_auth import login_form
from streamlit_js_eval import streamlit_js_eval
from typing import Optional, Dict, Any
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
# Go up 4 levels: components -> frontend -> root -> quibo
ROOT_DIR = Path(__file__).parent.parent.parent.parent
ENV_PATH = ROOT_DIR / '.env'
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)


class SupabaseAuthManager:
    """Manages Supabase OAuth authentication for the Streamlit app."""

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
        self.redirect_url = os.getenv("REDIRECT_URL", "http://localhost:8501/callback")

        if not self.supabase_url or not self.supabase_anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment")
        
        # Initialize Supabase client for proper session management
        self._supabase_client = None
    
    def _get_supabase_client(self):
        """Get or create Supabase client instance."""
        if self._supabase_client is None:
            self._supabase_client = create_client(self.supabase_url, self.supabase_anon_key)
        return self._supabase_client

    def get_session(self) -> Optional[Dict[str, Any]]:
        """Get the current authenticated session."""
        return st.session_state.get("supabase_session")

    def get_user(self) -> Optional[Dict[str, Any]]:
        """Get the current authenticated user."""
        session = self.get_session()
        if session and 'user' in session:
            return session['user']
        return None

    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated."""
        return self.get_user() is not None

    def authenticate_user(self) -> Optional[Dict[str, Any]]:
        """
        Display Google login form and handle authentication.

        Returns:
            Session dict if authenticated, None otherwise
        """
        # Handle pending logout - use streamlit_js_eval to clear browser localStorage
        if st.session_state.get("_pending_logout"):
            del st.session_state["_pending_logout"]
            
            # Use streamlit_js_eval to execute JavaScript in the main page context
            # This clears localStorage where streamlit-supabase-auth stores session data
            streamlit_js_eval(
                js_expressions="""
                    (function() {
                        localStorage.clear();
                        sessionStorage.clear();
                        return true;
                    })()
                """,
                key="clear_storage_js"
            )
            
            # Show logout message
            st.success("✅ Signed out successfully!")
            st.info("🔄 Refreshing page...")
            
            # Force a page reload to ensure clean state
            streamlit_js_eval(
                js_expressions="window.location.reload()",
                key="reload_page_js"
            )
            
            st.stop()
        
        # Use the streamlit-supabase-auth login form
        session = login_form(
            url=self.supabase_url,
            apiKey=self.supabase_anon_key,
            providers=["google"]
        )

        if session:
            logger.info(f"User authenticated: {session.get('user', {}).get('email')}")
            
            # The streamlit-supabase-auth library returns a session where access_token
            # is the Google OAuth token (RS256), not the Supabase JWT (HS256).
            # We need to use the Supabase Python client to set the session properly
            # and get the correct Supabase JWT for backend API calls.
            try:
                supabase = self._get_supabase_client()
                access_token = session.get('access_token')
                refresh_token = session.get('refresh_token')
                
                if access_token and refresh_token:
                    # Set the session using Supabase client - this will validate and
                    # potentially refresh the tokens, giving us the proper Supabase JWT
                    supabase_session = supabase.auth.set_session(access_token, refresh_token)
                    
                    if supabase_session and supabase_session.session:
                        # Store the PROPER Supabase session with HS256 JWT
                        proper_session = {
                            'access_token': supabase_session.session.access_token,
                            'refresh_token': supabase_session.session.refresh_token,
                            'expires_in': supabase_session.session.expires_in,
                            'expires_at': supabase_session.session.expires_at,
                            'token_type': supabase_session.session.token_type,
                            'user': session.get('user'),
                            'provider_token': session.get('provider_token'),
                        }
                        st.session_state["supabase_session"] = proper_session
                        logger.info("Proper Supabase session established")
                        return proper_session
                    else:
                        logger.warning("set_session returned no session, falling back to original")
                        st.session_state["supabase_session"] = session
                else:
                    logger.warning("Missing access_token or refresh_token, using original session")
                    st.session_state["supabase_session"] = session
                    
            except Exception as e:
                logger.error(f"Failed to set proper Supabase session: {e}")
                st.session_state["supabase_session"] = session
            
            return st.session_state.get("supabase_session")

        return None

    def handle_oauth_callback(self) -> bool:
        """
        Handle OAuth callback from Supabase.

        Returns:
            True if callback was handled successfully
        """
        query_params = st.query_params.to_dict()

        if 'access_token' in query_params or 'code' in query_params or 'error' in query_params:
            logger.info("OAuth callback detected, allowing library to handle...")
            return True

        return False

    def get_access_token(self) -> Optional[str]:
        """Get the current access token for API calls."""
        session = self.get_session()
        if session:
            token = session.get('access_token')
            if token:
                parts = token.split('.')
                if len(parts) != 3:
                    logger.error(f"Invalid JWT format: {len(parts)} parts (expected 3)")
                    return None
            return token
        return None

    def logout(self):
        """Sign out the current user and clear session."""
        # Sign out via Supabase client
        try:
            supabase = self._get_supabase_client()
            supabase.auth.sign_out()
            logger.info("Supabase sign_out() called successfully")
        except Exception as e:
            logger.warning(f"Supabase sign_out failed (may already be signed out): {e}")
        
        # Clear auth-related session data (keep app state like api_app_state)
        auth_keys_to_clear = [
            'supabase_session', 'auth_manager', 'login', 'user', 'session',
            'user_profile', 'authenticated', 'access_token'
        ]
        for key in auth_keys_to_clear:
            if key in st.session_state:
                try:
                    del st.session_state[key]
                except Exception:
                    pass
        
        # Set pending logout flag - browser storage will be cleared on next render
        st.session_state["_pending_logout"] = True
        
        logger.info("User logged out - pending browser storage clear on next render")
        
        st.success("✅ Signing out...")
        st.rerun()

    def show_login_ui(self):
        """Display the login UI for unauthenticated users."""
        st.markdown("### Welcome to Quibo")
        st.markdown("Sign in with Google to access your blog projects.")

        with st.expander("Why sign in?", expanded=True):
            st.markdown("""
            - ✨ Save and manage multiple blog projects
            - 🔒 Keep your work private and secure
            - 📊 Track your usage and costs
            - 🔄 Access your projects from any device
            - 🔗 Integrated with your Google account
            """)

    def show_user_profile(self):
        """Display user profile in the sidebar."""
        user = self.get_user()
        if not user:
            return

        with st.sidebar:
            st.markdown("---")

            full_name = user.get('user_metadata', {}).get('full_name', user.get('email', 'User'))
            avatar_url = user.get('user_metadata', {}).get('avatar_url')

            if avatar_url:
                st.image(avatar_url, width=50)

            st.markdown(f"**{full_name}**")
            st.caption(user.get('email', ''))

            if st.button("Sign out", type="secondary"):
                self.logout()


def require_auth() -> Optional[Dict[str, Any]]:
    """
    Decorator-like function that requires authentication.

    Returns:
        User dict if authenticated, None otherwise (and stops execution)
    """
    auth_manager = SupabaseAuthManager()

    if auth_manager.handle_oauth_callback():
        return None

    if not auth_manager.is_authenticated():
        auth_manager.authenticate_user()

    if not auth_manager.is_authenticated():
        auth_manager.show_login_ui()
        st.stop()

    return auth_manager.get_user()


def get_auth_manager() -> SupabaseAuthManager:
    """Get or create the auth manager instance."""
    if 'auth_manager' not in st.session_state:
        st.session_state.auth_manager = SupabaseAuthManager()
    return st.session_state.auth_manager
