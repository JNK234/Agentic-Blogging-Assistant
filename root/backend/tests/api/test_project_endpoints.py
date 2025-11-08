# ABOUTME: Comprehensive integration tests for FastAPI project management endpoints
# ABOUTME: Tests all project API endpoints with proper HTTP status codes and JSON responses

import pytest
import json
import uuid
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch, MagicMock

import sys
sys.path.append('/Users/jnk789/Developer/Agentic Blogging Assistant/Agentic-Blogging-Assistant')

from fastapi.testclient import TestClient
from fastapi import FastAPI

from root.backend.main import app, project_manager
from root.backend.services.project_manager import ProjectManager, ProjectStatus, MilestoneType


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    return TestClient(app)


@pytest.fixture
def temp_project_manager(tmp_path):
    """Create a temporary project manager for testing."""
    temp_pm = ProjectManager(base_dir=str(tmp_path / "test_projects"))
    return temp_pm


@pytest.fixture(autouse=True)
def mock_project_manager(temp_project_manager):
    """Replace the global project_manager with a temporary one."""
    with patch('root.backend.main.project_manager', temp_project_manager):
        yield temp_project_manager


@pytest.fixture
def sample_project_data(temp_project_manager):
    """Create a sample project for testing."""
    project_id = temp_project_manager.create_project(
        "Test Project",
        metadata={"model_name": "claude-sonnet-4", "persona": "expert"}
    )
    return {
        "id": project_id,
        "name": "Test Project",
        "metadata": {"model_name": "claude-sonnet-4", "persona": "expert"}
    }


@pytest.fixture
def project_with_milestones(temp_project_manager):
    """Create a project with multiple milestones."""
    project_id = temp_project_manager.create_project("Milestone Project")
    
    # Add milestones
    temp_project_manager.save_milestone(
        project_id,
        MilestoneType.FILES_UPLOADED,
        {"files": ["test.py"], "file_count": 1}
    )
    
    temp_project_manager.save_milestone(
        project_id,
        MilestoneType.OUTLINE_GENERATED,
        {"title": "Test Outline", "sections": [{"title": "Section 1"}]}
    )
    
    temp_project_manager.save_milestone(
        project_id,
        MilestoneType.DRAFT_COMPLETED,
        {"compiled_blog": "# Test Blog\\n\\nContent here..."}
    )
    
    temp_project_manager.save_milestone(
        project_id,
        MilestoneType.BLOG_REFINED,
        {"refined_content": "# Test Blog (Refined)\\n\\nRefined content..."}
    )
    
    return project_id


class TestProjectListingEndpoint:
    """Test the GET /projects endpoint."""
    
    def test_list_projects_empty(self, client):
        """Test listing projects when none exist."""
        response = client.get("/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 0
        assert data["projects"] == []
    
    def test_list_projects_with_data(self, client, sample_project_data):
        """Test listing projects with existing projects."""
        response = client.get("/projects")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["count"] == 1
        assert len(data["projects"]) == 1
        assert data["projects"][0]["id"] == sample_project_data["id"]
        assert data["projects"][0]["name"] == sample_project_data["name"]
    
    def test_list_projects_with_status_filter(self, client, temp_project_manager):
        """Test listing projects with status filter."""
        # Create projects with different statuses
        active_id = temp_project_manager.create_project("Active Project")
        archived_id = temp_project_manager.create_project("Archived Project")
        
        temp_project_manager.archive_project(archived_id)
        
        # Test filter for active projects
        response = client.get("/projects?status=active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["projects"][0]["id"] == active_id
        assert data["projects"][0]["status"] == "active"
        
        # Test filter for archived projects
        response = client.get("/projects?status=archived")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["projects"][0]["id"] == archived_id
        assert data["projects"][0]["status"] == "archived"
    
    def test_list_projects_invalid_status(self, client):
        """Test listing projects with invalid status filter."""
        response = client.get("/projects?status=invalid_status")
        
        assert response.status_code == 400
        data = response.json()
        assert "Invalid status" in data["error"]


class TestProjectDetailsEndpoint:
    """Test the GET /project/{project_id} endpoint."""
    
    def test_get_project_success(self, client, sample_project_data):
        """Test getting project details successfully."""
        response = client.get(f"/project/{sample_project_data['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["project"]["id"] == sample_project_data["id"]
        assert data["project"]["name"] == sample_project_data["name"]
        assert "milestones" in data
    
    def test_get_project_with_milestones(self, client, project_with_milestones):
        """Test getting project details with milestones."""
        response = client.get(f"/project/{project_with_milestones}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        milestones = data["milestones"]
        assert MilestoneType.FILES_UPLOADED.value in milestones
        assert MilestoneType.OUTLINE_GENERATED.value in milestones
        assert MilestoneType.DRAFT_COMPLETED.value in milestones
        assert MilestoneType.BLOG_REFINED.value in milestones
        
        # Check milestone metadata structure
        files_milestone = milestones[MilestoneType.FILES_UPLOADED.value]
        assert "created_at" in files_milestone
        assert "metadata" in files_milestone
    
    def test_get_project_not_found(self, client):
        """Test getting non-existent project."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/project/{fake_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert f"Project {fake_id} not found" in data["error"]
    
    def test_get_project_invalid_uuid(self, client):
        """Test getting project with invalid UUID format."""
        response = client.get("/project/invalid-uuid")
        
        # FastAPI should handle this at the path parameter level
        assert response.status_code in [404, 422]  # Depends on FastAPI validation


class TestProjectResumeEndpoint:
    """Test the POST /project/{project_id}/resume endpoint."""
    
    def test_resume_project_no_milestones(self, client, sample_project_data):
        """Test resuming project with no milestones."""
        response = client.post(f"/project/{sample_project_data['id']}/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        assert data["project_id"] == sample_project_data["id"]
        assert data["project_name"] == sample_project_data["name"]
        assert data["next_step"] == "upload_files"
        assert data["has_outline"] is False
        assert data["has_draft"] is False
        assert data["has_refined"] is False
    
    def test_resume_project_with_milestones(self, client, project_with_milestones):
        """Test resuming project with existing milestones."""
        response = client.post(f"/project/{project_with_milestones}/resume")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "job_id" in data
        assert data["next_step"] == "generate_social"  # Should be next step after blog refined
        assert data["has_outline"] is True
        assert data["has_draft"] is True
        assert data["has_refined"] is True
        
        # Verify job state is created in cache
        job_id = data["job_id"]
        assert job_id in state_cache
        
        job_state = state_cache[job_id]
        assert job_state["project_id"] == project_with_milestones
        assert "outline" in job_state
        assert "final_draft" in job_state
        assert "refined_draft" in job_state
    
    def test_resume_project_not_found(self, client):
        """Test resuming non-existent project."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/project/{fake_id}/resume")
        
        assert response.status_code == 404
        data = response.json()
        assert f"Project {fake_id} not found" in data["error"]


class TestProjectDeletionEndpoints:
    """Test project deletion endpoints."""
    
    def test_delete_project_permanent(self, client, sample_project_data, temp_project_manager):
        """Test permanently deleting a project."""
        project_id = sample_project_data["id"]
        project_path = temp_project_manager._get_project_path(project_id)
        assert project_path.exists()
        
        response = client.delete(f"/project/{project_id}/permanent")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert f"Project {project_id} permanently deleted" in data["message"]
        
        # Verify project is actually deleted
        assert not project_path.exists()
    
    def test_delete_project_permanent_not_found(self, client):
        """Test permanently deleting non-existent project."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/project/{fake_id}/permanent")
        
        assert response.status_code == 200  # Should succeed even if not found
        data = response.json()
        assert data["status"] == "success"


class TestProjectArchiveEndpoint:
    """Test the POST /project/{project_id}/archive endpoint."""
    
    def test_archive_project_success(self, client, sample_project_data, temp_project_manager):
        """Test successfully archiving a project."""
        project_id = sample_project_data["id"]
        
        response = client.post(f"/project/{project_id}/archive")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert f"Project {project_id} archived" in data["message"]
        
        # Verify project status changed
        project_data = temp_project_manager.get_project(project_id)
        assert project_data["status"] == ProjectStatus.ARCHIVED.value
    
    def test_archive_project_not_found(self, client):
        """Test archiving non-existent project."""
        fake_id = str(uuid.uuid4())
        response = client.post(f"/project/{fake_id}/archive")
        
        assert response.status_code == 404
        data = response.json()
        assert f"Failed to archive project {fake_id}" in data["error"]


class TestProjectExportEndpoint:
    """Test the GET /project/{project_id}/export endpoint."""
    
    def test_export_project_json(self, client, project_with_milestones):
        """Test exporting project as JSON."""
        response = client.get(f"/project/{project_with_milestones}/export?format=json")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "project" in data
        assert "milestones" in data
        assert data["project"]["id"] == project_with_milestones
        
        # Verify milestones are included
        milestones = data["milestones"]
        expected_milestones = [
            MilestoneType.FILES_UPLOADED.value,
            MilestoneType.OUTLINE_GENERATED.value,
            MilestoneType.DRAFT_COMPLETED.value,
            MilestoneType.BLOG_REFINED.value
        ]
        
        for milestone_type in expected_milestones:
            assert milestone_type in milestones
    
    def test_export_project_markdown(self, client, project_with_milestones):
        """Test exporting project as Markdown."""
        response = client.get(f"/project/{project_with_milestones}/export?format=markdown")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/markdown; charset=utf-8"
        
        content = response.content.decode()
        assert f"Project ID**: {project_with_milestones}" in content
        assert "# Test Blog (Refined)" in content  # Should use refined content
        assert "Refined content..." in content
    
    def test_export_project_zip(self, client, project_with_milestones):
        """Test exporting project as ZIP."""
        response = client.get(f"/project/{project_with_milestones}/export?format=zip")
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        
        # Verify it's a valid ZIP file
        zip_content = BytesIO(response.content)
        with zipfile.ZipFile(zip_content, 'r') as zf:
            file_list = zf.namelist()
            assert "project.json" in file_list
            assert f"{MilestoneType.FILES_UPLOADED.value}.json" in file_list
            assert f"{MilestoneType.OUTLINE_GENERATED.value}.json" in file_list
    
    def test_export_project_unsupported_format(self, client, sample_project_data):
        """Test exporting with unsupported format."""
        response = client.get(f"/project/{sample_project_data['id']}/export?format=xml")
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported export format: xml" in data["error"]
    
    def test_export_project_not_found(self, client):
        """Test exporting non-existent project."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/project/{fake_id}/export")
        
        assert response.status_code == 404
        data = response.json()
        assert f"Project {fake_id} not found" in data["error"]
    
    def test_export_project_default_format(self, client, sample_project_data):
        """Test exporting project with default format (should be JSON)."""
        response = client.get(f"/project/{sample_project_data['id']}/export")
        
        assert response.status_code == 200
        data = response.json()
        assert "project" in data
        assert data["project"]["id"] == sample_project_data["id"]


class TestProjectUploadEndpoint:
    """Test the POST /upload/{project_name} endpoint."""
    
    def test_upload_files_success(self, client, temp_project_manager):
        """Test successful file upload and project creation."""
        # Create test files
        test_files = [
            ("files", ("test.py", b"print('hello world')", "text/plain")),
            ("files", ("data.md", b"# Test Markdown\\n\\nContent here", "text/markdown"))
        ]
        
        project_name = "Upload Test Project"
        data = {
            "model_name": "claude-sonnet-4",
            "persona": "expert"
        }
        
        response = client.post(f"/upload/{project_name}", files=test_files, data=data)
        
        assert response.status_code == 200
        response_data = response.json()
        
        assert response_data["message"] == "Files uploaded successfully"
        assert response_data["project"] == project_name
        assert "project_id" in response_data
        assert len(response_data["files"]) == 2
        
        # Verify project was created in ProjectManager
        project_id = response_data["project_id"]
        project_data = temp_project_manager.get_project(project_id)
        assert project_data is not None
        assert project_data["name"] == project_name
        assert project_data["metadata"]["model_name"] == "claude-sonnet-4"
        assert project_data["metadata"]["persona"] == "expert"
        
        # Verify FILES_UPLOADED milestone was created
        files_milestone = temp_project_manager.load_milestone(project_id, MilestoneType.FILES_UPLOADED)
        assert files_milestone is not None
        assert files_milestone["data"]["file_count"] == 2
    
    def test_upload_files_unsupported_extension(self, client):
        """Test uploading files with unsupported extensions."""
        test_files = [
            ("files", ("test.txt", b"plain text content", "text/plain")),  # .txt not supported
        ]
        
        response = client.post("/upload/Test Project", files=test_files)
        
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported file type: .txt" in data["error"]
    
    def test_upload_no_files(self, client):
        """Test uploading without any files."""
        response = client.post("/upload/Empty Project", files=[])
        
        assert response.status_code == 400
        data = response.json()
        assert "No valid files were uploaded" in data["error"]
    
    def test_upload_files_with_special_characters_in_project_name(self, client):
        """Test uploading files with special characters in project name."""
        test_files = [
            ("files", ("test.py", b"print('test')", "text/plain"))
        ]
        
        project_name = "Project/with<special>characters"
        response = client.post(f"/upload/{project_name}", files=test_files)
        
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["project"] == project_name
    
    @patch('root.backend.main.project_manager.create_project')
    def test_upload_files_project_creation_failure(self, mock_create, client):
        """Test handling of project creation failure during upload."""
        mock_create.side_effect = Exception("Database error")
        
        test_files = [
            ("files", ("test.py", b"print('test')", "text/plain"))
        ]
        
        response = client.post("/upload/Failed Project", files=test_files)
        
        assert response.status_code == 500
        data = response.json()
        assert "Upload failed" in data["error"]


class TestLegacyProjectDeletionEndpoint:
    """Test the DELETE /project/{project_name} endpoint (legacy)."""
    
    def test_delete_project_legacy_success(self, client, tmp_path):
        """Test legacy project deletion by name."""
        # Create a project directory manually (simulating old-style projects)
        project_name = "Legacy Test Project"
        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()
        project_dir = upload_dir / project_name
        project_dir.mkdir()
        
        # Create a test file
        test_file = project_dir / "test.py"
        test_file.write_text("print('hello')")
        
        with patch('root.backend.main.UPLOAD_DIRECTORY', str(upload_dir)):
            # Test deletion
            response = client.delete(f"/project/{project_name}")
            
            assert response.status_code == 200
            data = response.json()
            assert f"Project '{project_name}' deleted successfully" in data["message"]
            
            # Verify directory was deleted
            assert not project_dir.exists()
    
    def test_delete_project_legacy_not_found(self, client):
        """Test legacy deletion of non-existent project."""
        response = client.delete("/project/NonExistent Project")
        
        assert response.status_code == 404
        data = response.json()
        assert "Project 'NonExistent Project' not found" in data["error"]


class TestHealthEndpoint:
    """Test the health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint returns OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases across endpoints."""
    
    @patch('root.backend.main.project_manager.list_projects')
    def test_internal_server_error_handling(self, mock_list, client):
        """Test handling of internal server errors."""
        mock_list.side_effect = Exception("Database connection failed")
        
        response = client.get("/projects")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to list projects" in data["error"]
    
    def test_malformed_project_id_handling(self, client):
        """Test handling of malformed project IDs in various endpoints."""
        malformed_ids = ["", "not-a-uuid", "12345", "null", "undefined"]
        
        for bad_id in malformed_ids:
            # Test get project
            response = client.get(f"/project/{bad_id}")
            assert response.status_code in [404, 422]  # Depends on validation
            
            # Test resume project
            response = client.post(f"/project/{bad_id}/resume")
            assert response.status_code in [404, 422]
            
            # Test archive project
            response = client.post(f"/project/{bad_id}/archive")
            assert response.status_code in [404, 422]
    
    def test_concurrent_endpoint_access(self, client, sample_project_data):
        """Test concurrent access to the same project endpoints."""
        import threading
        import time
        
        project_id = sample_project_data["id"]
        responses = []
        
        def make_request():
            response = client.get(f"/project/{project_id}")
            responses.append(response.status_code)
        
        # Create multiple threads to access the same endpoint
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(responses) == 10
        assert all(status == 200 for status in responses)
    
    def test_large_project_name_handling(self, client):
        """Test handling of very large project names."""
        large_name = "A" * 1000  # 1000 character project name
        test_files = [
            ("files", ("test.py", b"print('test')", "text/plain"))
        ]
        
        response = client.post(f"/upload/{large_name}", files=test_files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["project"] == large_name
    
    def test_unicode_project_name_handling(self, client):
        """Test handling of Unicode characters in project names."""
        unicode_names = [
            "Project with émojis 🚀",
            "プロジェクト名",
            "مشروع تجريبي",
            "Проект тест"
        ]
        
        test_files = [
            ("files", ("test.py", b"print('test')", "text/plain"))
        ]
        
        for name in unicode_names:
            response = client.post(f"/upload/{name}", files=test_files)
            assert response.status_code == 200
            data = response.json()
            assert data["project"] == name


class TestProjectManagementWorkflowIntegration:
    """Integration tests for complete project management workflows."""
    
    def test_complete_project_management_workflow(self, client, temp_project_manager):
        """Test a complete workflow from upload to export."""
        # 1. Upload files and create project
        test_files = [
            ("files", ("analysis.py", b"import pandas as pd\\nprint('analysis')", "text/plain")),
            ("files", ("documentation.md", b"# Project Documentation\\n\\nThis is documentation.", "text/markdown"))
        ]
        
        project_name = "Complete Workflow Test"
        upload_response = client.post(
            f"/upload/{project_name}",
            files=test_files,
            data={"model_name": "claude-sonnet-4", "persona": "data_scientist"}
        )
        
        assert upload_response.status_code == 200
        project_id = upload_response.json()["project_id"]
        
        # 2. Add additional milestones directly via ProjectManager
        temp_project_manager.save_milestone(
            project_id,
            MilestoneType.OUTLINE_GENERATED,
            {"title": "Data Analysis Tutorial", "sections": [{"title": "Introduction"}]}
        )
        
        temp_project_manager.save_milestone(
            project_id,
            MilestoneType.DRAFT_COMPLETED,
            {"compiled_blog": "# Data Analysis Tutorial\\n\\nThis is the complete tutorial..."}
        )
        
        temp_project_manager.save_milestone(
            project_id,
            MilestoneType.BLOG_REFINED,
            {"refined_content": "# Data Analysis Tutorial (Refined)\\n\\nRefined tutorial content..."}
        )
        
        # 3. Get project details
        details_response = client.get(f"/project/{project_id}")
        assert details_response.status_code == 200
        details_data = details_response.json()
        assert len(details_data["milestones"]) == 4  # Files + outline + draft + refined
        
        # 4. Resume project
        resume_response = client.post(f"/project/{project_id}/resume")
        assert resume_response.status_code == 200
        resume_data = resume_response.json()
        assert resume_data["next_step"] == "generate_social"
        assert resume_data["has_outline"] is True
        assert resume_data["has_refined"] is True
        
        # 5. List projects (should include our project)
        list_response = client.get("/projects")
        assert list_response.status_code == 200
        list_data = list_response.json()
        assert list_data["count"] == 1
        assert list_data["projects"][0]["id"] == project_id
        
        # 6. Export project in different formats
        # JSON export
        json_export_response = client.get(f"/project/{project_id}/export?format=json")
        assert json_export_response.status_code == 200
        json_data = json_export_response.json()
        assert json_data["project"]["id"] == project_id
        assert len(json_data["milestones"]) == 4
        
        # Markdown export
        md_export_response = client.get(f"/project/{project_id}/export?format=markdown")
        assert md_export_response.status_code == 200
        assert "Data Analysis Tutorial (Refined)" in md_export_response.content.decode()
        
        # ZIP export
        zip_export_response = client.get(f"/project/{project_id}/export?format=zip")
        assert zip_export_response.status_code == 200
        assert zip_export_response.headers["content-type"] == "application/zip"
        
        # 7. Archive project
        archive_response = client.post(f"/project/{project_id}/archive")
        assert archive_response.status_code == 200
        
        # 8. Verify archived status
        details_after_archive = client.get(f"/project/{project_id}")
        assert details_after_archive.status_code == 200
        assert details_after_archive.json()["project"]["status"] == "archived"
        
        # 9. List archived projects
        archived_list_response = client.get("/projects?status=archived")
        assert archived_list_response.status_code == 200
        archived_data = archived_list_response.json()
        assert archived_data["count"] == 1
        assert archived_data["projects"][0]["id"] == project_id
        
        # 10. Permanently delete project
        delete_response = client.delete(f"/project/{project_id}/permanent")
        assert delete_response.status_code == 200
        
        # 11. Verify project is gone
        final_details_response = client.get(f"/project/{project_id}")
        assert final_details_response.status_code == 404


class TestStateManagementIntegration:
    """Test integration between project management and state cache."""
    
    def test_resume_creates_proper_state_cache(self, client, project_with_milestones):
        """Test that resume endpoint creates proper state cache entries."""
        # Clear any existing state
        state_cache.clear()
        
        # Resume project
        response = client.post(f"/project/{project_with_milestones}/resume")
        assert response.status_code == 200
        
        data = response.json()
        job_id = data["job_id"]
        
        # Verify state cache entry
        assert job_id in state_cache
        job_state = state_cache[job_id]
        
        # Check required fields
        assert job_state["project_id"] == project_with_milestones
        assert "outline" in job_state
        assert "final_draft" in job_state
        assert "refined_draft" in job_state
        assert "model_name" in job_state
        
        # Verify outline structure
        outline = job_state["outline"]
        assert outline["title"] == "Test Outline"
        assert len(outline["sections"]) == 1
        
        # Verify content
        assert "# Test Blog\\n\\nContent here..." in job_state["final_draft"]
        assert "# Test Blog (Refined)\\n\\nRefined content..." in job_state["refined_draft"]