# ABOUTME: Project-aware session manager for non-destructive project switching and state caching
# ABOUTME: Manages multiple project states, auto-save functionality, and API v2 integration

"""
Project state management service for frontend.
Handles non-destructive project switching and state persistence.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
import streamlit as st
import httpx
import json

logger = logging.getLogger("ProjectStateManager")


class ProjectAwareSessionManager:
    """
    Manages project states with non-destructive switching.

    Features:
    - Cache multiple project states in memory
    - Non-destructive project switching
    - Auto-save section changes
    - API v2 integration
    """

    def __init__(self, api_base_url: str = "http://localhost:8000"):
        """Initialize project state manager."""
        self.api_base_url = api_base_url
        self.api_client = httpx.AsyncClient(base_url=api_base_url, timeout=30.0)

        # Project state caching
        self.project_states = {}  # Cache multiple project states
        self.current_project_id = None
        self.sections_modified = False
        self.auto_save_task = None

        # Initialize session state if needed
        if "project_manager" not in st.session_state:
            st.session_state.project_manager = {
                "current_project_id": None,
                "project_states": {},
                "projects_list": [],
                "last_refresh": None
            }

    # ==================== State Management ====================

    def get_current_state(self) -> Dict[str, Any]:
        """Get current project state from session."""
        if not self.current_project_id:
            return {}

        return {
            "project_id": self.current_project_id,
            "job_id": st.session_state.get("job_id"),
            "outline": st.session_state.get("generated_outline"),
            "sections": st.session_state.get("sections", []),
            "refined_draft": st.session_state.get("refined_draft"),
            "cost_summary": st.session_state.get("cost_summary", {}),
            "progress": st.session_state.get("progress", 0),
            "metadata": st.session_state.get("project_metadata", {})
        }

    def restore_state(self, state: Dict[str, Any]):
        """Restore project state to session."""
        if not state:
            return

        # Restore all state components
        st.session_state.job_id = state.get("job_id")
        st.session_state.generated_outline = state.get("outline")
        st.session_state.sections = state.get("sections", [])
        st.session_state.refined_draft = state.get("refined_draft")
        st.session_state.cost_summary = state.get("cost_summary", {})
        st.session_state.progress = state.get("progress", 0)
        st.session_state.project_metadata = state.get("metadata", {})

        # Update UI flags
        st.session_state.outline_generated = bool(state.get("outline"))
        st.session_state.draft_completed = any(
            s.get("status") == "completed" for s in state.get("sections", [])
        )
        st.session_state.blog_refined = bool(state.get("refined_draft"))

    # ==================== Project Switching ====================

    async def switch_project(self, project_id: str) -> bool:
        """
        Switch to a different project non-destructively.

        Args:
            project_id: Target project ID

        Returns:
            Success boolean
        """
        try:
            # Save current state if exists
            if self.current_project_id and self.current_project_id != project_id:
                await self.save_current_state()
                self.project_states[self.current_project_id] = self.get_current_state()

            # Check if state cached
            if project_id in self.project_states:
                # Restore from cache
                self.restore_state(self.project_states[project_id])
                logger.info(f"Restored project {project_id} from cache")
            else:
                # Load from backend
                success = await self.load_project_from_backend(project_id)
                if not success:
                    return False

            # Update current project
            self.current_project_id = project_id
            st.session_state.current_project_id = project_id
            st.session_state.project_manager["current_project_id"] = project_id

            logger.info(f"Switched to project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to switch project: {e}")
            return False

    async def load_project_from_backend(self, project_id: str) -> bool:
        """
        Load project state from backend.

        Args:
            project_id: Project ID to load

        Returns:
            Success boolean
        """
        try:
            # Call resume endpoint
            response = await self.api_client.post(f"/api/v2/projects/{project_id}/resume")

            if response.status_code != 200:
                logger.error(f"Failed to resume project: {response.text}")
                return False

            data = response.json()

            # Build state from response
            state = {
                "project_id": project_id,
                "job_id": data.get("job_id"),
                "outline": None,  # Will be loaded from milestones
                "sections": [],
                "refined_draft": None,
                "cost_summary": data.get("cost_summary", {}),
                "progress": data.get("progress", {}).get("percentage", 0),
                "metadata": data.get("project", {}).get("metadata", {})
            }

            # Load milestones
            milestones = data.get("milestones_completed", [])

            # Load outline if exists
            if "outline_generated" in milestones:
                outline_response = await self.api_client.get(
                    f"/api/v2/projects/{project_id}/milestones/outline_generated"
                )
                if outline_response.status_code == 200:
                    outline_data = outline_response.json()
                    state["outline"] = outline_data.get("milestone", {}).get("data")

            # Load sections
            sections_response = await self.api_client.get(
                f"/api/v2/projects/{project_id}/sections"
            )
            if sections_response.status_code == 200:
                sections_data = sections_response.json()
                state["sections"] = sections_data.get("sections", [])

            # Load refined draft if exists
            if "blog_refined" in milestones:
                refined_response = await self.api_client.get(
                    f"/api/v2/projects/{project_id}/milestones/blog_refined"
                )
                if refined_response.status_code == 200:
                    refined_data = refined_response.json()
                    state["refined_draft"] = refined_data.get("milestone", {}).get("data")

            # Cache and restore state
            self.project_states[project_id] = state
            self.restore_state(state)

            logger.info(f"Loaded project {project_id} from backend")
            return True

        except Exception as e:
            logger.error(f"Failed to load project from backend: {e}")
            return False

    # ==================== Auto-Save ====================

    async def save_current_state(self) -> bool:
        """Save current project state to backend."""
        if not self.current_project_id:
            return False

        try:
            # Save sections if modified
            if self.sections_modified:
                await self.auto_save_sections()

            # Update metadata
            metadata = st.session_state.get("project_metadata", {})
            metadata["last_saved"] = datetime.now().isoformat()

            response = await self.api_client.patch(
                f"/api/v2/projects/{self.current_project_id}/metadata",
                json={"metadata": metadata}
            )

            logger.info(f"Saved state for project {self.current_project_id}")
            return response.status_code == 200

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            return False

    async def auto_save_sections(self) -> bool:
        """
        Auto-save sections after changes.

        Returns:
            Success boolean
        """
        if not self.current_project_id or not self.sections_modified:
            return True

        try:
            sections = st.session_state.get("sections", [])
            if not sections:
                return True

            # Prepare section updates
            section_updates = []
            for i, section in enumerate(sections):
                section_updates.append({
                    "section_index": i,
                    "title": section.get("title", ""),
                    "content": section.get("content", ""),
                    "status": section.get("status", "pending"),
                    "cost_delta": section.get("cost_delta", 0.0),
                    "input_tokens": section.get("input_tokens", 0),
                    "output_tokens": section.get("output_tokens", 0)
                })

            # Save to backend
            response = await self.api_client.put(
                f"/api/v2/projects/{self.current_project_id}/sections",
                json=section_updates
            )

            if response.status_code == 200:
                self.sections_modified = False
                logger.info(f"Auto-saved {len(sections)} sections")
                return True
            else:
                logger.error(f"Failed to auto-save sections: {response.text}")
                return False

        except Exception as e:
            logger.error(f"Auto-save error: {e}")
            return False

    def mark_sections_modified(self):
        """Mark sections as modified for auto-save."""
        self.sections_modified = True

        # Schedule auto-save after 5 seconds of inactivity
        if self.auto_save_task:
            self.auto_save_task.cancel()

        self.auto_save_task = asyncio.create_task(
            self._delayed_auto_save()
        )

    async def _delayed_auto_save(self):
        """Delayed auto-save after inactivity."""
        await asyncio.sleep(5)  # Wait 5 seconds
        await self.auto_save_sections()

    # ==================== Project List Management ====================

    async def refresh_projects_list(self) -> List[Dict[str, Any]]:
        """
        Refresh the list of active projects.

        Returns:
            List of project summaries
        """
        try:
            response = await self.api_client.get(
                "/api/v2/projects",
                params={"status": "active"}
            )

            if response.status_code != 200:
                logger.error(f"Failed to list projects: {response.text}")
                return []

            data = response.json()
            projects = data.get("projects", [])

            # Cache in session state
            st.session_state.project_manager["projects_list"] = projects
            st.session_state.project_manager["last_refresh"] = datetime.now().isoformat()

            return projects

        except Exception as e:
            logger.error(f"Failed to refresh projects list: {e}")
            return []

    async def create_project(self, name: str, metadata: Dict[str, Any] = None) -> Optional[str]:
        """
        Create a new project.

        Args:
            name: Project name
            metadata: Optional metadata

        Returns:
            Project ID if successful
        """
        try:
            response = await self.api_client.post(
                "/api/v2/projects",
                json={
                    "name": name,
                    "metadata": metadata or {}
                }
            )

            if response.status_code != 200:
                logger.error(f"Failed to create project: {response.text}")
                return None

            data = response.json()
            project_id = data.get("project_id")

            # Refresh projects list
            await self.refresh_projects_list()

            logger.info(f"Created project {name} with ID {project_id}")
            return project_id

        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None

    async def archive_project(self, project_id: str) -> bool:
        """
        Archive a project.

        Args:
            project_id: Project to archive

        Returns:
            Success boolean
        """
        try:
            # Save current state first if it's the current project
            if project_id == self.current_project_id:
                await self.save_current_state()

            response = await self.api_client.delete(
                f"/api/v2/projects/{project_id}",
                params={"permanent": False}
            )

            if response.status_code != 200:
                logger.error(f"Failed to archive project: {response.text}")
                return False

            # Remove from cache
            if project_id in self.project_states:
                del self.project_states[project_id]

            # Clear current if archived
            if project_id == self.current_project_id:
                self.current_project_id = None

            # Refresh projects list
            await self.refresh_projects_list()

            logger.info(f"Archived project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive project: {e}")
            return False

    # ==================== Cost Tracking ====================

    async def track_operation_cost(
        self,
        agent_name: str,
        operation: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        model_used: str = None
    ) -> bool:
        """
        Track cost for an operation.

        Returns:
            Success boolean
        """
        if not self.current_project_id:
            return False

        try:
            response = await self.api_client.post(
                f"/api/v2/projects/{self.current_project_id}/costs",
                json={
                    "agent_name": agent_name,
                    "operation": operation,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost": cost,
                    "model_used": model_used,
                    "metadata": {}
                }
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            return False

    async def get_cost_analysis(self) -> Dict[str, Any]:
        """
        Get cost analysis for current project.

        Returns:
            Cost analysis data
        """
        if not self.current_project_id:
            return {}

        try:
            response = await self.api_client.get(
                f"/api/v2/projects/{self.current_project_id}/costs/analysis"
            )

            if response.status_code != 200:
                return {}

            data = response.json()
            return data.get("analysis", {})

        except Exception as e:
            logger.error(f"Failed to get cost analysis: {e}")
            return {}

    # ==================== Cleanup ====================

    async def cleanup(self):
        """Cleanup resources on shutdown."""
        try:
            # Save current state
            if self.current_project_id:
                await self.save_current_state()

            # Cancel auto-save task
            if self.auto_save_task:
                self.auto_save_task.cancel()

            # Close API client
            await self.api_client.aclose()

        except Exception as e:
            logger.error(f"Cleanup error: {e}")