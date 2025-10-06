# ABOUTME: Project dashboard UI component with cards view and project management features
# ABOUTME: Displays active projects with progress, cost tracking, and quick actions

"""
Project dashboard UI component for Streamlit frontend.
Provides card-based project view with management features.
"""

import streamlit as st
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger("ProjectDashboard")


class ProjectDashboard:
    """
    Project dashboard with card-based UI.

    Features:
    - Project cards with progress and cost
    - Quick actions (Resume, Switch, Archive)
    - Create new project
    - Section status overview
    """

    def __init__(self, state_manager):
        """
        Initialize project dashboard.

        Args:
            state_manager: ProjectAwareSessionManager instance
        """
        self.state_manager = state_manager

    def render(self):
        """Render the main project dashboard."""
        st.title("📂 Project Dashboard")

        # Dashboard header with actions
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            st.markdown("### Active Projects")

        with col2:
            if st.button("🔄 Refresh", key="refresh_projects"):
                asyncio.run(self._refresh_projects())

        with col3:
            if st.button("➕ New Project", key="new_project"):
                self._show_new_project_dialog()

        # Get projects list
        projects = st.session_state.project_manager.get("projects_list", [])

        if not projects:
            # No projects - show welcome message
            st.info("👋 No active projects yet. Click 'New Project' to get started!")
            return

        # Current project indicator
        current_project_id = st.session_state.project_manager.get("current_project_id")
        if current_project_id:
            project_name = next(
                (p["name"] for p in projects if p["id"] == current_project_id),
                "Unknown"
            )
            st.success(f"✨ Currently working on: **{project_name}**")

        # Project cards grid
        self._render_project_cards(projects)

        # Cost analysis section if project selected
        if current_project_id:
            with st.expander("💰 Cost Analysis", expanded=False):
                self._render_cost_analysis()

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
            # Card container with border
            card = st.container()
            with card:
                # Project header
                st.markdown(f"### 📁 {project['name']}")

                # Metadata
                col1, col2 = st.columns(2)
                with col1:
                    created = project.get("created_at", "")
                    if created:
                        try:
                            dt = datetime.fromisoformat(created)
                            st.caption(f"Created: {dt.strftime('%Y-%m-%d')}")
                        except:
                            st.caption(f"Created: {created}")

                with col2:
                    updated = project.get("updated_at", "")
                    if updated:
                        try:
                            dt = datetime.fromisoformat(updated)
                            st.caption(f"Updated: {dt.strftime('%Y-%m-%d %H:%M')}")
                        except:
                            st.caption(f"Updated: {updated}")

                # Progress bar
                progress = project.get("progress", 0)
                st.progress(progress / 100)
                st.caption(f"Progress: {progress}%")

                # Cost metric
                total_cost = project.get("total_cost", 0.0)
                st.metric("Total Cost", f"${total_cost:.4f}")

                # Section status if available
                sections = project.get("sections", {})
                if sections:
                    total = sections.get("total", 0)
                    completed = sections.get("completed", 0)
                    if total > 0:
                        st.caption(f"Sections: {completed}/{total} completed")

                # Action buttons
                col1, col2, col3 = st.columns(3)

                with col1:
                    if st.button(
                        "▶️ Resume",
                        key=f"resume_{project['id']}",
                        help="Continue working on this project"
                    ):
                        asyncio.run(self._resume_project(project['id']))

                with col2:
                    current = st.session_state.project_manager.get("current_project_id")
                    if current != project['id']:
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

    def _render_cost_analysis(self):
        """Render cost analysis for current project."""
        try:
            # Get cost analysis
            analysis = asyncio.run(self.state_manager.get_cost_analysis())

            if not analysis:
                st.info("No cost data available yet")
                return

            # Summary metrics
            summary = analysis.get("summary", {})
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Total Cost",
                    f"${summary.get('total_cost', 0):.4f}"
                )

            with col2:
                st.metric(
                    "Input Tokens",
                    f"{summary.get('total_input_tokens', 0):,}"
                )

            with col3:
                st.metric(
                    "Output Tokens",
                    f"{summary.get('total_output_tokens', 0):,}"
                )

            # Cost by agent
            cost_by_agent = summary.get("cost_by_agent", {})
            if cost_by_agent:
                st.markdown("#### Cost by Agent")
                for agent, cost in cost_by_agent.items():
                    st.text(f"{agent}: ${cost:.4f}")

            # Cost by model
            cost_by_model = summary.get("cost_by_model", {})
            if cost_by_model:
                st.markdown("#### Cost by Model")
                for model, cost in cost_by_model.items():
                    if model:  # Skip None models
                        st.text(f"{model}: ${cost:.4f}")

            # Timeline
            timeline = analysis.get("timeline", [])
            if timeline and len(timeline) > 5:
                st.markdown("#### Recent Operations")
                # Show last 5 operations
                for op in timeline[-5:]:
                    timestamp = op.get("timestamp", "")
                    agent = op.get("agent", "Unknown")
                    operation = op.get("operation", "Unknown")
                    cost = op.get("cost", 0)
                    st.text(f"{timestamp[:19]} - {agent}/{operation}: ${cost:.4f}")

        except Exception as e:
            logger.error(f"Failed to render cost analysis: {e}")
            st.error("Failed to load cost analysis")

    def _show_new_project_dialog(self):
        """Show dialog for creating new project."""
        with st.form("new_project_form"):
            st.markdown("### Create New Project")

            # Project name
            project_name = st.text_input(
                "Project Name",
                placeholder="Enter project name...",
                help="A descriptive name for your blog project"
            )

            # Model selection
            model_provider = st.selectbox(
                "Model Provider",
                options=["openai", "claude", "gemini", "deepseek"],
                help="Select the LLM provider"
            )

            model_name = st.text_input(
                "Model Name",
                value="gpt-4" if model_provider == "openai" else "",
                help="Specific model to use"
            )

            # Persona selection
            persona = st.selectbox(
                "Writing Persona",
                options=["default", "technical", "casual", "academic"],
                help="Writing style for the blog"
            )

            # Submit button
            if st.form_submit_button("Create Project"):
                if project_name:
                    metadata = {
                        "model_provider": model_provider,
                        "model_name": model_name,
                        "persona": persona,
                        "created_via": "dashboard"
                    }
                    asyncio.run(self._create_project(project_name, metadata))
                else:
                    st.error("Please enter a project name")

    # ==================== Async Actions ====================

    async def _refresh_projects(self):
        """Refresh projects list."""
        try:
            projects = await self.state_manager.refresh_projects_list()
            st.success(f"Loaded {len(projects)} active projects")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to refresh projects: {e}")

    async def _resume_project(self, project_id: str):
        """Resume a project."""
        try:
            success = await self.state_manager.switch_project(project_id)
            if success:
                st.success("Project resumed successfully!")
                # Switch to main workflow tab
                st.session_state.active_tab = "workflow"
                st.rerun()
            else:
                st.error("Failed to resume project")
        except Exception as e:
            st.error(f"Error resuming project: {e}")

    async def _switch_project(self, project_id: str):
        """Switch to a project."""
        try:
            success = await self.state_manager.switch_project(project_id)
            if success:
                st.success("Switched project successfully!")
                st.rerun()
            else:
                st.error("Failed to switch project")
        except Exception as e:
            st.error(f"Error switching project: {e}")

    async def _archive_project(self, project_id: str):
        """Archive a project."""
        try:
            # Confirm dialog
            if st.session_state.get(f"confirm_archive_{project_id}"):
                success = await self.state_manager.archive_project(project_id)
                if success:
                    st.success("Project archived successfully!")
                    st.rerun()
                else:
                    st.error("Failed to archive project")
            else:
                st.warning("Click Archive again to confirm")
                st.session_state[f"confirm_archive_{project_id}"] = True
        except Exception as e:
            st.error(f"Error archiving project: {e}")

    async def _create_project(self, name: str, metadata: Dict[str, Any]):
        """Create new project."""
        try:
            project_id = await self.state_manager.create_project(name, metadata)
            if project_id:
                st.success(f"Created project: {name}")
                # Auto-switch to new project
                await self.state_manager.switch_project(project_id)
                st.rerun()
            else:
                st.error("Failed to create project")
        except Exception as e:
            st.error(f"Error creating project: {e}")


class SectionManager:
    """
    Section management UI component.

    Features:
    - Section status grid
    - Individual section actions
    - Batch operations
    - Cost tracking per section
    """

    def __init__(self, state_manager):
        """Initialize section manager."""
        self.state_manager = state_manager

    def render(self):
        """Render section management UI."""
        sections = st.session_state.get("sections", [])

        if not sections:
            st.info("No sections generated yet")
            return

        st.markdown("### 📝 Section Management")

        # Summary stats
        col1, col2, col3, col4 = st.columns(4)

        completed = sum(1 for s in sections if s.get("status") == "completed")
        generating = sum(1 for s in sections if s.get("status") == "generating")
        pending = sum(1 for s in sections if s.get("status") == "pending")
        failed = sum(1 for s in sections if s.get("status") == "failed")

        with col1:
            st.metric("Completed", f"{completed}/{len(sections)}")
        with col2:
            st.metric("Generating", generating)
        with col3:
            st.metric("Pending", pending)
        with col4:
            st.metric("Failed", failed)

        # Batch actions
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🔄 Retry Failed", disabled=failed == 0):
                self._retry_failed_sections()
        with col2:
            if st.button("⏸️ Pause All", disabled=generating == 0):
                self._pause_all_sections()
        with col3:
            if st.button("💾 Save All"):
                asyncio.run(self._save_all_sections())

        st.divider()

        # Section grid
        for idx, section in enumerate(sections):
            self._render_section_row(idx, section)

    def _render_section_row(self, idx: int, section: Dict[str, Any]):
        """Render individual section row."""
        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

        with col1:
            # Status icon
            status = section.get("status", "pending")
            status_icon = {
                "completed": "✅",
                "generating": "⏳",
                "pending": "⭕",
                "failed": "❌"
            }.get(status, "❓")

            title = section.get("title", f"Section {idx + 1}")
            st.markdown(f"{status_icon} **{title}**")

        with col2:
            # Cost
            cost = section.get("cost_delta", 0.0)
            st.caption(f"${cost:.4f}")

        with col3:
            # Word count
            content = section.get("content", "")
            word_count = len(content.split()) if content else 0
            st.caption(f"{word_count} words")

        with col4:
            # Actions based on status
            if status == "failed":
                if st.button("🔄", key=f"retry_{idx}", help="Retry section"):
                    self._retry_section(idx)
            elif status == "completed":
                if st.button("✏️", key=f"edit_{idx}", help="Edit section"):
                    self._edit_section(idx)

        with col5:
            # View/expand
            if content:
                with st.expander("View", expanded=False):
                    st.markdown(content)

    def _retry_failed_sections(self):
        """Retry all failed sections."""
        sections = st.session_state.get("sections", [])
        for idx, section in enumerate(sections):
            if section.get("status") == "failed":
                section["status"] = "pending"
        st.session_state.sections = sections
        self.state_manager.mark_sections_modified()
        st.success("Marked failed sections for retry")
        st.rerun()

    def _pause_all_sections(self):
        """Pause all generating sections."""
        sections = st.session_state.get("sections", [])
        for section in sections:
            if section.get("status") == "generating":
                section["status"] = "pending"
        st.session_state.sections = sections
        self.state_manager.mark_sections_modified()
        st.info("Paused all generating sections")
        st.rerun()

    async def _save_all_sections(self):
        """Save all sections to backend."""
        success = await self.state_manager.auto_save_sections()
        if success:
            st.success("Sections saved successfully!")
        else:
            st.error("Failed to save sections")

    def _retry_section(self, idx: int):
        """Retry a specific section."""
        sections = st.session_state.get("sections", [])
        if idx < len(sections):
            sections[idx]["status"] = "pending"
            st.session_state.sections = sections
            self.state_manager.mark_sections_modified()
            st.success(f"Section {idx + 1} marked for retry")
            st.rerun()

    def _edit_section(self, idx: int):
        """Edit a specific section."""
        sections = st.session_state.get("sections", [])
        if idx < len(sections):
            # Store edit index
            st.session_state.editing_section = idx
            st.session_state.edit_content = sections[idx].get("content", "")
            st.info(f"Editing section {idx + 1}")
            st.rerun()