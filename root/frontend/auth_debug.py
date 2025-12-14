# -*- coding: utf-8 -*-
"""
Minimal Authentication Debug Page
Simple page to test Supabase Google OAuth without any other complexity
"""

import streamlit as st
import os
import logging
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file in parent directory
ROOT_DIR = Path(__file__).parent.parent
ENV_PATH = ROOT_DIR / '.env'
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuthDebug")

# Page config
st.set_page_config(
    page_title="Quibo Auth Debug",
    page_icon="🔍",
    layout="centered"
)

st.title("🔍 Authentication Debug Tool")
st.markdown("---")

# Environment check
st.subheader("1. Environment Configuration")
col1, col2 = st.columns(2)

with col1:
    supabase_url = os.getenv("SUPABASE_URL", "NOT SET")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "NOT SET")

    st.markdown(f"**SUPABASE_URL:**")
    st.code(supabase_url[:50] + "..." if supabase_url != "NOT SET" else "NOT SET", language="text")

    st.markdown(f"**SUPABASE_ANON_KEY:**")
    st.code(supabase_key[:20] + "..." if supabase_key != "NOT SET" else "NOT SET", language="text")

with col2:
    # Test button
    if st.button("Test Supabase Connection", type="primary"):
        try:
            from supabase import create_client
            client = create_client(supabase_url, supabase_key)

            # Try to get session
            session = client.auth.get_session()

            if session:
                st.success("✅ Connected to Supabase!")
                st.info(f"Session: {session.user.email if session.user else 'No user'}")
            else:
                st.info("ℹ️ Connected, but no active session")
        except Exception as e:
            st.error(f"❌ Connection failed: {str(e)}")
            logger.error(f"Supabase connection error: {e}")

st.markdown("---")

# Simple Google OAuth Test
st.subheader("2. Google OAuth Test")

if st.button("🔐 Sign in with Google (Simple Test)", use_container_width=True):
    try:
        from supabase import create_client
        import webbrowser

        client = create_client(supabase_url, supabase_key)

        # Start OAuth flow
        auth_response = client.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {
                "redirect_to": os.getenv("REDIRECT_URL", "http://localhost:8501")
            }
        })

        if auth_response:
            st.success("✅ OAuth flow initiated!")
            st.info("Check if you were redirected to Google...")

            # Show the URL
            st.markdown("**Auth URL:**")
            st.code(str(auth_response), language="text")

    except Exception as e:
        st.error(f"❌ OAuth failed: {str(e)}")
        logger.error(f"OAuth error: {e}")
        st.exception(e)

st.markdown("---")

# Session check
st.subheader("3. Current Session Status")

try:
    from supabase import create_client
    client = create_client(supabase_url, supabase_key)
    session = client.auth.get_session()

    if session and session.user:
        st.success("✅ User is logged in!")
        st.json({
            "email": session.user.email,
            "id": str(session.user.id),
            "provider": session.user.app_metadata.get("provider"),
        })

        if st.button("🚪 Sign Out", type="secondary"):
            client.auth.sign_out()
            st.rerun()
    else:
        st.info("ℹ️ No user logged in")

except Exception as e:
    st.error(f"❌ Session check failed: {str(e)}")

st.markdown("---")

# Backend connectivity test
st.subheader("4. Backend Connectivity Test")
backend_url = "https://quibo-backend-870041009851.us-central1.run.app"

if st.button("Test Backend Connection"):
    try:
        import httpx
        response = httpx.get(f"{backend_url}/health", timeout=10)

        if response.status_code == 200:
            st.success("✅ Backend is accessible!")
        else:
            st.warning(f"⚠️ Backend returned: {response.status_code}")
            st.text(response.text)
    except Exception as e:
        st.error(f"❌ Backend connection failed: {str(e)}")

st.markdown("---")

# Instructions
st.subheader("📋 Next Steps if OAuth Fails:")

st.markdown("""

1. **Check Supabase OAuth Settings:**
   - Go to Supabase → Authentication → Providers → Google
   - Ensure Google is enabled
   - Check Client ID and Secret are correct

2. **Verify Redirect URLs:**
   - Supabase → Authentication → URL Configuration
   - Site URL should match your frontend URL
   - Redirect URLs should include your callback

3. **Check Google Cloud OAuth:**
   - Console → APIs & Services → Credentials
   - Verify redirect URIs include your frontend
   - Check OAuth consent screen is configured

4. **Check IAM Access:**
   ```bash
   gcloud run services get-iam-policy quibo-frontend --region=us-central1 --project=personal-os-475406
   ```
   - Ensure your email has `roles/run.invoker`

5. **Try Incognito Mode:**
   - Open browser incognito/private window
   - Sign in with Google account
   - Check for specific error messages

6. **Check Browser Console:**
   - Open DevTools (F12)
   - Look for errors in Console and Network tabs
""")

st.info("After fixing issues, run this debug page again to verify")

st.markdown("---")
st.caption("For support, check logs in Cloud Logging or run with: streamlit run auth_debug.py")
