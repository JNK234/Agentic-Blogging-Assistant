# ABOUTME: API-based project dashboard UI component for Streamlit frontend
# ABOUTME: Adapted version of ProjectDashboard using BlogAPIClient instead of state_manager

import streamlit as st
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger("APIProjectDashboard")


class APIProjectDashboard:
    """
    Project dashboard with card-based UI using BlogAPIClient.

    Features:
    - Project cards with progress and cost
    - Quick actions (Resume, Switch, Archive)
    - Project listing and selection
    - Integration with session state
    """

    def __init__(self, api_client):
        """
        Initialize API project dashboard.

        Args:
            api_client: BlogAPIClient instance for API calls
        """
        self.api_client = api_client

    def render_sidebar(self) -> Optional[str]:
        """
        Render compact project selector in sidebar.

        Returns:
            Selected project_id if user clicked a project, None otherwise
        """
        st.sidebar.header("📁 Projects")

        # Refresh button
        if st.sidebar.button("🔄 Refresh", key="refresh_projects_sidebar"):
            asyncio.run(self._refresh_projects())

        # Get projects from session state or fetch
        if "available_projects" not in st.session_state.api_app_state:
            asyncio.run(self._refresh_projects())

        projects = st.session_state.api_app_state.get("available_projects", [])

        if not projects:
            st.sidebar.info("No projects yet. Upload files to create one.")
            return None

        # Current project indicator
        current_project_id = st.session_state.api_app_state.get("current_project_id")

        # Project selector dropdown
        project_options = {
            p["id"]: f"{'✅' if p['id'] == current_project_id else '📁'} {p['name']}"
            for p in projects
        }

        if project_options:
            selected_id = st.sidebar.selectbox(
                "Select Project",
                options=list(project_options.keys()),
                format_func=lambda x: project_options[x],
                key="project_selector",
                index=list(project_options.keys()).index(current_project_id) if current_project_id in project_options else 0
            )

            # Show project info and actions
            if selected_id:
                self._render_sidebar_project_info(selected_id, projects)

                # Return selected_id if it changed
                if selected_id != current_project_id:
                    return selected_id

        return None

    def _render_sidebar_project_info(self, project_id: str, projects: List[Dict[str, Any]]):
        """Render project info and quick actions in sidebar."""
        project = next((p for p in projects if p["id"] == project_id), None)
        if not project:
            return

        # Progress bar
        try:
            progress_data = asyncio.run(self.api_client.get_project_progress(project_id))
            progress_pct = progress_data.get("progress_percentage", 0)
            st.sidebar.progress(progress_pct / 100)
            st.sidebar.caption(f"Progress: {progress_pct}%")

            # Milestones summary
            milestones = progress_data.get("milestones", {})
            completed = sum(1 for v in milestones.values() if v)
            total = len(milestones)
            st.sidebar.caption(f"Milestones: {completed}/{total}")

            # Cost
            if "total_cost" in progress_data:
                st.sidebar.metric("Cost", f"${progress_data['total_cost']:.4f}")

        except Exception as e:
            logger.error(f"Failed to get progress for {project_id}: {e}")
            st.sidebar.error("Failed to load progress")

        # Action buttons
        col1, col2 = st.sidebar.columns(2)

        with col1:
            if st.button("▶️ Resume", key=f"resume_sidebar_{project_id}"):
                asyncio.run(self._resume_project(project_id))

        with col2:
            if st.button("📦 Archive", key=f"archive_sidebar_{project_id}"):
                asyncio.run(self._archive_project(project_id))

    def render_full_dashboard(self):
        """Render full project dashboard in main area."""
        st.title("📂 Project Dashboard")

        # Dashboard header with actions
        col1, col2 = st.columns([2, 1])

        with col1:
            st.markdown("### Active Projects")

        with col2:
            if st.button("🔄 Refresh All", key="refresh_all_projects"):
                asyncio.run(self._refresh_projects())

        # Get projects list
        if "available_projects" not in st.session_state.api_app_state:
            asyncio.run(self._refresh_projects())

        projects = st.session_state.api_app_state.get("available_projects", [])

        if not projects:
            st.info("👋 No active projects yet. Upload files to create your first project!")
            return

        # Current project indicator
        current_project_id = st.session_state.api_app_state.get("current_project_id")
        if current_project_id:
            project_name = next(
                (p["name"] for p in projects if p["id"] == current_project_id),
                "Unknown"
            )
            st.success(f"✨ Currently working on: **{project_name}**")

        # Project cards grid
        self._render_project_cards(projects)

    def _render_project_cards(self, projects: List[Dict[str, Any]]):
        """Render project cards in grid layout."""
        # Create 2-column grid for projects
        for i in range(0, len(projects), 2):
            cols = st.columns(2)

            for j, col in enumerate(cols):
                if i + j < len(projects):
                    project = projects[i + j]
                    with col:
                        self._render_project_card(project)

    def _render_project_card(self, project: Dict[str, Any]):
        """Render individual project card."""
        with st.container():
            # Project header
            st.markdown(f"### 📁 {project['name']}")

            # Metadata
            col1, col2 = st.columns(2)
            with col1:
                created = project.get("created_at", "")
                if created:
                    try:
                        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        st.caption(f"Created: {dt.strftime('%Y-%m-%d')}")
                    except:
                        st.caption(f"Created: {created}")

            with col2:
                updated = project.get("updated_at", "")
                if updated:
                    try:
                        dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                        st.caption(f"Updated: {dt.strftime('%Y-%m-%d %H:%M')}")
                    except:
                        st.caption(f"Updated: {updated}")

            # Progress bar (fetch from API)
            try:
                progress_data = asyncio.run(self.api_client.get_project_progress(project['id']))
                progress = progress_data.get("progress_percentage", 0)
                st.progress(progress / 100)
                st.caption(f"Progress: {progress}%")

                # Cost metric
                total_cost = progress_data.get("total_cost", 0.0)
                st.metric("Total Cost", f"${total_cost:.4f}")

                # Milestone status
                milestones = progress_data.get("milestones", {})
                completed_count = sum(1 for v in milestones.values() if v)
                total_count = len(milestones)
                st.caption(f"Milestones: {completed_count}/{total_count}")

            except Exception as e:
                logger.error(f"Failed to get progress for {project['id']}: {e}")
                st.caption("Progress: N/A")

            # Action buttons
            col1, col2, col3 = st.columns(3)

            current_id = st.session_state.api_app_state.get("current_project_id")

            with col1:
                if st.button(
                    "▶️ Resume",
                    key=f"resume_{project['id']}",
                    help="Continue working on this project"
                ):
                    asyncio.run(self._resume_project(project['id']))

            with col2:
                if current_id != project['id']:
                    if st.button(
                        "🔄 Switch",
                        key=f"switch_{project['id']}",
                        help="Switch to this project"
                    ):
                        asyncio.run(self._switch_project(project['id']))
                else:
                    st.button(
                        "✅ Current",
                        key=f"current_{project['id']}",
                        disabled=True
                    )

            with col3:
                if st.button(
                    "📦 Archive",
                    key=f"archive_{project['id']}",
                    help="Archive this project"
                ):
                    asyncio.run(self._archive_project(project['id']))

            # Add separator
            st.divider()

    # ==================== Async Actions ====================

    async def _refresh_projects(self):
        """Refresh projects list from API."""
        try:
            projects = await self.api_client.get_all_projects(status="active")
            st.session_state.api_app_state["available_projects"] = projects
            st.success(f"Loaded {len(projects)} active projects")
            st.rerun()
        except Exception as e:
            logger.error(f"Failed to refresh projects: {e}")
            st.error(f"Failed to refresh projects: {str(e)}")

    async def _resume_project(self, project_id: str):
        """Resume a project and restore its state."""
        try:
            resume_data = await self.api_client.resume_project(project_id)

            # Update session state with resumed project data
            st.session_state.api_app_state["current_project_id"] = project_id
            st.session_state.api_app_state["job_id"] = resume_data.get("job_id")
            st.session_state.api_app_state["current_project_name"] = resume_data.get("project_name")

            # Store resume point
            st.session_state.api_app_state["resume_point"] = resume_data.get("next_step")

            # Store project-specific data if available
            if "outline" in resume_data:
                st.session_state.api_app_state["generated_outline"] = resume_data["outline"]
            if "final_draft" in resume_data:
                st.session_state.api_app_state["final_draft"] = resume_data["final_draft"]
            if "refined_draft" in resume_data:
                st.session_state.api_app_state["refined_draft"] = resume_data["refined_draft"]

            st.success(f"Project resumed! Next step: {resume_data.get('next_step', 'unknown')}")
            st.rerun()

        except Exception as e:
            logger.error(f"Error resuming project {project_id}: {e}")
            st.error(f"Failed to resume project: {str(e)}")

    async def _switch_project(self, project_id: str):
        """Switch to a different project."""
        try:
            # Just update current project ID without resuming
            st.session_state.api_app_state["current_project_id"] = project_id

            # Get project details
            project_data = await self.api_client.get_project_details(project_id)
            st.session_state.api_app_state["current_project_name"] = project_data.get("project", {}).get("name")

            st.success("Switched project successfully!")
            st.rerun()

        except Exception as e:
            logger.error(f"Error switching to project {project_id}: {e}")
            st.error(f"Failed to switch project: {str(e)}")

    async def _archive_project(self, project_id: str):
        """Archive a project."""
        try:
            # Confirmation check
            confirm_key = f"confirm_archive_{project_id}"
            if not st.session_state.get(confirm_key, False):
                st.warning("Click Archive again to confirm")
                st.session_state[confirm_key] = True
                return

            # Clear confirmation flag
            st.session_state[confirm_key] = False

            # Archive the project
            await self.api_client.archive_project(project_id)

            # Clear current project if it was archived
            if st.session_state.api_app_state.get("current_project_id") == project_id:
                st.session_state.api_app_state["current_project_id"] = None
                st.session_state.api_app_state["current_project_name"] = None

            st.success("Project archived successfully!")

            # Refresh project list
            await self._refresh_projects()

        except Exception as e:
            logger.error(f"Error archiving project {project_id}: {e}")
            st.error(f"Failed to archive project: {str(e)}")
