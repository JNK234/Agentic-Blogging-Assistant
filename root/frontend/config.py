import streamlit as st
from pathlib import Path

# Constants
API_BASE_URL = "http://localhost:8000"  # FastAPI backend URL
ROOT_DIR = Path(__file__).parent.parent
CACHE_DIR = ROOT_DIR / "data" / "cache"
UPLOAD_DIRECTORY = ROOT_DIR / "data" / "uploads"

# Initialize cache directory
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Agentic Blogging Assistant",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded"
    )
