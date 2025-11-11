# ABOUTME: Async HTTP client for backend API communication using aiohttp
# ABOUTME: Provides methods for project management, file upload, outline generation, and section drafting

import aiohttp
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

from .config import settings

logger = logging.getLogger(__name__)


class BackendAPIClient:
    """Async HTTP client for communicating with the FastAPI backend."""

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Backend API base URL (defaults to config setting)
        """
        self.base_url = base_url or settings.backend_url
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry - creates HTTP session."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes HTTP session."""
        if self.session:
            await self.session.close()

    async def create_project(
        self,
        name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new project by uploading initial files.

        Args:
            name: Project name
            metadata: Optional metadata including model_name and persona

        Returns:
            API response with project_id and upload details
        """
        url = f"{self.base_url}/upload/{name}"

        data = aiohttp.FormData()
        if metadata:
            if "model_name" in metadata:
                data.add_field("model_name", metadata["model_name"])
            if "persona" in metadata:
                data.add_field("persona", metadata["persona"])

        # Add empty file list for project creation
        data.add_field("files", b"", filename="dummy.txt")

        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def list_projects(self, status: Optional[str] = None) -> Dict[str, Any]:
        """
        List all projects with optional status filter.

        Args:
            status: Optional status filter (active, archived, deleted)

        Returns:
            API response with list of projects
        """
        url = f"{self.base_url}/projects"
        params = {"status": status} if status else {}

        async with self.session.get(url, params=params) as response:
            return await response.json()

    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific project.

        Args:
            project_id: Project UUID

        Returns:
            API response with project details and milestones
        """
        url = f"{self.base_url}/project/{project_id}"

        async with self.session.get(url) as response:
            return await response.json()

    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Permanently delete a project.

        Args:
            project_id: Project UUID

        Returns:
            API response with deletion status
        """
        url = f"{self.base_url}/project/{project_id}/permanent"

        async with self.session.delete(url) as response:
            return await response.json()

    async def upload_files(
        self,
        project_id: str,
        files: List[Path]
    ) -> Dict[str, Any]:
        """
        Upload files to an existing project.

        Args:
            project_id: Project UUID
            files: List of file paths to upload

        Returns:
            API response with uploaded file details
        """
        # Get project to find project name
        project_data = await self.get_project(project_id)
        project_name = project_data.get("project", {}).get("name")

        url = f"{self.base_url}/upload/{project_name}"

        data = aiohttp.FormData()
        for file_path in files:
            with open(file_path, "rb") as f:
                data.add_field(
                    "files",
                    f.read(),
                    filename=file_path.name,
                    content_type="application/octet-stream"
                )

        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def process_files(
        self,
        project_id: str,
        model_name: str = "openai",
        file_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Process uploaded files for a project.

        Args:
            project_id: Project UUID
            model_name: Model to use for processing
            file_paths: List of file paths to process

        Returns:
            API response with processing results
        """
        # Get project to find project name
        project_data = await self.get_project(project_id)
        project_name = project_data.get("project", {}).get("name")

        url = f"{self.base_url}/process_files/{project_name}"

        data = aiohttp.FormData()
        data.add_field("model_name", model_name)

        if file_paths:
            for fp in file_paths:
                data.add_field("file_paths", fp)

        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def generate_outline(
        self,
        project_id: str,
        user_guidelines: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate blog outline for a project.

        Args:
            project_id: Project UUID
            user_guidelines: Optional user-provided outline guidelines

        Returns:
            API response with generated outline
        """
        # Get project to find project name and model
        project_data = await self.get_project(project_id)
        project_name = project_data.get("project", {}).get("name")
        metadata = project_data.get("project", {}).get("metadata", {})
        model_name = metadata.get("model_name", "openai")

        url = f"{self.base_url}/generate_outline/{project_name}"

        data = aiohttp.FormData()
        data.add_field("model_name", model_name)

        if user_guidelines:
            data.add_field("user_guidelines", user_guidelines)

        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def draft_section(
        self,
        project_id: str,
        section_index: int,
        max_iterations: int = 3,
        quality_threshold: float = 0.8
    ) -> Dict[str, Any]:
        """
        Generate a draft for a specific section.

        Args:
            project_id: Project UUID
            section_index: Index of section to draft
            max_iterations: Max refinement iterations
            quality_threshold: Quality score threshold

        Returns:
            API response with generated section content
        """
        # Get project to find project name
        project_data = await self.get_project(project_id)
        project_name = project_data.get("project", {}).get("name")

        url = f"{self.base_url}/generate_section/{project_name}"

        data = aiohttp.FormData()
        data.add_field("section_index", str(section_index))
        data.add_field("max_iterations", str(max_iterations))
        data.add_field("quality_threshold", str(quality_threshold))

        async with self.session.post(url, data=data) as response:
            return await response.json()

    async def get_section(
        self,
        project_id: str,
        section_index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific section by index.

        Args:
            project_id: Project UUID
            section_index: Index of section to retrieve

        Returns:
            Section data or None if not found
        """
        project_data = await self.get_project(project_id)
        sections = project_data.get("project", {}).get("sections", [])

        for section in sections:
            if section.get("section_index") == section_index:
                return section

        return None

    async def get_all_sections(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Get all sections for a project.

        Args:
            project_id: Project UUID

        Returns:
            List of section data dictionaries
        """
        project_data = await self.get_project(project_id)
        return project_data.get("project", {}).get("sections", [])
