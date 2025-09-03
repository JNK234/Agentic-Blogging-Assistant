# -*- coding: utf-8 -*-
"""
ABOUTME: Project service module for handling API calls related to project management
ABOUTME: Provides centralized interface for project operations like list, get, resume, delete, export
"""

import httpx
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class ProjectService:
    """Service class for project-related API operations."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        """Initialize with API base URL."""
        self.base_url = base_url.rstrip('/')
    
    async def list_projects(self, archived: bool = False) -> List[Dict[str, Any]]:
        """
        List all projects with their metadata and progress status.
        
        Args:
            archived: Include archived projects if True
            
        Returns:
            List of project dictionaries with metadata and progress
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/projects",
                    params={"archived": archived}
                )
                response.raise_for_status()
                return response.json().get("projects", [])
                
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            raise
    
    async def get_project(self, project_id: str) -> Dict[str, Any]:
        """
        Get detailed project information including all milestones.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Project dictionary with full details
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/projects/{project_id}")
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            raise
    
    async def resume_project(self, project_id: str) -> Dict[str, Any]:
        """
        Resume a project by loading its current state.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Project state data for session restoration
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/projects/{project_id}/resume")
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to resume project {project_id}: {e}")
            raise
    
    async def delete_project(self, project_id: str) -> Dict[str, Any]:
        """
        Delete a project and all its associated data.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Deletion confirmation
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(f"{self.base_url}/projects/{project_id}")
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
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
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.patch(
                    f"{self.base_url}/projects/{project_id}/archive",
                    json={"archived": archive}
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to archive project {project_id}: {e}")
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
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(
                    f"{self.base_url}/projects/{project_id}/export",
                    params={"format": format_type}
                )
                response.raise_for_status()
                return response.content
                
        except Exception as e:
            logger.error(f"Failed to export project {project_id}: {e}")
            raise
    
    async def get_project_progress(self, project_id: str) -> Dict[str, Any]:
        """
        Get progress information for a project.
        
        Args:
            project_id: Unique project identifier
            
        Returns:
            Progress data with completion percentages
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/projects/{project_id}/progress")
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to get project progress {project_id}: {e}")
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                
        except Exception as e:
            logger.error(f"Failed to search projects: {e}")
            raise