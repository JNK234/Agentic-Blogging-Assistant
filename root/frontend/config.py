import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory (.env is in root/)
ROOT_DIR = Path(__file__).parent.parent
ENV_PATH = ROOT_DIR / '.env'

# Verify .env exists, if not try alternative paths
if not ENV_PATH.exists():
    # Try current working directory as fallback
    ENV_PATH = Path.cwd() / '.env'
    if not ENV_PATH.exists():
        # Try looking in parent of current directory
        ENV_PATH = Path.cwd().parent / '.env'

load_dotenv(ENV_PATH)

# Constants
API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')
CACHE_DIR = ROOT_DIR / "data" / "cache"
UPLOAD_DIRECTORY = ROOT_DIR / "data" / "uploads"

# Initialize cache directory
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Model Configuration
class ModelConfig:
    """Centralized model configuration for the frontend."""

    # Default provider configuration - matches backend providers
    DEFAULT_PROVIDERS = ["gemini", "claude", "openai", "deepseek", "openrouter"]
    DEFAULT_MODEL = "gemini"

    # Provider display names and descriptions
    PROVIDER_INFO = {
        "gemini": {
            "display_name": "Google Gemini",
            "description": "Google's multimodal AI models with strong reasoning"
        },
        "claude": {
            "display_name": "Anthropic Claude",
            "description": "Advanced conversational AI with safety focus"
        },
        "openai": {
            "display_name": "OpenAI",
            "description": "GPT models for versatile AI tasks"
        },
        "deepseek": {
            "display_name": "DeepSeek",
            "description": "Efficient models optimized for coding"
        },
        "openrouter": {
            "display_name": "OpenRouter",
            "description": "Access to multiple models through one API"
        }
    }

    @classmethod
    def get_provider_display_name(cls, provider: str) -> str:
        """Get display name for a provider."""
        return cls.PROVIDER_INFO.get(provider, {}).get("display_name", provider.title())

    @classmethod
    def get_provider_description(cls, provider: str) -> str:
        """Get description for a provider."""
        return cls.PROVIDER_INFO.get(provider, {}).get("description", f"{provider} models")

def configure_page():
    """Configure Streamlit page settings."""
    st.set_page_config(
        page_title="Agentic Blogging Assistant",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded"
    )
