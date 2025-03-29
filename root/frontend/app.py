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
from root.backend.services.vector_store_service import VectorStoreService # Added import

load_dotenv()

# 2. Constants and Configuration
class AppConfig:
    # Use relative path from the project root
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
                'current_section_index': 0,
                'outline_was_cached': False,    # Added to track outline caching status
                'files_were_cached': False      # Added to track file caching status
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
                    ["Deepseek", "Claude", "OpenAI", "Gemini", "openrouter"] # Added Gemini
                )
                
                # OpenRouter specific settings
                openrouter_model = None
                max_tokens = None
                temperature = None
                
                if llm_provider == "OpenRouter":
                    openrouter_model = st.selectbox(
                        "Select OpenRouter Model",
                        [
                            "openrouter/auto",  # Default auto-selection
                            "anthropic/claude-3-opus",
                            "anthropic/claude-3-sonnet",
                            "anthropic/claude-3-haiku",
                            "google/gemini-pro",
                            "meta-llama/llama-2-70b-chat",
                            "mistral/mistral-medium",
                            "mistral/mistral-small"
                        ]
                    )
                    temperature = st.slider(
                        "Temperature",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.7,
                        step=0.1,
                        help="Controls randomness in the output. Higher values make the output more random, lower values make it more deterministic."
                    )
                    max_tokens = st.number_input(
                        "Max Tokens",
                        min_value=100,
                        max_value=4096,
                        value=1000,
                        step=100,
                        help="Maximum number of tokens to generate"
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
                                model_factory = ModelFactory()
                                
                                model = model_factory.create_model(llm_provider.lower())
                                SessionManager.set('model', model)
                                
                                # Store project name
                                SessionManager.set('project_name', blog_name)
                                
                                # Create and initialize all agents in a single async operation
                                async def initialize_agents():
                                    # Initialize content parser
                                    content_parser = ContentParsingAgent(model)
                                    await content_parser.initialize()
                                    
                                    # Initialize outline agent
                                    outline_agent = OutlineGeneratorAgent(model, content_parser)
                                    await outline_agent.initialize()
                                    
                                    # Initialize draft agent
                                    draft_agent = BlogDraftGeneratorAgent(model, content_parser)
                                    await draft_agent.initialize()
                                    
                                    return content_parser, outline_agent, draft_agent
                                
                                # Run initialization and store results
                                content_parser, outline_agent, draft_agent = asyncio.run(initialize_agents())
                                SessionManager.set('content_parser', content_parser)
                                SessionManager.set('outline_agent', outline_agent)
                                SessionManager.set('draft_agent', draft_agent)
                                
                                st.sidebar.success("Assistant initialized successfully!")
                                
                                # Show a notification if cached files were used
                                if SessionManager.get('files_were_cached', False):
                                    st.sidebar.info("♻️ Using cached content from previously processed files")
                                    
                                st.sidebar.write("Project Details:")
                                st.sidebar.write(f"- Blog Name: {blog_name}")
                                st.sidebar.write(f"- LLM Provider: {llm_provider}")
                                for file in saved_files:
                                    st.sidebar.write(f"✓ {file}")
                            except ValueError as e:
                                logger.error(f"SidebarUI.render: Failed to initialize LLM: {str(e)}", exc_info=True)
                                st.sidebar.error(f"Failed to initialize LLM: {str(e)}")
                                SessionManager.set('model', None)
                            except Exception as e:
                                logger.error(f"SidebarUI.render: Error during LLM/agent initialization: {str(e)}", exc_info=True)
                                st.sidebar.error(f"An error occurred during initialization: {str(e)}")
                    except Exception as e:
                        logger.error(f"SidebarUI.render: Error saving files: {str(e)}", exc_info=True)
                        st.sidebar.error(f"An error occurred while saving files: {str(e)}")

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
            # Check prerequisites synchronously first
            if not (SessionManager.get('notebook_path') or SessionManager.get('markdown_path')):
                st.error("Please upload at least one file (Jupyter Notebook or Markdown) first.")
            elif not SessionManager.get('outline_agent') or not SessionManager.get('content_parser'):
                st.error("Failed to initialize required agents.")
            else:
                # Define the async workflow
                async def generate_outline_async():
                    try:
                        project_name = SessionManager.get('project_name')
                        notebook_path = SessionManager.get('notebook_path')
                        markdown_path = SessionManager.get('markdown_path')
                        content_parser = SessionManager.get('content_parser')
                        outline_agent = SessionManager.get('outline_agent')
                        
                        # Get existing content hashes from session state if available
                        # Retrieve paths from session state
                        notebook_path = SessionManager.get('notebook_path')
                        markdown_path = SessionManager.get('markdown_path')
                        
                        # Initialize hashes to None
                        processed_notebook_hash = None
                        processed_markdown_hash = None

                        # Always attempt to process files if paths exist.
                        # The content_parser agent has internal checks to avoid reprocessing.
                        if notebook_path:
                            with st.spinner("Processing notebook file (checking cache)..."):
                                logger.info(f"Ensuring notebook file is processed: {notebook_path}")
                                # process_file_with_graph returns the hash if processed or found in cache
                                processed_notebook_hash = await content_parser.process_file_with_graph(notebook_path, project_name)
                                if processed_notebook_hash:
                                    SessionManager.set('notebook_hash', processed_notebook_hash) # Update session hash
                                    logger.info(f"Notebook hash confirmed/processed: {processed_notebook_hash}")
                                else:
                                    logger.error(f"Failed to process notebook: {notebook_path}")
                                    st.error(f"Failed to process notebook: {Path(notebook_path).name}")
                                    
                        if markdown_path:
                            with st.spinner("Processing markdown file (checking cache)..."):
                                logger.info(f"Ensuring markdown file is processed: {markdown_path}")
                                # process_file_with_graph returns the hash if processed or found in cache
                                processed_markdown_hash = await content_parser.process_file_with_graph(markdown_path, project_name)
                                if processed_markdown_hash:
                                    SessionManager.set('markdown_hash', processed_markdown_hash) # Update session hash
                                    logger.info(f"Markdown hash confirmed/processed: {processed_markdown_hash}")
                                else:
                                    logger.error(f"Failed to process markdown: {markdown_path}")
                                    st.error(f"Failed to process markdown: {Path(markdown_path).name}")

                        # Check if we have at least one valid content source *after* processing attempts
                        if not processed_notebook_hash and not processed_markdown_hash:
                            st.error("Failed to process any input files")
                            return
                        
                        # Log cache key components for debugging using the processed hashes
                        cache_key_components = {
                            "project_name": project_name,
                            "notebook_hash": processed_notebook_hash,
                            "markdown_hash": processed_markdown_hash
                        }
                        logger.info(f"Cache key components: {cache_key_components}")

                        # Generate outline using the processed content hashes
                        with st.spinner("Generating outline..."):
                            outline_result, notebook_content, markdown_content, was_cached = await outline_agent.generate_outline(
                                project_name=project_name,
                                notebook_hash=processed_notebook_hash, # Use processed hash
                                markdown_hash=processed_markdown_hash  # Use processed hash
                            )

                            # Store cache status for UI notification
                            SessionManager.set('outline_was_cached', was_cached)

                            # --- Start: Ensure content is loaded if outline was cached ---
                            if was_cached:
                                logger.info("Outline was retrieved from cache. Verifying content availability...")
                                vector_store = VectorStoreService() # Initialize service to fetch content

                                # Check and fetch notebook content if needed
                                if processed_notebook_hash and not notebook_content:
                                    logger.info(f"Notebook content missing for cached outline. Fetching using hash: {processed_notebook_hash}")
                                    try:
                                        # Fetch content based on hash and project name
                                        cached_docs = vector_store.search_content(
                                            metadata_filter={
                                                "content_hash": processed_notebook_hash,
                                                "project_name": project_name,
                                                "file_type": ".ipynb" # Ensure correct file type
                                            },
                                            limit=1 # Expecting only one match
                                        )
                                        if cached_docs:
                                            # Assuming the content is stored in page_content or similar field
                                            # Adjust based on actual vector store document structure
                                            notebook_content = cached_docs[0].get("page_content")
                                            if notebook_content:
                                                logger.info("Successfully fetched cached notebook content.")
                                            else:
                                                logger.warning("Fetched document for notebook hash, but content field is missing/empty.")
                                        else:
                                            logger.warning(f"Could not find cached notebook content for hash: {processed_notebook_hash}")
                                    except Exception as fetch_err:
                                        logger.error(f"Error fetching cached notebook content: {fetch_err}", exc_info=True)

                                # Check and fetch markdown content if needed
                                if processed_markdown_hash and not markdown_content:
                                    logger.info(f"Markdown content missing for cached outline. Fetching using hash: {processed_markdown_hash}")
                                    try:
                                        # Fetch content based on hash and project name
                                        cached_docs = vector_store.search_content(
                                            metadata_filter={
                                                "content_hash": processed_markdown_hash,
                                                "project_name": project_name,
                                                "file_type": ".md" # Ensure correct file type
                                            },
                                            limit=1 # Expecting only one match
                                        )
                                        if cached_docs:
                                            # Assuming the content is stored in page_content or similar field
                                            markdown_content = cached_docs[0].get("page_content")
                                            if markdown_content:
                                                logger.info("Successfully fetched cached markdown content.")
                                            else:
                                                logger.warning("Fetched document for markdown hash, but content field is missing/empty.")
                                        else:
                                            logger.warning(f"Could not find cached markdown content for hash: {processed_markdown_hash}")
                                    except Exception as fetch_err:
                                        logger.error(f"Error fetching cached markdown content: {fetch_err}", exc_info=True)
                            # --- End: Ensure content is loaded if outline was cached ---

                            if not outline_result or (isinstance(outline_result, str) and "error" in outline_result.lower()):
                                st.error(f"Outline generation failed: {outline_result}")
                                return

                            # Handle different return types (ensure this happens *after* potential content fetching)
                            if isinstance(outline_result, str):
                                try:
                                    # Try to parse as JSON
                                    outline_obj = json.loads(outline_result)
                                except json.JSONDecodeError:
                                    st.error(f"Invalid outline format: {outline_result}")
                                    return
                            else:
                                # Already an object
                                outline_obj = outline_result
                            
                            # Store processed content and outline
                            SessionManager.set('notebook_content', notebook_content)
                            SessionManager.set('markdown_content', markdown_content)
                            SessionManager.set('generated_outline', outline_obj)
                            
                            return True
                    except Exception as e:
                        logger.exception(f"OutlineGeneratorUI.generate_outline_async: Error generating outline: {str(e)}")
                        st.error(f"An error occurred during outline generation: {type(e).__name__}: {str(e)}")
                        return False
                
                # Run the async workflow and handle the result
                if asyncio.run(generate_outline_async()):
                    # Show appropriate success message based on cache status
                    if SessionManager.get('outline_was_cached', False):
                        st.success("✅ Outline retrieved from cache!")
                        st.info("Using cached outline from previous generation with the same content.")
                    else:
                        st.success("✅ Outline generated successfully!")
                    
                    # Render the outline
                    self._render_outline(SessionManager.get('generated_outline'))
                    
                    # Add button to navigate to Blog Draft tab
                    def switch_to_blog_draft():
                        SessionManager.set('current_tab', "Blog Draft")
                        
                    st.button("Continue to Blog Draft", on_click=switch_to_blog_draft)

    def _render_outline(self, outline_data):
        """Render the complete outline."""
        # Handle different input types to ensure consistent dictionary format
        try:
            # Case 1: It's a FinalOutline object
            if isinstance(outline_data, FinalOutline):
                outline_data = outline_data.model_dump()
            
            # Case 2: It's a string (JSON)
            elif isinstance(outline_data, str):
                try:
                    outline_data = json.loads(outline_data)
                except json.JSONDecodeError:
                    st.error("Failed to parse outline. Invalid JSON format.")
                    st.text(outline_data)  # Show raw string as fallback
                    return
            
            # Case 3: Neither a dict nor any of above
            if not isinstance(outline_data, dict):
                st.error(f"Invalid outline format. Expected dictionary but got {type(outline_data)}.")
                st.text(str(outline_data))  # Show raw value as fallback
                return
                
            # At this point, outline_data should be a dictionary
            logger.info(f"Rendering outline: {outline_data.get('title', 'Untitled')}")
            
        except json.JSONDecodeError as e:
            logger.error(f"OutlineGeneratorUI._render_outline: Failed to parse outline JSON: {str(e)}", exc_info=True)
            st.error(f"Failed to parse outline data: Invalid JSON format.")
            st.text(str(outline_data)) # Show raw data as fallback
            return
        except Exception as e:
            logger.exception(f"OutlineGeneratorUI._render_outline: Error processing outline data: {str(e)}")
            st.error(f"Error processing outline data: {type(e).__name__}: {str(e)}")
            st.text(str(outline_data)) # Show raw data as fallback
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
            if prerequisites.get("setup_instructions") is None or not prerequisites.get("setup_instructions"):
                st.markdown("No setup instructions provided.")
            else:
                for instruction in prerequisites.get("setup_instructions"):
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
        
        # Check if at least one content source is available
        notebook_content_present = SessionManager.get('notebook_content') is not None
        markdown_content_present = SessionManager.get('markdown_content') is not None
        
        if not notebook_content_present and not markdown_content_present:
            st.warning("Missing processed content for both notebook and markdown. Please regenerate the outline or check file processing.")
            logger.warning("Validation failed: Neither notebook nor markdown content is available.")
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
                # Create a placeholder for real-time progress updates
                progress_message = st.empty()
                progress_message.info("Starting generation...")
                
                # Run the async operation
                result = asyncio.run(self._generate_section(current_section_index, progress_callback=progress_message.info))
                
                # Clear progress message on completion
                progress_message.empty()
                
                if not result:
                    st.error(f"Failed to generate section {current_section_index + 1}")
                else:
                    st.success(f"Section {current_section_index + 1} generated successfully!")
    
    async def _generate_section(self, section_index, progress_callback=None):
        """Generate a single section of the blog draft.
        
        Args:
            section_index: Index of the section to generate
            progress_callback: Optional function to call with status updates
        
        Returns:
            Boolean indicating success or failure
        """
        logger.info(f"Generating section {section_index + 1}")
        
        # Use callback if provided, otherwise create placeholders
        if progress_callback:
            def update_progress(msg):
                logger.info(msg)
                progress_callback(msg)
        else:
            progress_placeholder = st.empty()
            def update_progress(msg):
                logger.info(msg)
                progress_placeholder.info(msg)
                
        error_placeholder = st.empty()
        
        try:
            # Get required data
            outline = SessionManager.get('generated_outline')
            notebook_content = SessionManager.get('notebook_content')
            markdown_content = SessionManager.get('markdown_content')
            draft_agent = SessionManager.get('draft_agent')
            
            # Check for essential components and at least one content source
            if not outline or not draft_agent or (not notebook_content and not markdown_content):
                missing_items = []
                if not outline: missing_items.append("outline")
                if not draft_agent: missing_items.append("draft_agent")
                if not notebook_content and not markdown_content: missing_items.append("notebook/markdown content")
                
                error_message = f"Missing required data for section generation: {', '.join(missing_items)}"
                logger.error(error_message)
                error_placeholder.error(error_message)
                return False # Return False on failure
            
            current_section = outline['sections'][section_index]
            
            # Show progress message
            update_progress(f"Starting generation for section: {current_section['title']}...")
            
            # Reset the draft agent's state for this section to ensure fresh generation
            # This ensures we don't reuse cached state from previous generations
            if hasattr(draft_agent, 'current_state'):
                draft_agent.current_state = None
                logger.info("Reset draft agent state to ensure fresh generation")
            
            # Convert outline to proper format if needed
            try:
                if not isinstance(outline, FinalOutline):
                    outline_obj = FinalOutline.model_validate(outline)
                else:
                    outline_obj = outline
            except Exception as e:
                logger.error(f"Failed to validate outline: {str(e)}")
                error_placeholder.error(f"Invalid outline format: {str(e)}")
                return False
                
            # Set a timeout for section generation (10 minutes)
            try:
                # Show progress updates during generation
                update_progress(f"Mapping content for section: {current_section['title']}...")
                
                # Generate the section content with timeout
                section_content = await asyncio.wait_for(
                    draft_agent.generate_section(
                        section=current_section,
                        outline=outline_obj,
                        notebook_content=notebook_content,
                        markdown_content=markdown_content,
                        current_section_index=section_index,
                        max_iterations=SessionManager.get('max_iterations', 3),
                        quality_threshold=SessionManager.get('quality_threshold', 0.8)
                    ),
                    timeout=600  # 10 minutes timeout
                )
                
                update_progress(f"Completed generation for section: {current_section['title']}")
                
            except asyncio.TimeoutError:
                logger.error(f"BlogDraftUI._generate_section: Section generation timed out for {current_section['title']}", exc_info=True)
                error_placeholder.error(f"Section generation timed out after 10 minutes. Please try again with fewer iterations.")
                return False
            
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
                
                # We'll let the caller handle UI updates to avoid rerun loops
                return True
            else:
                logger.error(f"Failed to generate section {section_index + 1} ({current_section['title']})")
                error_placeholder.error(f"Failed to generate section {section_index + 1} ({current_section['title']}). Check logs for details.")
                return False
                
        except Exception as e:
            logger.exception(f"BlogDraftUI._generate_section: Error generating section {section_index + 1}: {str(e)}")
            
            # Provide more helpful error message for recursion limit errors
            if isinstance(e, RecursionError) or "recursion limit" in str(e).lower():
                error_msg = (
                    f"Error generating section {section_index + 1}: Recursion limit reached. " +
                    "This is likely due to complexity in the section. Try again with fewer iterations."
                )
            else:
                error_msg = f"Error generating section {section_index + 1}: {str(e)}"
                
            error_placeholder.error(error_msg)
            return False
    
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
            
            # Check for essential components and at least one content source
            if not outline or not draft_agent or (not notebook_content and not markdown_content) or section_index >= len(sections_generated):
                missing_items = []
                if not outline: missing_items.append("outline")
                if not draft_agent: missing_items.append("draft_agent")
                if not notebook_content and not markdown_content: missing_items.append("notebook/markdown content")
                if section_index >= len(sections_generated): missing_items.append("valid section index")

                error_message = f"Missing required data for section regeneration: {', '.join(missing_items)}"
                logger.error(error_message)
                error_placeholder.error(error_message)
                return # Return early on failure
            
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
                logger.error(f"BlogDraftUI._regenerate_section_with_feedback: Section regeneration timed out for {section['title']}", exc_info=True)
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
            logger.exception(f"BlogDraftUI._regenerate_section_with_feedback: Error regenerating section {section_index + 1}: {str(e)}")
            progress_placeholder.empty()
            
            # Provide more helpful error message for recursion limit errors
            if isinstance(e, RecursionError) or "recursion limit" in str(e).lower():
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
                "\n## Prerequisites\n"
            ]

            # Add prerequisites (handle structured dict like FastAPI)
            prerequisites = outline.get("prerequisites", {})
            if isinstance(prerequisites, dict):
                if "required_knowledge" in prerequisites:
                    blog_parts.append("\n### Required Knowledge\n")
                    for item in prerequisites["required_knowledge"]:
                        blog_parts.append(f"- {item}\n")
                        
                if "recommended_tools" in prerequisites:
                    blog_parts.append("\n### Recommended Tools\n")
                    for tool in prerequisites["recommended_tools"]:
                        blog_parts.append(f"- {tool}\n")
                        
                if "setup_instructions" in prerequisites:
                    blog_parts.append("\n### Setup Instructions\n")
                    for instruction in prerequisites["setup_instructions"]:
                        blog_parts.append(f"- {instruction}\n")
            elif isinstance(prerequisites, str): # Fallback for simple string
                blog_parts.append(f"{prerequisites}\n")
            
            blog_parts.append("\n## Table of Contents\n")
            
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
            logger.exception(f"BlogDraftUI._compile_final_draft: Error compiling final draft: {str(e)}")
            st.error(f"Error compiling final draft: {type(e).__name__}: {str(e)}")

class SettingsUI:
    def render(self):
        st.title("Settings")
        st.info("Additional settings and configurations coming soon!")

# 5. Utility Functions
class FileHandler:
    @staticmethod
    def save_uploaded_files(blog_name, notebook_file, markdown_file):
        """Save uploaded files to the appropriate directory, checking for cached content."""
        try:
            # Create blog project directory
            blog_dir = AppConfig.UPLOAD_PATH / blog_name
            blog_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Created directory: {blog_dir}")
            
            # Initialize vector store for content hash checking
            vector_store = VectorStoreService()
                
            # Save files if they were uploaded
            saved_files = []
            
            # Process notebook file
            if notebook_file is not None:
                # Clean the filename to avoid special characters
                notebook_filename = notebook_file.name.replace(" ", "_")
                notebook_path = blog_dir / notebook_filename
                
                # Read content into memory to compute hash before saving
                notebook_content = notebook_file.getbuffer()
                content_hash = vector_store.compute_content_hash(
                    notebook_content.tobytes().decode('utf-8', errors='ignore'), 
                    ""
                )
                
                # Check if file with this hash already exists in the project
                existing_content = vector_store.search_content(
                    metadata_filter={
                        "content_hash": content_hash,
                        "project_name": blog_name,
                        "file_type": ".ipynb"
                    }
                )
                
                if existing_content:
                    logger.info(f"Using cached notebook with hash: {content_hash}")
                    # Use the existing file path from metadata
                    existing_path = existing_content[0].get("metadata", {}).get("file_path")
                    if existing_path and Path(existing_path).exists():
                        notebook_path = Path(existing_path)
                        logger.info(f"Using existing notebook file: {notebook_path}")
                        # Update files_were_cached in the session state
                        SessionManager.set('files_were_cached', True)
                    else:
                        # Save the file anyway if the existing path is invalid
                        with open(notebook_path, "wb") as f:
                            f.write(notebook_content)
                        logger.info(f"Saved notebook file to: {notebook_path} (existing path invalid)")
                else:
                    # Save new file
                    with open(notebook_path, "wb") as f:
                        f.write(notebook_content)
                    logger.info(f"Saved new notebook file to: {notebook_path}")
                
                # Store the absolute path and hash in session state
                SessionManager.set('notebook_path', str(notebook_path))
                SessionManager.set('notebook_hash', content_hash)
                saved_files.append(f"Notebook: {notebook_filename} (Hash: {content_hash[:8]}...)")
                    
            # Process markdown file
            if markdown_file is not None:
                # Clean the filename to avoid special characters
                markdown_filename = markdown_file.name.replace(" ", "_")
                markdown_path = blog_dir / markdown_filename
                
                # Read content into memory to compute hash before saving
                markdown_content = markdown_file.getbuffer()
                content_hash = vector_store.compute_content_hash(
                    markdown_content.tobytes().decode('utf-8', errors='ignore'), 
                    ""
                )
                
                # Check if file with this hash already exists in the project
                existing_content = vector_store.search_content(
                    metadata_filter={
                        "content_hash": content_hash,
                        "project_name": blog_name,
                        "file_type": ".md"
                    }
                )
                
                if existing_content:
                    logger.info(f"Using cached markdown with hash: {content_hash}")
                    # Use the existing file path from metadata
                    existing_path = existing_content[0].get("metadata", {}).get("file_path")
                    if existing_path and Path(existing_path).exists():
                        markdown_path = Path(existing_path)
                        logger.info(f"Using existing markdown file: {markdown_path}")
                        # Update files_were_cached in the session state
                        SessionManager.set('files_were_cached', True)
                    else:
                        # Save the file anyway if the existing path is invalid
                        with open(markdown_path, "wb") as f:
                            f.write(markdown_content)
                        logger.info(f"Saved markdown file to: {markdown_path} (existing path invalid)")
                else:
                    # Save new file
                    with open(markdown_path, "wb") as f:
                        f.write(markdown_content)
                    logger.info(f"Saved new markdown file to: {markdown_path}")
                
                # Store the absolute path and hash in session state
                SessionManager.set('markdown_path', str(markdown_path))
                SessionManager.set('markdown_hash', content_hash)
                saved_files.append(f"Markdown: {markdown_filename} (Hash: {content_hash[:8]}...)")
                
            return saved_files
        except Exception as e:
            logger.error(f"FileHandler.save_uploaded_files: Error saving uploaded files: {str(e)}", exc_info=True)
            # Re-raise the exception to be caught by the caller (SidebarUI)
            raise e

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
