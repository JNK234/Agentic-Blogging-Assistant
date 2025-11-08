# ABOUTME: Unified API client wrapper for blog generation and project management
# ABOUTME: Combines legacy API calls with modern project management endpoints

import httpx
import logging
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.append(str(Path(__file__).parent.parent))

# Import existing API client and ProjectService
from api_client import (
    upload_files, process_files, generate_outline, generate_section,
    regenerate_section_with_feedback, compile_draft, refine_blog,
    refine_standalone, generate_social_content, generate_social_content_standalone,
    health_check, get_job_status, get_personas, get_models
)
from services.project_service import ProjectService

logger = logging.getLogger(__name__)


class BlogAPIClient:
    """
    Unified API client for Agentic Blogging Assistant.

    Combines:
    - Legacy blog generation API calls
    - Modern project management endpoints

    This class provides a single interface for all frontend-backend interactions.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """
        Initialize the blog API client.

        Args:
            base_url: Base URL of the FastAPI backend
        """
        self.base_url = base_url
        self.project_service = ProjectService(base_url=base_url)
        logger.info(f"BlogAPIClient initialized with base_url: {base_url}")

    # ==================== Project Management Methods ====================

    async def create_project(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new project.

        Note: Projects are created automatically on file upload.
        This method uploads files to create a project.

        Args:
            name: Project name
            metadata: Optional metadata (model_name, persona, etc.)

        Returns:
            Project creation response with project_id
        """
        # Create empty project by uploading a minimal file
        # This is a workaround since there's no explicit create_project endpoint
        logger.warning("create_project: Projects are auto-created on file upload. "
                      "Use upload_files_and_create_project instead.")
        return {
            "status": "info",
            "message": "Use upload_files method to create project",
            "project_name": name,
            "metadata": metadata or {}
        }

    async def get_all_projects(self, status: str = "active") -> List[Dict[str, Any]]:
        """
        Get all projects with optional status filter.

        Args:
            status: Filter by status ('active', 'archived', 'all')

        Returns:
            List of project dictionaries
        """
        try:
            # Use the /projects endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                params = {}
                if status != "all":
                    params["status"] = status

                response = await client.get(f"{self.base_url}/projects", params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("projects", [])

        except Exception as e:
            logger.error(f"Failed to get all projects: {e}")
            raise

    async def get_project_details(self, project_id: str) -> Dict[str, Any]:
        """
        Get detailed project information.

        Args:
            project_id: Project identifier (UUID)

        Returns:
            Project details including milestones
        """
        return await self.project_service.get_project(project_id)

    async def get_project_progress(self, project_id: str) -> Dict[str, Any]:
        """
        Get project progress metrics.

        Args:
            project_id: Project identifier (UUID)

        Returns:
            Progress data with percentages and milestones
        """
        try:
            # Get project details which includes milestone information
            project_data = await self.get_project_details(project_id)
            milestones = project_data.get("milestones", {})

            # Calculate progress based on milestones
            milestone_types = [
                "files_uploaded",
                "outline_generated",
                "draft_completed",
                "blog_refined",
                "social_generated"
            ]

            completed_milestones = sum(1 for m in milestone_types if m in milestones)
            total_milestones = len(milestone_types)
            progress_percentage = (completed_milestones / total_milestones) * 100 if total_milestones > 0 else 0

            # Calculate cost if available
            total_cost = 0.0
            for milestone_data in milestones.values():
                if isinstance(milestone_data, dict) and "metadata" in milestone_data:
                    metadata = milestone_data["metadata"]
                    if "cost" in metadata:
                        total_cost += float(metadata.get("cost", 0))

            return {
                "project_id": project_id,
                "project_name": project_data.get("project", {}).get("name", ""),
                "progress_percentage": round(progress_percentage, 1),
                "milestones": {m: (m in milestones) for m in milestone_types},
                "completed_count": completed_milestones,
                "total_count": total_milestones,
                "total_cost": total_cost,
                "status": project_data.get("project", {}).get("status", "active")
            }

        except Exception as e:
            logger.error(f"Failed to get project progress for {project_id}: {e}")
            raise

    async def resume_project(self, project_id: str) -> Dict[str, Any]:
        """
        Resume a project and get its current state.

        Args:
            project_id: Project identifier (UUID)

        Returns:
            Project resume data with project_id and next_step
        """
        return await self.project_service.resume_project(project_id)

    async def archive_project(self, project_id: str) -> Dict[str, Any]:
        """
        Archive a project.

        Args:
            project_id: Project identifier (UUID)

        Returns:
            Archive operation confirmation
        """
        return await self.project_service.archive_project(project_id, archive=True)

    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Permanently delete a project.

        Args:
            project_id: Project identifier (UUID)

        Returns:
            Deletion confirmation
        """
        return await self.project_service.delete_project(project_id)

    async def export_project(self, project_id: str, format_type: str = "markdown") -> bytes:
        """
        Export project in specified format.

        Args:
            project_id: Project identifier (UUID)
            format_type: Export format ('markdown', 'zip', 'html')

        Returns:
            Export data as bytes
        """
        return await self.project_service.export_project(project_id, format_type)

    # ==================== Legacy Blog Generation Methods ====================
    # These methods wrap the existing api_client functions for backward compatibility

    async def upload_files(self, project_name: str, files_to_upload: List,
                          model_name: Optional[str] = None,
                          persona: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload files and create/update project.

        Args:
            project_name: Name of the project
            files_to_upload: List of (filename, content_bytes, content_type) tuples
            model_name: Model to use for generation
            persona: Writing persona

        Returns:
            Upload response with project_id and file paths
        """
        return await upload_files(project_name, files_to_upload, self.base_url)

    async def process_files(self, project_name: str, model_name: str,
                           file_paths: List[str]) -> Dict[str, Any]:
        """Process uploaded files."""
        return await process_files(project_name, model_name, file_paths, self.base_url)

    async def generate_outline(self, project_name: str, model_name: str,
                              **kwargs) -> Dict[str, Any]:
        """Generate blog outline."""
        return await generate_outline(project_name, model_name, base_url=self.base_url, **kwargs)

    async def generate_section(self, project_name: str, project_id: str,
                              section_index: int, **kwargs) -> Dict[str, Any]:
        """Generate a blog section."""
        return await generate_section(project_name, project_id, section_index,
                                     base_url=self.base_url, **kwargs)

    async def regenerate_section_with_feedback(self, project_name: str, project_id: str,
                                              section_index: int, feedback: str,
                                              **kwargs) -> Dict[str, Any]:
        """Regenerate section with user feedback."""
        return await regenerate_section_with_feedback(project_name, project_id, section_index,
                                                     feedback, base_url=self.base_url, **kwargs)

    async def compile_draft(self, project_name: str, project_id: str) -> Dict[str, Any]:
        """Compile final blog draft."""
        return await compile_draft(project_name, project_id, self.base_url)

    async def refine_blog(self, project_name: str, project_id: str,
                         compiled_draft: str, **kwargs) -> Dict[str, Any]:
        """Refine compiled blog draft."""
        return await refine_blog(project_name, project_id, compiled_draft,
                                base_url=self.base_url, **kwargs)

    async def refine_standalone(self, project_name: str, compiled_draft: str,
                               **kwargs) -> Dict[str, Any]:
        """Refine blog draft without job state."""
        return await refine_standalone(project_name, compiled_draft,
                                      base_url=self.base_url, **kwargs)

    async def generate_social_content(self, project_name: str, project_id: str) -> Dict[str, Any]:
        """Generate social media content."""
        return await generate_social_content(project_name, project_id, self.base_url)

    async def generate_social_content_standalone(self, project_name: str,
                                                refined_blog_content: str,
                                                **kwargs) -> Dict[str, Any]:
        """Generate social content without job state."""
        return await generate_social_content_standalone(project_name, refined_blog_content,
                                                       base_url=self.base_url, **kwargs)

    async def get_job_status(self, project_id: str) -> Dict[str, Any]:
        """Get project status."""
        return await get_job_status(project_id, self.base_url)

    async def get_personas(self) -> Dict[str, Any]:
        """Get available writing personas."""
        return await get_personas(self.base_url)

    async def get_models(self) -> Dict[str, Any]:
        """Get available models."""
        return await get_models(self.base_url)

    async def health_check(self) -> bool:
        """Check API health."""
        return await health_check(self.base_url)
