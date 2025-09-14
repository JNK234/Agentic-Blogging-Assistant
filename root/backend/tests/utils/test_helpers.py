# ABOUTME: Test helper utilities and common functions for test suites
# ABOUTME: Provides reusable functions for creating test data and assertions

import json
import uuid
import tempfile
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta

from root.backend.services.project_manager import ProjectManager, MilestoneType


class ProjectTestHelper:
    """Helper class for creating and managing test projects."""
    
    def __init__(self, project_manager: ProjectManager):
        self.project_manager = project_manager
        self.created_projects = []
    
    def create_test_project(self, name: str = None, metadata: Dict[str, Any] = None) -> str:
        """Create a test project with optional custom name and metadata."""
        if name is None:
            name = f"Test Project {uuid.uuid4().hex[:8]}"
        
        if metadata is None:
            metadata = {
                "model_name": "test-model",
                "persona": "test-persona",
                "created_by": "test-helper"
            }
        
        project_id = self.project_manager.create_project(name, metadata)
        self.created_projects.append(project_id)
        return project_id
    
    def create_project_with_milestones(self, milestone_types: List[MilestoneType]) -> str:
        """Create a project and add the specified milestones."""
        project_id = self.create_test_project()
        
        for milestone_type in milestone_types:
            test_data = self.get_test_milestone_data(milestone_type)
            self.project_manager.save_milestone(project_id, milestone_type, test_data)
        
        return project_id
    
    def get_test_milestone_data(self, milestone_type: MilestoneType) -> Dict[str, Any]:
        """Get appropriate test data for a milestone type."""
        test_data = {
            MilestoneType.FILES_UPLOADED: {
                "files": ["test1.py", "test2.md"],
                "file_count": 2,
                "upload_time": datetime.now().isoformat()
            },
            MilestoneType.OUTLINE_GENERATED: {
                "title": "Test Blog Outline",
                "sections": [
                    {"title": "Introduction", "description": "Test intro"},
                    {"title": "Main Content", "description": "Test content"}
                ],
                "difficulty_level": "beginner"
            },
            MilestoneType.DRAFT_COMPLETED: {
                "compiled_blog": "# Test Blog\\n\\nThis is test content.",
                "word_count": 100,
                "sections_count": 2
            },
            MilestoneType.BLOG_REFINED: {
                "refined_content": "# Test Blog (Refined)\\n\\nThis is refined test content.",
                "summary": "Test blog summary",
                "improvements": ["Better structure", "Clearer language"]
            },
            MilestoneType.SOCIAL_GENERATED: {
                "linkedin": "Test LinkedIn post",
                "twitter": "Test Twitter post",
                "newsletter": "Test newsletter content"
            }
        }
        
        return test_data.get(milestone_type, {"test_data": True})
    
    def cleanup(self):
        """Clean up all created test projects."""
        for project_id in self.created_projects:
            try:
                self.project_manager.delete_project(project_id, permanent=True)
            except Exception:
                pass  # Ignore cleanup errors
        self.created_projects.clear()


class AssertionHelper:
    """Helper class for common test assertions."""
    
    @staticmethod
    def assert_valid_uuid(uuid_string: str):
        """Assert that a string is a valid UUID."""
        try:
            uuid.UUID(uuid_string)
        except ValueError:
            raise AssertionError(f"'{uuid_string}' is not a valid UUID")
    
    @staticmethod
    def assert_valid_iso_datetime(datetime_string: str):
        """Assert that a string is a valid ISO datetime."""
        try:
            datetime.fromisoformat(datetime_string.replace('Z', '+00:00'))
        except ValueError:
            raise AssertionError(f"'{datetime_string}' is not a valid ISO datetime")
    
    @staticmethod
    def assert_project_data_structure(project_data: Dict[str, Any]):
        """Assert that project data has the expected structure."""
        required_fields = [
            "id", "name", "created_at", "updated_at", "status",
            "current_milestone", "milestones", "metadata"
        ]
        
        for field in required_fields:
            assert field in project_data, f"Missing required field: {field}"
        
        AssertionHelper.assert_valid_uuid(project_data["id"])
        AssertionHelper.assert_valid_iso_datetime(project_data["created_at"])
        AssertionHelper.assert_valid_iso_datetime(project_data["updated_at"])