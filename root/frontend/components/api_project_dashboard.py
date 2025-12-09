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

            # Cost and Duration
            if "total_cost" in progress_data:
                col_cost, col_time = st.sidebar.columns(2)
                with col_cost:
                    st.sidebar.metric("Cost", f"${progress_data['total_cost']:.4f}")
                
                with col_time:
                    duration = progress_data.get("workflow_duration_seconds")
                    if duration:
                        hours = int(duration // 3600)
                        minutes = int((duration % 3600) // 60)
                        st.sidebar.metric("Time", f"{hours}h {minutes}m")

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

                # Cost and Duration metrics
                total_cost = progress_data.get("total_cost", 0.0)
                duration = progress_data.get("workflow_duration_seconds", 0)
                
                m_col1, m_col2 = st.columns(2)
                with m_col1:
                    st.metric("Total Cost", f"${total_cost:.4f}")
                
                with m_col2:
                    if duration:
                        hours = int(duration // 3600)
                        minutes = int((duration % 3600) // 60)
                        st.metric("Duration", f"{hours}h {minutes}m")
                    else:
                        st.metric("Duration", "0h 0m")

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
        """Resume a project and restore its state using API v2."""
        try:
            # Get resume data from API v2
            logger.info(f"Attempting to resume project with ID: {project_id}")
            resume_data = await self.api_client.resume_project(project_id)

            # Extract project information from the flat response structure
            # The backend returns a flat JSON with keys like 'outline', 'generated_sections', etc.
            project_name = resume_data.get("project_name", "Unknown Project")
            next_step = resume_data.get("next_step", "upload_files")
            
            # Update session state with basic project data
            st.session_state.api_app_state["current_project_id"] = project_id
            st.session_state.api_app_state["current_project_name"] = project_name
            st.session_state.api_app_state["project_name"] = project_name
            st.session_state.api_app_state["resume_point"] = next_step
            st.session_state.api_app_state["is_initialized"] = True
            
            # Restore Configuration
            st.session_state.api_app_state["selected_model"] = resume_data.get("model_name")
            st.session_state.api_app_state["specific_model"] = resume_data.get("specific_model")
            st.session_state.api_app_state["selected_persona"] = resume_data.get("persona")

            # Restore Content
            # Outline
            outline_data = resume_data.get("outline")
            if outline_data:
                st.session_state.api_app_state["generated_outline"] = outline_data
            
            # Sections
            generated_sections = resume_data.get("generated_sections", {})
            if generated_sections:
                # Ensure keys are integers for the frontend
                sections_map = {}
                for k, v in generated_sections.items():
                    try:
                        sections_map[int(k)] = v
                    except ValueError:
                        sections_map[k] = v
                st.session_state.api_app_state["generated_sections"] = sections_map
            
            # Section Progress
            st.session_state.api_app_state["total_sections"] = resume_data.get("total_sections", 0)
            st.session_state.api_app_state["current_section_index"] = resume_data.get("completed_sections", 0)

            # Drafts
            final_draft = resume_data.get("final_draft")
            if final_draft:
                st.session_state.api_app_state["final_draft"] = final_draft

            refined_draft = resume_data.get("refined_draft")
            if refined_draft:
                st.session_state.api_app_state["refined_draft"] = refined_draft
                st.session_state.api_app_state["summary"] = resume_data.get("summary")
                st.session_state.api_app_state["title_options"] = resume_data.get("title_options")

            # Social Content
            social_content = resume_data.get("social_content")
            if social_content:
                st.session_state.api_app_state["social_content"] = social_content
            
            # Cost Tracking
            cost_summary = resume_data.get("cost_summary")
            if cost_summary:
                st.session_state.api_app_state["cost_summary"] = cost_summary
            
            # File Info (Reconstruct basic info if actual file objects aren't available)
            uploaded_files = resume_data.get("uploaded_files", [])
            if uploaded_files:
                # uploaded_files from backend is likely a list of filenames or dicts
                # We map it to the structure expected by uploaded_files_info
                file_info = []
                for f in uploaded_files:
                    if isinstance(f, dict):
                        file_info.append({"name": f.get("name"), "type": f.get("type"), "size": f.get("size", 0)})
                    elif isinstance(f, str):
                        file_info.append({"name": f, "type": "application/octet-stream", "size": 0})
                st.session_state.api_app_state["uploaded_files_info"] = file_info
            
            processed_hashes = resume_data.get("processed_file_hashes", {})
            if processed_hashes:
                st.session_state.api_app_state["processed_file_hashes"] = processed_hashes

            # Map next_step to user-friendly tab navigation hint
            tab_mapping = {
                "upload_files": "File Upload",
                "generate_outline": "Outline Generator",
                "section_generation": "Blog Draft",
                "compile_draft": "Blog Draft",
                "blog_refinement": "Refinement",
                "social_generation": "Social Media",
                "completed": "Social Media"
            }

            recommended_tab = tab_mapping.get(next_step, "Outline Generator")

            # Show success with navigation guidance
            st.success(f"✅ Project resumed successfully!")
            st.info(f"➡️ Navigate to the **{recommended_tab}** tab to continue")
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
