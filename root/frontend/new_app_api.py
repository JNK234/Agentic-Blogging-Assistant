# -*- coding: utf-8 -*-
"""
Streamlit frontend application for the Agentic Blogging Assistant,
interacting with the FastAPI backend via an API client.
"""

import streamlit as st
import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import httpx # For catching specific exceptions
from pathlib import Path
import json # Added for parsing section content

# Import the API client functions
import api_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BloggingAssistantAPIFrontend")

# Apply nest_asyncio patch if needed (often required in Streamlit/Jupyter)
try:
    import nest_asyncio
    nest_asyncio.apply()
    logger.info("Applied nest_asyncio patch.")
except ImportError:
    logger.warning("nest_asyncio not found. Skipping patch.")

# --- Configuration ---
class AppConfig:
    PAGE_TITLE = "Agentic Blogging Assistant (API)"
    PAGE_ICON = "📝"
    LAYOUT = "wide"
    DEFAULT_MODEL = "gemini" # Default model selection
    SUPPORTED_MODELS = ["gemini", "claude", "openai", "deepseek", "openrouter"] # Align with backend ModelFactory
    SUPPORTED_FILE_TYPES = ["ipynb", "md", "py"]

# --- Session State Management ---
class SessionManager:
    @staticmethod
    def initialize_state():
        """Initializes the Streamlit session state dictionary."""
        if 'api_app_state' not in st.session_state:
            st.session_state.api_app_state = {
                'api_base_url': api_client.DEFAULT_API_BASE_URL,
                'project_name': None,
                'selected_model': AppConfig.DEFAULT_MODEL,
                'uploaded_files_info': [], # Stores basic info like name, type
                'processed_file_paths': [], # Paths returned by backend /upload
                'processed_file_hashes': {}, # Hashes returned by backend /process_files
                'notebook_hash': None,
                'markdown_hash': None,
                'python_hashes': [], # Store multiple python file hashes if needed
                'job_id': None, # ID for the current outline/draft generation job
                'generated_outline': None,
                'generated_sections': {}, # Dict mapping index to section data {title, raw_content, formatted_content}
                'final_draft': None, # Compiled draft before refinement
                'refined_draft': None, # Draft after adding intro/conclusion
                'summary': None, # Generated summary
                'title_options': None, # List of generated TitleOption objects
                'social_content': None, # Dict for {breakdown, linkedin, x, newsletter}
                'current_section_index': 0,
                'total_sections': 0,
                'is_initialized': False, # Flag to indicate if setup is complete
                'error_message': None,
                'status_message': "Please initialize the assistant.",
            }
            logger.info("Initialized session state.")

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Gets a value from the session state."""
        return st.session_state.api_app_state.get(key, default)

    @staticmethod
    def set(key: str, value: Any):
        """Sets a value in the session state."""
        st.session_state.api_app_state[key] = value
        # logger.debug(f"Set state '{key}' to: {value}") # Optional: Debug logging

    @staticmethod
    def clear_error():
        """Clears the error message."""
        st.session_state.api_app_state['error_message'] = None

    @staticmethod
    def set_error(message: str):
        """Sets an error message."""
        st.session_state.api_app_state['error_message'] = message
        logger.error(f"UI Error Set: {message}")

    @staticmethod
    def set_status(message: str):
        """Sets a status message."""
        st.session_state.api_app_state['status_message'] = message
        logger.info(f"UI Status Set: {message}")


# --- Helper Functions ---
def display_readable_outline(outline_data: Optional[Dict[str, Any]]):
    """Displays the outline dictionary in a readable format using Streamlit."""
    if not outline_data:
        st.info("No outline data to display.")
        return

    # Display Title
    title = outline_data.get("title", "Blog Outline")
    st.subheader(title)

    # Display Sections and Subsections
    sections = outline_data.get("sections")
    if isinstance(sections, list) and sections:
        for i, section in enumerate(sections):
            if isinstance(section, dict):
                section_title = section.get("title", f"Section {i+1}")
                st.markdown(f"**{i+1}. {section_title}**")

                subsections = section.get("subsections")
                if isinstance(subsections, list) and subsections:
                    for sub_i, subsection in enumerate(subsections):
                        # Ensure subsection is treated as a string
                        st.markdown(f"    - {str(subsection)}")
            else:
                # Handle case where section is just a string (less likely based on structure)
                 st.markdown(f"**{i+1}. {str(section)}**")

    else:
        st.markdown("*No sections defined in the outline.*")


def format_section_content_as_markdown(content_data: Any) -> str:
    """
    Formats potentially structured section content into a consistent Markdown string.

    Tries to parse the input as JSON if it's a string. If it's a dictionary
    (either parsed or directly passed), it formats known keys like 'title',
    'content', and 'code_examples' into Markdown. Other keys are displayed generically.
    If parsing fails or the input isn't structured, it's treated as plain text/Markdown.

    Args:
        content_data: The raw content received for a section. Can be a string
                      (potentially JSON), a dictionary, or None.

    Returns:
        A formatted Markdown string suitable for st.markdown.
    """
    if not content_data:
        return "*No content available for this section.*"

    data = None
    if isinstance(content_data, str):
        try:
            # Attempt to parse the string as JSON
            parsed_json = json.loads(content_data)
            if isinstance(parsed_json, dict):
                data = parsed_json
            else:
                 # If it parses but isn't a dict, treat as plain text
                 return content_data
        except json.JSONDecodeError:
            # If it's not valid JSON, assume it's already Markdown or plain text
            return content_data
    elif isinstance(content_data, dict):
        data = content_data
    else:
        # Handle unexpected types by converting to string
        logger.warning(f"Unexpected content type received: {type(content_data)}. Displaying as string.")
        return str(content_data)

    # If we successfully got a dictionary, format it without modifying the original
    if data:
        markdown_parts = []
        # Use a copy or access keys directly to avoid modifying the original 'data'
        local_data = data.copy() # Work on a copy

        # Use H3 for sub-section title if present
        title = local_data.get("title")
        if title:
             markdown_parts.append(f"### {title}")

        # Main content block
        content = local_data.get("content")
        if content:
            markdown_parts.append(str(content))

        # Format code examples, avoiding double-fencing
        examples = local_data.get("code_examples")
        if examples:
            markdown_parts.append("\n**Code Examples:**\n") # Add header regardless of type
            if isinstance(examples, list) and examples:
                for i, example in enumerate(examples):
                    lang = ""
                    code = ""
                    if isinstance(example, dict):
                        lang = example.get("language", "")
                        code = example.get("code", "")
                    else:
                        code = str(example) # Assume the list item is the code string

                    code_str = str(code).strip()
                    # Check if it already looks like a fenced block
                    if code_str.startswith("```") and code_str.endswith("```"):
                        markdown_parts.append(code_str) # Use as-is
                    else:
                        markdown_parts.append(f"``` {lang}\n{code_str}\n```") # Add fences

            elif isinstance(examples, str): # Handle single code example string
                 code_str = examples.strip()
                 if code_str.startswith("```") and code_str.endswith("```"):
                     markdown_parts.append(code_str) # Use as-is
                 else:
                     # Assume python if language not specified for single string example
                     markdown_parts.append(f"``` python\n{code_str}\n```")

        # Note: We no longer need to handle 'remaining keys' as we are not deleting.
        # If other keys need specific formatting, add logic here.

        return "\n\n".join(filter(None, markdown_parts)) # Join non-empty parts
    else:
        # This case handles non-dict data or data that became None/empty after parsing attempts
        # but handles edge cases where data becomes None/empty after processing
        return str(content_data)


# --- UI Components ---

class SidebarUI:
    """Handles rendering the sidebar and initialization logic."""

    def render(self):
        with st.sidebar:
            st.title(AppConfig.PAGE_TITLE)
            st.markdown("Configure your blogging assistant.")

            # API Base URL (optional override)
            api_base_url = st.text_input(
                "API Base URL",
                value=SessionManager.get('api_base_url', api_client.DEFAULT_API_BASE_URL),
                help="The base URL of the running FastAPI backend."
            )
            SessionManager.set('api_base_url', api_base_url) # Update state immediately

            # Check API Health
            if st.button("Check API Connection"):
                self._check_api_health(api_base_url)

            # Initialization Form
            with st.form("init_form"):
                st.subheader("Initialize Project")
                project_name = st.text_input(
                    "Blog Project Name",
                    value=SessionManager.get('project_name', ""),
                    help="A unique name for your blog project."
                )
                selected_model = st.selectbox(
                    "Select LLM Model",
                    options=AppConfig.SUPPORTED_MODELS,
                    index=AppConfig.SUPPORTED_MODELS.index(SessionManager.get('selected_model', AppConfig.DEFAULT_MODEL)),
                    help="Choose the language model for generation."
                )
                uploaded_files = st.file_uploader(
                    "Upload Files (.ipynb, .md, .py)",
                    type=AppConfig.SUPPORTED_FILE_TYPES,
                    accept_multiple_files=True,
                    help="Upload Jupyter notebooks, Markdown notes, or Python scripts."
                )

                initialize_button = st.form_submit_button("Initialize Assistant")

            if initialize_button:
                if not project_name:
                    st.sidebar.error("Please enter a project name.")
                elif not uploaded_files:
                    st.sidebar.error("Please upload at least one file.")
                else:
                    # Store basic info immediately for potential later use
                    SessionManager.set('project_name', project_name)
                    SessionManager.set('selected_model', selected_model)
                    SessionManager.set('uploaded_files_info', [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_files])
                    SessionManager.set('is_initialized', False) # Reset initialization status
                    SessionManager.set_status("Initializing...")
                    SessionManager.clear_error()

                    # Run the async initialization process
                    try:
                        asyncio.run(self._initialize_assistant(project_name, selected_model, uploaded_files, api_base_url))
                    except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                        SessionManager.set_error(f"API Error: {str(api_err)}")
                        SessionManager.set_status("Initialization failed.")
                    except Exception as e:
                        logger.exception(f"Unexpected error during initialization: {e}")
                        SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                        SessionManager.set_status("Initialization failed.")

            # Display Status/Error
            status_message = SessionManager.get('status_message')
            error_message = SessionManager.get('error_message')

            if error_message:
                st.sidebar.error(error_message)
            elif status_message:
                if SessionManager.get('is_initialized'):
                    st.sidebar.success(status_message)
                    # Display project details on success
                    st.sidebar.markdown("---")
                    st.sidebar.write("**Project Details:**")
                    st.sidebar.write(f"- **Name:** {SessionManager.get('project_name')}")
                    st.sidebar.write(f"- **Model:** {SessionManager.get('selected_model')}")
                    st.sidebar.write("**Processed Files:**")
                    hashes = SessionManager.get('processed_file_hashes', {})
                    if hashes:
                        for path, hash_val in hashes.items():
                            st.sidebar.write(f"  - `{Path(path).name}` (Hash: `{hash_val[:8]}...`)")
                    else:
                        st.sidebar.write("  (No files processed yet)")

                else:
                    st.sidebar.info(status_message)

    def _check_api_health(self, base_url):
        """Checks the API health and updates the sidebar."""
        SessionManager.set_status("Checking API connection...")
        SessionManager.clear_error()
        try:
            is_healthy = asyncio.run(api_client.health_check(base_url=base_url))
            if is_healthy:
                st.sidebar.success("API Connection Successful!")
                SessionManager.set_status("API is reachable.")
            else:
                SessionManager.set_error("API Connection Failed. Check URL and ensure the backend is running.")
                SessionManager.set_status("API unreachable.")
        except Exception as e:
            logger.exception(f"Error during health check: {e}")
            SessionManager.set_error(f"API Connection Error: {str(e)}")
            SessionManager.set_status("API unreachable.")


    async def _initialize_assistant(self, project_name, model_name, uploaded_files, base_url):
        """Handles the async steps of uploading and processing files via API."""
        SessionManager.set_status("Uploading files...")
        files_to_send: List[Tuple[str, bytes, str]] = []
        for f in uploaded_files:
            files_to_send.append((f.name, f.getvalue(), f.type or "application/octet-stream"))

        upload_result = await api_client.upload_files(project_name, files_to_send, base_url=base_url)
        uploaded_paths = upload_result.get("files", [])
        if not uploaded_paths:
            SessionManager.set_error("File upload failed or returned no paths.")
            SessionManager.set_status("Initialization failed.")
            return

        SessionManager.set('processed_file_paths', uploaded_paths)
        SessionManager.set_status(f"Files uploaded ({len(uploaded_paths)}). Processing...")

        process_result = await api_client.process_files(project_name, model_name, uploaded_paths, base_url=base_url)
        file_hashes = process_result.get("file_hashes", {})
        SessionManager.set('processed_file_hashes', file_hashes)

        # Store specific hashes for outline generation
        SessionManager.set('notebook_hash', next((h for p, h in file_hashes.items() if p.endswith(".ipynb")), None))
        SessionManager.set('markdown_hash', next((h for p, h in file_hashes.items() if p.endswith(".md")), None))
        SessionManager.set('python_hashes', [h for p, h in file_hashes.items() if p.endswith(".py")]) # Store potentially multiple python hashes

        SessionManager.set_status("Assistant Initialized Successfully!")
        SessionManager.set('is_initialized', True)
        SessionManager.clear_error()
        logger.info(f"Initialization complete for project '{project_name}' with model '{model_name}'.")


class OutlineGeneratorUI:
    """Handles the Outline Generation Tab."""
    def render(self):
        st.header("1. Generate Blog Outline")

        if not SessionManager.get('is_initialized'):
            st.warning("Please initialize the assistant using the sidebar first.")
            return

        project_name = SessionManager.get('project_name')
        model_name = SessionManager.get('selected_model')
        notebook_hash = SessionManager.get('notebook_hash')
        markdown_hash = SessionManager.get('markdown_hash')
        # TODO: Decide how to handle multiple python hashes if needed for outline
        # python_hash = SessionManager.get('python_hashes')[0] if SessionManager.get('python_hashes') else None

        if not notebook_hash and not markdown_hash:
             st.info("No processed notebook or markdown files found. Outline generation requires at least one.")
             # Optionally allow generating outline without content? Requires backend change.

        # Add text area for user guidelines here
        user_guidelines = st.text_area("Optional Guidelines:",
                                       help="Provide specific instructions for the outline generation (e.g., 'Focus on practical examples', 'Exclude section on history').",
                                       key="user_guidelines_input")

        if st.button("Generate Outline", key="gen_outline_btn"):
            # Retrieve guideline text inside the button's logic block
            guideline_text = st.session_state.get('user_guidelines_input', '') # Get value using key

            if not notebook_hash and not markdown_hash:
                st.error("Cannot generate outline without processed notebook or markdown content.")
                return

            SessionManager.set_status("Generating outline...")
            SessionManager.clear_error()
            try:
                with st.spinner("Calling API to generate outline..."):
                    result = asyncio.run(api_client.generate_outline(
                        project_name=project_name,
                        model_name=model_name,
                        notebook_hash=notebook_hash,
                        markdown_hash=markdown_hash,
                        user_guidelines=guideline_text, # Pass the retrieved guidelines
                        base_url=SessionManager.get('api_base_url')
                    ))
                SessionManager.set('job_id', result.get('job_id'))
                SessionManager.set('generated_outline', result.get('outline'))
                SessionManager.set('total_sections', len(result.get('outline', {}).get('sections', [])))
                SessionManager.set('current_section_index', 0) # Reset section index
                SessionManager.set('generated_sections', {}) # Clear old sections
                SessionManager.set('final_draft', None) # Clear old draft
                SessionManager.set('social_content', None) # Clear old social content
                SessionManager.set_status("Outline generated successfully.")
                logger.info(f"Outline generated for job ID: {result.get('job_id')}")
            except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                SessionManager.set_error(f"API Error generating outline: {str(api_err)}")
                SessionManager.set_status("Outline generation failed.")
            except Exception as e:
                logger.exception(f"Unexpected error during outline generation: {e}")
                SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                SessionManager.set_status("Outline generation failed.")

        # Display Outline
        outline = SessionManager.get('generated_outline')
        if outline:
            st.subheader("Generated Outline")
            # Display the outline in a readable format
            display_readable_outline(outline)
            st.success(f"Outline ready for Job ID: `{SessionManager.get('job_id')}`")
            st.markdown("---")
            st.info("Proceed to the 'Blog Draft' tab to generate sections.")
        else:
            st.info("Click 'Generate Outline' to start.")


class BlogDraftUI:
    """Handles the Blog Draft Tab."""
    def render(self):
        st.header("2. Generate Blog Draft Sections")

        if not SessionManager.get('job_id') or not SessionManager.get('generated_outline'):
            st.warning("Please generate an outline first on the 'Outline' tab.")
            return

        job_id = SessionManager.get('job_id')
        project_name = SessionManager.get('project_name')
        outline = SessionManager.get('generated_outline')
        total_sections = SessionManager.get('total_sections', 0)
        current_section_index = SessionManager.get('current_section_index', 0)
        generated_sections = SessionManager.get('generated_sections', {})

        if total_sections == 0:
            st.warning("The generated outline has no sections.")
            return

        st.progress(current_section_index / total_sections if total_sections > 0 else 0)
        st.write(f"Progress: {current_section_index}/{total_sections} sections generated.")
        st.markdown("---")

        # --- Section Generation ---
        if current_section_index < total_sections:
            current_section_info = outline['sections'][current_section_index]
            st.subheader(f"Next Section ({current_section_index + 1}/{total_sections}): {current_section_info.get('title', 'Untitled')}")

            with st.form(key=f"gen_section_{current_section_index}"):
                st.write("Generate the content for this section.")
                # Advanced options (optional)
                with st.expander("Advanced Options"):
                    max_iter = st.slider("Max Iterations", 1, 5, 3, key=f"iter_{current_section_index}")
                    quality_thresh = st.slider("Quality Threshold", 0.0, 1.0, 0.8, step=0.05, key=f"qual_{current_section_index}")
                generate_button = st.form_submit_button(f"Generate Section {current_section_index + 1}")

            if generate_button:
                SessionManager.set_status(f"Generating section {current_section_index + 1}...")
                SessionManager.clear_error()
                try:
                    with st.spinner(f"Calling API to generate section {current_section_index + 1}..."):
                        result = asyncio.run(api_client.generate_section(
                            project_name=project_name,
                            job_id=job_id,
                            section_index=current_section_index,
                            max_iterations=max_iter,
                            quality_threshold=quality_thresh,
                            base_url=SessionManager.get('api_base_url')
                        ))
                    # Store the generated section content, ensuring it's a string
                    section_content_raw = result.get("section_content")
                    section_title_raw = result.get("section_title", current_section_info.get('title', 'Untitled'))

                    if isinstance(section_content_raw, str):
                        section_content = section_content_raw
                    elif section_content_raw is None:
                        section_content = "Error: No content received from API."
                        logger.warning(f"generate_section for job {job_id}, section {current_section_index} returned None content. Full result: {result}")
                    else:
                        # Handle unexpected non-string content
                        logger.error(f"generate_section for job {job_id}, section {current_section_index} returned non-string content: {type(section_content_raw)}. Value: {section_content_raw}")
                        section_content = f"Error: Received unexpected content format: {type(section_content_raw)}. Check logs."

                    new_sections = SessionManager.get('generated_sections', {})
                    # Store both raw and formatted content
                    new_sections[current_section_index] = {
                        "title": section_title_raw,
                        "raw_content": section_content_raw, # Store original API response (might be dict or string)
                        "formatted_content": format_section_content_as_markdown(section_content_raw) # Store formatted version
                    }
                    SessionManager.set('generated_sections', new_sections)
                    SessionManager.set('current_section_index', current_section_index + 1)
                    SessionManager.set_status(f"Section {current_section_index + 1} generated.")
                    st.rerun() # Rerun to update progress and show generated section
                except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                    SessionManager.set_error(f"API Error generating section: {str(api_err)}")
                    SessionManager.set_status("Section generation failed.")
                except Exception as e:
                    logger.exception(f"Unexpected error during section generation: {e}")
                    SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                    SessionManager.set_status("Section generation failed.")
        else:
            # --- Draft Compilation ---
            st.subheader("All Sections Generated!")
            if st.button("Compile Final Draft", key="compile_draft_btn"):
                SessionManager.set_status("Compiling final draft from formatted sections...")
                SessionManager.clear_error()
                try:
                    # --- Frontend Draft Compilation ---
                    blog_title = SessionManager.get('generated_outline', {}).get('title', 'My Blog Post')
                    sections_data = SessionManager.get('generated_sections', {})
                    sorted_indices = sorted(sections_data.keys())

                    draft_parts = [f"# {blog_title}\n"] # Start with H1 title

                    for index in sorted_indices:
                        section = sections_data.get(index, {})
                        section_title = section.get('title', f'Section {index + 1}')
                        formatted_content = section.get('formatted_content', '')

                        draft_parts.append(f"## {section_title}\n") # Add H2 for section title
                        draft_parts.append(formatted_content)

                    final_draft_content = "\n\n".join(draft_parts)
                    SessionManager.set('final_draft', final_draft_content)
                    SessionManager.set_status("Draft compiled successfully in frontend.")
                    logger.info(f"Draft compiled in frontend for job ID: {job_id}")
                    # No API call needed here anymore
                    # --- End Frontend Draft Compilation ---
                except Exception as e:
                    logger.exception(f"Unexpected error during frontend draft compilation: {e}")
                    SessionManager.set_error(f"An unexpected error occurred during compilation: {str(e)}")
                    SessionManager.set_status("Draft compilation failed.")

        st.markdown("---")

        # --- Display Generated Sections & Feedback ---
        if generated_sections:
            st.subheader("Generated Content")
            sorted_indices = sorted(generated_sections.keys())
            for index in sorted_indices:
                section_data = generated_sections[index]
                with st.expander(f"Section {index + 1}: {section_data.get('title', 'Untitled')}", expanded=True): # Expand by default now
                    # Display the pre-formatted content stored in the state
                    st.markdown(section_data.get('formatted_content', '*Error: Formatted content not found.*'))
                    # Feedback Form
                    with st.form(key=f"feedback_form_{index}"):
                        feedback_text = st.text_area("Provide feedback to regenerate this section:", key=f"feedback_text_{index}")
                        regen_button = st.form_submit_button("Regenerate with Feedback")

                    if regen_button and feedback_text:
                        SessionManager.set_status(f"Regenerating section {index + 1} with feedback...")
                        SessionManager.clear_error()
                        try:
                            with st.spinner(f"Calling API to regenerate section {index + 1}..."):
                                result = asyncio.run(api_client.regenerate_section_with_feedback(
                                    project_name=project_name,
                                    job_id=job_id,
                                    section_index=index,
                                    feedback=feedback_text,
                                    # Add advanced options if needed, e.g., from sliders outside the form
                                    base_url=SessionManager.get('api_base_url')
                                ))
                            # Update the section content, ensuring it's a string
                            section_content_raw = result.get("section_content")

                            if isinstance(section_content_raw, str):
                                section_content = section_content_raw
                            elif section_content_raw is None:
                                section_content = "Error: Regeneration failed to return content."
                                logger.warning(f"regenerate_section for job {job_id}, section {index} returned None content. Full result: {result}")
                            else:
                                # Handle unexpected non-string content
                                logger.error(f"regenerate_section for job {job_id}, section {index} returned non-string content: {type(section_content_raw)}. Value: {section_content_raw}")
                                # Note: section_content variable is not directly used below, but error logging is kept.

                            # Explicitly fetch the latest state right before updating
                            current_sections_state = SessionManager.get('generated_sections', {})
                            if index in current_sections_state:
                                current_sections_state[index]['raw_content'] = section_content_raw # Update raw content
                                current_sections_state[index]['formatted_content'] = format_section_content_as_markdown(section_content_raw) # Update formatted content
                                # Note: Title is assumed unchanged during regeneration, but could be updated if API returns it
                                SessionManager.set('generated_sections', current_sections_state) # Save updated state
                                SessionManager.set_status(f"Section {index + 1} regenerated.")
                                st.rerun() # Update UI
                            else:
                                # Handle case where the section index somehow disappeared
                                SessionManager.set_error(f"Error: Could not find section {index + 1} in state to update after regeneration.")
                                SessionManager.set_status("Section regeneration failed (state error).")

                        except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                            SessionManager.set_error(f"API Error regenerating section: {str(api_err)}")
                            SessionManager.set_status("Section regeneration failed.")
                        except Exception as e:
                            logger.exception(f"Unexpected error during section regeneration: {e}")
                            SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                            SessionManager.set_status("Section regeneration failed.")

        # --- Display Final Draft ---
        final_draft = SessionManager.get('final_draft')
        if final_draft:
            st.subheader("Final Blog Draft")
            st.download_button(
                label="Download Draft (.md)",
                data=final_draft,
                file_name=f"{project_name}_draft.md",
                mime="text/markdown"
            )
            with st.expander("Preview Draft", expanded=True):
                st.markdown(final_draft)
            with st.expander("Markdown Source", expanded=False):
                st.text_area("Markdown", final_draft, height=400)
            st.info("Proceed to the 'Refine & Finalize' tab to add introduction, conclusion, summary, and titles.") # Updated instruction


class RefinementUI:
    """Handles the Refine & Finalize Tab."""
    def render(self):
        st.header("3. Refine & Finalize Blog")

        if not SessionManager.get('final_draft'):
            st.warning("Please compile the draft on the 'Blog Draft' tab first.")
            return

        job_id = SessionManager.get('job_id')
        project_name = SessionManager.get('project_name')
        final_draft = SessionManager.get('final_draft')

        st.subheader("Compiled Draft Preview")
        st.download_button(
            label="Download Compiled Draft (.md)",
            data=final_draft,
            file_name=f"{project_name}_compiled_draft.md",
            mime="text/markdown",
            key="download_compiled_draft_refine_tab"
        )
        with st.expander("View Compiled Draft", expanded=False):
            st.markdown(final_draft)

        st.markdown("---")
        st.subheader("Generate Introduction, Conclusion, Summary & Titles")

        if st.button("Refine Blog", key="refine_blog_btn"):
            SessionManager.set_status("Refining blog draft...")
            SessionManager.clear_error()
            try:
                with st.spinner("Calling API to refine blog..."):
                    # Assuming api_client has a refine_blog function
                    result = asyncio.run(api_client.refine_blog(
                        project_name=project_name,
                        job_id=job_id,
                        base_url=SessionManager.get('api_base_url')
                    ))
                SessionManager.set('refined_draft', result.get('refined_draft'))
                SessionManager.set('summary', result.get('summary'))
                SessionManager.set('title_options', result.get('title_options')) # Expecting a list of dicts
                SessionManager.set_status("Blog refined successfully.")
                logger.info(f"Blog refined for job ID: {job_id}")
            except AttributeError:
                 SessionManager.set_error("API Error: `refine_blog` function not found in `api_client.py`. Please update the client.")
                 SessionManager.set_status("Refinement failed.")
            except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                SessionManager.set_error(f"API Error refining blog: {str(api_err)}")
                SessionManager.set_status("Refinement failed.")
            except Exception as e:
                logger.exception(f"Unexpected error during blog refinement: {e}")
                SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                SessionManager.set_status("Refinement failed.")

        # Display Refinement Results
        refined_draft = SessionManager.get('refined_draft')
        summary = SessionManager.get('summary')
        title_options = SessionManager.get('title_options') # This should be List[Dict]

        if refined_draft:
            st.markdown("---")
            st.subheader("Refined Blog Draft")
            st.download_button(
                label="Download Refined Draft (.md)",
                data=refined_draft,
                file_name=f"{project_name}_refined_draft.md",
                mime="text/markdown",
                key="download_refined_draft"
            )
            with st.expander("Preview Refined Draft", expanded=True):
                st.markdown(refined_draft)

        if summary:
             st.subheader("Generated Summary")
             st.markdown(summary)

        if title_options:
            st.subheader("Generated Title & Subtitle Options")
            for i, option in enumerate(title_options):
                with st.container(border=True):
                    st.markdown(f"**Option {i+1}:**")
                    st.markdown(f"**Title:** {option.get('title', 'N/A')}")
                    st.markdown(f"**Subtitle:** {option.get('subtitle', 'N/A')}")
                    st.caption(f"Reasoning: {option.get('reasoning', 'N/A')}")

        if refined_draft:
             st.info("Proceed to the 'Social Posts' tab to generate promotional content using the refined draft.")


class SocialPostsUI:
    """Handles the Social Posts Tab."""
    def render(self):
        st.header("4. Generate Social Media Content") # Updated header number

        # Check for refined draft now
        if not SessionManager.get('refined_draft'):
            st.warning("Please refine the blog draft on the 'Refine & Finalize' tab first.")
            return

        job_id = SessionManager.get('job_id')
        project_name = SessionManager.get('project_name')

        if st.button("Generate Social Content", key="gen_social_btn"):
            SessionManager.set_status("Generating social content...")
            SessionManager.clear_error()
            try:
                with st.spinner("Calling API to generate social content..."):
                    result = asyncio.run(api_client.generate_social_content(
                        project_name=project_name,
                        job_id=job_id,
                        base_url=SessionManager.get('api_base_url')
                    ))
                SessionManager.set('social_content', result.get('social_content'))
                SessionManager.set_status("Social content generated.")
                logger.info(f"Social content generated for job ID: {job_id}")
            except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                SessionManager.set_error(f"API Error generating social content: {str(api_err)}")
                SessionManager.set_status("Social content generation failed.")
            except Exception as e:
                logger.exception(f"Unexpected error during social content generation: {e}")
                SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                SessionManager.set_status("Social content generation failed.")

        # Display Social Content
        social_content = SessionManager.get('social_content')
        if social_content:
            st.subheader("Generated Content")

            with st.expander("Content Breakdown Analysis", expanded=False):
                st.markdown(social_content.get('content_breakdown', 'Not available.'))

            with st.expander("LinkedIn Post", expanded=True):
                st.markdown(social_content.get('linkedin_post', 'Not available.'))

            with st.expander("X (Twitter) Post", expanded=True):
                st.markdown(social_content.get('x_post', 'Not available.'))

            with st.expander("Newsletter Content", expanded=True):
                st.markdown(social_content.get('newsletter_content', 'Not available.'))
        else:
            st.info("Click 'Generate Social Content' after compiling the draft.")


# --- Main Application Class ---
class BloggingAssistantAPIApp:
    def __init__(self):
        self.session = SessionManager()
        self.sidebar = SidebarUI()
        self.outline_generator = OutlineGeneratorUI()
        self.blog_draft = BlogDraftUI()
        self.refinement = RefinementUI() # Added refinement UI instance
        self.social_posts = SocialPostsUI()

    def setup(self):
        """Sets up Streamlit page configuration."""
        st.set_page_config(
            page_title=AppConfig.PAGE_TITLE,
            page_icon=AppConfig.PAGE_ICON,
            layout=AppConfig.LAYOUT
        )
        self.session.initialize_state() # Ensure state is initialized on first run/refresh

    def run(self):
        """Runs the main application flow."""
        self.setup()
        self.sidebar.render() # Render sidebar first for initialization

        # Display global status/error messages prominently
        error_message = SessionManager.get('error_message')
        status_message = SessionManager.get('status_message')
        if error_message:
            st.error(error_message)
        elif status_message and not SessionManager.get('is_initialized'): # Show status only if not initialized
             st.info(status_message)


        if SessionManager.get('is_initialized'):
            # Create tabs only after initialization, including the new Refine tab
            tab_outline, tab_draft, tab_refine, tab_social = st.tabs([
                "1. Outline", "2. Blog Draft", "3. Refine & Finalize", "4. Social Posts"
            ])

            with tab_outline:
                self.outline_generator.render()

            with tab_draft:
                self.blog_draft.render()

            with tab_refine: # Added tab rendering
                self.refinement.render()

            with tab_social:
                self.social_posts.render()
        else:
            # Optionally show a placeholder if not initialized
            st.markdown("---")
            st.info("⬅️ Please configure and initialize the assistant using the sidebar.")


# --- Application Entry Point ---
if __name__ == "__main__":
    app = BloggingAssistantAPIApp()
    app.run()
