# ABOUTME: Production-ready Streamlit blogging assistant with complete workflow integration and sophisticated backend utilization.
# ABOUTME: Provides seamless file upload → outline generation → blog drafting → social media → export pipeline with project management and state persistence.

import streamlit as st
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import httpx
from pathlib import Path
import json
import re
from datetime import datetime
import zipfile
import io
import time
from dataclasses import dataclass
from enum import Enum
import uuid

# Import components and services
from components.blog_workflow import BlogWorkflow
from services.state_manager import StateManager
from services.project_service import ProjectService

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AppConfig:
    PAGE_TITLE = "Agentic Blogging Assistant"
    PAGE_ICON = "📝"
    LAYOUT = "wide"
    API_BASE_URL = "http://127.0.0.1:8000"
    DEFAULT_MODEL = "gemini"
    SUPPORTED_MODELS = ["gemini", "claude", "openai", "deepseek", "openrouter"]
    SUPPORTED_EXTENSIONS = [".ipynb", ".md", ".py"]

def main():
    """Main application entry point with complete workflow integration."""
    # Page configuration
    st.set_page_config(
        page_title=AppConfig.PAGE_TITLE,
        page_icon=AppConfig.PAGE_ICON,
        layout=AppConfig.LAYOUT,
        initial_sidebar_state="expanded"
    )
    
    # Initialize state management
    state_manager = StateManager()
    state_manager.initialize()
    
    # Initialize blog workflow component
    workflow = BlogWorkflow(state_manager, AppConfig.API_BASE_URL)
    
    # Application header
    st.title("📝 Agentic Blogging Assistant")
    st.markdown(
        "Transform your technical content into engaging blog posts with AI-powered workflows. "
        "Upload → Outline → Draft → Refine → Share → Export."
    )
    
    # Render main workflow
    workflow.render()
    
    # Auto-save state changes
    state_manager.auto_save()

if __name__ == "__main__":
    main()