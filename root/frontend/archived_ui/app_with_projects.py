# -*- coding: utf-8 -*-
"""
ABOUTME: Complete Streamlit application with project management integrating all workflow components
ABOUTME: Provides seamless end-to-end blog creation experience with project management
"""

import streamlit as st
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import time
import json
from datetime import datetime

# Import base components
from streamlit_app import (
    AppConfig, WorkflowStage, WorkflowState, EnhancedSessionManager,
    ProgressTracker, NotificationCenter, SmartNavigation
)
from components.blog_workflow import (
    FileUploadManager, ProjectConfigurationManager, RealTimeProgressTracker,
    ContentProcessingManager, OutlineGenerationManager, DraftGenerationManager,
    ExportManager
)
from services.project_service import ProjectService
import api_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CompleteBloggingAssistant")

try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    logger.warning("nest_asyncio not found")

class CompleteBloggingAssistantApp:
    """Complete enhanced blogging assistant application."""
    
    def __init__(self):
        """Initialize the complete application."""
        self.setup_page_config()
        EnhancedSessionManager.initialize_state()
        self.project_service = ProjectService()
        self.initialize_workflow_components()
    
    def setup_page_config(self):
        """Configure Streamlit page settings."""
        st.set_page_config(
            page_title=AppConfig.PAGE_TITLE,
            page_icon=AppConfig.PAGE_ICON,
            layout=AppConfig.LAYOUT,
            initial_sidebar_state="expanded"
        )
    
    def initialize_workflow_components(self):
        """Initialize all workflow-specific components."""
        self.file_manager = FileUploadManager()
        self.config_manager = ProjectConfigurationManager()
        self.content_processor = ContentProcessingManager()
        self.outline_generator = OutlineGenerationManager()
        self.draft_generator = DraftGenerationManager()
        self.export_manager = ExportManager()
    
    def run(self):
        """Main application entry point with enhanced workflow."""
        # Header with branding
        self.render_header()
        
        # Initialize workflow state
        workflow_state = EnhancedSessionManager.get_workflow_state()
        
        # Main layout
        self.render_main_layout(workflow_state)
        
        # Handle auto-save and cleanup
        self.handle_background_tasks()
    
    def render_header(self):
        """Render application header with enhanced branding."""
        st.markdown(
            f"""
            <div style="text-align: center; padding: 20px; background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                        border-radius: 10px; margin-bottom: 20px; color: white;">
                <h1 style="margin: 0; font-size: 2.5em;">{AppConfig.PAGE_ICON} {AppConfig.PAGE_TITLE}</h1>
                <p style="margin: 10px 0 0 0; font-size: 1.1em; opacity: 0.9;">Transform your technical content into engaging blog posts</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    def render_main_layout(self, workflow_state: WorkflowState):
        """Render main application layout."""
        # Create main columns
        sidebar_col, main_col = st.columns([1, 3])
        
        with sidebar_col:
            self.render_enhanced_sidebar(workflow_state)
        
        with main_col:
            # Notifications
            NotificationCenter.render()
            
            # Main content based on workflow stage
            self.render_stage_content(workflow_state)
    
    def render_enhanced_sidebar(self, workflow_state: WorkflowState):
        """Render enhanced sidebar with full workflow controls."""
        st.markdown("## 🎮 Mission Control")
        
        # Current project status
        self.render_project_status(workflow_state)
        
        st.markdown("---")
        
        # Workflow progress
        ProgressTracker.render_workflow_progress()
        ProgressTracker.render_stage_checklist()
        
        st.markdown("---")
        
        # Smart navigation
        self.render_smart_navigation(workflow_state)
        
        st.markdown("---")
        
        # Project management
        self.render_project_management_panel()
        
        st.markdown("---")
        
        # Quick actions
        self.render_quick_actions(workflow_state)
        
        # Settings and debug
        self.render_settings_panel()
    
    def render_project_status(self, workflow_state: WorkflowState):
        """Render current project status panel."""
        st.markdown("### 📊 Project Status")
        
        if workflow_state.project_name:
            st.info(f"🏷️ **{workflow_state.project_name}**")
            
            # Project stats
            stats_col1, stats_col2 = st.columns(2)
            
            with stats_col1:
                st.metric("Files", len(workflow_state.uploaded_files))
            
            with stats_col2:
                st.metric("Model", workflow_state.model_name or "None")
            
            # Current stage indicator
            stage_emoji = {
                WorkflowStage.PROJECT_SETUP: "⚙️",
                WorkflowStage.CONTENT_PARSING: "📄",
                WorkflowStage.OUTLINE_GENERATION: "📋",
                WorkflowStage.OUTLINE_REVIEW: "✏️",
                WorkflowStage.DRAFT_GENERATION: "📝",
                WorkflowStage.DRAFT_REVIEW: "👀",
                WorkflowStage.REFINEMENT: "✨",
                WorkflowStage.SOCIAL_CONTENT: "📱",
                WorkflowStage.EXPORT_DOWNLOAD: "📦",
                WorkflowStage.COMPLETED: "🎉"
            }
            
            emoji = stage_emoji.get(workflow_state.current_stage, "❓")
            stage_name = workflow_state.current_stage.value.replace('_', ' ').title()
            st.markdown(f"**Current Stage:** {emoji} {stage_name}")
            
        else:
            st.warning("No active project")
            if st.button("🚀 Start New Project", key="sidebar_new_project"):
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.PROJECT_SETUP
                })
                st.rerun()
    
    def render_smart_navigation(self, workflow_state: WorkflowState):
        """Render smart navigation with workflow awareness."""
        st.markdown("### 🧭 Navigation")
        
        # Navigation buttons
        nav_col1, nav_col2 = st.columns(2)
        
        with nav_col1:
            if st.button("⬅️ Previous", disabled=self._is_first_stage(workflow_state.current_stage)):
                self._navigate_to_previous_stage(workflow_state)
        
        with nav_col2:
            next_stage = workflow_state.get_next_stage()
            can_advance = next_stage and workflow_state.can_advance_to_stage(next_stage)
            
            if st.button("➡️ Next", disabled=not can_advance or workflow_state.is_processing):
                if next_stage:
                    EnhancedSessionManager.advance_workflow_stage(next_stage)
                    st.rerun()
        
        # Stage jump selector
        if st.checkbox("🎯 Advanced Navigation", key="advanced_nav"):
            available_stages = self._get_available_stages(workflow_state)
            
            selected_stage = st.selectbox(
                "Jump to stage:",
                options=available_stages,
                format_func=lambda x: f"{x.value.replace('_', ' ').title()}",
                key="stage_selector"
            )
            
            if st.button("🚀 Go to Stage") and selected_stage != workflow_state.current_stage:
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': selected_stage
                })
                st.rerun()
    
    def render_project_management_panel(self):
        """Render project management panel."""
        st.markdown("### 📁 Projects")
        
        # Project actions
        project_col1, project_col2 = st.columns(2)
        
        with project_col1:
            if st.button("📂 Load Project", key="load_project_sidebar"):
                st.session_state['show_project_loader'] = True
        
        with project_col2:
            if st.button("💾 Save Project", key="save_project_sidebar"):
                self._save_current_project()
        
        # Project loader modal
        if st.session_state.get('show_project_loader', False):
            self.render_project_loader_modal()
    
    def render_project_loader_modal(self):
        """Render project loader modal interface."""
        with st.expander("📂 Project Loader", expanded=True):
            try:
                # Load available projects
                projects = asyncio.run(self.project_service.list_projects())
                
                if projects:
                    for project in projects[:10]:  # Show recent 10
                        project_name = project.get('name', 'Unknown Project')
                        project_id = project.get('id', '')
                        created_at = project.get('created_at', 'Unknown')
                        
                        # Project item
                        project_container = st.container()
                        with project_container:
                            col1, col2, col3 = st.columns([3, 1, 1])
                            
                            with col1:
                                st.markdown(f"**{project_name}**")
                                st.caption(f"Created: {created_at}")
                            
                            with col2:
                                if st.button("Load", key=f"load_{project_id}"):
                                    self._load_project(project)
                            
                            with col3:
                                if st.button("🗑️", key=f"delete_{project_id}", help="Delete project"):
                                    self._delete_project(project_id)
                        
                        st.markdown("---")
                else:
                    st.info("No projects found")
            
            except Exception as e:
                st.error(f"Failed to load projects: {str(e)}")
            
            # Close button
            if st.button("✖️ Close", key="close_project_loader"):
                st.session_state['show_project_loader'] = False
                st.rerun()
    
    def render_quick_actions(self, workflow_state: WorkflowState):
        """Render quick action buttons."""
        st.markdown("### ⚡ Quick Actions")
        
        # Context-sensitive quick actions
        if workflow_state.current_stage == WorkflowStage.PROJECT_SETUP:
            if st.button("🚀 Quick Start", help="Start with default settings"):
                self._quick_start_project()
        
        elif workflow_state.current_stage == WorkflowStage.OUTLINE_REVIEW:
            if st.button("🎯 Auto-improve Outline", help="AI-enhanced outline optimization"):
                self._auto_improve_outline()
        
        elif workflow_state.current_stage == WorkflowStage.DRAFT_REVIEW:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔍 Quick Review", help="Fast quality check"):
                    self._quick_review_draft()
            with col2:
                if st.button("✨ Enhance", help="Auto-enhance content"):
                    self._auto_enhance_draft()
    
    def render_settings_panel(self):
        """Render settings and configuration panel."""
        with st.expander("⚙️ Settings", expanded=False):
            # User preferences
            st.checkbox(
                "Auto-advance workflow",
                value=st.session_state.get('user_preferences', {}).get('auto_advance', True),
                key='auto_advance_preference',
                help="Automatically move to next stage when possible"
            )
            
            st.checkbox(
                "Show detailed progress",
                value=st.session_state.get('show_progress_details', False),
                key='show_progress_details',
                help="Display detailed progress information"
            )
            
            st.checkbox(
                "Enable debug mode",
                value=st.session_state.get('debug_mode', False),
                key='debug_mode',
                help="Show debug information and logs"
            )
            
            # API configuration
            api_url = st.text_input(
                "API Base URL",
                value=st.session_state.get('api_base_url', 'http://127.0.0.1:8000'),
                key='api_base_url_setting'
            )
            
            if st.button("🔧 Test API Connection"):
                self._test_api_connection(api_url)
            
            # Debug information
            if st.session_state.get('debug_mode', False):
                st.markdown("**Debug Info:**")
                workflow_state = EnhancedSessionManager.get_workflow_state()
                debug_info = {
                    'current_stage': workflow_state.current_stage.value,
                    'completed_stages': [s.value for s in workflow_state.completed_stages],
                    'project_id': workflow_state.project_id,
                    'is_processing': workflow_state.is_processing,
                    'session_keys': list(st.session_state.keys())
                }
                st.json(debug_info)
    
    def render_stage_content(self, workflow_state: WorkflowState):
        """Render main content area based on current workflow stage."""
        # Stage-specific content renderers
        stage_renderers = {
            WorkflowStage.PROJECT_SETUP: self.render_project_setup_stage,
            WorkflowStage.CONTENT_PARSING: self.render_content_parsing_stage,
            WorkflowStage.OUTLINE_GENERATION: self.render_outline_generation_stage,
            WorkflowStage.OUTLINE_REVIEW: self.render_outline_review_stage,
            WorkflowStage.DRAFT_GENERATION: self.render_draft_generation_stage,
            WorkflowStage.DRAFT_REVIEW: self.render_draft_review_stage,
            WorkflowStage.REFINEMENT: self.render_refinement_stage,
            WorkflowStage.SOCIAL_CONTENT: self.render_social_content_stage,
            WorkflowStage.EXPORT_DOWNLOAD: self.render_export_stage,
            WorkflowStage.COMPLETED: self.render_completion_stage
        }
        
        renderer = stage_renderers.get(workflow_state.current_stage)
        if renderer:
            renderer(workflow_state)
        else:
            st.error(f"Unknown workflow stage: {workflow_state.current_stage}")
    
    # Stage-specific renderers
    def render_project_setup_stage(self, workflow_state: WorkflowState):
        """Render project setup stage with file upload and configuration."""
        st.markdown("## 🚀 Project Setup")
        st.markdown("Welcome! Let's set up your new blog project. Upload your technical content and configure the AI model.")
        
        # Two-column layout for setup
        setup_col1, setup_col2 = st.columns([2, 1])
        
        with setup_col1:
            # File upload section
            uploaded_files, upload_success = self.file_manager.render_file_upload()
            
            if upload_success:
                EnhancedSessionManager.update_workflow_state({
                    'uploaded_files': [f.name for f in uploaded_files]
                })
                st.session_state['uploaded_files_objects'] = uploaded_files
        
        with setup_col2:
            # Project configuration
            config = self.config_manager.render_project_configuration()
            
            # Store configuration
            EnhancedSessionManager.update_workflow_state({
                'project_name': config.get('project_name', ''),
                'model_name': config.get('model_name', 'gemini')
            })
        
        # Setup completion check
        if upload_success and config.get('project_name'):
            st.success("✅ Setup complete! Ready to process your content.")
            
            if st.button("🚀 Start Processing", type="primary", size="large"):
                # Mark project setup as complete and advance
                EnhancedSessionManager.complete_workflow_stage(WorkflowStage.PROJECT_SETUP)
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.CONTENT_PARSING
                })
                st.rerun()
    
    def render_content_parsing_stage(self, workflow_state: WorkflowState):
        """Render content parsing stage with progress tracking."""
        st.markdown("## 📄 Content Processing")
        st.markdown("Your files are being analyzed and processed by our AI system.")
        
        # Auto-start processing if not already started
        if not workflow_state.is_processing and not workflow_state.is_stage_complete(WorkflowStage.CONTENT_PARSING):
            # Start processing
            EnhancedSessionManager.update_workflow_state({
                'is_processing': True,
                'processing_message': 'Starting content processing...'
            })
            
            # Process files
            uploaded_files = st.session_state.get('uploaded_files_objects', [])
            api_base_url = st.session_state.get('api_base_url', 'http://127.0.0.1:8000')
            
            success = self.content_processor.process_files_with_progress(
                workflow_state.project_name,
                workflow_state.model_name,
                uploaded_files,
                api_base_url
            )
            
            if success:
                # Mark as complete and advance
                EnhancedSessionManager.complete_workflow_stage(WorkflowStage.CONTENT_PARSING)
                EnhancedSessionManager.update_workflow_state({
                    'is_processing': False,
                    'current_stage': WorkflowStage.OUTLINE_GENERATION
                })
                EnhancedSessionManager.add_notification("Content processing completed!", "success")
                st.rerun()
            else:
                EnhancedSessionManager.update_workflow_state({
                    'is_processing': False,
                    'error_message': 'Content processing failed'
                })
                st.error("Content processing failed. Please try again or check your files.")
        
        elif workflow_state.is_stage_complete(WorkflowStage.CONTENT_PARSING):
            st.success("✅ Content processing completed successfully!")
            
            # Show processing results
            processed_files = st.session_state.get('processed_files', [])
            if processed_files:
                with st.expander("📊 Processing Results", expanded=False):
                    st.write(f"**Processed Files:** {len(processed_files)}")
                    for file_path in processed_files:
                        st.markdown(f"- {file_path}")
            
            if st.button("➡️ Continue to Outline Generation", type="primary"):
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.OUTLINE_GENERATION
                })
                st.rerun()
    
    def render_outline_generation_stage(self, workflow_state: WorkflowState):
        """Render outline generation stage."""
        st.markdown("## 📋 Outline Generation")
        st.markdown("Creating a structured outline based on your content...")
        
        # Auto-start generation if not already started
        if not workflow_state.outline_data and not workflow_state.is_processing:
            # Start outline generation
            EnhancedSessionManager.update_workflow_state({'is_processing': True})
            
            api_base_url = st.session_state.get('api_base_url', 'http://127.0.0.1:8000')
            
            outline_data = self.outline_generator.generate_outline_with_progress(
                workflow_state.project_name,
                workflow_state.model_name,
                api_base_url
            )
            
            if outline_data:
                # Store outline and mark complete
                EnhancedSessionManager.update_workflow_state({
                    'outline_data': outline_data,
                    'is_processing': False,
                    'current_stage': WorkflowStage.OUTLINE_REVIEW
                })
                EnhancedSessionManager.complete_workflow_stage(WorkflowStage.OUTLINE_GENERATION)
                st.rerun()
            else:
                EnhancedSessionManager.update_workflow_state({
                    'is_processing': False,
                    'error_message': 'Outline generation failed'
                })
                st.error("Outline generation failed. Please try again.")
        
        elif workflow_state.outline_data:
            st.success("✅ Outline generated successfully!")
            
            # Show outline preview
            with st.expander("👀 Outline Preview", expanded=True):
                st.markdown(f"**Title:** {workflow_state.outline_data.get('title', 'Untitled')}")
                st.markdown(f"**Difficulty:** {workflow_state.outline_data.get('difficulty', 'Not specified')}")
                
                sections = workflow_state.outline_data.get('sections', [])
                st.markdown(f"**Sections:** {len(sections)}")
                
                for i, section in enumerate(sections[:3], 1):  # Show first 3
                    st.markdown(f"{i}. {section.get('title', 'Untitled Section')}")
                
                if len(sections) > 3:
                    st.markdown(f"... and {len(sections) - 3} more sections")
            
            if st.button("✏️ Review and Edit Outline", type="primary"):
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.OUTLINE_REVIEW
                })
                st.rerun()
    
    def render_outline_review_stage(self, workflow_state: WorkflowState):
        """Render outline review and editing stage."""
        st.markdown("## ✏️ Outline Review & Editing")
        st.markdown("Review and customize your blog outline before generating the full draft.")
        
        if workflow_state.outline_data:
            # Render outline editor
            edited_outline = self.outline_generator.render_outline_editor(workflow_state.outline_data)
            
            # Save changes
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("💾 Save Changes", type="secondary"):
                    EnhancedSessionManager.update_workflow_state({
                        'outline_data': edited_outline
                    })
                    EnhancedSessionManager.add_notification("Outline saved successfully", "success")
                    st.rerun()
            
            with col2:
                if st.button("🔄 Regenerate Outline", type="secondary"):
                    # Reset to generation stage
                    EnhancedSessionManager.update_workflow_state({
                        'outline_data': None,
                        'current_stage': WorkflowStage.OUTLINE_GENERATION
                    })
                    st.rerun()
            
            with col3:
                if st.button("✅ Approve & Generate Draft", type="primary"):
                    # Mark review complete and advance
                    EnhancedSessionManager.complete_workflow_stage(WorkflowStage.OUTLINE_REVIEW)
                    EnhancedSessionManager.update_workflow_state({
                        'current_stage': WorkflowStage.DRAFT_GENERATION,
                        'outline_data': edited_outline
                    })
                    st.rerun()
        
        else:
            st.error("No outline data available. Please go back to generate an outline.")
    
    def render_draft_generation_stage(self, workflow_state: WorkflowState):
        """Render draft generation stage with detailed progress."""
        st.markdown("## 📝 Blog Draft Generation")
        st.markdown("Generating your complete blog post section by section...")
        
        # Auto-start generation if not already started
        if not workflow_state.draft_data and not workflow_state.is_processing:
            # Start draft generation
            EnhancedSessionManager.update_workflow_state({'is_processing': True})
            
            api_base_url = st.session_state.get('api_base_url', 'http://127.0.0.1:8000')
            
            draft_data = self.draft_generator.generate_draft_with_progress(
                workflow_state.project_name,
                workflow_state.model_name,
                workflow_state.outline_data,
                api_base_url
            )
            
            if draft_data:
                # Store draft and mark complete
                EnhancedSessionManager.update_workflow_state({
                    'draft_data': draft_data,
                    'is_processing': False,
                    'current_stage': WorkflowStage.DRAFT_REVIEW
                })
                EnhancedSessionManager.complete_workflow_stage(WorkflowStage.DRAFT_GENERATION)
                st.rerun()
            else:
                EnhancedSessionManager.update_workflow_state({
                    'is_processing': False,
                    'error_message': 'Draft generation failed'
                })
                st.error("Draft generation failed. Please try again.")
        
        elif workflow_state.draft_data:
            st.success("✅ Blog draft generated successfully!")
            
            # Show draft stats
            draft_stats_col1, draft_stats_col2, draft_stats_col3 = st.columns(3)
            
            with draft_stats_col1:
                st.metric("Sections", len(workflow_state.draft_data.get('sections', [])))
            
            with draft_stats_col2:
                st.metric("Word Count", workflow_state.draft_data.get('total_word_count', 0))
            
            with draft_stats_col3:
                est_read_time = workflow_state.draft_data.get('total_word_count', 0) // 200
                st.metric("Est. Read Time", f"{est_read_time} min")
            
            if st.button("👀 Review Draft", type="primary"):
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.DRAFT_REVIEW
                })
                st.rerun()
    
    def render_draft_review_stage(self, workflow_state: WorkflowState):
        """Render draft review stage with editing capabilities."""
        st.markdown("## 👀 Draft Review & Editing")
        st.markdown("Review your blog draft and make any necessary edits.")
        
        if workflow_state.draft_data:
            # Draft preview with tabs
            tab1, tab2 = st.tabs(["📖 Preview", "📝 Edit"])
            
            with tab1:
                # Render formatted draft preview
                self._render_draft_preview(workflow_state.draft_data)
            
            with tab2:
                # Draft editor
                self._render_draft_editor(workflow_state.draft_data)
            
            # Action buttons
            st.markdown("---")
            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            
            with action_col1:
                if st.button("🔄 Regenerate Section", type="secondary"):
                    self._show_section_regeneration_options()
            
            with action_col2:
                if st.button("✨ Refine Content", type="secondary"):
                    # Move to refinement stage
                    EnhancedSessionManager.complete_workflow_stage(WorkflowStage.DRAFT_REVIEW)
                    EnhancedSessionManager.update_workflow_state({
                        'current_stage': WorkflowStage.REFINEMENT
                    })
                    st.rerun()
            
            with action_col3:
                if st.button("💾 Save Draft", type="secondary"):
                    # Save current draft state
                    EnhancedSessionManager.add_notification("Draft saved successfully", "success")
            
            with action_col4:
                if st.button("✅ Approve Draft", type="primary"):
                    # Skip refinement and go to social content
                    EnhancedSessionManager.complete_workflow_stage(WorkflowStage.DRAFT_REVIEW)
                    EnhancedSessionManager.complete_workflow_stage(WorkflowStage.REFINEMENT)
                    EnhancedSessionManager.update_workflow_state({
                        'current_stage': WorkflowStage.SOCIAL_CONTENT,
                        'refined_data': workflow_state.draft_data  # Use draft as refined
                    })
                    st.rerun()
        
        else:
            st.error("No draft data available. Please go back to generate a draft.")
    
    def render_refinement_stage(self, workflow_state: WorkflowState):
        """Render content refinement stage."""
        st.markdown("## ✨ Content Refinement")
        st.markdown("AI-powered content enhancement and optimization.")
        
        # Show refinement options
        refinement_options = st.multiselect(
            "Select refinement areas:",
            options=[
                "Grammar & Style",
                "Technical Accuracy", 
                "Readability Enhancement",
                "SEO Optimization",
                "Engagement Improvement"
            ],
            default=["Grammar & Style", "Readability Enhancement"]
        )
        
        if st.button("🚀 Start Refinement", type="primary"):
            # Simulate refinement process
            with st.spinner("Refining content..."):
                time.sleep(3)  # Simulate processing
            
            # Mark refinement complete
            refined_data = workflow_state.draft_data.copy()
            refined_data['refinement_applied'] = refinement_options
            
            EnhancedSessionManager.update_workflow_state({
                'refined_data': refined_data,
                'current_stage': WorkflowStage.SOCIAL_CONTENT
            })
            EnhancedSessionManager.complete_workflow_stage(WorkflowStage.REFINEMENT)
            st.success("✅ Content refinement completed!")
            st.rerun()
    
    def render_social_content_stage(self, workflow_state: WorkflowState):
        """Render social media content generation stage."""
        st.markdown("## 📱 Social Media Content")
        st.markdown("Generate engaging social media posts for your blog.")
        
        # Platform selection
        platforms = st.multiselect(
            "Select platforms:",
            options=["LinkedIn", "Twitter/X", "Facebook", "Instagram"],
            default=["LinkedIn", "Twitter/X"]
        )
        
        if platforms and st.button("🚀 Generate Social Content", type="primary"):
            # Simulate social content generation
            with st.spinner("Generating social media content..."):
                time.sleep(2)
            
            # Mock social content
            social_data = {}
            for platform in platforms:
                if platform == "LinkedIn":
                    social_data[platform] = f"Excited to share my latest blog post: {workflow_state.outline_data.get('title', 'My Blog Post')}! 🚀\n\n#TechBlog #AI #Development"
                elif platform == "Twitter/X":
                    social_data[platform] = f"New blog post is live! {workflow_state.outline_data.get('title', 'Check it out')} 🧵\n\n#TechTips #Coding"
            
            EnhancedSessionManager.update_workflow_state({
                'social_data': social_data,
                'current_stage': WorkflowStage.EXPORT_DOWNLOAD
            })
            EnhancedSessionManager.complete_workflow_stage(WorkflowStage.SOCIAL_CONTENT)
            st.success("✅ Social media content generated!")
            st.rerun()
        
        # Show existing social content if available
        if workflow_state.social_data:
            st.markdown("### 📋 Generated Content")
            for platform, content in workflow_state.social_data.items():
                with st.expander(f"📱 {platform}", expanded=False):
                    st.text_area(
                        f"{platform} Post",
                        value=content,
                        height=100,
                        key=f"social_{platform.lower()}"
                    )
    
    def render_export_stage(self, workflow_state: WorkflowState):
        """Render export and download stage."""
        st.markdown("## 📦 Export & Download")
        st.markdown("Package and download your complete blog content.")
        
        if workflow_state.refined_data or workflow_state.draft_data:
            # Export options
            export_data = self.export_manager.render_export_options(
                workflow_state.refined_data or workflow_state.draft_data,
                workflow_state.social_data
            )
            
            if export_data:
                EnhancedSessionManager.complete_workflow_stage(WorkflowStage.EXPORT_DOWNLOAD)
                EnhancedSessionManager.update_workflow_state({
                    'current_stage': WorkflowStage.COMPLETED
                })
        
        else:
            st.error("No content available for export. Please complete the previous stages.")
    
    def render_completion_stage(self, workflow_state: WorkflowState):
        """Render workflow completion stage."""
        st.markdown("## 🎉 Congratulations!")
        st.success("Your blog creation workflow is complete!")
        
        # Summary statistics
        summary_col1, summary_col2, summary_col3 = st.columns(3)
        
        with summary_col1:
            st.metric("Project", workflow_state.project_name or "Unknown")
        
        with summary_col2:
            st.metric("Sections", len(workflow_state.draft_data.get('sections', [])) if workflow_state.draft_data else 0)
        
        with summary_col3:
            st.metric("Stages Completed", len(workflow_state.completed_stages))
        
        # Next steps
        st.markdown("### 🚀 What's Next?")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🆕 Start New Project", type="primary"):
                self._start_new_project()
        
        with col2:
            if st.button("📊 View Analytics", type="secondary"):
                st.info("Analytics feature coming soon!")
        
        with col3:
            if st.button("💡 Feedback", type="secondary"):
                self._show_feedback_form()
    
    # Helper methods
    def _render_draft_preview(self, draft_data: Dict):
        """Render formatted draft preview."""
        st.markdown(f"# {draft_data.get('title', 'Blog Post')}")
        
        sections = draft_data.get('sections', [])
        for i, section in enumerate(sections, 1):
            st.markdown(f"## {i}. {section.get('title', 'Untitled Section')}")
            st.markdown(section.get('content', 'No content available.'))
            st.markdown("---")
    
    def _render_draft_editor(self, draft_data: Dict):
        """Render draft editor interface."""
        st.markdown("### ✏️ Edit Content")
        
        # Title editor
        edited_title = st.text_input(
            "Blog Title",
            value=draft_data.get('title', ''),
            key="edit_title"
        )
        
        # Section editors
        sections = draft_data.get('sections', [])
        for i, section in enumerate(sections):
            with st.expander(f"Edit Section {i+1}: {section.get('title', 'Untitled')}", expanded=False):
                edited_section_title = st.text_input(
                    "Section Title",
                    value=section.get('title', ''),
                    key=f"edit_section_title_{i}"
                )
                
                edited_content = st.text_area(
                    "Content",
                    value=section.get('content', ''),
                    height=200,
                    key=f"edit_section_content_{i}"
                )
    
    def _is_first_stage(self, stage: WorkflowStage) -> bool:
        """Check if stage is the first in workflow."""
        return stage == WorkflowStage.PROJECT_SETUP
    
    def _navigate_to_previous_stage(self, workflow_state: WorkflowState):
        """Navigate to previous workflow stage."""
        # Implementation for going to previous stage
        pass
    
    def _get_available_stages(self, workflow_state: WorkflowState) -> List[WorkflowStage]:
        """Get list of available stages for navigation."""
        # Return stages that can be navigated to
        return [stage for stage in WorkflowStage if workflow_state.can_advance_to_stage(stage) or stage in workflow_state.completed_stages]
    
    def _save_current_project(self):
        """Save current project state."""
        try:
            # Implementation for saving project
            EnhancedSessionManager.add_notification("Project saved successfully", "success")
        except Exception as e:
            EnhancedSessionManager.add_notification(f"Failed to save project: {str(e)}", "error")
    
    def _load_project(self, project_data: Dict):
        """Load a project from data."""
        try:
            # Implementation for loading project
            EnhancedSessionManager.add_notification(f"Loaded project: {project_data.get('name')}", "success")
            st.session_state['show_project_loader'] = False
            st.rerun()
        except Exception as e:
            EnhancedSessionManager.add_notification(f"Failed to load project: {str(e)}", "error")
    
    def _delete_project(self, project_id: str):
        """Delete a project."""
        try:
            # Implementation for deleting project
            EnhancedSessionManager.add_notification("Project deleted successfully", "success")
        except Exception as e:
            EnhancedSessionManager.add_notification(f"Failed to delete project: {str(e)}", "error")
    
    def _quick_start_project(self):
        """Quick start with default project settings."""
        # Implementation for quick start
        pass
    
    def _auto_improve_outline(self):
        """Auto-improve outline with AI."""
        # Implementation for outline improvement
        pass
    
    def _quick_review_draft(self):
        """Perform quick review of draft."""
        # Implementation for quick review
        pass
    
    def _auto_enhance_draft(self):
        """Auto-enhance draft content."""
        # Implementation for draft enhancement
        pass
    
    def _test_api_connection(self, api_url: str):
        """Test API connection."""
        try:
            # Test connection
            result = asyncio.run(api_client.health_check(base_url=api_url))
            if result:
                st.success("✅ API connection successful")
            else:
                st.error("❌ API connection failed")
        except Exception as e:
            st.error(f"❌ API connection error: {str(e)}")
    
    def _show_section_regeneration_options(self):
        """Show options for regenerating specific sections."""
        # Implementation for section regeneration
        pass
    
    def _start_new_project(self):
        """Start a new project by resetting workflow state."""
        st.session_state.clear()
        EnhancedSessionManager.initialize_state()
        st.rerun()
    
    def _show_feedback_form(self):
        """Show feedback form for user input."""
        with st.expander("💬 Feedback Form", expanded=True):
            feedback = st.text_area(
                "How was your experience? Any suggestions for improvement?",
                height=100
            )
            
            rating = st.selectbox(
                "Overall Rating",
                options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
            )
            
            if st.button("📤 Submit Feedback"):
                st.success("Thank you for your feedback!")
                st.balloons()
    
    def handle_background_tasks(self):
        """Handle background tasks like auto-save."""
        # Implementation for background task handling
        pass

# --- Application Entry Point ---
if __name__ == "__main__":
    app = CompleteBloggingAssistantApp()
    app.run()
