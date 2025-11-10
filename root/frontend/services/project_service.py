# -*- coding: utf-8 -*-
"""
ABOUTME: Project service module for handling API calls related to project management
ABOUTME: Provides centralized interface for project operations like list, get, resume, delete, export
"""

import httpx
import logging
import re
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Constants for validation
ALLOWED_EXPORT_FORMATS = {"markdown", "zip", "html"}
DEFAULT_TIMEOUT = 30.0
EXPORT_TIMEOUT = 60.0

class ProjectService:
    """Service class for project-related API operations."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """Initialize with API base URL."""
        self.base_url = base_url.rstrip('/')
    
    def _validate_project_id(self, project_id: str) -> None:
        """
        Validate project ID format (should be UUID).
        
        Args:
            project_id: Project identifier to validate
            
        Raises:
            ValueError: If project_id is not a valid UUID format
        """
        if not project_id or not isinstance(project_id, str):
            raise ValueError("Project ID must be a non-empty string")
        
        try:
            uuid.UUID(project_id)
        except ValueError:
            raise ValueError(f"Invalid project ID format: {project_id}. Expected UUID format.")
    
    def _validate_export_format(self, format_type: str) -> None:
        """
        Validate export format.
        
        Args:
            format_type: Export format to validate
            
        Raises:
            ValueError: If format_type is not supported
        """
        if format_type not in ALLOWED_EXPORT_FORMATS:
            raise ValueError(f"Invalid export format: {format_type}. Allowed formats: {', '.join(ALLOWED_EXPORT_FORMATS)}")
    
    async def list_projects(self, archived: bool = False) -> List[Dict[str, Any]]:
        """
        List all projects with their metadata and progress status.
        
        Args:
            archived: Include archived projects if True
            
        Returns:
            List of project dictionaries with metadata and progress
        """
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/projects",
                    params={"archived": archived}
                )
                response.raise_for_status()
                return response.json().get("projects", [])
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error listing projects: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error listing projects: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error listing projects: {e}")
            raise
    
    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Get detailed project information including all milestones.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Project dictionary with full details
        """
        self._validate_project_id(project_id)
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(f"{self.base_url}/project/{project_id}")
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting project {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error getting project {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting project {project_id}: {e}")
            raise
    
    async def resume_project(self, project_id: str) -> Dict[str, Any]:
        """
        Resume a project by loading its current state using API v2.

        Args:
            project_id: Unique project identifier

        Returns:
            Enhanced project state with progress, milestones, and next_step guidance
        """
        self._validate_project_id(project_id)

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(f"{self.base_url}/api/v2/projects/{project_id}/resume")
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error resuming project {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error resuming project {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error resuming project {project_id}: {e}")
            raise
    
    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Delete a project and all its associated data.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Deletion confirmation
        """
        self._validate_project_id(project_id)
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.delete(f"{self.base_url}/project/{project_id}/permanent")
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error deleting project {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error deleting project {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting project {project_id}: {e}")
            raise
    
    async def archive_project(self, project_id: str, archive: bool = True) -> Dict[str, Any]:
        """
        Archive or unarchive a project.
        
        Args:
            project_id: Unique project identifier
            archive: True to archive, False to unarchive
            
        Returns:
            Archive operation confirmation
        """
        self._validate_project_id(project_id)
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/project/{project_id}/archive",
                    json={"archived": archive}
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error archiving project {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error archiving project {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error archiving project {project_id}: {e}")
            raise
    
    async def export_project(self, project_id: str, format_type: str = "markdown") -> bytes:
        """
        Export project in specified format.
        
        Args:
            project_id: Unique project identifier
            format_type: Export format ('markdown', 'zip', 'html')
            
        Returns:
            Export data as bytes
        """
        self._validate_project_id(project_id)
        self._validate_export_format(format_type)
        
        try:
            async with httpx.AsyncClient(timeout=EXPORT_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/project/{project_id}/export",
                    params={"format": format_type}
                )
                response.raise_for_status()
                return response.content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error exporting project {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error exporting project {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error exporting project {project_id}: {e}")
            raise
    
    async def get_project_progress(self, project_id: str) -> Dict[str, Any]:
        """
        Get progress information for a project.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Progress data with completion percentages
        """
        self._validate_project_id(project_id)
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(f"{self.base_url}/projects/{project_id}/progress")
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting project progress {project_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error getting project progress {project_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting project progress {project_id}: {e}")
            raise
    
    async def search_projects(self, query: str = "", 
                            status: str = "all", 
                            sort_by: str = "updated_at") -> List[Dict[str, Any]]:
        """
        Search and filter projects.
        
        Args:
            query: Search term for project names
            status: Filter by status ('active', 'archived', 'all')
            sort_by: Sort field ('created_at', 'updated_at', 'name')
            
        Returns:
            Filtered list of projects
        """
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(
                    f"{self.base_url}/projects/search",
                    params={
                        "query": query,
                        "status": status,
                        "sort_by": sort_by
                    }
                )
                response.raise_for_status()
                return response.json().get("projects", [])
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching projects: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error searching projects: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error searching projects: {e}")
            raise
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status including available content.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status data including content availability
        """
        self._validate_job_id(job_id)
        
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.get(f"{self.base_url}/job_status/{job_id}")
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting job status {job_id}: {e.response.status_code}")
            raise
        except httpx.ConnectError as e:
            logger.error(f"Connection error getting job status {job_id}: {e}")
            raise  
        except Exception as e:
            logger.error(f"Unexpected error getting job status {job_id}: {e}")
            raise
            
    def _validate_job_id(self, job_id: str):
        """Validate job ID format."""
        if not job_id or not isinstance(job_id, str):
            raise ValueError("Job ID must be a non-empty string")