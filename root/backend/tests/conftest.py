# ABOUTME: Global pytest configuration and shared fixtures for all tests
# ABOUTME: Provides common test setup, cleanup, and utilities for project management tests

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.append('/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant')

from root.backend.services.project_manager import ProjectManager
from root.backend.main import state_cache


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide a temporary directory for test data that persists for the session."""
    temp_dir = tempfile.mkdtemp(prefix="blog_assistant_tests_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state_cache():
    """Automatically clean the state cache before each test."""
    state_cache.clear()
    yield
    state_cache.clear()


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent timestamp testing."""
    from datetime import datetime
    from unittest.mock import patch
    
    fixed_datetime = datetime(2024, 1, 15, 12, 0, 0)
    
    with patch('root.backend.services.project_manager.datetime') as mock_dt:
        mock_dt.now.return_value = fixed_datetime
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield fixed_datetime


# Common test data fixtures
@pytest.fixture
def sample_project_metadata():
    """Standard project metadata for testing."""
    return {
        "model_name": "claude-sonnet-4",
        "persona": "technical_writer",
        "difficulty_level": "intermediate",
        "target_audience": "developers"
    }


@pytest.fixture
def sample_milestone_data():
    """Standard milestone data for testing."""
    return {
        MilestoneType.FILES_UPLOADED: {
            "files": ["analysis.ipynb", "data.csv", "utils.py"],
            "file_count": 3,
            "total_size": 15420
        },
        MilestoneType.OUTLINE_GENERATED: {
            "title": "Machine Learning Model Deployment Guide",
            "difficulty_level": "intermediate",
            "sections": [
                {"title": "Introduction", "description": "Overview of ML deployment"},
                {"title": "Model Preparation", "description": "Preparing models for production"},
                {"title": "Deployment Strategies", "description": "Different deployment approaches"},
                {"title": "Monitoring and Maintenance", "description": "Post-deployment considerations"}
            ],
            "prerequisites": {
                "required_knowledge": ["Python", "Machine Learning basics", "Docker"],
                "recommended_tools": ["scikit-learn", "Flask", "Docker"],
                "setup_instructions": ["Install required packages", "Set up development environment"]
            }
        },
        MilestoneType.DRAFT_COMPLETED: {
            "compiled_blog": """# Machine Learning Model Deployment Guide

## Introduction
This guide covers the essential steps for deploying machine learning models to production...

## Model Preparation
Before deploying your model, you need to ensure it's production-ready...

## Deployment Strategies
There are several approaches to deploying ML models...

## Monitoring and Maintenance
Once deployed, your model requires ongoing monitoring...

## Conclusion
Successful ML model deployment requires careful planning and execution...""",
            "word_count": 1250,
            "sections_count": 4
        },
        MilestoneType.BLOG_REFINED: {
            "refined_content": """# Machine Learning Model Deployment: A Complete Guide

## Introduction
Deploying machine learning models to production is a critical step that bridges the gap between experimentation and real-world impact...

[Content continues with improved structure and clarity...]

## Conclusion
Successful ML model deployment is an iterative process that requires attention to detail and continuous improvement...""",
            "summary": "A comprehensive guide covering ML model deployment from preparation to monitoring, suitable for intermediate-level practitioners.",
            "improvements_made": [
                "Enhanced introduction with better context",
                "Added practical examples throughout",
                "Improved section transitions",
                "Clarified technical concepts"
            ]
        },
        MilestoneType.SOCIAL_GENERATED: {
            "linkedin_post": "🚀 New blog post: Machine Learning Model Deployment Guide! Learn how to take your ML models from development to production with practical strategies and best practices. #MachineLearning #MLOps #DataScience",
            "twitter_thread": [
                "🧵 Thread: ML Model Deployment Guide (1/5)",
                "Deploying ML models isn't just about code - it's about creating robust, scalable systems that deliver value. Here's what you need to know: 👇",
                "// Additional thread tweets..."
            ],
            "newsletter_snippet": "This week's featured article explores the complete process of ML model deployment, from initial preparation to ongoing maintenance and monitoring."
        }
    }


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "api: mark test as an API test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "concurrency: mark test as testing concurrent behavior"
    )