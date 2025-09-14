# ABOUTME: Comprehensive unit tests for ProjectManager service covering all CRUD operations
# ABOUTME: Tests include happy paths, edge cases, error conditions, and atomic operations

import pytest
import json
import os
import uuid
import zipfile
import tempfile
import shutil
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys
sys.path.append('/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant')

from root.backend.services.project_manager import ProjectManager, ProjectStatus, MilestoneType


class TestProjectManagerInitialization:
    """Test ProjectManager initialization and setup."""
    
    def test_initialization_creates_base_directory(self, tmp_path):
        """Test that ProjectManager initializes and creates its base directory."""
        # Arrange
        base_dir = tmp_path / "projects"
        assert not base_dir.exists()
        
        # Act
        ProjectManager(base_dir=str(base_dir))
        
        # Assert
        assert base_dir.exists()
        assert base_dir.is_dir()
    
    def test_initialization_with_existing_directory(self, tmp_path):
        """Test initialization when base directory already exists."""
        # Arrange
        base_dir = tmp_path / "existing_projects"
        base_dir.mkdir()
        
        # Act & Assert (should not raise)
        pm = ProjectManager(base_dir=str(base_dir))
        assert pm.base_dir == base_dir
    
    def test_default_base_directory_path(self):
        """Test that default base directory is correctly set."""
        # Act
        pm = ProjectManager()
        
        # Assert
        expected_path = Path(__file__).parent.parent.parent.parent / "data" / "projects"
        assert str(pm.base_dir).endswith("data/projects")


@pytest.fixture
def temp_project_dir(tmp_path: Path) -> Path:
    """Provides a temporary directory for project storage."""
    return tmp_path / "projects"


@pytest.fixture
def project_manager(temp_project_dir: Path) -> ProjectManager:
    """Provides a ProjectManager instance using a temporary directory."""
    return ProjectManager(base_dir=str(temp_project_dir))


@pytest.fixture
def sample_metadata() -> dict:
    """Provides sample project metadata."""
    return {
        "model_name": "claude-3",
        "persona": "expert_developer",
        "created_by": "test_user"
    }


@pytest.fixture
def created_project(project_manager: ProjectManager, sample_metadata: dict) -> str:
    """Creates a project and returns its ID."""
    project_id = project_manager.create_project(
        "Test Project",
        metadata=sample_metadata
    )
    return project_id


@pytest.fixture
def project_with_milestones(project_manager: ProjectManager, created_project: str) -> str:
    """Creates a project with several milestones for testing."""
    # Add files uploaded milestone
    project_manager.save_milestone(
        created_project,
        MilestoneType.FILES_UPLOADED,
        {"files": ["test.py", "data.csv"], "file_count": 2}
    )
    
    # Add outline generated milestone  
    project_manager.save_milestone(
        created_project,
        MilestoneType.OUTLINE_GENERATED,
        {
            "title": "Test Blog Post",
            "sections": [
                {"title": "Introduction", "description": "Intro content"},
                {"title": "Main Content", "description": "Main content"}
            ]
        }
    )
    
    return created_project


class TestProjectCreation:
    """Test project creation functionality."""
    
    def test_create_project_success(self, project_manager: ProjectManager, temp_project_dir: Path):
        """Test successful project creation with all components."""
        # Arrange
        project_name = "My Awesome Project"
        metadata = {"model": "gpt-4", "persona": "teacher"}
        
        # Act
        project_id = project_manager.create_project(project_name, metadata)
        
        # Assert
        # Validate UUID format
        assert uuid.UUID(project_id)
        
        # Check directory structure
        project_path = temp_project_dir / project_id
        assert project_path.exists()
        assert project_path.is_dir()
        
        # Check project.json content
        project_file = project_path / "project.json"
        assert project_file.exists()
        
        with open(project_file, 'r') as f:
            data = json.load(f)
        
        assert data["id"] == project_id
        assert data["name"] == project_name
        assert data["status"] == ProjectStatus.ACTIVE.value
        assert data["current_milestone"] is None
        assert data["milestones"] == {}
        assert data["metadata"] == metadata
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_project_no_metadata(self, project_manager: ProjectManager):
        """Test creating a project without metadata."""
        # Act
        project_id = project_manager.create_project("Simple Project")
        
        # Assert
        project_data = project_manager.get_project(project_id)
        assert project_data["metadata"] == {}
    
    def test_create_project_empty_name(self, project_manager: ProjectManager):
        """Test creating a project with empty name."""
        # Act
        project_id = project_manager.create_project("")
        
        # Assert
        project_data = project_manager.get_project(project_id)
        assert project_data["name"] == ""
    
    def test_create_multiple_projects_unique_ids(self, project_manager: ProjectManager):
        """Test that multiple projects get unique IDs."""
        # Act
        id1 = project_manager.create_project("Project 1")
        id2 = project_manager.create_project("Project 2")
        id3 = project_manager.create_project("Project 3")
        
        # Assert
        assert id1 != id2 != id3
        assert len({id1, id2, id3}) == 3
    
    @patch('root.backend.services.project_manager.ProjectManager._atomic_write')
    def test_create_project_atomic_write_failure(self, mock_atomic_write, project_manager: ProjectManager):
        """Test project creation handles atomic write failure."""
        # Arrange
        mock_atomic_write.side_effect = IOError("Disk full")
        
        # Act & Assert
        with pytest.raises(IOError):
            project_manager.create_project("Failed Project")


class TestProjectRetrieval:
    """Test project retrieval functionality."""
    
    def test_get_project_success(self, project_manager: ProjectManager, created_project: str):
        """Test retrieving an existing project."""
        # Act
        project_data = project_manager.get_project(created_project)
        
        # Assert
        assert project_data is not None
        assert project_data["id"] == created_project
        assert project_data["name"] == "Test Project"
        assert project_data["status"] == ProjectStatus.ACTIVE.value
    
    def test_get_project_not_found(self, project_manager: ProjectManager):
        """Test retrieving a non-existent project returns None."""
        # Arrange
        fake_id = str(uuid.uuid4())
        
        # Act
        project_data = project_manager.get_project(fake_id)
        
        # Assert
        assert project_data is None
    
    def test_get_project_corrupted_json(self, project_manager: ProjectManager, created_project: str):
        """Test handling corrupted project.json file."""
        # Arrange
        project_file = project_manager._get_project_path(created_project) / "project.json"
        with open(project_file, "w") as f:
            f.write("{ invalid json content")
        
        # Act
        result = project_manager.get_project(created_project)
        
        # Assert
        assert result is None
    
    def test_get_project_missing_file(self, project_manager: ProjectManager, temp_project_dir: Path):
        """Test handling when project directory exists but project.json is missing."""
        # Arrange
        project_id = str(uuid.uuid4())
        project_dir = temp_project_dir / project_id
        project_dir.mkdir(parents=True)
        # Don't create project.json
        
        # Act
        result = project_manager.get_project(project_id)
        
        # Assert
        assert result is None
    
    def test_get_project_permission_denied(self, project_manager: ProjectManager, created_project: str):
        """Test handling permission denied errors."""
        # Arrange
        project_file = project_manager._get_project_path(created_project) / "project.json"
        
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            # Act
            result = project_manager.get_project(created_project)
            
            # Assert
            assert result is None


class TestProjectListing:
    """Test project listing and filtering functionality."""
    
    def test_list_projects_empty(self, project_manager: ProjectManager):
        """Test listing when no projects exist."""
        # Act
        projects = project_manager.list_projects()
        
        # Assert
        assert projects == []
    
    def test_list_all_projects(self, project_manager: ProjectManager):
        """Test listing all projects without status filter."""
        # Arrange
        p1_id = project_manager.create_project("Active Project 1")
        p2_id = project_manager.create_project("Active Project 2")
        
        # Act
        projects = project_manager.list_projects()
        
        # Assert
        assert len(projects) == 2
        project_ids = [p["id"] for p in projects]
        assert p1_id in project_ids
        assert p2_id in project_ids
    
    def test_list_projects_with_different_statuses(self, project_manager: ProjectManager):
        """Test listing projects with different statuses and filtering."""
        # Arrange
        active_id = project_manager.create_project("Active Project")
        archived_id = project_manager.create_project("Archived Project")  
        deleted_id = project_manager.create_project("Deleted Project")
        
        # Change statuses
        project_manager.archive_project(archived_id)
        project_manager.delete_project(deleted_id, permanent=False)  # Soft delete
        
        # Act
        all_projects = project_manager.list_projects()
        active_projects = project_manager.list_projects(status=ProjectStatus.ACTIVE)
        archived_projects = project_manager.list_projects(status=ProjectStatus.ARCHIVED)
        deleted_projects = project_manager.list_projects(status=ProjectStatus.DELETED)
        
        # Assert
        assert len(all_projects) == 3
        
        assert len(active_projects) == 1
        assert active_projects[0]["id"] == active_id
        assert active_projects[0]["status"] == ProjectStatus.ACTIVE.value
        
        assert len(archived_projects) == 1
        assert archived_projects[0]["id"] == archived_id
        assert archived_projects[0]["status"] == ProjectStatus.ARCHIVED.value
        
        assert len(deleted_projects) == 1
        assert deleted_projects[0]["id"] == deleted_id
        assert deleted_projects[0]["status"] == ProjectStatus.DELETED.value
    
    def test_list_projects_sorted_by_updated_at(self, project_manager: ProjectManager):
        """Test that projects are sorted by updated_at in descending order."""
        # Arrange
        p1_id = project_manager.create_project("First Project")
        time.sleep(0.1)  # Ensure different timestamps
        p2_id = project_manager.create_project("Second Project")
        time.sleep(0.1)
        p3_id = project_manager.create_project("Third Project")
        
        # Act
        projects = project_manager.list_projects()
        
        # Assert
        assert len(projects) == 3
        assert projects[0]["id"] == p3_id  # Most recent first
        assert projects[1]["id"] == p2_id
        assert projects[2]["id"] == p1_id  # Oldest last
    
    def test_list_projects_with_corrupted_entries(self, project_manager: ProjectManager, temp_project_dir: Path):
        """Test listing projects ignores corrupted entries."""
        # Arrange
        good_id = project_manager.create_project("Good Project")
        
        # Create a corrupted entry
        bad_id = str(uuid.uuid4())
        bad_dir = temp_project_dir / bad_id
        bad_dir.mkdir()
        bad_file = bad_dir / "project.json"
        with open(bad_file, "w") as f:
            f.write("{ corrupted json")
        
        # Act
        projects = project_manager.list_projects()
        
        # Assert
        assert len(projects) == 1
        assert projects[0]["id"] == good_id


class TestMilestoneManagement:
    """Test milestone saving and loading functionality."""
    
    def test_save_milestone_success(self, project_manager: ProjectManager, created_project: str):
        """Test successfully saving a milestone."""
        # Arrange
        milestone_type = MilestoneType.OUTLINE_GENERATED
        milestone_data = {
            "title": "My Blog Post",
            "sections": [{"title": "Intro", "content": "..."}],
            "difficulty": "intermediate"
        }
        metadata = {"model_used": "claude-3", "generation_time": 12.5}
        
        # Act
        success = project_manager.save_milestone(
            created_project, milestone_type, milestone_data, metadata
        )
        
        # Assert
        assert success is True
        
        # Check milestone file
        milestone_file = project_manager._get_project_path(created_project) / f"{milestone_type.value}.json"
        assert milestone_file.exists()
        
        with open(milestone_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data["type"] == milestone_type.value
        assert saved_data["data"] == milestone_data
        assert saved_data["metadata"] == metadata
        assert "created_at" in saved_data
        
        # Check project.json updated
        project_data = project_manager.get_project(created_project)
        assert project_data["current_milestone"] == milestone_type.value
        assert milestone_type.value in project_data["milestones"]
        assert "saved_at" in project_data["milestones"][milestone_type.value]
    
    def test_save_milestone_project_not_found(self, project_manager: ProjectManager):
        """Test saving milestone for non-existent project."""
        # Arrange
        fake_id = str(uuid.uuid4())
        
        # Act
        success = project_manager.save_milestone(
            fake_id, MilestoneType.FILES_UPLOADED, {"files": []}
        )
        
        # Assert
        assert success is False
    
    def test_save_milestone_overwrites_existing(self, project_manager: ProjectManager, created_project: str):
        """Test that saving a milestone overwrites existing milestone of same type."""
        # Arrange
        milestone_type = MilestoneType.DRAFT_COMPLETED
        first_data = {"version": 1, "content": "First version"}
        second_data = {"version": 2, "content": "Second version"}
        
        # Act
        success1 = project_manager.save_milestone(created_project, milestone_type, first_data)
        success2 = project_manager.save_milestone(created_project, milestone_type, second_data)
        
        # Assert
        assert success1 is True
        assert success2 is True
        
        loaded = project_manager.load_milestone(created_project, milestone_type)
        assert loaded["data"] == second_data
    
    def test_load_milestone_success(self, project_manager: ProjectManager, project_with_milestones: str):
        """Test successfully loading a milestone."""
        # Act
        milestone = project_manager.load_milestone(project_with_milestones, MilestoneType.OUTLINE_GENERATED)
        
        # Assert
        assert milestone is not None
        assert milestone["type"] == MilestoneType.OUTLINE_GENERATED.value
        assert milestone["data"]["title"] == "Test Blog Post"
        assert len(milestone["data"]["sections"]) == 2
        assert "created_at" in milestone
    
    def test_load_milestone_not_found(self, project_manager: ProjectManager, created_project: str):
        """Test loading non-existent milestone returns None."""
        # Act
        milestone = project_manager.load_milestone(created_project, MilestoneType.SOCIAL_GENERATED)
        
        # Assert
        assert milestone is None
    
    def test_load_milestone_corrupted(self, project_manager: ProjectManager, created_project: str):
        """Test loading corrupted milestone file."""
        # Arrange
        milestone_type = MilestoneType.BLOG_REFINED
        project_manager.save_milestone(created_project, milestone_type, {"data": "test"})
        
        # Corrupt the file
        milestone_file = project_manager._get_project_path(created_project) / f"{milestone_type.value}.json"
        with open(milestone_file, "w") as f:
            f.write("{ corrupted")
        
        # Act
        result = project_manager.load_milestone(created_project, milestone_type)
        
        # Assert
        assert result is None
    
    def test_get_latest_milestone(self, project_manager: ProjectManager, project_with_milestones: str):
        """Test getting the latest milestone for a project."""
        # Act
        latest = project_manager.get_latest_milestone(project_with_milestones)
        
        # Assert
        assert latest is not None
        assert latest["type"] == MilestoneType.OUTLINE_GENERATED.value
        
        # Add another milestone and test again
        project_manager.save_milestone(
            project_with_milestones,
            MilestoneType.DRAFT_COMPLETED,
            {"content": "Final draft"}
        )
        
        latest = project_manager.get_latest_milestone(project_with_milestones)
        assert latest["type"] == MilestoneType.DRAFT_COMPLETED.value
    
    def test_get_latest_milestone_no_milestones(self, project_manager: ProjectManager, created_project: str):
        """Test getting latest milestone when none exist."""
        # Act
        latest = project_manager.get_latest_milestone(created_project)
        
        # Assert
        assert latest is None


class TestProjectLifecycle:
    """Test project lifecycle operations (archive, delete, etc.)."""
    
    def test_archive_project_success(self, project_manager: ProjectManager, created_project: str):
        """Test successfully archiving a project."""
        # Act
        success = project_manager.archive_project(created_project)
        
        # Assert
        assert success is True
        
        project_data = project_manager.get_project(created_project)
        assert project_data["status"] == ProjectStatus.ARCHIVED.value
        assert "archived_at" in project_data
        assert "updated_at" in project_data
    
    def test_archive_project_not_found(self, project_manager: ProjectManager):
        """Test archiving non-existent project."""
        # Act
        success = project_manager.archive_project(str(uuid.uuid4()))
        
        # Assert
        assert success is False
    
    def test_delete_project_soft(self, project_manager: ProjectManager, created_project: str):
        """Test soft-deleting a project."""
        # Arrange
        project_path = project_manager._get_project_path(created_project)
        assert project_path.exists()
        
        # Act
        success = project_manager.delete_project(created_project, permanent=False)
        
        # Assert
        assert success is True
        
        # Directory should still exist
        assert project_path.exists()
        
        # Status should be updated
        project_data = project_manager.get_project(created_project)
        assert project_data["status"] == ProjectStatus.DELETED.value
        assert "updated_at" in project_data
    
    def test_delete_project_permanent(self, project_manager: ProjectManager, created_project: str):
        """Test permanently deleting a project."""
        # Arrange
        project_path = project_manager._get_project_path(created_project)
        assert project_path.exists()
        
        # Act
        success = project_manager.delete_project(created_project, permanent=True)
        
        # Assert
        assert success is True
        assert not project_path.exists()
    
    def test_delete_project_not_found_permanent(self, project_manager: ProjectManager):
        """Test permanently deleting non-existent project."""
        # Act
        success = project_manager.delete_project(str(uuid.uuid4()), permanent=True)
        
        # Assert
        assert success is True  # Should return True even if nothing to delete
    
    def test_delete_project_not_found_soft(self, project_manager: ProjectManager):
        """Test soft deleting non-existent project."""
        # Act
        success = project_manager.delete_project(str(uuid.uuid4()), permanent=False)
        
        # Assert
        assert success is False


class TestProjectExport:
    """Test project export functionality in different formats."""
    
    def test_export_project_json(self, project_manager: ProjectManager, project_with_milestones: str):
        """Test exporting project as JSON."""
        # Act
        export_data = project_manager.export_project(project_with_milestones, format="json")
        
        # Assert
        assert export_data is not None
        assert isinstance(export_data, dict)
        assert "project" in export_data
        assert "milestones" in export_data
        
        assert export_data["project"]["id"] == project_with_milestones
        assert export_data["project"]["name"] == "Test Project"
        
        assert MilestoneType.FILES_UPLOADED.value in export_data["milestones"]
        assert MilestoneType.OUTLINE_GENERATED.value in export_data["milestones"]
    
    def test_export_project_markdown_with_content(self, project_manager: ProjectManager, created_project: str):
        """Test exporting project as Markdown with refined content."""
        # Arrange
        project_manager.save_milestone(
            created_project,
            MilestoneType.BLOG_REFINED,
            {"refined_content": "# My Blog Post\\n\\nThis is the refined content with **formatting**."}
        )
        
        # Act
        export_data = project_manager.export_project(created_project, format="markdown")
        
        # Assert
        assert export_data is not None
        assert isinstance(export_data, str)
        assert f"Project ID**: {created_project}" in export_data
        assert "# My Blog Post" in export_data
        assert "This is the refined content" in export_data
    
    def test_export_project_markdown_with_draft_fallback(self, project_manager: ProjectManager, created_project: str):
        """Test Markdown export falls back to draft if no refined content."""
        # Arrange
        project_manager.save_milestone(
            created_project,
            MilestoneType.DRAFT_COMPLETED,
            {"compiled_blog": "# Draft Blog\\n\\nThis is the draft content."}
        )
        
        # Act
        export_data = project_manager.export_project(created_project, format="markdown")
        
        # Assert
        assert "# Draft Blog" in export_data
        assert "This is the draft content" in export_data
    
    def test_export_project_zip(self, project_manager: ProjectManager, project_with_milestones: str):
        """Test exporting project as ZIP archive."""
        # Act
        export_data = project_manager.export_project(project_with_milestones, format="zip")
        
        # Assert
        assert export_data is not None
        assert isinstance(export_data, bytes)
        
        # Verify it's a valid ZIP file
        zip_buffer = BytesIO(export_data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            file_list = zf.namelist()
            assert "project.json" in file_list
            assert f"{MilestoneType.FILES_UPLOADED.value}.json" in file_list
            assert f"{MilestoneType.OUTLINE_GENERATED.value}.json" in file_list
            
            # Test reading project.json from ZIP
            project_json = zf.read("project.json")
            project_data = json.loads(project_json)
            assert project_data["id"] == project_with_milestones
    
    def test_export_project_unsupported_format(self, project_manager: ProjectManager, created_project: str):
        """Test exporting with unsupported format returns None."""
        # Act
        result = project_manager.export_project(created_project, format="xml")
        
        # Assert
        assert result is None
    
    def test_export_project_not_found(self, project_manager: ProjectManager):
        """Test exporting non-existent project."""
        # Act
        result = project_manager.export_project(str(uuid.uuid4()), format="json")
        
        # Assert
        assert result is None


class TestProjectResume:
    """Test project resumption functionality."""
    
    def test_resume_project_no_milestones(self, project_manager: ProjectManager, created_project: str):
        """Test resuming a project with no milestones."""
        # Act
        resume_data = project_manager.resume_project(created_project)
        
        # Assert
        assert resume_data is not None
        assert resume_data["project"]["id"] == created_project
        assert resume_data["latest_milestone"] is None
        assert resume_data["next_step"] == "upload_files"
    
    def test_resume_project_with_files_uploaded(self, project_manager: ProjectManager, created_project: str):
        """Test resuming after files uploaded."""
        # Arrange
        project_manager.save_milestone(
            created_project,
            MilestoneType.FILES_UPLOADED,
            {"files": ["test.py"], "file_count": 1}
        )
        
        # Act
        resume_data = project_manager.resume_project(created_project)
        
        # Assert
        assert resume_data["next_step"] == "generate_outline"
        assert resume_data["latest_milestone"]["type"] == MilestoneType.FILES_UPLOADED.value
    
    def test_resume_project_workflow_progression(self, project_manager: ProjectManager, created_project: str):
        """Test resume determines correct next step based on current milestone."""
        milestone_progression = [
            (MilestoneType.FILES_UPLOADED, "generate_outline"),
            (MilestoneType.OUTLINE_GENERATED, "generate_draft"),
            (MilestoneType.DRAFT_COMPLETED, "refine_blog"),
            (MilestoneType.BLOG_REFINED, "generate_social"),
            (MilestoneType.SOCIAL_GENERATED, "completed")
        ]
        
        for milestone_type, expected_next_step in milestone_progression:
            # Arrange
            project_manager.save_milestone(
                created_project,
                milestone_type,
                {"data": f"test data for {milestone_type.value}"}
            )
            
            # Act
            resume_data = project_manager.resume_project(created_project)
            
            # Assert
            assert resume_data["next_step"] == expected_next_step
    
    def test_resume_project_not_found(self, project_manager: ProjectManager):
        """Test resuming non-existent project."""
        # Act
        resume_data = project_manager.resume_project(str(uuid.uuid4()))
        
        # Assert
        assert resume_data is None


class TestMetadataManagement:
    """Test project metadata operations."""
    
    def test_update_metadata_success(self, project_manager: ProjectManager, created_project: str):
        """Test successfully updating project metadata."""
        # Arrange
        initial_data = project_manager.get_project(created_project)
        initial_updated_at = initial_data["updated_at"]
        
        new_metadata = {"new_field": "new_value", "model_name": "updated_model"}
        
        # Act
        success = project_manager.update_metadata(created_project, new_metadata)
        
        # Assert
        assert success is True
        
        updated_data = project_manager.get_project(created_project)
        expected_metadata = {**initial_data["metadata"], **new_metadata}
        assert updated_data["metadata"] == expected_metadata
        assert updated_data["updated_at"] > initial_updated_at
    
    def test_update_metadata_not_found(self, project_manager: ProjectManager):
        """Test updating metadata for non-existent project."""
        # Act
        success = project_manager.update_metadata(str(uuid.uuid4()), {"test": "data"})
        
        # Assert
        assert success is False
    
    def test_update_metadata_empty(self, project_manager: ProjectManager, created_project: str):
        """Test updating with empty metadata."""
        # Act
        success = project_manager.update_metadata(created_project, {})
        
        # Assert
        assert success is True
        
        # Should still update the updated_at timestamp
        updated_data = project_manager.get_project(created_project)
        assert "updated_at" in updated_data


class TestAtomicOperations:
    """Test atomic write operations and error handling."""
    
    def test_atomic_write_success(self, project_manager: ProjectManager, tmp_path: Path):
        """Test successful atomic write operation."""
        # Arrange
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        
        # Act
        project_manager._atomic_write(test_file, test_data)
        
        # Assert
        assert test_file.exists()
        with open(test_file, 'r') as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data
    
    def test_atomic_write_failure_cleanup(self, project_manager: ProjectManager, tmp_path: Path):
        """Test atomic write cleans up temporary files on failure."""
        # Arrange
        test_file = tmp_path / "fail.json"
        test_data = {"key": "value"}
        
        # Mock json.dump to fail
        with patch('json.dump', side_effect=IOError("Disk full")):
            # Act & Assert
            with pytest.raises(IOError):
                project_manager._atomic_write(test_file, test_data)
        
        # Assert cleanup
        assert not test_file.exists()
        temp_files = list(tmp_path.glob(".tmp_*"))
        assert len(temp_files) == 0
    
    def test_atomic_write_preserves_existing_on_failure(self, project_manager: ProjectManager, tmp_path: Path):
        """Test that atomic write preserves existing file content on failure."""
        # Arrange
        test_file = tmp_path / "preserve.json"
        original_data = {"original": "data"}
        new_data = {"new": "data"}
        
        # Create original file
        with open(test_file, 'w') as f:
            json.dump(original_data, f)
        
        # Mock failure during atomic write
        with patch('json.dump', side_effect=IOError("Write failed")):
            # Act & Assert
            with pytest.raises(IOError):
                project_manager._atomic_write(test_file, new_data)
        
        # Assert original file is preserved
        assert test_file.exists()
        with open(test_file, 'r') as f:
            preserved_data = json.load(f)
        assert preserved_data == original_data


class TestConcurrencyAndRaceConditions:
    """Test concurrent access and race condition handling."""
    
    def test_concurrent_project_creation(self, project_manager: ProjectManager):
        """Test that concurrent project creation produces unique IDs."""
        # Arrange
        project_ids = []
        errors = []
        
        def create_project_worker(worker_id):
            try:
                project_id = project_manager.create_project(f"Project {worker_id}")
                project_ids.append(project_id)
            except Exception as e:
                errors.append(e)
        
        # Act
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_project_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Assert
        assert len(errors) == 0
        assert len(project_ids) == 10
        assert len(set(project_ids)) == 10  # All IDs unique
    
    def test_concurrent_milestone_saves(self, project_manager: ProjectManager, created_project: str):
        """Test concurrent milestone saves for the same project."""
        # This test demonstrates the potential race condition but doesn't fail
        # In a real implementation, you might want file locking
        
        # Arrange
        results = []
        
        def save_milestone_worker(milestone_num):
            try:
                success = project_manager.save_milestone(
                    created_project,
                    MilestoneType.DRAFT_COMPLETED,
                    {"version": milestone_num, "content": f"Content {milestone_num}"}
                )
                results.append(success)
            except Exception as e:
                results.append(e)
        
        # Act
        threads = []
        for i in range(5):
            thread = threading.Thread(target=save_milestone_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Assert - at least the operations completed without exceptions
        assert len(results) == 5
        assert all(result is True for result in results)
        
        # The final milestone should have data from one of the workers
        final_milestone = project_manager.load_milestone(created_project, MilestoneType.DRAFT_COMPLETED)
        assert final_milestone is not None
        assert "version" in final_milestone["data"]


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling scenarios."""
    
    def test_path_traversal_prevention(self, project_manager: ProjectManager):
        """Test that path traversal attempts are prevented."""
        # Arrange
        malicious_ids = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "project/../../../sensitive"
        ]
        
        for malicious_id in malicious_ids:
            # Act
            project_path = project_manager._get_project_path(malicious_id)
            
            # Assert - path should be contained within base directory
            resolved_base = project_manager.base_dir.resolve()
            resolved_path = project_path.resolve()
            
            # The resolved path should start with the base directory
            assert str(resolved_path).startswith(str(resolved_base))
            
            # Should not contain sensitive path components
            path_str = str(resolved_path).lower()
            assert "etc" not in path_str or "passwd" not in path_str
            assert "system32" not in path_str
    
    def test_very_long_project_name(self, project_manager: ProjectManager):
        """Test handling very long project names."""
        # Arrange
        very_long_name = "A" * 1000  # 1000 character name
        
        # Act
        project_id = project_manager.create_project(very_long_name)
        
        # Assert
        project_data = project_manager.get_project(project_id)
        assert project_data["name"] == very_long_name
    
    def test_special_characters_in_project_name(self, project_manager: ProjectManager):
        """Test handling special characters in project names."""
        # Arrange
        special_names = [
            "Project with émojis 🚀",
            "Project/with\\slashes",
            "Project<>with|symbols",
            "Project\"with'quotes",
            "Project\nwith\nnewlines",
            "Project\twith\ttabs"
        ]
        
        for name in special_names:
            # Act
            project_id = project_manager.create_project(name)
            
            # Assert
            project_data = project_manager.get_project(project_id)
            assert project_data["name"] == name
    
    def test_invalid_milestone_type_handling(self, project_manager: ProjectManager, created_project: str):
        """Test handling invalid milestone types gracefully."""
        # This is mainly a type safety test - if using enums properly,
        # this shouldn't be possible, but good to verify
        with pytest.raises((ValueError, AttributeError)):
            # Try to access non-existent enum value
            invalid_milestone = MilestoneType("invalid_milestone_type")
    
    def test_disk_space_simulation(self, project_manager: ProjectManager, created_project: str):
        """Test behavior when disk space is exhausted."""
        # Mock the OS to simulate disk full error
        with patch('tempfile.mkstemp', side_effect=OSError("No space left on device")):
            # Act & Assert
            with pytest.raises(OSError):
                project_manager.save_milestone(
                    created_project,
                    MilestoneType.OUTLINE_GENERATED,
                    {"large_data": "x" * 10000}
                )
    
    def test_permission_errors(self, project_manager: ProjectManager, temp_project_dir: Path):
        """Test handling of permission errors."""
        # Create a project normally
        project_id = project_manager.create_project("Permission Test")
        
        # Make the project directory read-only
        project_path = temp_project_dir / project_id
        project_path.chmod(0o444)  # Read-only
        
        try:
            # Act - try to save a milestone (should fail due to permissions)
            success = project_manager.save_milestone(
                project_id,
                MilestoneType.FILES_UPLOADED,
                {"files": ["test.txt"]}
            )
            
            # Assert
            assert success is False
        finally:
            # Cleanup - restore permissions
            project_path.chmod(0o755)
    
    def test_json_serialization_edge_cases(self, project_manager: ProjectManager, created_project: str):
        """Test JSON serialization of edge case data types."""
        # Arrange - data with datetime objects (should be handled by default=str)
        milestone_data = {
            "timestamp": datetime.now(),
            "none_value": None,
            "boolean": True,
            "nested": {
                "list": [1, 2, 3],
                "empty_list": [],
                "empty_dict": {}
            }
        }
        
        # Act
        success = project_manager.save_milestone(
            created_project,
            MilestoneType.OUTLINE_GENERATED,
            milestone_data
        )
        
        # Assert
        assert success is True
        
        loaded = project_manager.load_milestone(created_project, MilestoneType.OUTLINE_GENERATED)
        assert loaded is not None
        # datetime should be serialized as string
        assert isinstance(loaded["data"]["timestamp"], str)
        assert loaded["data"]["none_value"] is None
        assert loaded["data"]["boolean"] is True


# Integration test to verify the complete workflow
class TestProjectWorkflowIntegration:
    """Integration tests for complete project workflows."""
    
    def test_complete_project_lifecycle(self, project_manager: ProjectManager):
        """Test a complete project lifecycle from creation to export."""
        # Create project
        project_id = project_manager.create_project(
            "Integration Test Project",
            metadata={"model": "claude-3", "user": "test_user"}
        )
        
        # Add files uploaded milestone
        assert project_manager.save_milestone(
            project_id,
            MilestoneType.FILES_UPLOADED,
            {"files": ["notebook.ipynb", "data.csv"], "file_count": 2}
        )
        
        # Add outline milestone
        assert project_manager.save_milestone(
            project_id,
            MilestoneType.OUTLINE_GENERATED,
            {
                "title": "Complete Integration Test",
                "sections": [
                    {"title": "Introduction", "description": "Intro"},
                    {"title": "Methods", "description": "Methods"},
                    {"title": "Results", "description": "Results"},
                    {"title": "Conclusion", "description": "Conclusion"}
                ]
            }
        )
        
        # Add draft milestone
        assert project_manager.save_milestone(
            project_id,
            MilestoneType.DRAFT_COMPLETED,
            {"compiled_blog": "# Complete Integration Test\\n\\nThis is the complete blog content..."}
        )
        
        # Add refined blog milestone
        assert project_manager.save_milestone(
            project_id,
            MilestoneType.BLOG_REFINED,
            {"refined_content": "# Complete Integration Test (Refined)\\n\\nThis is the refined content..."}
        )
        
        # Add social media milestone
        assert project_manager.save_milestone(
            project_id,
            MilestoneType.SOCIAL_GENERATED,
            {
                "linkedin": "LinkedIn post content",
                "twitter": "Twitter post content",
                "newsletter": "Newsletter content"
            }
        )
        
        # Test resume at final stage
        resume_data = project_manager.resume_project(project_id)
        assert resume_data["next_step"] == "completed"
        assert resume_data["project"]["current_milestone"] == MilestoneType.SOCIAL_GENERATED.value
        
        # Test export in all formats
        json_export = project_manager.export_project(project_id, "json")
        assert json_export is not None
        assert len(json_export["milestones"]) == 5
        
        markdown_export = project_manager.export_project(project_id, "markdown")
        assert "Complete Integration Test (Refined)" in markdown_export
        
        zip_export = project_manager.export_project(project_id, "zip")
        assert isinstance(zip_export, bytes)
        
        # Archive the project
        assert project_manager.archive_project(project_id) is True
        
        # Verify archived status
        project_data = project_manager.get_project(project_id)
        assert project_data["status"] == ProjectStatus.ARCHIVED.value
        
        # Test listing shows archived project
        archived_projects = project_manager.list_projects(ProjectStatus.ARCHIVED)
        assert len(archived_projects) == 1
        assert archived_projects[0]["id"] == project_id