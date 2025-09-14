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
            # Temporarily disabled - progress endpoint not yet implemented in backend
            # with st.spinner("Loading project progress..."):
            #     progress_data = asyncio.run(self.project_service.get_project_progress(current_project_id))
            
            # st.markdown("#### 📊 Progress")
            
            # # Overall progress bar
            # overall_progress = progress_data.get('overall_progress', 0)
            # st.progress(overall_progress / 100.0, text=f"Overall: {overall_progress}%")
            
            # # Milestone indicators
            # milestones = progress_data.get('milestones', {})
            pass  # Progress display temporarily disabled
            
            # cols = st.columns(5)
            # milestone_names = ['Upload', 'Outline', 'Draft', 'Refined', 'Social']
            # milestone_keys = ['files_uploaded', 'outline_generated', 'draft_completed', 'blog_refined', 'social_generated']
            
            # for i, (name, key) in enumerate(zip(milestone_names, milestone_keys)):
            #     with cols[i]:
            #         completed = milestones.get(key, {}).get('completed', False)
            #         if completed:
            #             st.success(f"✅ {name}")
            #         else:
            #             st.info(f"⏳ {name}")
            
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
                st.session_state["delete_mode"] = current_project_id
                st.rerun()
            
            if st.button("📦 Archive Project", key="archive_project_btn"):
                self._archive_project(current_project_id)
        
        # Show delete confirmation if in delete mode
        if st.session_state.get("delete_mode") == current_project_id:
            st.markdown("---")
            self._delete_project(current_project_id)
    
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
                resume_data = asyncio.run(self.project_service.resume_project(project_id))
                
                # Set the job_id first (critical for workflow continuation)
                job_id = resume_data.get('job_id')
                if job_id:
                    self.session_manager.set('job_id', job_id)
                    
                    # Now fetch the actual job state content
                    try:
                        job_status = asyncio.run(self.project_service.get_job_status(job_id))
                        self._restore_content_from_job_state(job_status)
                    except Exception as job_err:
                        logger.warning(f"Could not fetch job state content: {job_err}")
                        # Continue with basic resume data
                
                # Restore session state from project data
                self._restore_session_from_project(resume_data)
                
                # Set the next step hint for user guidance
                next_step = resume_data.get('next_step', 'Unknown')
                self.session_manager.set('status_message', f"Project resumed! Next step: {next_step}")
                
                st.success(f"Project resumed successfully! Next step: {next_step}")
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
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("❌ Cancel", key="cancel_delete_btn"):
                st.session_state.pop("delete_mode", None)
                st.rerun()
        
        with col2:
            if confirm_delete == "DELETE" and st.button("🗑️ Permanently Delete", key="confirm_delete_btn"):
                try:
                    with st.spinner("Deleting project..."):
                        asyncio.run(self.project_service.delete_project(project_id))
                        
                        # Clear current project if it was the deleted one
                        if self.session_manager.get('current_project_id') == project_id:
                            self._clear_current_project()
                        
                        # Clear delete mode
                        st.session_state.pop("delete_mode", None)
                        
                        st.success("Project deleted successfully!")
                        st.rerun()
                        
                except Exception as e:
                    logger.error(f"Failed to delete project {project_id}: {e}")
                    st.error(f"Failed to delete project: {str(e)}")
                    st.session_state.pop("delete_mode", None)
    
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
    
    def _restore_session_from_project(self, resume_data: Dict[str, Any]):
        """Restore session state from resume data."""
        # Handle both direct milestones format and nested project format
        if 'project' in resume_data:
            # New format: resume_data contains nested project data
            project_data = resume_data['project']
            milestones = project_data.get('milestones', {})
        else:
            # Legacy format: resume_data is the project data directly
            project_data = resume_data
            milestones = resume_data.get('milestones', {})
        
        # Basic project info
        self.session_manager.set('current_project_id', project_data.get('id') or resume_data.get('project_id'))
        self.session_manager.set('current_project_name', project_data.get('name') or resume_data.get('project_name'))
        self.session_manager.set('project_name', project_data.get('name') or resume_data.get('project_name'))
        self.session_manager.set('selected_model', project_data.get('metadata', {}).get('model_used', 'gemini'))
        
        # Restore milestones (check both formats)
        if 'outline_generated' in milestones:
            outline_data = milestones['outline_generated'].get('data')
            self.session_manager.set('generated_outline', outline_data)
            # Set total_sections for frontend navigation
            if outline_data and isinstance(outline_data, dict):
                sections = outline_data.get('sections', [])
                self.session_manager.set('total_sections', len(sections))
                logger.info(f"Restored outline with {len(sections)} sections from milestones")
        elif resume_data.get('has_outline'):
            # Backend indicates outline exists, but we may need to fetch it separately
            pass
            
        if 'draft_completed' in milestones:
            self.session_manager.set('final_draft', milestones['draft_completed'].get('data'))
        elif resume_data.get('has_draft'):
            # Backend indicates draft exists, but we may need to fetch it separately
            pass
            
        if 'blog_refined' in milestones:
            refined_data = milestones['blog_refined'].get('data', {})
            self.session_manager.set('refined_draft', refined_data.get('content'))
            self.session_manager.set('summary', refined_data.get('summary'))
            self.session_manager.set('title_options', refined_data.get('title_options'))
        elif resume_data.get('has_refined'):
            # Backend indicates refined content exists, but we may need to fetch it separately
            pass
            
        if 'social_generated' in milestones:
            self.session_manager.set('social_content', milestones['social_generated'].get('data'))
        
        # Set default session variables for workflow navigation
        if not self.session_manager.get('current_section_index'):
            self.session_manager.set('current_section_index', 0)
        if not self.session_manager.get('generated_sections'):
            self.session_manager.set('generated_sections', {})
        
        # Set initialization flag
        self.session_manager.set('is_initialized', True)
        
    def _restore_content_from_job_state(self, job_status: Dict[str, Any]):
        """Restore actual content from job state cache."""
        try:
            # Restore outline if available
            if job_status.get('has_outline'):
                outline_data = job_status.get('outline')
                if outline_data:
                    self.session_manager.set('generated_outline', outline_data)
                    # Set total_sections for frontend navigation
                    if isinstance(outline_data, dict):
                        sections = outline_data.get('sections', [])
                        self.session_manager.set('total_sections', len(sections))
                        logger.info(f"Restored outline with {len(sections)} sections from job state")
                    else:
                        logger.info("Restored outline from job state")
                    
            # Restore draft if available  
            if job_status.get('has_final_draft'):
                final_draft = job_status.get('final_draft')
                if final_draft:
                    self.session_manager.set('final_draft', final_draft)
                    logger.info("Restored final draft from job state")
                    
            # Restore refined content if available
            if job_status.get('has_refined_draft'):
                refined_draft = job_status.get('refined_draft')
                summary = job_status.get('summary')
                title_options = job_status.get('title_options')
                
                if refined_draft:
                    self.session_manager.set('refined_draft', refined_draft)
                    logger.info("Restored refined draft from job state")
                if summary:
                    self.session_manager.set('summary', summary)
                if title_options:
                    self.session_manager.set('title_options', title_options)
                    
            # Restore social content if available
            social_content = job_status.get('social_content')
            if social_content:
                self.session_manager.set('social_content', social_content)
                logger.info("Restored social content from job state")
            
            # Restore generated sections if available
            generated_sections = job_status.get('generated_sections', {})
            if generated_sections:
                self.session_manager.set('generated_sections', generated_sections)
                logger.info(f"Restored {len(generated_sections)} generated sections from job state")
                
            # Set current section index based on progress
            current_section_index = job_status.get('current_section_index', 0)
            self.session_manager.set('current_section_index', current_section_index)
                
        except Exception as e:
            logger.error(f"Error restoring content from job state: {e}")
            # Don't fail the entire resume process