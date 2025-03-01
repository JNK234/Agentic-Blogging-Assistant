import streamlit as st
import os
import sys
import asyncio
import json
import logging
from datetime import datetime
sys.path.append(".")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("BloggingAssistant")

from pathlib import Path
from dotenv import load_dotenv
from root.backend.models.model_factory import ModelFactory
from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.outline_generator.state import FinalOutline

print(os.listdir())

load_dotenv()

# 2. Constants and Configuration
class AppConfig:
    UPLOAD_PATH = Path("root/data/uploads")
    PAGE_TITLE = "Agentic Blogging Assistant"
    PAGE_ICON = "📝"
    LAYOUT = "wide"

# 3. State Management
class SessionManager:
    @staticmethod
    def initialize_state():
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'messages': [],
                'model': None,
                'notebook_path': None,
                'markdown_path': None,
                'current_tab': "Outline Generator",
                'generated_outline': None,
                'content_parser': None,
                'notebook_content': None,
                'markdown_content': None,
                'notebook_hash': None,
                'markdown_hash': None,
                'project_name': None,
                'draft_sections': [],
                'current_section': None,
                'draft_generation_status': None,
                'draft_complete': False,
                'final_draft': None,
                'show_section_content': False,  # New flag to control section content display
                'sections_generated': [],
                'current_section_index': 0
            }
    
    @staticmethod
    def get(key, default=None):
        return st.session_state.app_state.get(key, default)
    
    @staticmethod
    def set(key, value):
        st.session_state.app_state[key] = value

# 4. UI Components
class SidebarUI:
    def render(self):
        with st.sidebar:
            st.title("Agentic Blogging Assistant")
            st.markdown("Configure your blogging assistant.")

            # Form in sidebar
            with st.form("config_form"):
                # Blog project name
                blog_name = st.text_input("Blog Project Name")
                
                # LLM type selection
                llm_provider = st.selectbox(
                    "Select LLM Provider",
                    ["Deepseek", "Claude", "OpenAI"]
                )
                
                # File uploaders
                notebook_file = st.file_uploader("Upload Jupyter Notebook", type=["ipynb"])
                markdown_file = st.file_uploader("Upload Markdown Notes", type=["md"])
                
                # Submit button
                submit_button = st.form_submit_button("Initialize Assistant")

            # Handle form submission
            if submit_button:
                if not blog_name:
                    st.sidebar.error("Please enter a blog project name.")
                elif not (notebook_file or markdown_file):
                    st.sidebar.error("Please upload at least one file.")
                else:
                    try:
                        # Save files
                        with st.spinner("Saving files..."):
                            saved_files = FileHandler.save_uploaded_files(blog_name, notebook_file, markdown_file)
                        
                        # Initialize the LLM model
                        with st.spinner("Initializing LLM..."):
                            try:
                                # Initialize model
                                model = ModelFactory().create_model(llm_provider)
                                SessionManager.set('model', model)
                                
                                # Store project name
                                SessionManager.set('project_name', blog_name)
                                
                                # Initialize content parser
                                content_parser = ContentParsingAgent(model)
                                asyncio.run(content_parser.initialize())
                                SessionManager.set('content_parser', content_parser)
                                
                                # Initialize outline agent
                                outline_agent = OutlineGeneratorAgent(model, content_parser)
                                asyncio.run(outline_agent.initialize())
                                SessionManager.set('outline_agent', outline_agent)
                                
                                # Initialize draft agent
                                draft_agent = BlogDraftGeneratorAgent(model, content_parser)
                                asyncio.run(draft_agent.initialize())
                                SessionManager.set('draft_agent', draft_agent)
                                
                                st.sidebar.success("Assistant initialized successfully!")
                                st.sidebar.write("Project Details:")
                                st.sidebar.write(f"- Blog Name: {blog_name}")
                                st.sidebar.write(f"- LLM Provider: {llm_provider}")
                                for file in saved_files:
                                    st.sidebar.write(f"✓ {file}")
                            except ValueError as e:
                                st.sidebar.error(f"Failed to initialize LLM: {str(e)}")
                                SessionManager.set('model', None)
                            except Exception as e:
                                st.sidebar.error(f"An error occurred: {str(e)}")
                    except Exception as e:
                        st.sidebar.error(f"An error occurred: {str(e)}")

class OutlineGeneratorUI:
    def render(self):
        st.title("Outline Generator")
        
        with st.form("outline_form"):
            st.subheader("Generate Blog Outline")
            generate_outline_button = st.form_submit_button("Generate Outline")

        # Display outline if available
        if SessionManager.get('generated_outline'):
            self._render_outline(SessionManager.get('generated_outline'))
            
            # Add button to navigate to Blog Draft tab
            def switch_to_blog_draft():
                SessionManager.set('current_tab', "Blog Draft")
                
            st.button("Continue to Blog Draft", on_click=switch_to_blog_draft)
        else:
            pass

        # Handle outline generation
        if generate_outline_button:
            async def generate():
                if not SessionManager.get('notebook_path') or not SessionManager.get('markdown_path'):
                    st.error("Please upload both Jupyter Notebook and Markdown files first.")
                elif not SessionManager.get('outline_agent') or not SessionManager.get('content_parser'):
                    st.error("Failed to initialize required agents.")
                else:
                    try:
                        project_name = SessionManager.get('project_name')
                        notebook_path = SessionManager.get('notebook_path')
                        markdown_path = SessionManager.get('markdown_path')
                        content_parser = SessionManager.get('content_parser')
                        outline_agent = SessionManager.get('outline_agent')
                        model = SessionManager.get('model')
                        
                        # Process files with content parser
                        with st.spinner("Processing input files..."):
                            notebook_hash = await content_parser.process_file_with_graph(notebook_path, project_name)
                            markdown_hash = await content_parser.process_file_with_graph(markdown_path, project_name)
                            
                            if not notebook_hash or not markdown_hash:
                                st.error("Failed to process input files")
                                return
                                
                            # Store hashes in session state
                            SessionManager.set('notebook_hash', notebook_hash)
                            SessionManager.set('markdown_hash', markdown_hash)
                        
                        # Generate outline using the content hashes
                        with st.spinner("Generating outline..."):
                            outline_json, notebook_content, markdown_content = await outline_agent.generate_outline(
                                project_name=project_name,
                                notebook_hash=notebook_hash,
                                markdown_hash=markdown_hash
                            )
                            
                            if not outline_json:
                                st.error("Outline generation failed")
                                return
                                
                            # Store processed content and outline
                            SessionManager.set('notebook_content', notebook_content)
                            SessionManager.set('markdown_content', markdown_content)
                            SessionManager.set('generated_outline', json.loads(outline_json))
                            
                            st.success("Outline generated successfully!")
                            
                            # Render the outline
                            self._render_outline(outline_json)
                            
                            # Add button to navigate to Blog Draft tab
                            def switch_to_blog_draft():
                                SessionManager.set('current_tab', "Blog Draft")
                                
                            st.button("Continue to Blog Draft", on_click=switch_to_blog_draft)

                    except Exception as e:
                        st.error(f"An error occurred: {type(e).__name__}: {str(e)}")
            
            asyncio.run(generate())

    def _render_outline(self, outline_data):
        """Render the complete outline."""
        # Handle string input
        
        # print(type(outline_data.model_dump()))
        
        if isinstance(outline_data, FinalOutline):
            outline_data = outline_data.model_dump()
        
        if isinstance(outline_data, str):
            try:
                import json
                outline_data = json.loads(outline_data)
            except json.JSONDecodeError:
                st.error("Failed to parse outline. Invalid JSON format.")
                st.text(outline_data)  # Show raw string as fallback
                return

        if not isinstance(outline_data, dict):
            st.error("Invalid outline format. Expected a dictionary.")
            return

        st.title(outline_data["title"])
        st.markdown("---")
        
        # Introduction
        st.header("Introduction")
        st.write(outline_data["introduction"])
        st.markdown("---")
        
        # Prerequisites
        self._render_prerequisites(outline_data["prerequisites"])
        st.markdown("---")
        
        # Main Sections
        st.header("Blog Content")
        for section in outline_data["sections"]:
            self._render_section(section)
        
        # Conclusion
        st.markdown("---")
        st.header("Conclusion")
        st.write(outline_data["conclusion"])

    def _render_prerequisites(self, prerequisites):
        """Render the prerequisites section."""
        with st.expander("Prerequisites", expanded=True):
            # Required Knowledge
            st.subheader("Required Knowledge")
            for item in prerequisites["required_knowledge"]:
                st.markdown(f"- {item}")
            
            # Recommended Tools
            st.subheader("Recommended Tools")
            for tool in prerequisites["recommended_tools"]:
                st.markdown(f"- {tool}")
            
            # Setup Instructions
            st.subheader("Setup Instructions")
            for instruction in prerequisites["setup_instructions"]:
                st.markdown(f"- {instruction}")

    def _render_section(self, section):
        """Render a single section of the outline."""
        with st.expander(f"{section['title']} ({section['estimated_time']})", expanded=False):
            # Subsections
            st.subheader("Subsections")
            for subsection in section["subsections"]:
                st.markdown(f"- {subsection}")
            
            # Learning Goals
            st.subheader("Learning Goals")
            for goal in section["learning_goals"]:
                st.markdown(f"- {goal}")

class BlogDraftUI:
    def render(self):
        """Render the Blog Draft Generator UI."""
        logger.info("Rendering BlogDraftUI")
        st.title("Blog Draft Generator")
        
        # Step 1: Validate prerequisites
        if not self._validate_prerequisites():
            return
            
        # Step 2: Get current state
        draft_complete = SessionManager.get('draft_complete', False)
        final_draft = SessionManager.get('final_draft')
        sections_generated = SessionManager.get('sections_generated', [])
        
        # Step 3: Render appropriate view
        if draft_complete and final_draft:
            self._render_final_draft(final_draft)
        else:
            # Display generated sections
            self._render_generated_sections(sections_generated)
            
            # Continue draft generation
            self._render_section_generation()
    
    def _validate_prerequisites(self):
        """Validate that we have all necessary data to generate a blog draft."""
        logger.info("Validating prerequisites for blog draft generation")
        
        if not SessionManager.get('generated_outline'):
            st.warning("Please generate an outline first before proceeding to draft generation.")
            return False
        
        if not SessionManager.get('notebook_content') or not SessionManager.get('markdown_content'):
            st.warning("Missing processed content. Please regenerate the outline.")
            return False
            
        return True
    
    def _render_final_draft(self, final_draft):
        """Render the final blog draft with download option."""
        logger.info("Rendering final draft view")
        st.success("Blog draft completed!")
        
        # Display the draft in a tabbed interface
        tab1, tab2 = st.tabs(["Preview", "Markdown"])
        
        with tab1:
            st.markdown(final_draft, unsafe_allow_html=True)
            
        with tab2:
            st.text_area("Markdown Content", final_draft, height=500)
        
        # Add download button
        project_name = SessionManager.get('project_name', 'blog')
        st.download_button(
            label="Download Draft",
            data=final_draft,
            file_name=f"{project_name}_draft.md",
            mime="text/markdown"
        )
        
        # Add button to start over
        if st.button("Generate New Draft"):
            SessionManager.set('draft_complete', False)
            SessionManager.set('final_draft', None)
            SessionManager.set('sections_generated', [])
            SessionManager.set('current_section_index', 0)
            st.rerun()
    
    def _render_generated_sections(self, sections_generated):
        """Render sections that have been generated so far."""
        if not sections_generated:
            return
            
        logger.info(f"Rendering {len(sections_generated)} generated sections")
        st.subheader("Generated Sections")
        
        for i, section in enumerate(sections_generated):
            with st.expander(f"Section {i+1}: {section['title']}", expanded=False):
                st.markdown(section['content'])
                
                # Add feedback form for each section
                with st.form(key=f"feedback_form_{i}"):
                    feedback = st.text_area("Provide feedback for this section:", key=f"feedback_{i}")
                    submit_feedback = st.form_submit_button("Submit Feedback & Regenerate")
                
                if submit_feedback and feedback:
                    with st.spinner(f"Regenerating section with feedback..."):
                        asyncio.run(self._regenerate_section_with_feedback(i, feedback))
    
    def _render_section_generation(self):
        """Render the section generation interface."""
        current_section_index = SessionManager.get('current_section_index', 0)
        outline = SessionManager.get('generated_outline')
        
        if current_section_index >= len(outline['sections']):
            # All sections have been generated, show compile button
            logger.info("All sections generated, showing compile button")
            if st.button("Compile Final Draft"):
                with st.spinner("Compiling final draft..."):
                    asyncio.run(self._compile_final_draft())
            return
        
        # Show progress
        progress = current_section_index / len(outline['sections'])
        st.progress(progress)
        st.write(f"Progress: {current_section_index}/{len(outline['sections'])} sections")
        
        # Get current section to generate
        current_section = outline['sections'][current_section_index]
        
        # Section generation form
        with st.form("section_form"):
            st.subheader(f"Generate Section: {current_section['title']}")
            st.write("Click the button below to generate this section of your blog draft.")
            
            # Add advanced options
            with st.expander("Advanced Options"):
                max_iterations = st.slider(
                    "Maximum iterations for this section",
                    min_value=1,
                    max_value=5,
                    value=3,
                    help="Maximum number of refinement iterations for this section"
                )
                
                quality_threshold = st.slider(
                    "Quality threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.8,
                    help="Minimum quality score required for section approval"
                )
            
            generate_section_button = st.form_submit_button(f"Generate Section {current_section_index + 1}")
        
        if generate_section_button:
            # Store advanced options in session state
            SessionManager.set('max_iterations', max_iterations)
            SessionManager.set('quality_threshold', quality_threshold)
            
            # Generate the current section
            with st.spinner(f"Generating section {current_section_index + 1}: {current_section['title']}..."):
                asyncio.run(self._generate_section(current_section_index))
    
    async def _generate_section(self, section_index):
        """Generate a single section of the blog draft."""
        logger.info(f"Generating section {section_index + 1}")
        progress_placeholder = st.empty()
        error_placeholder = st.empty()
        
        try:
            # Get required data
            outline = SessionManager.get('generated_outline')
            notebook_content = SessionManager.get('notebook_content')
            markdown_content = SessionManager.get('markdown_content')
            draft_agent = SessionManager.get('draft_agent')
            
            if not all([outline, notebook_content, markdown_content, draft_agent]):
                logger.error("Missing required data for section generation")
                error_placeholder.error("Missing required data for section generation.")
                return
            
            current_section = outline['sections'][section_index]
            
            # Show progress message
            progress_placeholder.info(f"Starting generation for section: {current_section['title']}...")
            logger.info(f"Starting generation for section: {current_section['title']}")
            
            # Reset the draft agent's state for this section to ensure fresh generation
            # This ensures we don't reuse cached state from previous generations
            if hasattr(draft_agent, 'current_state'):
                draft_agent.current_state = None
                logger.info("Reset draft agent state to ensure fresh generation")
            
            # Set a timeout for section generation (10 minutes)
            import asyncio
            try:
                # Generate the section content with timeout
                section_content = await asyncio.wait_for(
                    draft_agent.generate_section(
                        section=current_section,
                        outline=FinalOutline.model_validate(outline),
                        notebook_content=notebook_content,
                        markdown_content=markdown_content,
                        current_section_index=section_index,
                        max_iterations=SessionManager.get('max_iterations', 3),
                        quality_threshold=SessionManager.get('quality_threshold', 0.8)
                    ),
                    timeout=600  # 10 minutes timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Section generation timed out for {current_section['title']}")
                error_placeholder.error(f"Section generation timed out after 10 minutes. Please try again with fewer iterations.")
                return
            
            # Log the result for debugging
            logger.info(f"Section generation result for {current_section['title']}: {'Success' if section_content else 'Failed'}")
            
            if section_content:
                logger.info(f"Content length: {len(section_content)} characters")
                
                # Add to generated sections
                sections_generated = SessionManager.get('sections_generated', [])
                
                # Check if we're replacing an existing section or adding a new one
                existing_section_index = -1
                for i, section in enumerate(sections_generated):
                    if section['title'] == current_section['title']:
                        existing_section_index = i
                        break
                
                new_section = {
                    'title': current_section['title'],
                    'content': section_content,
                    'feedback': [],
                    'version': 1
                }
                
                if existing_section_index >= 0:
                    # Replace existing section
                    logger.info(f"Replacing existing section at index {existing_section_index}")
                    sections_generated[existing_section_index] = new_section
                else:
                    # Add new section
                    sections_generated.append(new_section)
                
                # Update session state
                SessionManager.set('sections_generated', sections_generated)
                SessionManager.set('current_section_index', section_index + 1)
                
                logger.info(f"Section {section_index + 1} ({current_section['title']}) generated successfully")
                logger.info(f"Updated sections_generated list now has {len(sections_generated)} sections")
                
                # Clear progress message and show success
                progress_placeholder.empty()
                st.success(f"Section {section_index + 1} ({current_section['title']}) generated successfully!")
                
                # Force a rerun to update the UI
                st.rerun()
            else:
                logger.error(f"Failed to generate section {section_index + 1} ({current_section['title']})")
                progress_placeholder.empty()
                error_placeholder.error(f"Failed to generate section {section_index + 1} ({current_section['title']}). Check logs for details.")
                
        except Exception as e:
            logger.exception(f"Error generating section {section_index + 1}: {str(e)}")
            progress_placeholder.empty()
            
            # Provide more helpful error message for recursion limit errors
            if "recursion limit" in str(e).lower():
                error_placeholder.error(
                    f"Error generating section {section_index + 1}: Recursion limit reached. " +
                    "This is likely due to complexity in the section. Try again with fewer iterations."
                )
            else:
                error_placeholder.error(f"Error generating section {section_index + 1}: {str(e)}")
    
    async def _regenerate_section_with_feedback(self, section_index, feedback):
        """Regenerate a section with user feedback."""
        logger.info(f"Regenerating section {section_index + 1} with feedback")
        progress_placeholder = st.empty()
        error_placeholder = st.empty()
        
        try:
            # Get required data
            outline = SessionManager.get('generated_outline')
            notebook_content = SessionManager.get('notebook_content')
            markdown_content = SessionManager.get('markdown_content')
            draft_agent = SessionManager.get('draft_agent')
            sections_generated = SessionManager.get('sections_generated', [])
            
            if not all([outline, notebook_content, markdown_content, draft_agent]) or section_index >= len(sections_generated):
                logger.error("Missing required data for section regeneration")
                error_placeholder.error("Missing required data for section regeneration.")
                return
            
            section = sections_generated[section_index]
            
            # Show progress message
            progress_placeholder.info(f"Regenerating section: {section['title']} with feedback...")
            logger.info(f"Starting regeneration for section: {section['title']} with feedback")
            
            # Reset the draft agent's state for this section to ensure fresh generation
            # This ensures we don't reuse cached state from previous generations
            if hasattr(draft_agent, 'current_state'):
                draft_agent.current_state = None
                logger.info("Reset draft agent state to ensure fresh regeneration")
            
            # Set a timeout for section regeneration (10 minutes)
            import asyncio
            try:
                # Regenerate the section with feedback and timeout
                new_content = await asyncio.wait_for(
                    draft_agent.regenerate_section_with_feedback(
                        section=outline['sections'][section_index],
                        outline=outline,
                        notebook_content=notebook_content,
                        markdown_content=markdown_content,
                        feedback=feedback,
                        max_iterations=SessionManager.get('max_iterations', 3),
                        quality_threshold=SessionManager.get('quality_threshold', 0.8)
                    ),
                    timeout=600  # 10 minutes timeout
                )
            except asyncio.TimeoutError:
                logger.error(f"Section regeneration timed out for {section['title']}")
                progress_placeholder.empty()
                error_placeholder.error(f"Section regeneration timed out after 10 minutes. Please try again with fewer iterations.")
                return
            
            # Log the result for debugging
            logger.info(f"Section regeneration result for {section['title']}: {'Success' if new_content else 'Failed'}")
            
            if new_content:
                logger.info(f"New content length: {len(new_content)} characters")
                
                # Update section with new content
                section['content'] = new_content
                section['feedback'].append({
                    'text': feedback,
                    'timestamp': datetime.now().isoformat()
                })
                section['version'] += 1
                
                # Update session state
                sections_generated[section_index] = section
                SessionManager.set('sections_generated', sections_generated)
                
                logger.info(f"Section {section_index + 1} ({section['title']}) regenerated successfully")
                
                # Clear progress message and show success
                progress_placeholder.empty()
                st.success(f"Section {section_index + 1} ({section['title']}) regenerated successfully!")
                
                # Force a rerun to update the UI
                st.rerun()
            else:
                logger.error(f"Failed to regenerate section {section_index + 1} ({section['title']})")
                progress_placeholder.empty()
                error_placeholder.error(f"Failed to regenerate section {section_index + 1} ({section['title']}). Check logs for details.")
                
        except Exception as e:
            logger.exception(f"Error regenerating section {section_index + 1}: {str(e)}")
            progress_placeholder.empty()
            
            # Provide more helpful error message for recursion limit errors
            if "recursion limit" in str(e).lower():
                error_placeholder.error(
                    f"Error regenerating section {section_index + 1}: Recursion limit reached. " +
                    "This is likely due to complexity in the section. Try again with fewer iterations."
                )
            else:
                error_placeholder.error(f"Error regenerating section {section_index + 1}: {str(e)}")
    
    async def _compile_final_draft(self):
        """Compile the final blog draft from all generated sections."""
        logger.info("Compiling final draft")
        try:
            # Get required data
            outline = SessionManager.get('generated_outline')
            sections_generated = SessionManager.get('sections_generated', [])
            
            if not outline or not sections_generated:
                logger.error("Missing required data for compiling the final draft")
                st.error("Missing required data for compiling the final draft.")
                return
            
            # Start with blog title and metadata
            blog_parts = [
                f"# {outline['title']}\n",
                f"**Difficulty Level**: {outline['difficulty_level']}\n",
                "\n## Prerequisites\n",
                f"{outline['prerequisites']}\n\n",
                "## Table of Contents\n"
            ]
            
            # Add table of contents
            for i, section in enumerate(sections_generated):
                blog_parts.append(f"{i+1}. [{section['title']}](#section-{i+1})\n")
            
            blog_parts.append("\n")
            
            # Add each section
            for i, section in enumerate(sections_generated):
                # Add section anchor and title
                blog_parts.extend([
                    f"<a id='section-{i+1}'></a>\n",
                    f"## {section['title']}\n",
                    f"{section['content']}\n\n"
                ])
            
            # Add conclusion if available
            if 'conclusion' in outline and outline['conclusion']:
                blog_parts.extend([
                    "## Conclusion\n",
                    f"{outline['conclusion']}\n\n"
                ])
            
            # Combine all parts
            final_draft = "\n".join(blog_parts)
            
            # Store the final draft
            SessionManager.set('final_draft', final_draft)
            SessionManager.set('draft_complete', True)
            
            logger.info("Final draft compiled successfully")
            st.success("Final draft compiled successfully!")
            st.rerun()
            
        except Exception as e:
            logger.exception(f"Error compiling final draft: {str(e)}")
            st.error(f"Error compiling final draft: {str(e)}")

class SettingsUI:
    def render(self):
        st.title("Settings")
        st.info("Additional settings and configurations coming soon!")

# 5. Utility Functions
class FileHandler:
    @staticmethod
    def save_uploaded_files(blog_name, notebook_file, markdown_file):
        """Save uploaded files to the appropriate directory."""
        # Create blog project directory
        blog_dir = AppConfig.UPLOAD_PATH / blog_name
        blog_dir.mkdir(parents=True, exist_ok=True)
            
        # Save files if they were uploaded
        saved_files = []
        if notebook_file is not None:
            notebook_path = blog_dir / notebook_file.name
            with open(notebook_path, "wb") as f:
                f.write(notebook_file.getbuffer())
            SessionManager.set('notebook_path', str(notebook_path))
            saved_files.append(f"Notebook: {notebook_file.name}")
                
        if markdown_file is not None:
            markdown_path = blog_dir / markdown_file.name
            with open(markdown_path, "wb") as f:
                f.write(markdown_file.getbuffer())
            SessionManager.set('markdown_path', str(markdown_path))
            saved_files.append(f"Markdown: {markdown_file.name}")
            
        return saved_files

# 6. Main Application
class BloggingAssistant:
    def __init__(self):
        self.session = SessionManager()
        self.sidebar = SidebarUI()
        self.outline_generator = OutlineGeneratorUI()
        self.blog_draft = BlogDraftUI()
        self.settings = SettingsUI()

    def setup(self):
        st.set_page_config(
            page_title=AppConfig.PAGE_TITLE,
            page_icon=AppConfig.PAGE_ICON,
            layout=AppConfig.LAYOUT
        )
        self.session.initialize_state()

    def run(self):
        self.setup()
        self.sidebar.render()

        if self.session.get('model'):
            # Create tabs
            tab_names = ["Outline Generator", "Blog Draft", "Settings"]
            outline_tab, draft_tab, settings_tab = st.tabs(tab_names)
            
            # Get current tab from session state
            current_tab = self.session.get('current_tab', tab_names[0])
            
            # Render content based on current tab
            with outline_tab:
                if current_tab == tab_names[0]:
                    self.outline_generator.render()
            
            with draft_tab:
                if current_tab == tab_names[1]:
                    self.blog_draft.render()
                
            with settings_tab:
                if current_tab == tab_names[2]:
                    self.settings.render()
        else:
            st.info("Please configure and initialize your assistant using the sidebar.")

# 7. Application Entry Point
def main():
    app = BloggingAssistant()
    app.run()

if __name__ == "__main__":
    main()
