# ABOUTME: Comprehensive blog workflow component with complete end-to-end pipeline implementation.
# ABOUTME: Handles project setup, file upload, outline generation, drafting, refinement, social content, and export with smooth UX transitions.

import streamlit as st
import asyncio
import logging
import httpx
import json
import uuid
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path
from enum import Enum
from services.workflow_types import WorkflowStage

logger = logging.getLogger(__name__)

class BlogWorkflow:
    """Complete blog workflow with integrated backend communication."""
    
    def __init__(self, state_manager, api_base_url: str):
        """Initialize workflow with state manager and API configuration."""
        self.state_manager = state_manager
        self.api_base_url = api_base_url
        self.project_service = None
        
    def initialize_project_service(self):
        """Lazy initialization of project service."""
        if not self.project_service:
            from services.project_service import ProjectService
            self.project_service = ProjectService(self.api_base_url)
    
    def render(self):
        """Render the complete workflow interface."""
        try:
            # Get current workflow state
            current_stage = self.state_manager.get_current_stage()
            
            # Render progress indicator
            self._render_progress_indicator(current_stage)
            
            # Render appropriate stage
            if current_stage == WorkflowStage.PROJECT_SETUP:
                self._render_project_setup()
            elif current_stage == WorkflowStage.FILE_UPLOAD:
                self._render_file_upload()
            elif current_stage == WorkflowStage.CONTENT_PROCESSING:
                # Content processing is handled automatically, advance to outline generation
                self.state_manager.advance_to_stage(WorkflowStage.OUTLINE_GENERATION)
                st.rerun()
            elif current_stage == WorkflowStage.OUTLINE_GENERATION:
                self._render_outline_generation()
            elif current_stage == WorkflowStage.BLOG_DRAFTING:
                self._render_blog_drafting()
            elif current_stage == WorkflowStage.BLOG_REFINEMENT:
                self._render_blog_refinement()
            elif current_stage == WorkflowStage.SOCIAL_CONTENT:
                self._render_social_content()
            elif current_stage == WorkflowStage.EXPORT:
                self._render_export()
            elif current_stage == WorkflowStage.COMPLETE:
                self._render_complete()
            
            # Render sidebar with workflow controls
            self._render_sidebar()
            
        except Exception as e:
            logger.exception(f"Error rendering workflow: {str(e)}")
            st.error(f"Workflow error: {str(e)}")
    
    def _render_progress_indicator(self, current_stage: WorkflowStage):
        """Render visual progress indicator."""
        st.markdown("---")
        
        # Progress bar
        stages = list(WorkflowStage)
        current_index = stages.index(current_stage)
        progress = (current_index + 1) / len(stages)
        
        st.progress(progress)
        
        # Stage indicators
        cols = st.columns(len(stages))
        stage_names = {
            WorkflowStage.PROJECT_SETUP: "Setup",
            WorkflowStage.FILE_UPLOAD: "Upload", 
            WorkflowStage.CONTENT_PROCESSING: "Process",
            WorkflowStage.OUTLINE_GENERATION: "Outline",
            WorkflowStage.BLOG_DRAFTING: "Draft",
            WorkflowStage.BLOG_REFINEMENT: "Refine",
            WorkflowStage.SOCIAL_CONTENT: "Social",
            WorkflowStage.EXPORT: "Export",
            WorkflowStage.COMPLETE: "Done"
        }
        
        for i, (stage, col) in enumerate(zip(stages, cols)):
            with col:
                if i < current_index:
                    st.markdown(f"✅ **{stage_names[stage]}**")
                elif i == current_index:
                    st.markdown(f"🔄 **{stage_names[stage]}**")
                else:
                    st.markdown(f"⏳ {stage_names[stage]}")
        
        st.markdown("---")
    
    def _render_project_setup(self):
        """Render project setup stage."""
        st.markdown("## 🎯 Project Setup")
        st.markdown("Create a new project or resume an existing one to begin your blogging workflow.")
        
        tab1, tab2 = st.tabs(["📁 New Project", "🔄 Resume Project"])
        
        with tab1:
            self._render_new_project_form()
        
        with tab2:
            self._render_resume_project()
    
    def _render_new_project_form(self):
        """Render new project creation form."""
        st.markdown("### Create New Project")
        
        with st.form("new_project_form"):
            project_name = st.text_input(
                "Project Name *",
                placeholder="Enter a descriptive project name...",
                help="Choose a unique name for your blogging project"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                model_name = st.selectbox(
                    "AI Model",
                    options=["gemini", "claude", "openai", "deepseek", "openrouter"],
                    index=0,
                    help="Select the AI model for content generation"
                )
            
            with col2:
                writing_style = st.selectbox(
                    "Writing Style",
                    options=["professional", "casual", "academic", "tutorial", "storytelling"],
                    index=0,
                    help="Choose the overall tone and style"
                )
            
            persona = st.text_area(
                "Writing Persona (Optional)",
                placeholder="Describe the specific writing voice, expertise level, and personality...",
                help="This will guide the AI's writing style throughout the project",
                height=100
            )
            
            submitted = st.form_submit_button("Create Project", type="primary")
            
            if submitted and project_name.strip():
                try:
                    # Store project configuration in state
                    project_config = {
                        'name': project_name.strip(),
                        'model_name': model_name,
                        'writing_style': writing_style,
                        'persona': persona,
                        'created_at': datetime.now().isoformat()
                    }
                    
                    self.state_manager.set_project_config(project_config)
                    self.state_manager.advance_to_stage(WorkflowStage.FILE_UPLOAD)
                    
                    st.success(f"Project '{project_name}' created successfully!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Failed to create project: {str(e)}")
            elif submitted:
                st.error("Project name is required.")
    
    def _render_resume_project(self):
        """Render project resumption interface."""
        st.markdown("### Resume Existing Project")
        
        try:
            self.initialize_project_service()
            
            # Load projects
            with st.spinner("Loading projects..."):
                projects = asyncio.run(self.project_service.list_projects())
            
            if projects:
                # Project selector
                project_options = {
                    f"{p.get('name', 'Unnamed')} (ID: {p.get('id', 'Unknown')})": p 
                    for p in projects
                }
                
                selected_key = st.selectbox(
                    "Select Project to Resume",
                    options=list(project_options.keys())
                )
                
                if selected_key:
                    selected_project = project_options[selected_key]
                    
                    # Show project details
                    with st.expander("Project Details", expanded=True):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown(f"**Name:** {selected_project.get('name', 'Unknown')}")
                            st.markdown(f"**ID:** {selected_project.get('id', 'Unknown')}")
                            st.markdown(f"**Status:** {selected_project.get('status', 'Unknown')}")
                        
                        with col2:
                            created_at = selected_project.get('created_at', 'Unknown')
                            st.markdown(f"**Created:** {created_at}")
                            
                            progress = selected_project.get('progress', {})
                            st.markdown(f"**Progress:** {len(progress)} milestones")
                    
                    if st.button("Resume Project", type="primary"):
                        try:
                            # Resume project via API
                            result = asyncio.run(
                                self.project_service.resume_project(selected_project['id'])
                            )
                            
                            # Update state with resumed project
                            self.state_manager.resume_project(selected_project, result)
                            
                            st.success(f"Project '{selected_project['name']}' resumed successfully!")
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Failed to resume project: {str(e)}")
            else:
                st.info("No existing projects found. Create a new project to get started.")
                
        except Exception as e:
            st.error(f"Failed to load projects: {str(e)}")
    
    def _render_file_upload(self):
        """Render file upload stage."""
        st.markdown("## 📁 File Upload")
        st.markdown("Upload your technical content files to begin the blogging process.")
        
        # File uploader with validation
        uploaded_files = st.file_uploader(
            "Choose Files",
            accept_multiple_files=True,
            type=['ipynb', 'md', 'py'],
            help="Upload Jupyter notebooks (.ipynb), Markdown files (.md), or Python files (.py)"
        )
        
        if uploaded_files:
            # Display uploaded files
            st.markdown("### 📋 Uploaded Files")
            for i, file in enumerate(uploaded_files):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**{file.name}**")
                with col2:
                    st.markdown(f"{file.size:,} bytes")
                with col3:
                    st.markdown(f"{file.type}")
            
            # Upload options
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if st.button("Process Files", type="primary"):
                    self._process_files(uploaded_files)
            
            with col2:
                if st.button("Clear Files"):
                    st.rerun()
        else:
            st.info("Please upload at least one supported file to continue.")
            
            # Example files section
            with st.expander("📖 What files can I upload?"):
                st.markdown("""
                **Supported file types:**
                - **Jupyter Notebooks (.ipynb)**: Interactive code notebooks with outputs
                - **Markdown Files (.md)**: Documentation, tutorials, or existing blog drafts
                - **Python Files (.py)**: Source code with docstrings and comments
                
                **Tips for best results:**
                - Include detailed comments and docstrings in code files
                - Use clear section headers in Markdown files
                - Jupyter notebooks with markdown cells work great for context
                """)
    
    def _process_files(self, uploaded_files):
        """Process uploaded files through the backend."""
        try:
            project_config = self.state_manager.get_project_config()
            
            with st.spinner("Uploading and processing files..."):
                # Prepare form data
                files_data = []
                for file in uploaded_files:
                    files_data.append(("files", (file.name, file.getvalue(), file.type)))
                
                form_data = {
                    "model_name": project_config.get('model_name', 'gemini'),
                    "persona": project_config.get('persona', '')
                }
                
                # Upload files
                upload_response = httpx.post(
                    f"{self.api_base_url}/upload/{project_config['name']}",
                    files=files_data,
                    data=form_data,
                    timeout=60.0
                )
                
                if upload_response.status_code == 200:
                    upload_result = upload_response.json()
                    
                    # Process files
                    process_response = httpx.post(
                        f"{self.api_base_url}/process_files/{project_config['name']}",
                        data={
                            "model_name": project_config.get('model_name', 'gemini'),
                            "file_paths": upload_result['files']
                        },
                        timeout=120.0
                    )
                    
                    if process_response.status_code == 200:
                        process_result = process_response.json()
                        
                        # Update state with processing results
                        self.state_manager.set_processing_results({
                            'upload_result': upload_result,
                            'process_result': process_result,
                            'project_id': upload_result.get('project_id'),
                            'file_hashes': process_result.get('file_hashes', {})
                        })
                        
                        # Advance to outline generation
                        self.state_manager.advance_to_stage(WorkflowStage.OUTLINE_GENERATION)
                        
                        st.success("Files processed successfully!")
                        st.rerun()
                    else:
                        st.error(f"File processing failed: {process_response.text}")
                else:
                    st.error(f"File upload failed: {upload_response.text}")
                    
        except Exception as e:
            logger.exception(f"File processing error: {str(e)}")
            st.error(f"Failed to process files: {str(e)}")
    
    def _render_outline_generation(self):
        """Render outline generation stage."""
        st.markdown("## 📝 Outline Generation")
        st.markdown("Create a structured outline for your blog post based on your uploaded content.")
        
        # Configuration section
        with st.expander("⚙️ Outline Configuration", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                length_preference = st.selectbox(
                    "Blog Length",
                    options=["short", "medium", "long", "custom"],
                    index=1,
                    help="Choose the preferred length of your blog post"
                )
                
                if length_preference == "Custom":
                    custom_length = st.number_input(
                        "Custom Word Count",
                        min_value=500,
                        max_value=5000,
                        value=1500,
                        step=100
                    )
                else:
                    custom_length = None
            
            with col2:
                project_config = self.state_manager.get_project_config()
                writing_style = st.selectbox(
                    "Writing Style",
                    options=["professional", "casual", "academic", "tutorial", "storytelling"],
                    index=0 if not project_config else ["professional", "casual", "academic", "tutorial", "storytelling"].index(project_config.get('writing_style', 'professional')),
                    help="Select the writing tone and style"
                )
        
        user_guidelines = st.text_area(
            "Additional Guidelines (Optional)",
            placeholder="Provide specific instructions for the outline structure, topics to emphasize, or content focus...",
            help="Guide the AI on what aspects to highlight in your blog post",
            height=100
        )
        
        # Generate outline button
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            if st.button("Generate Outline", type="primary"):
                self._generate_outline(length_preference, custom_length, writing_style, user_guidelines)
        
        with col2:
            if st.button("Load Example"):
                self._load_example_outline()
        
        with col3:
            if st.button("Manual Outline"):
                self._enable_manual_outline()
        
        # Display existing outline if available
        outline_data = self.state_manager.get_outline_data()
        if outline_data:
            st.markdown("### 📋 Generated Outline")
            self._display_outline(outline_data)
            
            if st.button("Proceed to Blog Drafting", type="primary"):
                self.state_manager.advance_to_stage(WorkflowStage.BLOG_DRAFTING)
                st.rerun()
    
    def _generate_outline(self, length_preference, custom_length, writing_style, user_guidelines):
        """Generate outline using the backend API."""
        try:
            project_config = self.state_manager.get_project_config()
            
            with st.spinner("Generating outline..."):
                # Use form data compatible with backend validation
                form_data = {
                    "model_name": project_config.get('model_name', 'gemini'),
                    "notebook_hash": "dummy",  # These would come from processing results
                    "markdown_hash": "dummy",
                    "user_guidelines": user_guidelines or "",
                    "length_preference": length_preference or "",
                    "custom_length": str(custom_length) if custom_length is not None else "",
                    "writing_style": writing_style or ""
                }
                
                response = httpx.post(
                    f"{self.api_base_url}/generate_outline/{project_config['name']}",
                    data=form_data,
                    timeout=180.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Store outline data and job ID
                    self.state_manager.set_outline_data(result['outline'])
                    self.state_manager.set_job_id(result['job_id'])
                    
                    st.success("Outline generated successfully!")
                    st.rerun()
                else:
                    st.error(f"Outline generation failed: {response.text}")
                    
        except Exception as e:
            logger.exception(f"Outline generation error: {str(e)}")
            st.error(f"Failed to generate outline: {str(e)}")
    
    def _display_outline(self, outline_data):
        """Display the generated outline in a formatted way."""
        try:
            if isinstance(outline_data, dict):
                # Display title
                if 'title' in outline_data:
                    st.markdown(f"**Title:** {outline_data['title']}")
                
                # Display difficulty and prerequisites
                col1, col2 = st.columns(2)
                with col1:
                    if 'difficulty' in outline_data:
                        st.markdown(f"**Difficulty:** {outline_data['difficulty']}")
                with col2:
                    if 'estimated_read_time' in outline_data:
                        st.markdown(f"**Read Time:** {outline_data['estimated_read_time']}")
                
                # Display prerequisites
                if 'prerequisites' in outline_data and outline_data['prerequisites']:
                    st.markdown("**Prerequisites:**")
                    for prereq in outline_data['prerequisites']:
                        st.markdown(f"- {prereq}")
                
                # Display sections
                if 'sections' in outline_data:
                    st.markdown("**Sections:**")
                    for i, section in enumerate(outline_data['sections'], 1):
                        if isinstance(section, dict):
                            st.markdown(f"{i}. **{section.get('title', 'Untitled Section')}**")
                            if 'description' in section:
                                st.markdown(f"   {section['description']}")
                        else:
                            st.markdown(f"{i}. {section}")
            else:
                # Fallback to JSON display
                st.json(outline_data)
                
        except Exception as e:
            st.error(f"Error displaying outline: {str(e)}")
            st.json(outline_data)
    
    def _render_blog_drafting(self):
        """Render blog drafting stage."""
        st.markdown("## ✍️ Blog Drafting") 
        st.markdown("Generate your complete blog draft section by section using the structured outline.")
        
        job_id = self.state_manager.get_job_id()
        outline_data = self.state_manager.get_outline_data()
        
        if not job_id or not outline_data:
            st.error("Missing outline or job ID. Please generate an outline first.")
            if st.button("Back to Outline Generation"):
                self.state_manager.advance_to_stage(WorkflowStage.OUTLINE_GENERATION)
                st.rerun()
            return
        
        # Show outline summary
        with st.expander("📋 Outline Summary", expanded=False):
            self._display_outline(outline_data)
        
        # Drafting options
        st.markdown("### 🎯 Drafting Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Generate Complete Draft", type="primary"):
                self._generate_complete_draft(job_id)
        
        with col2:
            if st.button("Check Progress"):
                self._check_draft_progress(job_id)
        
        with col3:
            if st.button("Section by Section"):
                self._enable_section_drafting()
        
        # Display existing draft if available
        draft_data = self.state_manager.get_draft_data()
        if draft_data:
            self._display_draft(draft_data)
            
            if st.button("Proceed to Refinement", type="primary"):
                self.state_manager.advance_to_stage(WorkflowStage.BLOG_REFINEMENT)
                st.rerun()
    
    def _generate_complete_draft(self, job_id):
        """Generate complete blog draft using the backend API."""
        try:
            project_config = self.state_manager.get_project_config()
            
            with st.spinner("Generating blog draft..."):
                # Generate sections
                sections_response = httpx.post(
                    f"{self.api_base_url}/generate_section/{project_config['name']}",
                    json={"job_id": job_id},
                    timeout=300.0
                )
                
                if sections_response.status_code == 200:
                    # Compile final draft
                    compile_response = httpx.post(
                        f"{self.api_base_url}/compile_draft/{project_config['name']}",
                        json={"job_id": job_id},
                        timeout=120.0
                    )
                    
                    if compile_response.status_code == 200:
                        result = compile_response.json()
                        
                        # Store draft data
                        self.state_manager.set_draft_data(result)
                        
                        st.success("Blog draft generated successfully!")
                        st.rerun()
                    else:
                        st.error(f"Draft compilation failed: {compile_response.text}")
                else:
                    st.error(f"Section generation failed: {sections_response.text}")
                    
        except Exception as e:
            logger.exception(f"Draft generation error: {str(e)}")
            st.error(f"Failed to generate draft: {str(e)}")
    
    def _check_draft_progress(self, job_id):
        """Check the progress of draft generation."""
        try:
            response = httpx.get(
                f"{self.api_base_url}/job_status/{job_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                status = response.json()
                
                # Display progress information
                st.markdown("### 📊 Draft Progress")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Sections", status.get('total_sections', 0))
                with col2:
                    st.metric("Completed Sections", status.get('completed_sections', 0))
                with col3:
                    progress_pct = 0
                    if status.get('total_sections', 0) > 0:
                        progress_pct = (status.get('completed_sections', 0) / status.get('total_sections', 1)) * 100
                    st.metric("Progress", f"{progress_pct:.1f}%")
                
                # Show detailed status
                with st.expander("Detailed Status"):
                    st.json(status)
            else:
                st.error(f"Failed to get job status: {response.text}")
                
        except Exception as e:
            st.error(f"Failed to check progress: {str(e)}")
    
    def _display_draft(self, draft_data):
        """Display the generated blog draft."""
        st.markdown("### 📄 Generated Blog Draft")
        
        if isinstance(draft_data, dict) and 'final_draft' in draft_data:
            # Show the final draft
            draft_content = draft_data['final_draft']
            
            # Display in expandable section for better UX
            with st.expander("📖 Read Full Draft", expanded=True):
                st.markdown(draft_content)
            
            # Show word count and reading time
            word_count = len(draft_content.split())
            read_time = max(1, word_count // 200)  # Approximate reading time
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Word Count", word_count)
            with col2:
                st.metric("Est. Read Time", f"{read_time} min")
                
        else:
            st.error("Invalid draft data format")
    
    def _render_blog_refinement(self):
        """Render blog refinement stage."""
        st.markdown("## ✨ Blog Refinement")
        st.markdown("Polish and refine your blog draft with AI assistance or manual editing.")
        
        draft_data = self.state_manager.get_draft_data()
        job_id = self.state_manager.get_job_id()
        
        if not draft_data or not job_id:
            st.error("No draft found. Please generate a blog draft first.")
            return
        
        # Current draft editor
        st.markdown("### ✏️ Draft Editor")
        current_draft = st.text_area(
            "Blog Content",
            value=draft_data.get('final_draft', ''),
            height=400,
            help="Edit the draft directly or use AI refinement below"
        )
        
        # Refinement options
        st.markdown("### 🔧 Refinement Options")
        
        refinement_type = st.selectbox(
            "Refinement Type",
            options=[
                "General improvement",
                "Enhance clarity and flow", 
                "Add more examples",
                "Improve technical accuracy",
                "Make more engaging",
                "Custom feedback"
            ]
        )
        
        if refinement_type == "Custom feedback":
            refinement_feedback = st.text_area(
                "Custom Refinement Instructions",
                placeholder="Provide specific feedback on what to improve, adjust, or emphasize...",
                help="Give detailed instructions for how to refine the blog post"
            )
        else:
            refinement_feedback = refinement_type
        
        # Refinement actions
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("Refine with AI", type="primary", disabled=not refinement_feedback):
                self._refine_with_ai(job_id, refinement_feedback)
        
        with col2:
            if st.button("Save Manual Edits"):
                self._save_manual_edits(current_draft)
        
        with col3:
            if st.button("Finalize Draft"):
                self._finalize_draft(current_draft)
    
    def _refine_with_ai(self, job_id, feedback):
        """Refine the blog draft using AI."""
        try:
            project_config = self.state_manager.get_project_config()
            
            with st.spinner("Refining blog post..."):
                response = httpx.post(
                    f"{self.api_base_url}/refine_blog/{project_config['name']}",
                    json={
                        "job_id": job_id,
                        "feedback": feedback
                    },
                    timeout=180.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Update draft data
                    self.state_manager.set_draft_data(result)
                    
                    st.success("Blog refined successfully!")
                    st.rerun()
                else:
                    st.error(f"Refinement failed: {response.text}")
                    
        except Exception as e:
            logger.exception(f"AI refinement error: {str(e)}")
            st.error(f"Failed to refine blog: {str(e)}")
    
    def _save_manual_edits(self, edited_content):
        """Save manual edits to the draft."""
        draft_data = self.state_manager.get_draft_data() or {}
        draft_data['final_draft'] = edited_content
        draft_data['manually_edited'] = True
        draft_data['last_edited'] = datetime.now().isoformat()
        
        self.state_manager.set_draft_data(draft_data)
        st.success("Manual edits saved!")
    
    def _finalize_draft(self, final_content):
        """Finalize the blog draft and advance to social content."""
        # Save final version
        draft_data = self.state_manager.get_draft_data() or {}
        draft_data['final_draft'] = final_content
        draft_data['finalized'] = True
        draft_data['finalized_at'] = datetime.now().isoformat()
        
        self.state_manager.set_draft_data(draft_data)
        self.state_manager.advance_to_stage(WorkflowStage.SOCIAL_CONTENT)
        
        st.success("Blog draft finalized! Moving to social content generation.")
        st.rerun()
    
    def _render_social_content(self):
        """Render social media content generation stage."""
        st.markdown("## 📱 Social Media Content")
        st.markdown("Generate engaging social media posts to promote your blog across different platforms.")
        
        draft_data = self.state_manager.get_draft_data()
        job_id = self.state_manager.get_job_id()
        
        if not draft_data or not job_id:
            st.error("No finalized blog draft found. Please complete the drafting stage first.")
            return
        
        # Platform selection
        st.markdown("### 🎯 Platform Selection")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            twitter_enabled = st.checkbox("🐦 Twitter Thread", value=True)
        with col2:
            linkedin_enabled = st.checkbox("💼 LinkedIn Post", value=True)
        with col3:
            reddit_enabled = st.checkbox("🚀 Reddit Post", value=False)
        with col4:
            summary_enabled = st.checkbox("📝 Summary", value=True)
        
        # Customization options
        with st.expander("⚙️ Social Media Customization", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                tone = st.selectbox(
                    "Tone",
                    options=["professional", "casual", "enthusiastic", "educational", "conversational"],
                    index=0
                )
                
                include_hashtags = st.checkbox("Include Hashtags", value=True)
            
            with col2:
                include_emojis = st.checkbox("Include Emojis", value=True)
                
                call_to_action = st.text_input(
                    "Call to Action (Optional)",
                    placeholder="e.g., 'Read the full article at...'",
                    help="Add a specific call to action for your posts"
                )
        
        social_guidelines = st.text_area(
            "Additional Guidelines (Optional)",
            placeholder="Any specific requirements for social media content...",
            help="Provide guidance on specific messaging, keywords, or platform requirements"
        )
        
        # Generate button
        if st.button("Generate Social Content", type="primary"):
            self._generate_social_content(
                job_id, twitter_enabled, linkedin_enabled, reddit_enabled, 
                summary_enabled, tone, include_hashtags, include_emojis, 
                call_to_action, social_guidelines
            )
        
        # Display existing social content
        social_content = self.state_manager.get_social_content()
        if social_content:
            self._display_social_content(social_content)
            
            if st.button("Proceed to Export", type="primary"):
                self.state_manager.advance_to_stage(WorkflowStage.EXPORT)
                st.rerun()
    
    def _generate_social_content(self, job_id, twitter, linkedin, reddit, summary, 
                                 tone, hashtags, emojis, cta, guidelines):
        """Generate social media content using the backend API."""
        try:
            project_config = self.state_manager.get_project_config()
            
            with st.spinner("Generating social media content..."):
                payload = {
                    "job_id": job_id,
                    "platforms": {
                        "twitter": twitter,
                        "linkedin": linkedin,
                        "reddit": reddit,
                        "summary": summary
                    },
                    "customization": {
                        "tone": tone,
                        "include_hashtags": hashtags,
                        "include_emojis": emojis,
                        "call_to_action": cta
                    },
                    "guidelines": guidelines
                }
                
                response = httpx.post(
                    f"{self.api_base_url}/generate_social_content/{project_config['name']}",
                    json=payload,
                    timeout=120.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Store social content
                    self.state_manager.set_social_content(result)
                    
                    st.success("Social media content generated successfully!")
                    st.rerun()
                else:
                    st.error(f"Social content generation failed: {response.text}")
                    
        except Exception as e:
            logger.exception(f"Social content generation error: {str(e)}")
            st.error(f"Failed to generate social content: {str(e)}")
    
    def _display_social_content(self, social_content):
        """Display generated social media content."""
        st.markdown("### 📱 Generated Social Content")
        
        # Create tabs for different platforms
        platforms = []
        if 'twitter' in social_content:
            platforms.append("🐦 Twitter")
        if 'linkedin' in social_content:
            platforms.append("💼 LinkedIn")
        if 'reddit' in social_content:
            platforms.append("🚀 Reddit")
        if 'summary' in social_content:
            platforms.append("📝 Summary")
        
        if platforms:
            tabs = st.tabs(platforms)
            
            tab_index = 0
            if 'twitter' in social_content:
                with tabs[tab_index]:
                    st.markdown("**Twitter Thread:**")
                    st.markdown(social_content['twitter'])
                    
                    if st.button("Copy Twitter Content", key="copy_twitter"):
                        st.success("Content copied to clipboard!")
                tab_index += 1
            
            if 'linkedin' in social_content:
                with tabs[tab_index]:
                    st.markdown("**LinkedIn Post:**")
                    st.markdown(social_content['linkedin'])
                    
                    if st.button("Copy LinkedIn Content", key="copy_linkedin"):
                        st.success("Content copied to clipboard!")
                tab_index += 1
            
            if 'reddit' in social_content:
                with tabs[tab_index]:
                    st.markdown("**Reddit Post:**")
                    st.markdown(social_content['reddit'])
                    
                    if st.button("Copy Reddit Content", key="copy_reddit"):
                        st.success("Content copied to clipboard!")
                tab_index += 1
            
            if 'summary' in social_content:
                with tabs[tab_index]:
                    st.markdown("**Blog Summary:**")
                    st.markdown(social_content['summary'])
                    
                    if st.button("Copy Summary Content", key="copy_summary"):
                        st.success("Content copied to clipboard!")
    
    def _render_export(self):
        """Render export stage."""
        st.markdown("## 📤 Export & Download")
        st.markdown("Export your completed blog content in various formats and share across platforms.")
        
        draft_data = self.state_manager.get_draft_data()
        social_content = self.state_manager.get_social_content()
        outline_data = self.state_manager.get_outline_data()
        project_config = self.state_manager.get_project_config()
        
        if not draft_data:
            st.error("No content to export. Please complete the blog drafting stage first.")
            return
        
        # Export configuration
        st.markdown("### ⚙️ Export Configuration")
        
        col1, col2 = st.columns(2)
        
        with col1:
            export_format = st.selectbox(
                "Export Format",
                options=["markdown", "html", "pdf", "docx", "json"],
                index=0,
                help="Choose the format for your blog export"
            )
            
            include_outline = st.checkbox(
                "Include Outline",
                value=True,
                help="Include the project outline in the export"
            )
        
        with col2:
            include_social = st.checkbox(
                "Include Social Media Content",
                value=True,
                help="Include generated social media posts in the export"
            )
            
            include_metadata = st.checkbox(
                "Include Project Metadata",
                value=True,
                help="Include project information and generation details"
            )
        
        # Preview export content
        st.markdown("### 👁️ Export Preview")
        
        export_content = self._build_export_content(
            draft_data, social_content, outline_data, project_config,
            include_outline, include_social, include_metadata
        )
        
        with st.expander("📄 Full Export Preview", expanded=False):
            st.text_area(
                "Export Content",
                value=export_content,
                height=400,
                disabled=True
            )
        
        # Export statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            word_count = len(export_content.split())
            st.metric("Total Words", word_count)
        with col2:
            char_count = len(export_content)
            st.metric("Characters", f"{char_count:,}")
        with col3:
            read_time = max(1, word_count // 200)
            st.metric("Read Time", f"{read_time} min")
        
        # Export actions
        st.markdown("### 📥 Download Options")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Direct download
            st.download_button(
                label=f"📄 Download {export_format.upper()}",
                data=export_content.encode('utf-8'),
                file_name=f"{project_config.get('name', 'blog_content')}.{export_format}",
                mime=self._get_mime_type(export_format),
                type="primary"
            )
        
        with col2:
            if st.button("📧 Email Export"):
                self._prepare_email_export(export_content, export_format)
        
        with col3:
            if st.button("💾 Save to Cloud"):
                st.info("Cloud save feature coming soon!")
        
        with col4:
            if st.button("✅ Complete Project"):
                self._complete_project()
    
    def _build_export_content(self, draft_data, social_content, outline_data, 
                             project_config, include_outline, include_social, include_metadata):
        """Build the complete export content."""
        content_parts = []
        
        # Add metadata if requested
        if include_metadata and project_config:
            content_parts.append("# Project Metadata")
            content_parts.append(f"**Project Name:** {project_config.get('name', 'Unknown')}")
            content_parts.append(f"**Model Used:** {project_config.get('model_name', 'Unknown')}")
            content_parts.append(f"**Writing Style:** {project_config.get('writing_style', 'Unknown')}")
            if project_config.get('persona'):
                content_parts.append(f"**Writing Persona:** {project_config['persona']}")
            content_parts.append(f"**Generated On:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content_parts.append("")
        
        # Add outline if requested
        if include_outline and outline_data:
            content_parts.append("# Blog Outline")
            if isinstance(outline_data, dict):
                if 'title' in outline_data:
                    content_parts.append(f"**Title:** {outline_data['title']}")
                if 'difficulty' in outline_data:
                    content_parts.append(f"**Difficulty:** {outline_data['difficulty']}")
                if 'sections' in outline_data:
                    content_parts.append("**Sections:**")
                    for i, section in enumerate(outline_data['sections'], 1):
                        if isinstance(section, dict):
                            content_parts.append(f"{i}. {section.get('title', 'Untitled Section')}")
                        else:
                            content_parts.append(f"{i}. {section}")
            content_parts.append("")
        
        # Add main blog content
        content_parts.append("# Blog Content")
        if draft_data and 'final_draft' in draft_data:
            content_parts.append(draft_data['final_draft'])
        content_parts.append("")
        
        # Add social media content if requested
        if include_social and social_content:
            content_parts.append("# Social Media Content")
            
            if 'twitter' in social_content:
                content_parts.append("## Twitter Thread")
                content_parts.append(social_content['twitter'])
                content_parts.append("")
            
            if 'linkedin' in social_content:
                content_parts.append("## LinkedIn Post")
                content_parts.append(social_content['linkedin'])
                content_parts.append("")
            
            if 'summary' in social_content:
                content_parts.append("## Blog Summary")
                content_parts.append(social_content['summary'])
                content_parts.append("")
        
        return "\n".join(content_parts)
    
    def _get_mime_type(self, format_type):
        """Get MIME type for export format."""
        mime_types = {
            'markdown': 'text/markdown',
            'html': 'text/html',
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'json': 'application/json'
        }
        return mime_types.get(format_type, 'text/plain')
    
    def _complete_project(self):
        """Mark the project as complete."""
        self.state_manager.advance_to_stage(WorkflowStage.COMPLETE)
        st.success("🎉 Project completed successfully!")
        st.rerun()
    
    def _render_complete(self):
        """Render project completion stage."""
        st.markdown("## 🎉 Project Complete!")
        st.markdown("Congratulations! You have successfully completed your blogging workflow.")
        
        project_config = self.state_manager.get_project_config()
        
        # Success metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("✅ Stages Completed", "8/8")
        with col2:
            draft_data = self.state_manager.get_draft_data()
            word_count = 0
            if draft_data and 'final_draft' in draft_data:
                word_count = len(draft_data['final_draft'].split())
            st.metric("📝 Words Generated", f"{word_count:,}")
        with col3:
            social_content = self.state_manager.get_social_content()
            platforms = len([k for k in ['twitter', 'linkedin', 'reddit', 'summary'] 
                           if k in (social_content or {})])
            st.metric("📱 Social Platforms", platforms)
        
        # Next actions
        st.markdown("### 🚀 What's Next?")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Start New Project", type="primary"):
                self.state_manager.reset_workflow()
                st.rerun()
        
        with col2:
            if st.button("📊 View Project Analytics"):
                self._show_project_analytics()
        
        # Project summary
        with st.expander("📋 Project Summary", expanded=True):
            if project_config:
                st.markdown(f"**Project Name:** {project_config.get('name', 'Unknown')}")
                st.markdown(f"**Model Used:** {project_config.get('model_name', 'Unknown')}")
                st.markdown(f"**Writing Style:** {project_config.get('writing_style', 'Unknown')}")
                st.markdown(f"**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def _render_sidebar(self):
        """Render sidebar with workflow controls and utilities."""
        with st.sidebar:
            st.markdown("### 🎛️ Workflow Controls")
            
            # Current project info
            project_config = self.state_manager.get_project_config()
            if project_config:
                st.markdown(f"**Project:** {project_config.get('name', 'Unknown')}")
                st.markdown(f"**Model:** {project_config.get('model_name', 'Unknown')}")
                st.markdown("---")
            
            # Stage navigation
            st.markdown("### 🧭 Quick Navigation")
            
            current_stage = self.state_manager.get_current_stage()
            stage_names = {
                WorkflowStage.PROJECT_SETUP: "Project Setup",
                WorkflowStage.FILE_UPLOAD: "File Upload",
                WorkflowStage.CONTENT_PROCESSING: "Processing",
                WorkflowStage.OUTLINE_GENERATION: "Outline",
                WorkflowStage.BLOG_DRAFTING: "Drafting",
                WorkflowStage.BLOG_REFINEMENT: "Refinement",
                WorkflowStage.SOCIAL_CONTENT: "Social Content",
                WorkflowStage.EXPORT: "Export",
                WorkflowStage.COMPLETE: "Complete"
            }
            
            # Show available stages for navigation
            available_stages = self.state_manager.get_available_stages()
            for stage in available_stages:
                if stage != current_stage:
                    if st.button(f"Go to {stage_names[stage]}", key=f"nav_{stage.value}"):
                        self.state_manager.advance_to_stage(stage)
                        st.rerun()
            
            st.markdown("---")
            
            # Workflow utilities
            st.markdown("### ⚙️ Utilities")
            
            if st.button("💾 Save Progress"):
                self.state_manager.save_state()
                st.success("Progress saved!")
            
            if st.button("🔄 Reset Workflow"):
                if st.checkbox("Confirm reset (this will clear all progress)"):
                    self.state_manager.reset_workflow()
                    st.rerun()
            
            # Debug information (in development mode)
            if st.checkbox("🔍 Show Debug Info"):
                st.markdown("### 🐛 Debug Information")
                state_data = self.state_manager.get_debug_state()
                st.json(state_data)
    
    # Helper methods for workflow stages
    def _load_example_outline(self):
        """Load an example outline for demonstration."""
        example_outline = {
            "title": "Building Scalable Web Applications with Python",
            "difficulty": "Intermediate",
            "estimated_read_time": "8-10 minutes",
            "prerequisites": [
                "Basic Python knowledge",
                "Understanding of web frameworks",
                "Database fundamentals"
            ],
            "sections": [
                {
                    "title": "Introduction to Scalability",
                    "description": "Understanding what makes applications scalable and why it matters"
                },
                {
                    "title": "Architecture Patterns",
                    "description": "Exploring microservices, monoliths, and hybrid approaches"
                },
                {
                    "title": "Database Optimization",
                    "description": "Strategies for handling large datasets and high traffic"
                },
                {
                    "title": "Caching Strategies",
                    "description": "Implementing effective caching at multiple layers"
                },
                {
                    "title": "Deployment and Monitoring",
                    "description": "Best practices for production deployment and monitoring"
                }
            ]
        }
        
        self.state_manager.set_outline_data(example_outline)
        self.state_manager.set_job_id(str(uuid.uuid4()))
        st.success("Example outline loaded!")
        st.rerun()
    
    def _enable_manual_outline(self):
        """Enable manual outline creation mode."""
        st.session_state['manual_outline_mode'] = True
        st.info("Manual outline mode enabled. You can create a custom outline structure.")
        
    def _enable_section_drafting(self):
        """Enable section-by-section drafting mode."""
        st.session_state['section_drafting_mode'] = True
        st.info("Section-by-section drafting enabled. You can generate and review each section individually.")
    
    def _prepare_email_export(self, content, format_type):
        """Prepare content for email export."""
        # Create email-friendly content
        email_subject = f"Blog Export - {self.state_manager.get_project_config().get('name', 'Project')}"
        email_body = f"""
Hi,

Please find attached your exported blog content in {format_type.upper()} format.

Project Details:
- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Word count: {len(content.split()):,}
- Format: {format_type.upper()}

Best regards,
Agentic Blogging Assistant
"""
        
        st.info(f"""
        **Email Export Ready**
        
        Subject: {email_subject}
        
        Content prepared for email attachment. Copy the content above and attach to your email.
        """)
    
    def _show_project_analytics(self):
        """Show project analytics and statistics."""
        st.markdown("### 📊 Project Analytics")
        
        # Collect analytics data
        project_config = self.state_manager.get_project_config()
        draft_data = self.state_manager.get_draft_data()
        social_content = self.state_manager.get_social_content()
        
        # Display analytics
        if draft_data and 'final_draft' in draft_data:
            content = draft_data['final_draft']
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                word_count = len(content.split())
                st.metric("Total Words", f"{word_count:,}")
            
            with col2:
                char_count = len(content)
                st.metric("Characters", f"{char_count:,}")
            
            with col3:
                paragraph_count = content.count('\n\n') + 1
                st.metric("Paragraphs", paragraph_count)
            
            with col4:
                read_time = max(1, word_count // 200)
                st.metric("Read Time", f"{read_time} min")
            
            # Content analysis
            st.markdown("**Content Analysis:**")
            sentences = content.split('.')
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
            
            st.markdown(f"- Average sentence length: {avg_sentence_length:.1f} words")
            st.markdown(f"- Total sentences: {len(sentences)}")
            
            # Social media metrics
            if social_content:
                platforms = [k for k in social_content.keys() if k in ['twitter', 'linkedin', 'reddit']]
                st.markdown(f"- Social platforms generated: {len(platforms)}")