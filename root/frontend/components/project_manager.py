# -*- coding: utf-8 -*-
"""
ABOUTME: Project management UI component for handling project selection, creation, and resumption
ABOUTME: Provides visual progress indicators and project switching functionality
"""

import streamlit as st
import asyncio
import logging
from typing import List, Dict, Any, Optional
from services.project_service import ProjectService

logger = logging.getLogger(__name__)

class ProjectManagerUI:
    """UI component for project management functionality."""
    
    def __init__(self, session_manager, api_base_url: str):
        """Initialize with session manager and API base URL."""
        self.session_manager = session_manager
        self.project_service = ProjectService(api_base_url)
    
    def render(self):
        """Render the project management UI section."""
        st.markdown("### 🗂️ Project Management")
        
        # Load available projects
        self._load_projects()
        
        # Project selector and actions
        self._render_project_selector()
        
        # Progress indicator for current project
        self._render_progress_indicator()
        
        # Project actions
        self._render_project_actions()
    
    def _load_projects(self):
        """Load available projects from backend."""
        try:
            show_archived = self.session_manager.get('show_archived_projects', False)
            with st.spinner("Loading projects..."):
                projects = asyncio.run(self.project_service.list_projects(archived=show_archived))
                self.session_manager.set('available_projects', projects)
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
            st.error(f"Failed to load projects: {str(e)}")
    
    def _render_project_selector(self):
        """Render project selection dropdown and controls."""
        projects = self.session_manager.get('available_projects', [])
        current_project_id = self.session_manager.get('current_project_id')
        
        # Show archived projects toggle
        show_archived = st.checkbox(
            "Show archived projects",
            value=self.session_manager.get('show_archived_projects', False),
            key="show_archived_toggle"
        )
        if show_archived != self.session_manager.get('show_archived_projects', False):
            self.session_manager.set('show_archived_projects', show_archived)
            self._load_projects()
            st.rerun()
        
        if not projects:
            st.info("No projects available. Create one by initializing with files.")
            return
        
        # Project selector
        project_options = ["-- Select Project --"] + [
            f"{'[ARCHIVED] ' if p.get('archived') else ''}{p['name']} ({p['id'][:8]}...)"
            for p in projects
        ]
        
        current_index = 0
        if current_project_id:
            for i, project in enumerate(projects, 1):
                if project['id'] == current_project_id:
                    current_index = i
                    break
        
        selected_index = st.selectbox(
            "Select Project",
            range(len(project_options)),
            format_func=lambda i: project_options[i],
            index=current_index,
            key="project_selector"
        )
        
        # Handle project selection change
        if selected_index > 0:
            selected_project = projects[selected_index - 1]
            if selected_project['id'] != current_project_id:
                self._switch_project(selected_project)
        elif current_project_id:
            # User selected "-- Select Project --", clear current project
            self._clear_current_project()
    
    def _render_progress_indicator(self):
        """Render progress indicator for current project."""
        current_project_id = self.session_manager.get('current_project_id')
        if not current_project_id:
            return
        
        try:
            with st.spinner("Loading project progress..."):
                progress_data = asyncio.run(self.project_service.get_project_progress(current_project_id))
            
            st.markdown("#### 📊 Progress")
            
            # Overall progress bar
            overall_progress = progress_data.get('overall_progress', 0)
            st.progress(overall_progress / 100.0, text=f"Overall: {overall_progress}%")
            
            # Milestone indicators
            milestones = progress_data.get('milestones', {})
            
            cols = st.columns(5)
            milestone_names = ['Upload', 'Outline', 'Draft', 'Refined', 'Social']
            milestone_keys = ['files_uploaded', 'outline_generated', 'draft_completed', 'blog_refined', 'social_generated']
            
            for i, (name, key) in enumerate(zip(milestone_names, milestone_keys)):
                with cols[i]:
                    completed = milestones.get(key, {}).get('completed', False)
                    if completed:
                        st.success(f"✅ {name}")
                    else:
                        st.info(f"⏳ {name}")
            
        except Exception as e:
            logger.error(f"Failed to get progress for project {current_project_id}: {e}")
            st.warning("Could not load project progress")
    
    def _render_project_actions(self):
        """Render project action buttons."""
        current_project_id = self.session_manager.get('current_project_id')
        if not current_project_id:
            return
        
        st.markdown("#### ⚡ Quick Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Resume Project", key="resume_project_btn"):
                self._resume_project(current_project_id)
            
            if st.button("📤 Export Project", key="export_project_btn"):
                self._export_project(current_project_id)
        
        with col2:
            if st.button("🗑️ Delete Project", key="delete_project_btn"):
                self._delete_project(current_project_id)
            
            if st.button("📦 Archive Project", key="archive_project_btn"):
                self._archive_project(current_project_id)
    
    def _switch_project(self, project: Dict[str, Any]):
        """Switch to a different project."""
        try:
            # Confirm switch if current work might be lost
            if (self.session_manager.get('is_initialized') and 
                self.session_manager.get('current_project_id') and 
                not st.session_state.get('switch_confirmed', False)):
                
                st.warning("⚠️ Switching projects will lose unsaved work in the current session!")
                if st.button("Confirm Switch", key="confirm_switch"):
                    st.session_state.switch_confirmed = True
                    st.rerun()
                return
            
            # Reset confirmation flag
            if 'switch_confirmed' in st.session_state:
                del st.session_state.switch_confirmed
            
            # Update project context
            self.session_manager.set('current_project_id', project['id'])
            self.session_manager.set('current_project_name', project['name'])
            
            # Reset session state for new project
            self.session_manager.reset_project_state()
            
            st.success(f"Switched to project: {project['name']}")
            st.rerun()
            
        except Exception as e:
            logger.error(f"Failed to switch project: {e}")
            st.error(f"Failed to switch project: {str(e)}")
    
    def _clear_current_project(self):
        """Clear current project selection."""
        self.session_manager.set('current_project_id', None)
        self.session_manager.set('current_project_name', None)
        self.session_manager.reset_project_state()
        st.rerun()
    
    def _resume_project(self, project_id: str):
        """Resume a project by loading its state."""
        try:
            with st.spinner("Resuming project..."):
                project_data = asyncio.run(self.project_service.resume_project(project_id))
                
                # Restore session state from project data
                self._restore_session_from_project(project_data)
                
                st.success("Project resumed successfully!")
                st.rerun()
                
        except Exception as e:
            logger.error(f"Failed to resume project {project_id}: {e}")
            st.error(f"Failed to resume project: {str(e)}")
    
    def _export_project(self, project_id: str):
        """Export project in selected format."""
        export_format = st.selectbox(
            "Export Format",
            ["markdown", "zip", "html"],
            key="export_format_selector"
        )
        
        if st.button("Download Export", key="download_export_btn"):
            try:
                with st.spinner(f"Exporting project as {export_format}..."):
                    export_data = asyncio.run(self.project_service.export_project(project_id, export_format))
                    
                    # Determine filename and MIME type
                    project_name = self.session_manager.get('current_project_name', 'project')
                    if export_format == "markdown":
                        filename = f"{project_name}.md"
                        mime_type = "text/markdown"
                    elif export_format == "zip":
                        filename = f"{project_name}.zip"
                        mime_type = "application/zip"
                    elif export_format == "html":
                        filename = f"{project_name}.html"
                        mime_type = "text/html"
                    
                    st.download_button(
                        label=f"📥 Download {export_format.upper()}",
                        data=export_data,
                        file_name=filename,
                        mime=mime_type,
                        key="download_btn"
                    )
                    
            except Exception as e:
                logger.error(f"Failed to export project {project_id}: {e}")
                st.error(f"Failed to export project: {str(e)}")
    
    def _delete_project(self, project_id: str):
        """Delete a project with confirmation."""
        st.warning("⚠️ This action cannot be undone!")
        
        confirm_delete = st.text_input(
            "Type 'DELETE' to confirm",
            key="delete_confirmation_input"
        )
        
        if confirm_delete == "DELETE" and st.button("🗑️ Permanently Delete", key="confirm_delete_btn"):
            try:
                with st.spinner("Deleting project..."):
                    asyncio.run(self.project_service.delete_project(project_id))
                    
                    # Clear current project if it was the deleted one
                    if self.session_manager.get('current_project_id') == project_id:
                        self._clear_current_project()
                    
                    st.success("Project deleted successfully!")
                    st.rerun()
                    
            except Exception as e:
                logger.error(f"Failed to delete project {project_id}: {e}")
                st.error(f"Failed to delete project: {str(e)}")
    
    def _archive_project(self, project_id: str):
        """Archive or unarchive a project."""
        # Check if project is currently archived
        projects = self.session_manager.get('available_projects', [])
        current_project = next((p for p in projects if p['id'] == project_id), None)
        is_archived = current_project.get('archived', False) if current_project else False
        
        action = "Unarchive" if is_archived else "Archive"
        
        if st.button(f"📦 {action} Project", key="toggle_archive_btn"):
            try:
                with st.spinner(f"{action.lower()}ing project..."):
                    asyncio.run(self.project_service.archive_project(project_id, not is_archived))
                    
                    st.success(f"Project {action.lower()}d successfully!")
                    st.rerun()
                    
            except Exception as e:
                logger.error(f"Failed to {action.lower()} project {project_id}: {e}")
                st.error(f"Failed to {action.lower()} project: {str(e)}")
    
    def _restore_session_from_project(self, project_data: Dict[str, Any]):
        """Restore session state from project data."""
        # Map project data to session state
        milestones = project_data.get('milestones', {})
        
        # Basic project info
        self.session_manager.set('project_name', project_data.get('name'))
        self.session_manager.set('selected_model', project_data.get('metadata', {}).get('model_used', 'gemini'))
        
        # Restore milestones
        if 'outline_generated' in milestones:
            self.session_manager.set('generated_outline', milestones['outline_generated'].get('data'))
            
        if 'draft_completed' in milestones:
            self.session_manager.set('final_draft', milestones['draft_completed'].get('data'))
            
        if 'blog_refined' in milestones:
            refined_data = milestones['blog_refined'].get('data', {})
            self.session_manager.set('refined_draft', refined_data.get('content'))
            self.session_manager.set('summary', refined_data.get('summary'))
            self.session_manager.set('title_options', refined_data.get('title_options'))
            
        if 'social_generated' in milestones:
            self.session_manager.set('social_content', milestones['social_generated'].get('data'))
        
        # Set initialization flag
        self.session_manager.set('is_initialized', True)
        self.session_manager.set('status_message', "Project resumed successfully!")