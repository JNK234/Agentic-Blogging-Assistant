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
import re # Added for regex operations
from datetime import datetime
import zipfile
import io

# Import the API client functions
import api_client
from auto_save_manager import AutoSaveManager
from services.project_service import ProjectService
from components.project_manager import ProjectManagerUI
from utils.api_client import BlogAPIClient
from components.api_project_dashboard import APIProjectDashboard
from auth import require_auth, show_user_profile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BloggingAssistantAPIFrontend")

try:
    import nest_asyncio
    nest_asyncio.apply()
    logger.info("Applied nest_asyncio patch.")
except ImportError:
    logger.warning("nest_asyncio not found. Skipping patch.")

# --- Configuration ---
from config import ModelConfig

class AppConfig:
    PAGE_TITLE = "Agentic Blogging Assistant (API)"
    PAGE_ICON = "📝"
    LAYOUT = "wide"
    DEFAULT_MODEL = ModelConfig.DEFAULT_MODEL # Default provider selection
    SUPPORTED_MODELS = ModelConfig.DEFAULT_PROVIDERS # Provider keys
    SUPPORTED_FILE_TYPES = ["ipynb", "md", "py"]

# --- Session State Management ---
class SessionManager:
    # Initialize auto-save manager as class variable
    _auto_save_manager = None
    
    @staticmethod
    def get_auto_save_manager():
        """Get or create the auto-save manager instance."""
        if SessionManager._auto_save_manager is None:
            SessionManager._auto_save_manager = AutoSaveManager()
        return SessionManager._auto_save_manager
    
    @staticmethod
    def initialize_state():
        """Initializes the Streamlit session state dictionary."""
        if 'api_app_state' not in st.session_state:
            st.session_state.api_app_state = {
                'api_base_url': api_client.DEFAULT_API_BASE_URL,
                'project_name': None,
                'selected_model': AppConfig.DEFAULT_MODEL,
                'selected_persona': 'neuraforge', # Default persona
                'specific_model': None, # Specific model within provider
                'available_personas': {}, # Cache for personas from API
                'available_models': {}, # Cache for models from API
                'uploaded_files_info': [], # Stores basic info like name, type
                'processed_file_paths': [], # Paths returned by backend /upload
                'processed_file_hashes': {}, # Hashes returned by backend /process_files
                'notebook_hash': None,
                'markdown_hash': None,
                'python_hashes': [], # Store multiple python file hashes if needed
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
                'cost_summary': None,
                # Project Management State
                'current_project_id': None,
                'current_project_name': None,
                'project_milestones': {},
                'resume_point': None,
                'project_metadata': {},
                'available_projects': [],
                'show_archived_projects': False,
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
    
    @staticmethod
    def reset_project_state():
        """Resets all project-related state for switching projects."""
        keys_to_reset = [
            'project_name', 'selected_model', 'selected_persona', 'specific_model', 'uploaded_files_info', 'processed_file_paths',
            'processed_file_hashes', 'notebook_hash', 'markdown_hash', 'python_hashes',
            'generated_outline', 'generated_sections', 'final_draft', 'refined_draft',
            'summary', 'title_options', 'social_content', 'current_section_index', 'total_sections',
            'is_initialized', 'error_message'
        ]
        for key in keys_to_reset:
            st.session_state.api_app_state[key] = None if key not in ['uploaded_files_info', 'processed_file_paths', 
                                                                     'processed_file_hashes', 'python_hashes', 
                                                                     'generated_sections'] else []
        st.session_state.api_app_state['current_section_index'] = 0
        st.session_state.api_app_state['total_sections'] = 0
        st.session_state.api_app_state['is_initialized'] = False
        st.session_state.api_app_state['status_message'] = "Project switched. Please initialize if needed."
        logger.info("Project state reset for switching projects.")


# --- Helper Functions ---
def display_readable_outline(outline_data: Optional[Dict[str, Any]]):
    """Displays the outline dictionary in a readable format using Streamlit."""
    if not outline_data:
        st.info("No outline data to display.")
        return

    # Display Title
    title = outline_data.get("title", "Blog Outline")
    st.subheader(f"Outline: {title}")

    # Display Difficulty Level
    difficulty = outline_data.get("difficulty_level")
    if difficulty:
        st.markdown(f"**Difficulty Level:** {difficulty}")

    # Display Prerequisites
    prerequisites = outline_data.get("prerequisites")
    if isinstance(prerequisites, dict):
        st.markdown("**Prerequisites:**")
        if prerequisites.get("required_knowledge"):
            st.markdown("- **Required Knowledge:**")
            for item in prerequisites["required_knowledge"]:
                st.markdown(f"  - {item}")
        if prerequisites.get("recommended_tools"):
            st.markdown("- **Recommended Tools:**")
            for item in prerequisites["recommended_tools"]:
                st.markdown(f"  - {item}")
        if prerequisites.get("setup_instructions"):
            st.markdown("- **Setup Instructions:**")
            for item in prerequisites["setup_instructions"]:
                st.markdown(f"  - {item}")
    
    st.markdown("---")

    # Display Introduction (collapsible)
    introduction = outline_data.get("introduction")
    if introduction:
        with st.expander("View Introduction"):
            st.markdown(introduction)

    # Display Sections and Subsections with more details
    st.markdown("### Sections")
    sections = outline_data.get("sections")
    if isinstance(sections, list) and sections:
        for i, section_details in enumerate(sections):
            if isinstance(section_details, dict):
                section_title = section_details.get("title", f"Section {i+1}")
                st.markdown(f"**{i+1}. {section_title}**")

                # Display section-specific details
                learning_goals = section_details.get("learning_goals")
                if learning_goals and isinstance(learning_goals, list):
                    st.markdown("    - **Learning Goals:**")
                    for goal in learning_goals:
                        st.markdown(f"        - {goal}")
                
                estimated_time = section_details.get("estimated_time")
                if estimated_time:
                    st.markdown(f"    - **Estimated Time:** {estimated_time}")

                include_code = section_details.get("include_code")
                st.markdown(f"    - **Include Code Examples:** {'Yes' if include_code else 'No'}")

                if include_code:
                    max_code_examples = section_details.get("max_code_examples")
                    if max_code_examples is not None:
                         st.markdown(f"    - **Max Code Examples:** {max_code_examples}")
                
                max_subpoints = section_details.get("max_subpoints")
                if max_subpoints is not None:
                    st.markdown(f"    - **Max Subpoints/Subsections:** {max_subpoints}")

                subsections = section_details.get("subsections")
                if subsections and isinstance(subsections, list):
                    st.markdown("    - **Subsections:**")
                    for sub_i, subsection_title in enumerate(subsections):
                        st.markdown(f"        - {str(subsection_title)}")
                st.markdown("") # Add a little space after each section
            else:
                # Handle case where section is just a string (less likely based on structure)
                 st.markdown(f"**{i+1}. {str(section_details)}**")
    else:
        st.markdown("*No sections defined in the outline.*")

    st.markdown("---")
    # Display Conclusion (collapsible)
    conclusion = outline_data.get("conclusion")
    if conclusion:
        with st.expander("View Conclusion"):
            st.markdown(conclusion)


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
    logger.info(f"format_section_content_as_markdown received content_data of type: {type(content_data)}")
    if isinstance(content_data, str):
        logger.info(f"content_data (string preview): {content_data[:200]}...")
    elif isinstance(content_data, dict):
        logger.info(f"content_data (dict keys): {list(content_data.keys())}")


    if not content_data:
        return "*No content available for this section.*"
        

    data = None
    if isinstance(content_data, str):
        try:
            # Attempt to parse the string as JSON
            
            # Clean the string if it has ```json ```
            content_data = content_data.strip()
            if content_data.startswith("```json") and content_data.endswith("```"):
                content_data = content_data[7:-3].strip() 
                
            parsed_json = json.loads(content_data)
            if isinstance(parsed_json, dict):
                data = parsed_json # Successfully parsed into a dictionary
            else:
                 # Parsed into something other than a dictionary (e.g., a list if the JSON was just `[]`)
                 logger.warning(f"format_section_content_as_markdown: Parsed JSON but it's not a dictionary. Type: {type(parsed_json)}. Original: {content_data[:200]}...")
                 return f"*Error: Section content was valid JSON but not the expected dictionary structure. Content: {content_data[:200]}...*"
        except json.JSONDecodeError:
            # Failed to parse as JSON. Assume it's already Markdown or plain text.
            # This is where the raw JSON string might be returned if it's not caught as a dict later.
            # Let's keep 'content_data' as is for now, and the 'if data:' check below will handle it.
            # If it's not a dict, it will fall through to the final 'return str(content_data)'
            pass # Keep content_data as the original string

    elif isinstance(content_data, dict):
        data = content_data # Input was already a dictionary
    else:
        # Handle unexpected non-string, non-dict types by converting to string
        logger.warning(f"Unexpected content type received: {type(content_data)}. Displaying as string: {str(content_data)[:200]}...")
        return str(content_data)

    # At this point, 'data' is either a dictionary (parsed or passed in) or None (if input was a string that failed to parse to dict)
    if isinstance(data, dict):
        main_markdown_content = data.get("content")
        if isinstance(main_markdown_content, str):
            # If 'content' field exists and is a string, this is the primary Markdown.
            # Strip potential outer markdown code fences from the content itself.
            processed_main_content = main_markdown_content.strip()
            if processed_main_content.startswith("```markdown") and processed_main_content.endswith("```"):
                processed_main_content = processed_main_content[11:-3].strip()
            elif processed_main_content.startswith("```") and processed_main_content.endswith("```"):
                # Handle generic triple backticks as well
                # Find the first newline to remove the language specifier if present
                first_newline = processed_main_content.find('\n')
                if first_newline != -1:
                    processed_main_content = processed_main_content[first_newline+1:-3].strip()
                else: # Should not happen with valid fenced blocks but as a fallback
                    processed_main_content = processed_main_content[3:-3].strip()
            
            current_section_markdown_parts = [processed_main_content]

            # Add image placeholders if present
            image_placeholders = data.get("image_placeholders")
            if image_placeholders and isinstance(image_placeholders, list):
                for placeholder in image_placeholders:
                    if isinstance(placeholder, dict):
                        placeholder_md = f"\n\n**[Image Placeholder: {placeholder.get('type', 'Unknown')}]**"
                        placeholder_md += f"\n- **Description:** {placeholder.get('description', 'No description')}"
                        placeholder_md += f"\n- **Alt Text:** {placeholder.get('alt_text', 'No alt text')}"
                        placeholder_md += f"\n- **Purpose:** {placeholder.get('purpose', 'No purpose specified')}"
                        if placeholder.get('placement'):
                            placeholder_md += f"\n- **Placement:** {placeholder.get('placement')}"
                        if placeholder.get('section_context'):
                            placeholder_md += f"\n- **Context:** {placeholder.get('section_context')}"
                        current_section_markdown_parts.append(placeholder_md)

            examples = data.get("code_examples")
            if examples:
                current_section_markdown_parts.append("\n\n**Code Examples:**") # Add a clear separator
                if isinstance(examples, list):
                    for example in examples:
                        lang = example.get("language", "") if isinstance(example, dict) else ""
                        code = example.get("code", str(example)) if isinstance(example, dict) else str(example)
                        desc = example.get("description", "") if isinstance(example, dict) else ""
                        
                        if desc:
                             current_section_markdown_parts.append(f"\n_{desc}_")
                        
                        code_str = str(code).strip()
                        if code_str.startswith("```") and code_str.endswith("```"):
                            current_section_markdown_parts.append(f"\n{code_str}")
                        else:
                            current_section_markdown_parts.append(f"\n```{lang}\n{code_str}\n```")
                elif isinstance(examples, str): # Single code example string
                    code_str = examples.strip()
                    if code_str.startswith("```") and code_str.endswith("```"):
                        current_section_markdown_parts.append(f"\n{code_str}")
                    else:
                        current_section_markdown_parts.append(f"\n```python\n{code_str}\n```")
            
            return "\n".join(current_section_markdown_parts).strip() # Join with single newline, then strip
        else:
            # If 'content' field is missing/not a string, but 'data' is a dict,
            # this indicates the LLM did not follow instructions to put Markdown in 'content'.
            # Log the problematic structure and return it as JSON for debugging.
            logger.warning(f"format_section_content_as_markdown: Parsed input as dict, but 'content' field is missing or not a string. Data: {json.dumps(data, indent=2)}")
            # For display, try to return something sensible, or just the JSON dump.
            # Returning the raw 'content_data' (original string if it was a string) might be safer than data dump.
            # However, if 'data' was passed in as a dict directly, content_data might not be the original string.
            # If 'content' key is missing or its value is not a string
            error_msg_template = "*Error: Section data was a dictionary but the 'content' key was missing or not a string. Raw data for section:*\n```json\n{}\n```"
            logger.error(f"format_section_content_as_markdown: 'content' key missing or not a string in parsed data. Data: {json.dumps(data, indent=2)}")
            return error_msg_template.format(json.dumps(data, indent=2))

    # Fallback: If 'data' is None (meaning content_data was a string but failed json.loads)
    # or if content_data was not a string or dict initially.
    # We assume the original content_data might be plain Markdown or an error string itself.
    # Attempt to strip common Markdown fences if it's a string.
    if isinstance(content_data, str):
        logger.warning(f"format_section_content_as_markdown: Content data was not a processable dictionary with a 'content' key. Treating as direct Markdown/text: {content_data[:200]}...")
        processed_content_data = content_data.strip()
        if processed_content_data.startswith("```markdown") and processed_content_data.endswith("```"):
            return processed_content_data[11:-3].strip()
        # Handle generic ```language ``` (e.g. ```python ... ```) by stripping the fence
        # This regex looks for ``` followed by optional language, then newline, then content, then ```
        match = re.match(r"^```[\w]*\n(.*?)\n```$", processed_content_data, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Handle simple ``` ``` without language specifier on the first line
        if processed_content_data.startswith("```") and processed_content_data.endswith("```"):
             # Check if it's a multi-line code block (```\ncode\n```) vs inline (```code```)
            if '\n' in processed_content_data:
                # Attempt to remove first and last lines if they are just backticks
                lines = processed_content_data.splitlines()
                if lines[0].strip() == "```" and lines[-1].strip() == "```":
                    return "\n".join(lines[1:-1]).strip()
            # For simple inline or single-line blocks, just remove the backticks
            return processed_content_data[3:-3].strip()
        return processed_content_data # Return the original string, possibly stripped of outer fences
    
    # If content_data was not a string initially (e.g. int, float, list not parsed to dict)
    logger.warning(f"format_section_content_as_markdown: Original content_data was not a string or dict. Type: {type(content_data)}. Returning as string.")
    return str(content_data)


def create_complete_blog_package() -> Dict[str, str]:
    """
    Creates a complete package of all generated content for download.
    Returns a dictionary with filename -> content mappings.
    """
    package = {}
    project_name = SessionManager.get('project_name', 'blog_project')
    
    # Clean project name for filenames
    safe_project_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in project_name)
    
    # 1. Raw/Original Blog Draft
    final_draft = SessionManager.get('final_draft')
    if final_draft:
        package[f"{safe_project_name}_original_draft.md"] = final_draft
    
    # 2. Refined Blog Draft
    refined_draft = SessionManager.get('refined_draft')
    if refined_draft:
        package[f"{safe_project_name}_refined_blog.md"] = refined_draft
    
    # 3. Blog Summary
    summary = SessionManager.get('summary')
    if summary:
        package[f"{safe_project_name}_summary.md"] = f"# Blog Summary\n\n{summary}"
    
    # 4. Title and Subtitle Options
    title_options = SessionManager.get('title_options')
    if title_options:
        titles_content = "# Title and Subtitle Options\n\n"
        for i, option in enumerate(title_options, 1):
            if isinstance(option, dict):
                title = option.get('title', 'N/A')
                subtitle = option.get('subtitle', 'N/A')
                titles_content += f"## Option {i}\n"
                titles_content += f"**Title:** {title}\n\n"
                titles_content += f"**Subtitle:** {subtitle}\n\n"
                titles_content += "---\n\n"
        package[f"{safe_project_name}_title_options.md"] = titles_content
    
    # 5. Social Media Content
    social_content = SessionManager.get('social_content')
    if social_content:
        # Individual social platform files
        if social_content.get('linkedin_post'):
            package[f"{safe_project_name}_linkedin_post.md"] = f"# LinkedIn Post\n\n{social_content['linkedin_post']}"
        
        if social_content.get('x_post'):
            package[f"{safe_project_name}_twitter_post.md"] = f"# X (Twitter) Post\n\n{social_content['x_post']}"
        
        if social_content.get('newsletter_content'):
            package[f"{safe_project_name}_newsletter.md"] = f"# Newsletter Content\n\n{social_content['newsletter_content']}"
        
        if social_content.get('content_breakdown'):
            package[f"{safe_project_name}_content_analysis.md"] = f"# Content Breakdown\n\n{social_content['content_breakdown']}"
        
        # Twitter Thread file
        x_thread = social_content.get('x_thread')
        if x_thread:
            thread_content = f"# X (Twitter) Thread\n\n"
            thread_content += f"**Topic:** {x_thread.get('thread_topic', 'N/A')}\n\n"
            thread_content += f"**Total Tweets:** {x_thread.get('total_tweets', 0)}\n\n"
            thread_content += "---\n\n"
            
            tweets = x_thread.get('tweets', [])
            for tweet in tweets:
                tweet_num = tweet.get('tweet_number', 1)
                tweet_content_text = tweet.get('content', '')
                char_count = tweet.get('character_count', len(tweet_content_text))
                
                thread_content += f"## Tweet {tweet_num} ({char_count} chars)\n\n"
                thread_content += f"{tweet_content_text}\n\n"
            
            package[f"{safe_project_name}_twitter_thread.md"] = thread_content
        
        # Combined social media file
        combined_social = "# Social Media Content Package\n\n"
        
        if social_content.get('content_breakdown'):
            combined_social += "## Content Analysis\n\n"
            combined_social += social_content['content_breakdown'] + "\n\n"
            combined_social += "---\n\n"
        
        if social_content.get('linkedin_post'):
            combined_social += "## LinkedIn Post\n\n"
            combined_social += social_content['linkedin_post'] + "\n\n"
            combined_social += "---\n\n"
        
        if social_content.get('x_post'):
            combined_social += "## X (Twitter) Post\n\n"
            combined_social += social_content['x_post'] + "\n\n"
            combined_social += "---\n\n"
        
        # Add Twitter Thread to combined file
        x_thread = social_content.get('x_thread')
        if x_thread:
            combined_social += "## X (Twitter) Thread\n\n"
            combined_social += f"**Topic:** {x_thread.get('thread_topic', 'N/A')}\n\n"
            combined_social += f"**Total Tweets:** {x_thread.get('total_tweets', 0)}\n\n"
            
            tweets = x_thread.get('tweets', [])
            for tweet in tweets:
                tweet_num = tweet.get('tweet_number', 1)
                tweet_content_text = tweet.get('content', '')
                char_count = tweet.get('character_count', len(tweet_content_text))
                
                combined_social += f"**Tweet {tweet_num}** ({char_count} chars): {tweet_content_text}\n\n"
            
            combined_social += "---\n\n"
        
        if social_content.get('newsletter_content'):
            combined_social += "## Newsletter Content\n\n"
            combined_social += social_content['newsletter_content'] + "\n\n"
        
        package[f"{safe_project_name}_all_social_content.md"] = combined_social
    
    # 6. Complete Project Summary
    outline = SessionManager.get('generated_outline')
    master_content = f"# {project_name} - Complete Blog Project\n\n"
    master_content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    if outline:
        master_content += f"**Blog Title:** {outline.get('title', 'N/A')}\n"
        master_content += f"**Difficulty Level:** {outline.get('difficulty_level', 'N/A')}\n\n"
    
    master_content += "## Project Contents\n\n"
    master_content += "This package contains the following files:\n\n"
    
    for filename in package.keys():
        master_content += f"- `{filename}`\n"
    
    master_content += "\n## Workflow Summary\n\n"
    master_content += "1. **Original Draft**: Raw blog content compiled from generated sections\n"
    master_content += "2. **Refined Blog**: Enhanced version with improved introduction and conclusion\n"
    master_content += "3. **Summary**: AI-generated summary of the blog content\n"
    master_content += "4. **Title Options**: Multiple title and subtitle suggestions\n"
    master_content += "5. **Social Content**: Ready-to-use social media posts for promotion\n\n"
    
    package[f"{safe_project_name}_README.md"] = master_content
    
    return package


def create_zip_download(package: Dict[str, str]) -> bytes:
    """
    Creates a ZIP file from the package dictionary.
    Returns the ZIP file as bytes for download.
    """
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in package.items():
            zip_file.writestr(filename, content)
    
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# --- UI Components ---

class ProjectHubUI:
    """
    Main landing page for project management: listing, resuming, and creating projects.
    """
    def render(self):
        st.title("🚀 Project Hub")
        st.markdown("Manage your blogging projects. Resume an existing project or start a new one.")

        api_base_url = SessionManager.get('api_base_url')
        
        # Create a container for the project list
        project_container = st.container()
        
        with project_container:
            try:
                # Fetch projects from backend
                with st.spinner("Loading projects..."):
                    response = asyncio.run(api_client.get_projects(base_url=api_base_url))
                    projects = response.get('projects', [])
                
                if not projects:
                    st.info("No projects found. Create a new project in the sidebar to get started!")
                    return

                # Convert to DataFrame for easier display if needed, or just iterate
                # Sort by updated_at desc
                projects.sort(key=lambda x: x.get('updated_at') or '', reverse=True)

                st.subheader(f"Your Projects ({len(projects)})")
                
                # Create a grid layout for project cards
                for project in projects:
                    project_id = project.get('id')
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([3, 2, 1])

                        with col1:
                            # Progress indicator
                            is_completed = project.get('completed_at') is not None
                            progress_icon = "✅" if is_completed else "🔄"
                            progress_text = "Completed" if is_completed else "In Progress"

                            st.markdown(f"### {progress_icon} {project.get('name', 'Untitled')}")
                            st.caption(f"ID: {project_id}")

                        with col2:
                            updated = project.get('updated_at')
                            if updated:
                                try:
                                    dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                                    updated_str = dt.strftime("%Y-%m-%d %H:%M")
                                except:
                                    updated_str = updated
                            else:
                                updated_str = "N/A"
                            st.caption(f"Last Updated: {updated_str}")

                            status = project.get('status', 'active')
                            st.caption(f"Status: {status.title()} | {progress_text}")

                        with col3:
                            btn_col1, btn_col2 = st.columns(2)
                            with btn_col1:
                                if st.button("▶️", key=f"resume_{project_id}", help="Resume Project"):
                                    self._resume_project(project_id, api_base_url)
                            with btn_col2:
                                if st.button("🗑️", key=f"delete_{project_id}", help="Delete Project"):
                                    st.session_state[f"confirm_delete_{project_id}"] = True
                                    st.rerun()

                    # Delete confirmation (outside the card columns for full width)
                    if st.session_state.get(f"confirm_delete_{project_id}"):
                        with st.container():
                            st.warning(f"⚠️ Are you sure you want to permanently delete **{project.get('name')}**?")
                            confirm_col1, confirm_col2, confirm_col3 = st.columns([2, 1, 1])
                            with confirm_col2:
                                if st.button("Yes, Delete", key=f"confirm_yes_{project_id}", type="primary"):
                                    self._delete_project(project_id, api_base_url)
                            with confirm_col3:
                                if st.button("Cancel", key=f"confirm_no_{project_id}"):
                                    st.session_state[f"confirm_delete_{project_id}"] = False
                                    st.rerun()

            except Exception as e:
                st.error(f"Failed to load projects: {str(e)}")
                logger.error(f"Project Hub Error: {e}")

    def _resume_project(self, project_id: str, api_base_url: str):
        """
        Resumes a project by fetching its full state from the backend
        and rehydrating the SessionManager.
        """
        try:
            with st.spinner(f"Resuming project {project_id}..."):
                # 1. Fetch full state
                state = asyncio.run(api_client.resume_project(project_id, base_url=api_base_url))
                
                if not state:
                    st.error("Failed to load project state.")
                    return

                # 2. Reset current state to avoid pollution
                SessionManager.reset_project_state()

                # 3. Rehydrate SessionManager
                SessionManager.set('current_project_id', state.get('project_id'))
                SessionManager.set('project_name', state.get('project_name'))
                SessionManager.set('selected_model', state.get('model_name') or AppConfig.DEFAULT_MODEL)
                SessionManager.set('selected_persona', state.get('persona') or 'neuraforge')
                SessionManager.set('specific_model', state.get('specific_model'))
                
                # Restore milestones
                outline = state.get('outline')
                SessionManager.set('generated_outline', outline)
                # Calculate total_sections from outline
                SessionManager.set('total_sections', len(outline.get('sections', [])) if outline else 0)
                # Set current_section_index based on generated_sections count
                generated_sections = state.get('generated_sections', {})
                SessionManager.set('current_section_index', len(generated_sections))
                SessionManager.set('final_draft', state.get('final_draft'))
                SessionManager.set('refined_draft', state.get('refined_draft'))
                SessionManager.set('summary', state.get('summary'))
                SessionManager.set('title_options', state.get('title_options'))
                SessionManager.set('social_content', state.get('social_content'))
                SessionManager.set('generated_sections', state.get('generated_sections', {}))
                SessionManager.set('cost_summary', state.get('cost_summary'))
                
                # Restore hashes if available (critical for caching)
                SessionManager.set('outline_hash', state.get('outline_hash'))
                
                # Set initialization flag
                SessionManager.set('is_initialized', True)
                SessionManager.set_status(f"Resumed project: {state.get('project_name')}")
                
                # 4. Rerun to switch view
                st.rerun()

        except Exception as e:
            st.error(f"Error resuming project: {str(e)}")
            logger.exception(f"Resume Error: {e}")

    def _delete_project(self, project_id: str, api_base_url: str):
        """
        Permanently deletes a project from Supabase.
        """
        try:
            with st.spinner(f"Deleting project..."):
                # Call the v2 API endpoint for permanent deletion
                import httpx
                response = asyncio.run(self._async_delete_project(project_id, api_base_url))

                if response.get('status') == 'success':
                    # Clear confirmation state
                    st.session_state[f"confirm_delete_{project_id}"] = False

                    # Clear current project if it was the deleted one
                    if SessionManager.get('current_project_id') == project_id:
                        SessionManager.reset_project_state()
                        SessionManager.set('current_project_id', None)

                    st.success("Project deleted successfully!")
                    st.rerun()
                else:
                    st.error(f"Failed to delete project: {response.get('message', 'Unknown error')}")

        except Exception as e:
            st.error(f"Error deleting project: {str(e)}")
            logger.exception(f"Delete Error: {e}")

    async def _async_delete_project(self, project_id: str, api_base_url: str) -> dict:
        """Async helper to delete project via API."""
        import httpx
        from utils.auth import get_auth_headers
        headers = get_auth_headers(target_audience=api_base_url)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{api_base_url}/api/v2/projects/{project_id}",
                params={"permanent": "true"},
                headers=headers
            )
            response.raise_for_status()
            return response.json()

class SidebarUI:
    """Handles rendering the sidebar and initialization logic."""

    def _fetch_personas(self, api_base_url: str) -> Dict[str, Any]:
        """Fetch available personas from backend, with caching."""
        cached_personas = SessionManager.get('available_personas', {})
        if cached_personas:
            return cached_personas

        try:
            personas = asyncio.run(api_client.get_personas(api_base_url))
            SessionManager.set('available_personas', personas)
            return personas
        except Exception as e:
            logger.error(f"Failed to fetch personas: {e}")
            # Return default fallback
            return {
                'neuraforge': {'name': 'Neuraforge', 'description': 'Technical newsletter voice'},
                'student_sharing': {'name': 'Student Sharing', 'description': 'Authentic student voice'},
                'sebastian_raschka': {'name': 'Sebastian Raschka', 'description': 'Expert practitioner voice'},
                'tech_blog_writer': {'name': 'Tech Blog Writer', 'description': 'Technical blog writer following industry best practices'}
            }

    def _fetch_models(self, api_base_url: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch available models from backend, with caching."""
        cached_models = SessionManager.get('available_models', {})
        if cached_models and not force_refresh:
            return cached_models

        try:
            models_resp = asyncio.run(api_client.get_models(api_base_url))
            # Normalize shape to { 'providers': { provider: { name, models: [ {id, name, description} ] } } }
            providers = {}
            if isinstance(models_resp, dict) and 'providers' in models_resp:
                providers = models_resp['providers'] or {}
            else:
                # Backward-compat: assume {provider: [model_ids]}
                providers = {p: {"name": p.title(), "models": [{"id": mid, "name": mid, "description": ""} for mid in mids]}
                             for p, mids in (models_resp or {}).items()}

            normalized = { 'providers': providers }
            SessionManager.set('available_models', normalized)
            return normalized
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            # Return default fallback based on current config
            fallback = {
                'providers': {
                    provider: {
                        "name": ModelConfig.get_provider_display_name(provider),
                        "models": [{"id": f"{provider}-default", "name": f"Default {ModelConfig.get_provider_display_name(provider)} Model", "description": "Default model for this provider"}]
                    }
                    for provider in AppConfig.SUPPORTED_MODELS
                }
            }
            return fallback

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

            st.markdown("---")

            # Project Dashboard Section (New API-based)
            # try:
            #     # Initialize API client if not already done
            #     if not hasattr(st.session_state, 'blog_api_client'):
            #         st.session_state.blog_api_client = BlogAPIClient(base_url=api_base_url)

            #     # Render project dashboard in sidebar
            #     api_dashboard = APIProjectDashboard(st.session_state.blog_api_client)
            #     selected_project = api_dashboard.render_sidebar()

            #     # Handle project selection
            #     if selected_project:
            #         SessionManager.set('current_project_id', selected_project)
            #         SessionManager.set('project_id', selected_project)
            #         st.rerun()

            # except Exception as e:
            #     st.error(f"Dashboard error: {str(e)}")
            #     logger.error(f"Dashboard error: {e}")
            
            # Add "Back to Hub" button if in a project
            if SessionManager.get('current_project_id'):
                if st.button("⬅️ Back to Project Hub", use_container_width=True):
                    SessionManager.set('current_project_id', None)
                    SessionManager.set('is_initialized', False)
                    st.rerun()

            st.markdown("---")

            # --- Model Configuration (outside form for reactivity) ---
            st.markdown("**🤖 Model Configuration**")

            # Get available providers first (with fallback to config)
            # We'll fetch models after we know if provider changed
            cached_models = SessionManager.get('available_models', {})
            provider_map = (cached_models or {}).get('providers', {})
            available_providers = list(provider_map.keys()) if provider_map else AppConfig.SUPPORTED_MODELS

            # Provider selection with enhanced display
            current_model = SessionManager.get('selected_model', AppConfig.DEFAULT_MODEL)
            if current_model not in available_providers:
                current_model = available_providers[0] if available_providers else AppConfig.DEFAULT_MODEL

            # Create provider options with clean display
            def format_provider_option(provider):
                return ModelConfig.get_provider_display_name(provider)

            selected_model = st.selectbox(
                "Model Provider",
                options=available_providers,
                index=available_providers.index(current_model) if current_model in available_providers else 0,
                format_func=format_provider_option,
                help="Choose the LLM provider. Each provider offers different models and capabilities."
            )

            # Check if provider changed (for reactivity) - store before updating
            provider_changed = selected_model != current_model

            # Fetch available models (used for provider/model dropdowns)
            # Force refresh when provider changes to ensure models list updates
            available_models = self._fetch_models(api_base_url, force_refresh=provider_changed)

            # Update session state immediately when provider changes
            if provider_changed:
                SessionManager.set('selected_model', selected_model)
                # Clear specific model when provider changes
                SessionManager.set('specific_model', None)
                # Rerun will happen automatically since this widget is outside a form

            # Specific model selection within provider (using /models shape)
            specific_model = None
            provider_entry = provider_map.get(selected_model, {})
            provider_models = provider_entry.get('models', []) or []

            if provider_models:
                # Show provider description
                provider_description = ModelConfig.get_provider_description(selected_model)
                st.caption(provider_description)

                # Build options with enhanced formatting
                model_ids = [m.get('id') for m in provider_models if m.get('id')]
                id_to_display = {}
                id_to_description = {}

                for model in provider_models:
                    model_id = model.get('id')
                    model_name = model.get('name', model_id)
                    model_desc = model.get('description', '')
                    id_to_display[model_id] = model_name
                    id_to_description[model_id] = model_desc

                if model_ids:
                    # Handle dependent dropdown logic properly
                    current_specific = SessionManager.get('specific_model')
                    specific_index = 0

                    # Reset to first option if provider changed OR current specific model not available
                    if provider_changed or not (current_specific and current_specific in model_ids):
                        specific_index = 0
                    else:
                        specific_index = model_ids.index(current_specific)

                    def format_model_option(model_id):
                        name = id_to_display.get(model_id, model_id)
                        desc = id_to_description.get(model_id, '')
                        if desc:
                            return f"{name} - {desc}"
                        return name

                    specific_model = st.selectbox(
                        f"{ModelConfig.get_provider_display_name(selected_model)} Model",
                        options=model_ids,
                        index=specific_index,
                        format_func=format_model_option,
                        help=f"Choose the specific model variant for {ModelConfig.get_provider_display_name(selected_model)}",
                        key=f"specific_model_{selected_model}"  # Dynamic key for reactivity
                    )

                    # Show selected model description
                    if specific_model and id_to_description.get(specific_model):
                        st.caption(id_to_description[specific_model])
                else:
                    st.info(f"No specific models available for {selected_model}")
            else:
                st.info(f"Using default model for {ModelConfig.get_provider_display_name(selected_model)}")

            # Persist the latest specific model selection
            if specific_model:
                SessionManager.set('specific_model', specific_model)

            st.markdown("---")

            # Initialization Form (keeps project name, persona, file upload inside form)
            with st.form("init_form"):
                st.subheader("Initialize Project")
                project_name = st.text_input(
                    "Blog Project Name",
                    value=SessionManager.get('project_name', ""),
                    help="A unique name for your blog project."
                )

                # Persona/Output Style Selection
                st.markdown("**✍️ Writing Style Configuration**")

                # Fetch available personas
                available_personas = self._fetch_personas(api_base_url)

                # Create persona selection
                persona_options = list(available_personas.keys())
                persona_names = [available_personas[p].get('name', p.title()) for p in persona_options]
                persona_descriptions = [available_personas[p].get('description', 'No description') for p in persona_options]

                current_persona = SessionManager.get('selected_persona', 'neuraforge')
                persona_index = 0
                if current_persona in persona_options:
                    persona_index = persona_options.index(current_persona)

                selected_persona = st.selectbox(
                    "Writing Persona",
                    options=persona_options,
                    format_func=lambda x: available_personas[x].get('name', x.title()),
                    index=persona_index,
                    help="Choose the writing style and voice for your blog content."
                )

                # Show persona description
                if selected_persona in available_personas:
                    st.markdown(f"*{available_personas[selected_persona].get('description', '')}*")
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
                    SessionManager.set('selected_persona', selected_persona)
                    SessionManager.set('uploaded_files_info', [{"name": f.name, "type": f.type, "size": f.size} for f in uploaded_files])
                    SessionManager.set('is_initialized', False) # Reset initialization status
                    SessionManager.set_status("Initializing...")
                    SessionManager.clear_error()

                    # Run the async initialization process
                    try:
                        # Use current provider and persona from session (reactive section above)
                        provider_for_init = SessionManager.get('selected_model', AppConfig.DEFAULT_MODEL)
                        persona_for_init = SessionManager.get('selected_persona', 'neuraforge')
                        asyncio.run(self._initialize_assistant(project_name, provider_for_init, uploaded_files, api_base_url, persona=persona_for_init))
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
                    sel_provider = SessionManager.get('selected_model')
                    sel_specific = SessionManager.get('specific_model') or 'default'
                    st.sidebar.write(f"- **Model:** {sel_provider} / {sel_specific}")
                    st.sidebar.write("**Processed Files:**")
                    hashes = SessionManager.get('processed_file_hashes', {})
                    if hashes:
                        for path, hash_val in hashes.items():
                            hash_display = f"{hash_val[:8]}..." if hash_val else "pending"
                            st.sidebar.write(f"  - `{Path(path).name}` (Hash: `{hash_display}`)")
                    else:
                        st.sidebar.write("  (No files processed yet)")

                else:
                    st.sidebar.info(status_message)

            # Cost tracking summary
            cost_summary = SessionManager.get('cost_summary')
            st.sidebar.markdown("---")
            st.sidebar.markdown("**💰 Cost Tracking**")
            if cost_summary:
                total_cost = cost_summary.get('total_cost', 0.0)
                # Handle both field naming conventions (from resume vs from generation)
                total_tokens = cost_summary.get('total_tokens') or (
                    cost_summary.get('total_input_tokens', 0) + cost_summary.get('total_output_tokens', 0)
                )
                total_calls = cost_summary.get('total_calls', 0)

                st.sidebar.metric("Total Cost", f"${total_cost:.4f}")

                # Duration display
                duration = cost_summary.get('workflow_duration_seconds')
                if duration:
                    hours = int(duration // 3600)
                    minutes = int((duration % 3600) // 60)
                    st.sidebar.metric("Total Time", f"{hours}h {minutes}m")

                st.sidebar.write(f"Tokens: {total_tokens:,}")
                if total_calls > 0:
                    st.sidebar.write(f"LLM Calls: {total_calls}")

                by_stage = cost_summary.get('by_stage') or {}
                if by_stage:
                    with st.sidebar.expander("Stage Breakdown", expanded=False):
                        for stage_name, data in by_stage.items():
                            stage_cost = data.get('cost', 0.0)
                            stage_tokens = data.get('tokens', 0)
                            st.markdown(
                                f"- **{stage_name.replace('_', ' ').title()}**: ${stage_cost:.4f}"
                                f" ({stage_tokens:,} tokens)"
                            )
            else:
                st.sidebar.caption("No cost data yet. Generate content to see usage.")

            # How to Use Section
            st.sidebar.markdown("---")
            with st.sidebar.expander("📚 How to Use", expanded=False):
                st.markdown("""
                1. **Create Project**: Upload files (notebooks, markdown) and name your project.
                2. **Generate Outline**: The AI analyzes your files and proposes a blog outline.
                3. **Generate Draft**: Create the blog post section by section.
                4. **Refine**: Add introduction, conclusion, and polish the content.
                5. **Social Media**: Generate LinkedIn posts, Tweets, and newsletters.
                """)

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


    async def _initialize_assistant(self, project_name, model_name, uploaded_files, base_url, persona=None):
        """Handles the async steps of uploading and processing files via API."""
        SessionManager.set_status("Uploading files...")
        files_to_send: List[Tuple[str, bytes, str]] = []
        for f in uploaded_files:
            files_to_send.append((f.name, f.getvalue(), f.type or "application/octet-stream"))

        upload_result = await api_client.upload_files(project_name, files_to_send, base_url=base_url,
                                                      model_name=model_name, persona=persona)
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

        # Try to get project_id from upload result (assumes backend creates project during upload)
        project_id = upload_result.get("project_id")
        if project_id:
            SessionManager.set('current_project_id', project_id)
            SessionManager.set('current_project_name', project_name)
            logger.info(f"Project created with ID: {project_id}")

        SessionManager.set_status("Assistant Initialized Successfully!")
        SessionManager.set('is_initialized', True)
        SessionManager.clear_error()
        SessionManager.set('cost_summary', None)
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

        # Display current configuration
        with st.expander("🔧 Current Configuration", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Model Provider:** {model_name}")
                specific_model = SessionManager.get('specific_model')
                if specific_model:
                    st.markdown(f"**Specific Model:** {specific_model}")
                else:
                    st.markdown(f"**Specific Model:** Default")
            with col2:
                persona = SessionManager.get('selected_persona', 'neuraforge')
                personas = SessionManager.get('available_personas', {})
                # Handle None persona gracefully
                if persona:
                    persona_name = personas.get(persona, {}).get('name', persona.title()) if personas else persona.title()
                else:
                    persona_name = "Default"
                st.markdown(f"**Writing Style:** {persona_name}")

                if personas and persona in personas:
                    st.markdown(f"*{personas[persona].get('description', '')}*")

        # Add text area for user guidelines here
        user_guidelines = st.text_area("Optional Guidelines:",
                                       help="Provide specific instructions for the outline generation (e.g., 'Focus on practical examples', 'Exclude section on history').",
                                       key="user_guidelines_input")
        
        # Add length preference controls
        with st.expander("📏 Blog Length Preferences (Optional)", expanded=False):
            st.markdown("**System will analyze your content and suggest optimal length, but you can override these preferences.**")
            
            length_preference = st.selectbox(
                "Preferred Blog Length",
                ["Auto-detect (Recommended)", "Short (800-1200)", "Medium (1200-2000)", 
                 "Long (2000-3000)", "Very Long (3000+)", "Custom"],
                help="System will analyze content density and suggest optimal length. Choose 'Auto-detect' for best results.",
                key="length_preference_select"
            )
            
            custom_length = None
            if length_preference == "Custom":
                custom_length = st.number_input(
                    "Target Word Count", 
                    min_value=500, 
                    max_value=5000, 
                    value=1500,
                    step=100,
                    help="Specify exact target word count for your blog",
                    key="custom_length_input"
                )
            
            writing_style = st.selectbox(
                "Writing Style",
                ["Balanced", "Concise & Focused", "Comprehensive & Detailed"],
                help="Affects content depth and explanation verbosity. 'Balanced' is recommended for most content.",
                key="writing_style_select"
            )
            
            st.info("💡 The AI will analyze your content type (theoretical/practical/mixed) and density to suggest the optimal length, then adjust based on your preferences.")

        # Resume from saved outline option
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("Generate Outline", key="gen_outline_btn"):
                # Retrieve guideline text and length preferences inside the button's logic block
                guideline_text = st.session_state.get('user_guidelines_input', '') # Get value using key
                length_pref = st.session_state.get('length_preference_select', 'Auto-detect (Recommended)')
                custom_len = st.session_state.get('custom_length_input', 1500) if length_pref == "Custom" else None
                style_pref = st.session_state.get('writing_style_select', 'Balanced')

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
                            length_preference=length_pref, # Pass length preference
                            custom_length=custom_len, # Pass custom length if specified
                            writing_style=style_pref, # Pass writing style
                            persona_style=SessionManager.get('selected_persona'), # Pass selected persona
                            specific_model=SessionManager.get('specific_model'), # Pass specific model
                            base_url=SessionManager.get('api_base_url')
                        ))
                    SessionManager.set('current_project_id', result.get('project_id'))
                    SessionManager.set('generated_outline', result.get('outline'))
                    SessionManager.set('total_sections', len(result.get('outline', {}).get('sections', [])))
                    SessionManager.set('current_section_index', 0) # Reset section index
                    SessionManager.set('generated_sections', {}) # Clear old sections
                    SessionManager.set('final_draft', None) # Clear old draft
                    SessionManager.set('social_content', None) # Clear old social content
                    SessionManager.set('cost_summary', result.get('cost_summary'))
                    SessionManager.set_status("Outline generated successfully.")
                    logger.info(f"Outline generated for project ID: {result.get('project_id')}")
                    
                    # Auto-save the generated outline
                    try:
                        auto_save_manager = SessionManager.get_auto_save_manager()
                        outline_data = result.get('outline')
                        if outline_data:
                            saved_path = auto_save_manager.save_outline(
                                project_name=project_name,
                                outline_data=outline_data,
                                project_id=result.get('project_id'),
                                add_timestamp=True
                            )
                            logger.info(f"Auto-saved outline to: {saved_path}")
                    except Exception as save_err:
                        logger.warning(f"Failed to auto-save outline: {save_err}")
                except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                    SessionManager.set_error(f"API Error generating outline: {str(api_err)}")
                    SessionManager.set_status("Outline generation failed.")
                except Exception as e:
                    logger.exception(f"Unexpected error during outline generation: {e}")
                    SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                    SessionManager.set_status("Outline generation failed.")
        
        with col2:
            if st.button("📁 I have outline already", key="load_outline_btn"):
                # Show option to load from saved outlines
                auto_save_manager = SessionManager.get_auto_save_manager()
                project_name = SessionManager.get('project_name')
                if project_name:
                    saved_outlines = auto_save_manager.list_saved_outlines(project_name)
                    if saved_outlines:
                        st.write("**Available saved outlines:**")
                        for i, outline_info in enumerate(saved_outlines):
                            col_load, col_info = st.columns([1, 3])
                            with col_load:
                                if st.button("Load", key=f"load_outline_{i}"):
                                    try:
                                        # Load the outline
                                        loaded_outline = auto_save_manager.load_outline(outline_info["file_path"])
                                        SessionManager.set('generated_outline', loaded_outline)
                                        SessionManager.set('total_sections', len(loaded_outline.get('sections', [])))
                                        SessionManager.set('current_section_index', 0)
                                        SessionManager.set('generated_sections', {})
                                        SessionManager.set('final_draft', None)
                                        SessionManager.set('social_content', None)
                                        SessionManager.set('current_project_id', outline_info.get("project_id"))
                                        SessionManager.set_status("Outline loaded successfully from saved file.")
                                        st.success(f"✅ Loaded outline: {outline_info['title']}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed to load outline: {str(e)}")
                            with col_info:
                                st.caption(f"**{outline_info['title']}** ({outline_info['filename']})")
                                if outline_info.get('saved_at'):
                                    st.caption(f"Saved: {outline_info['saved_at'][:19]}")
                    else:
                        st.info("No saved outlines found for this project.")
                else:
                    st.warning("Please set a project name first.")

        # Display Outline
        outline = SessionManager.get('generated_outline')
        if outline:
            st.subheader("Generated Outline")
            # Display the outline in a readable format
            display_readable_outline(outline)
            st.success(f"Outline ready for Project ID: `{SessionManager.get('current_project_id')}`")
            st.markdown("---")
            st.info("Proceed to the 'Blog Draft' tab to generate sections.")
        else:
            st.info("Click 'Generate Outline' to start.")


class BlogDraftUI:
    """Handles the Blog Draft Tab."""
    def render(self):
        st.header("2. Generate Blog Draft Sections")

        if not SessionManager.get('current_project_id') or not SessionManager.get('generated_outline'):
            st.warning("Please generate an outline first on the 'Outline' tab.")
            return

        project_id = SessionManager.get('current_project_id')
        project_name = SessionManager.get('project_name')
        outline = SessionManager.get('generated_outline')
        total_sections = SessionManager.get('total_sections', 0)
        current_section_index = SessionManager.get('current_section_index', 0)
        generated_sections = SessionManager.get('generated_sections', {})

        if total_sections == 0:
            st.warning("The generated outline has no sections.")
            return

        # Resume from saved draft option
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.progress(current_section_index / total_sections if total_sections > 0 else 0)
            st.write(f"Progress: {current_section_index}/{total_sections} sections generated.")
        
        with col2:
            if st.button("📁 I have draft already", key="load_draft_btn"):
                # Show option to load from saved drafts
                auto_save_manager = SessionManager.get_auto_save_manager()
                if project_name:
                    saved_drafts = auto_save_manager.list_saved_drafts(project_name)
                    if saved_drafts:
                        st.write("**Available saved drafts:**")
                        for i, draft_info in enumerate(saved_drafts):
                            col_load, col_info = st.columns([1, 3])
                            with col_load:
                                if st.button("Load", key=f"load_draft_{i}"):
                                    try:
                                        # Load the draft
                                        loaded_draft = auto_save_manager.load_draft_content(draft_info["file_path"])
                                        SessionManager.set('final_draft', loaded_draft)
                                        SessionManager.set('current_project_id', draft_info.get("project_id"))
                                        SessionManager.set_status("Blog draft loaded successfully from saved file.")
                                        st.success(f"✅ Loaded draft: {draft_info['filename']}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed to load draft: {str(e)}")
                            with col_info:
                                st.caption(f"**{draft_info['filename']}**")
                                if draft_info.get('saved_at'):
                                    st.caption(f"Saved: {draft_info['saved_at'][:19]}")
                    else:
                        st.info("No saved drafts found for this project.")
                else:
                    st.warning("Please set a project name first.")
        
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
                            project_id=project_id,
                            section_index=current_section_index,
                            max_iterations=max_iter,
                            quality_threshold=quality_thresh,
                            base_url=SessionManager.get('api_base_url')
                        ))

                    # Extract data from the result dictionary
                    section_content_raw = result.get("section_content")
                    section_title_raw = result.get("section_title", current_section_info.get('title', 'Untitled'))
                    image_placeholders = result.get("image_placeholders", [])  # Extract image placeholders
                    was_cached = result.get("was_cached", False) # Get the cache status flag

                    # Log whether the section was cached or generated
                    if was_cached:
                        logger.info(f"Section {current_section_index + 1} ('{section_title_raw}') loaded from cache.")
                        status_msg = f"Section {current_section_index + 1} loaded from cache."
                    else:
                        logger.info(f"Section {current_section_index + 1} ('{section_title_raw}') generated.")
                        status_msg = f"Section {current_section_index + 1} generated."

                    # Create a dict with content and placeholders for formatting
                    section_data = {
                        "content": section_content_raw,
                        "image_placeholders": image_placeholders
                    }

                    # Validate content (format_section_content_as_markdown now handles the dict with placeholders)
                    formatted_content = format_section_content_as_markdown(section_data)
                    if "Error:" in formatted_content and section_content_raw is None:
                         logger.warning(f"generate_section (cached={was_cached}) for project {project_id}, section {current_section_index} returned None content. Full result: {result}")
                    elif "Error:" in formatted_content:
                         logger.error(f"generate_section (cached={was_cached}) for project {project_id}, section {current_section_index} returned unexpected content type: {type(section_content_raw)}. Value: {section_content_raw}")


                    # Update session state
                    new_sections = SessionManager.get('generated_sections', {})
                    new_sections[current_section_index] = {
                        "title": section_title_raw,
                        "raw_content": section_content_raw, # Store original API response
                        "formatted_content": formatted_content, # Store formatted version
                        "image_placeholders": image_placeholders,  # Store image placeholders
                        "cost_delta": result.get("section_cost"),
                        "token_delta": result.get("section_tokens")
                    }
                    SessionManager.set('generated_sections', new_sections)
                    SessionManager.set('cost_summary', result.get('cost_summary'))
                    SessionManager.set('current_section_index', current_section_index + 1)
                    SessionManager.set_status(status_msg) # Use the dynamic status message
                    st.rerun() # Rerun to update progress and show generated section

                except (httpx.HTTPStatusError, ConnectionError, ValueError) as api_err:
                    SessionManager.set_error(f"API Error generating section {current_section_index + 1}: {str(api_err)}")
                    SessionManager.set_status("Section generation failed.")
                except Exception as e:
                    logger.exception(f"Unexpected error during section generation: {e}")
                    SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                    SessionManager.set_status("Section generation failed.")
        else:
            # --- Draft Compilation ---
            st.subheader("All Sections Generated!")
            if st.button("Compile Final Draft", key="compile_draft_btn"):
                SessionManager.set_status("Compiling final draft from sections...")
                SessionManager.clear_error()
                try:
                    # --- Frontend Draft Compilation ---
                    blog_title = SessionManager.get('generated_outline', {}).get('title', 'My Blog Post')
                    sections_data = SessionManager.get('generated_sections', {})
                    # Convert keys to int for proper sorting (keys may be strings from JSON/resume)
                    sorted_indices = sorted(sections_data.keys(), key=lambda x: int(x))

                    draft_parts = [f"# {blog_title}\n"] # Start with H1 title

                    for index in sorted_indices:
                        section = sections_data.get(index, {})
                        section_num = int(index) + 1  # Convert to int for display
                        section_title = section.get('title', f'Section {section_num}')
                        # Try formatted_content first, fall back to content (from backend resume)
                        formatted_content = section.get('formatted_content') or section.get('content', '')

                        draft_parts.append(f"## {section_title}\n") # Add H2 for section title
                        draft_parts.append(formatted_content)

                    final_draft_content = "\n\n".join(draft_parts)
                    SessionManager.set('final_draft', final_draft_content)
                    SessionManager.set_status("Draft compiled successfully in frontend.")
                    logger.info(f"Draft compiled in frontend for project ID: {project_id}")

                    # Auto-save the compiled blog draft
                    try:
                        auto_save_manager = SessionManager.get_auto_save_manager()
                        project_name = SessionManager.get('project_name')
                        if project_name and final_draft_content:
                            saved_path = auto_save_manager.save_blog_draft(
                                project_name=project_name,
                                draft_content=final_draft_content,
                                project_id=project_id,
                                add_timestamp=True
                            )
                            logger.info(f"Auto-saved blog draft to: {saved_path}")
                    except Exception as save_err:
                        logger.warning(f"Failed to auto-save blog draft: {save_err}")
                    
                    st.rerun() # Rerun to update UI and show compiled draft
                except Exception as e:
                    logger.exception(f"Unexpected error during draft compilation: {e}")
                    SessionManager.set_error(f"An unexpected error occurred: {str(e)}")
                    SessionManager.set_status("Draft compilation failed.")
            
            # Display the final draft here if it exists in session state, after the compile button
            final_draft_content_for_display_in_blog_draft_tab = SessionManager.get('final_draft')
            project_name_for_download_in_blog_draft_tab = SessionManager.get('project_name', "untitled_project")
            if final_draft_content_for_display_in_blog_draft_tab:
                st.subheader("Compiled Blog Draft Preview")
                st.download_button(
                    label="Download Compiled Draft (.md)",
                    data=final_draft_content_for_display_in_blog_draft_tab,
                    file_name=f"{project_name_for_download_in_blog_draft_tab}_compiled_draft.md",
                    mime="text/markdown",
                    key="download_compiled_draft_blog_draft_tab_primary"
                )
                with st.expander("View Compiled Draft", expanded=True):
                    st.markdown(final_draft_content_for_display_in_blog_draft_tab)
                with st.expander("Markdown Source", expanded=False):
                    st.text_area("Markdown Source (Compiled)", final_draft_content_for_display_in_blog_draft_tab, height=400, key="md_source_blog_draft_tab_primary")
                st.info("Proceed to the 'Refine & Finalize' tab to add introduction, conclusion, summary, and titles.")


        st.markdown("---")

        # --- Display Final Draft ---
        final_draft = SessionManager.get('final_draft')
        if final_draft:
            st.subheader("Final Blog Draft")
            st.download_button(
                label="Download Draft (.md)",
                data=final_draft,
                file_name=f"{project_name}_draft.md",
                mime="text/markdown",
                key="dl_compiled_blog_tab" # Static unique key
            )
            with st.expander("Preview Draft", expanded=True):
                st.markdown(final_draft)
            with st.expander("Markdown Source", expanded=False):
                st.text_area("Markdown", final_draft, height=400)
            st.info("Proceed to the 'Refine & Finalize' tab to add introduction, conclusion, summary, and titles.") # Updated instruction

        # --- Display Generated Sections & Feedback ---
        if generated_sections:
            st.subheader("Generated Content")
            # Convert keys to int for proper sorting (keys may be strings from JSON)
            sorted_indices = sorted(generated_sections.keys(), key=lambda x: int(x))
            for index in sorted_indices:
                section_data = generated_sections[index]
                section_num = int(index) + 1  # Convert to int for display
                with st.expander(f"Section {section_num}: {section_data.get('title', 'Untitled')}", expanded=True): # Expand by default now
                    # Display content - try formatted_content first, fall back to content (from backend resume)
                    content = section_data.get('formatted_content') or section_data.get('content') or '*No content available.*'
                    st.markdown(content)

                    # Display Raw Section Data (not nested in an expander)
                    st.markdown("---") # Visual separator
                    st.markdown("**Raw Section Data:**")
                    raw_content_display = section_data.get('raw_content') or section_data.get('content')
                    if isinstance(raw_content_display, (dict, list)):
                        st.json(raw_content_display)
                    elif isinstance(raw_content_display, str):
                        # If it's a string, try to parse as JSON for pretty printing, else show as text
                        try:
                            # Attempt to load and re-dump for consistent formatting if it's a JSON string
                            st.json(json.loads(raw_content_display))
                        except json.JSONDecodeError:
                            # If not valid JSON, display as a text area for potentially long strings
                            st.text_area("Raw Text Data", raw_content_display, height=150, key=f"raw_text_{index}")
                    elif raw_content_display is None:
                        st.caption("*Raw content is not available (None).*")
                    else:
                        # For any other type, display as string in a text area
                        st.text_area("Raw Data", str(raw_content_display), height=100, key=f"raw_other_{index}")
                    st.markdown("---") # Visual separator

                    section_cost = section_data.get('cost_delta')
                    section_tokens = section_data.get('token_delta')
                    if section_cost is not None or section_tokens is not None:
                        cost_str = f"${section_cost:.4f}" if isinstance(section_cost, (int, float)) else "N/A"
                        tokens_str = f"{section_tokens:,}" if isinstance(section_tokens, (int, float)) else "N/A"
                        st.caption(f"Section cost (incremental): {cost_str} | Tokens: {tokens_str}")
                    
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
                                    project_id=project_id,
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
                                logger.warning(f"regenerate_section for project {project_id}, section {index} returned None content. Full result: {result}")
                            else:
                                # Handle unexpected non-string content
                                logger.error(f"regenerate_section for project {project_id}, section {index} returned non-string content: {type(section_content_raw)}. Value: {section_content_raw}")
                                # Note: section_content variable is not directly used below, but error logging is kept.

                            # Explicitly fetch the latest state right before updating
                            current_sections_state = SessionManager.get('generated_sections', {})
                            if index in current_sections_state:
                                current_sections_state[index]['raw_content'] = section_content_raw # Update raw content
                                current_sections_state[index]['formatted_content'] = format_section_content_as_markdown(section_content_raw) # Update formatted content
                                current_sections_state[index]['cost_delta'] = result.get("section_cost")
                                current_sections_state[index]['token_delta'] = result.get("section_tokens")
                                # Note: Title is assumed unchanged during regeneration, but could be updated if API returns it
                                SessionManager.set('generated_sections', current_sections_state) # Save updated state
                                SessionManager.set('cost_summary', result.get('cost_summary'))
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

        # Removed the old display block for final_draft from the end of this method.
        # It's now handled within the 'else' block (all sections generated).

class RefinementUI:
    """Handles the Refine & Finalize Tab."""
    def render(self):
        st.header("3. Refine & Finalize Blog")

        final_draft = SessionManager.get('final_draft')
        project_id = SessionManager.get('current_project_id')
        project_name = SessionManager.get('project_name')

        if not final_draft:
            st.warning("No blog draft found in current session.")
            
            # Add upload option for resuming with existing draft
            st.subheader("📁 Resume with Existing Draft")
            st.info("Upload your previously generated blog draft to continue with refinement.")
            
            uploaded_file = st.file_uploader(
                "Choose your blog draft file", 
                type=['md', 'txt'],
                help="Upload a markdown (.md) or text (.txt) file containing your blog draft"
            )
            
            if uploaded_file is not None:
                # Read the uploaded file
                draft_content = uploaded_file.read().decode('utf-8')
                
                # Preview the uploaded content
                st.subheader("📝 Preview Uploaded Draft")
                with st.expander("View uploaded content", expanded=False):
                    st.markdown(draft_content)
                
                # Allow user to set project name if not available
                if not project_name:
                    project_name = st.text_input(
                        "Project Name", 
                        value=uploaded_file.name.split('.')[0],
                        help="Enter a name for this project"
                    )
                
                if st.button("Use This Draft for Refinement", key="use_uploaded_draft"):
                    if project_name:
                        # Store the uploaded draft in session state
                        SessionManager.set('final_draft', draft_content)
                        SessionManager.set('project_name', project_name)
                        # Clear any existing project_id since we're starting fresh
                        SessionManager.set('current_project_id', None)
                        st.success("✅ Draft loaded successfully! You can now refine it.")
                        st.rerun()
                    else:
                        st.error("Please enter a project name.")
            
            return
        # final_draft = SessionManager.get('final_draft') # This is the unrefined draft

        # Removed the preview of the unrefined 'final_draft' from this tab.
        # This tab should focus on the 'refined_draft' which is its output.
        # The 'final_draft' (unrefined) is displayed on the 'Blog Draft' tab.

        st.subheader("Generate Introduction, Conclusion, Summary, Titles & Suggestions") # Updated subheader

        # Import the configuration UI component
        from components.generation_config_ui import get_generation_configs

        # Add configuration controls
        title_config_json, social_config_json = get_generation_configs()

        st.divider()

        # Resume from saved refined blog option
        col1, col2 = st.columns([2, 1])

        with col1:
            if st.button("Refine Blog", key="refine_blog_btn"):
                SessionManager.set_status("Refining blog draft...")
                SessionManager.clear_error()
                try:
                    with st.spinner("Calling API to refine blog..."):
                        # Get the compiled draft from session state
                        compiled_draft_content = SessionManager.get('final_draft')
                        if not compiled_draft_content:
                            raise ValueError("Compiled draft content is missing from session state.")

                        # Call the appropriate API client function based on whether we have a project_id
                        if project_id:
                            # Use regular refine_blog with project state
                            result = asyncio.run(api_client.refine_blog(
                                project_name=project_name,
                                project_id=project_id,
                                compiled_draft=compiled_draft_content, # Pass the draft content
                                title_config=title_config_json,  # Pass configuration
                                social_config=social_config_json,  # Pass configuration
                                base_url=SessionManager.get('api_base_url')
                            ))
                        else:
                            # Use standalone refinement for uploaded drafts without project state
                            selected_model = SessionManager.get('selected_model', 'claude')  # Provider key
                            specific_model = SessionManager.get('specific_model')
                            result = asyncio.run(api_client.refine_standalone(
                                project_name=project_name,
                                compiled_draft=compiled_draft_content,
                                model_name=selected_model,  # Provider key
                                specific_model=specific_model,  # Specific model id if available
                                title_config=title_config_json,  # Pass configuration
                                social_config=social_config_json,  # Pass configuration
                                base_url=SessionManager.get('api_base_url')
                            ))
                    # Store the results from the API response
                    SessionManager.set('refined_draft', result.get('refined_draft')) # This should be the final text
                    SessionManager.set('summary', result.get('summary'))
                    SessionManager.set('title_options', result.get('title_options')) # Expecting a list of dicts
                    SessionManager.set('cost_summary', result.get('cost_summary'))
                    SessionManager.set_status("Blog refined successfully.")
                    logger.info(f"Blog refined for project ID: {project_id}")
                    
                    # Auto-save the refined blog content
                    try:
                        auto_save_manager = SessionManager.get_auto_save_manager()
                        refined_content = result.get('refined_draft')
                        summary_content = result.get('summary')
                        title_options_content = result.get('title_options', [])
                        if project_name and refined_content:
                            saved_path = auto_save_manager.save_refined_blog(
                                project_name=project_name,
                                refined_content=refined_content,
                                summary=summary_content,
                                title_options=title_options_content,
                                project_id=project_id,
                                add_timestamp=True
                            )
                            logger.info(f"Auto-saved refined blog to: {saved_path}")
                    except Exception as save_err:
                        logger.warning(f"Failed to auto-save refined blog: {save_err}")
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
        
        with col2:
            if st.button("📁 I have refined already", key="load_refined_btn"):
                # Show option to load from saved refined blogs
                auto_save_manager = SessionManager.get_auto_save_manager()
                if project_name:
                    saved_refined = auto_save_manager.list_saved_refined_blogs(project_name)
                    if saved_refined:
                        st.write("**Available refined blogs:**")
                        for i, refined_info in enumerate(saved_refined):
                            col_load, col_info = st.columns([1, 3])
                            with col_load:
                                if st.button("Load", key=f"load_refined_{i}"):
                                    try:
                                        # Load the refined content
                                        loaded_refined = auto_save_manager.load_refined_content(refined_info["file_path"])
                                        SessionManager.set('refined_draft', loaded_refined)
                                        SessionManager.set('current_project_id', refined_info.get("project_id"))
                                        SessionManager.set_status("Refined blog loaded successfully from saved file.")
                                        st.success(f"✅ Loaded refined blog: {refined_info['filename']}")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Failed to load refined blog: {str(e)}")
                            with col_info:
                                st.caption(f"**{refined_info['filename']}**")
                                if refined_info.get('saved_at'):
                                    st.caption(f"Saved: {refined_info['saved_at'][:19]}")
                    else:
                        st.info("No saved refined blogs found for this project.")
                else:
                    st.warning("Please set a project name first.")

        # Display Refinement Results
        refined_draft = SessionManager.get('refined_draft')
        summary = SessionManager.get('summary')
        title_options = SessionManager.get('title_options') # This should be List[Dict]

        if refined_draft:
            st.markdown("---")
            st.subheader("Refined Blog Draft")
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="Download Refined Draft (.md)",
                    data=refined_draft,
                    file_name=f"{project_name}_refined_draft.md",
                    mime="text/markdown",
                    key="dl_refined_refine_tab" # Static unique key
                )
            
            with col2:
                # Complete package download (without social content yet)
                package = create_complete_blog_package()
                if package:
                    zip_data = create_zip_download(package)
                    
                    file_count = len(package)
                    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in project_name)
                    
                    st.download_button(
                        label=f"📦 Blog Package ({file_count} files)",
                        data=zip_data,
                        file_name=f"{safe_name}_blog_package.zip",
                        mime="application/zip",
                        key="dl_package_refine_tab",
                        help="Downloads complete blog package: drafts, summary, and title options"
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

        # Check for refined draft
        refined_draft = SessionManager.get('refined_draft')
        
        if not refined_draft:
            st.info("📁 **Upload your refined blog to generate social media content**")
            
            # Upload section for refined blog
            uploaded_file = st.file_uploader(
                "Choose your refined blog file", 
                type=['md', 'txt'],
                help="Upload a markdown (.md) or text (.txt) file containing your refined blog"
            )
            
            if uploaded_file is not None:
                # Read the content
                refined_content = uploaded_file.read().decode('utf-8')
                
                # Display preview
                st.subheader("📄 Refined Blog Preview")
                st.text_area("Content Preview", refined_content[:500] + "...", height=150, disabled=True)
                
                # Project name input
                project_name = SessionManager.get('project_name')
                if not project_name:
                    project_name = st.text_input(
                        "Project Name", 
                        value=uploaded_file.name.split('.')[0],
                        help="Enter a name for this project"
                    )
                
                if st.button("✅ Use This Refined Blog", key="use_uploaded_refined"):
                    if project_name and refined_content:
                        # Store in session state
                        SessionManager.set('refined_draft', refined_content)
                        SessionManager.set('project_name', project_name)
                        # Clear project_id since we're using uploaded content
                        SessionManager.set('current_project_id', None)
                        st.success("✅ Refined blog loaded successfully! You can now generate social content.")
                        st.rerun()
                    else:
                        st.error("Please enter a project name.")
            return

        project_id = SessionManager.get('current_project_id')
        project_name = SessionManager.get('project_name')

        if st.button("Generate Social Content", key="gen_social_btn"):
            SessionManager.set_status("Generating social content...")
            SessionManager.clear_error()
            try:
                with st.spinner("Calling API to generate social content..."):
                    # Check if we have a project_id and use appropriate endpoint
                    if project_id:
                        # Use regular social content generation with project state
                        result = asyncio.run(api_client.generate_social_content(
                            project_name=project_name,
                            project_id=project_id,
                            base_url=SessionManager.get('api_base_url')
                        ))
                    else:
                        # Use standalone social content generation for uploaded drafts
                        refined_content = SessionManager.get('refined_draft')
                        selected_model = SessionManager.get('selected_model', 'claude')
                        result = asyncio.run(api_client.generate_social_content_standalone(
                            project_name=project_name,
                            refined_blog_content=refined_content,
                            model_name=selected_model,
                            specific_model=SessionManager.get('specific_model'),
                            base_url=SessionManager.get('api_base_url')
                        ))
                SessionManager.set('social_content', result.get('social_content'))
                SessionManager.set_status("Social content generated.")
                logger.info(f"Social content generated for project: {project_name}")
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

            # Display Twitter Thread if available
            x_thread = social_content.get('x_thread')
            if x_thread:
                with st.expander("X (Twitter) Thread", expanded=True):
                    st.markdown(f"**Thread Topic:** {x_thread.get('thread_topic', 'N/A')}")
                    st.markdown(f"**Total Tweets:** {x_thread.get('total_tweets', 0)}")
                    st.markdown("---")
                    
                    tweets = x_thread.get('tweets', [])
                    for tweet in tweets:
                        tweet_num = tweet.get('tweet_number', 1)
                        tweet_content = tweet.get('content', '')
                        char_count = tweet.get('character_count', len(tweet_content))
                        
                        st.markdown(f"**Tweet {tweet_num}:** ({char_count} chars)")
                        st.markdown(f"> {tweet_content}")
                        st.markdown("")

            with st.expander("Newsletter Content", expanded=True):
                st.markdown(social_content.get('newsletter_content', 'Not available.'))
            
            # Download section for social content and complete package
            st.subheader("Download Options")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Individual Downloads:**")
                
                # Individual social media downloads
                if social_content.get('linkedin_post'):
                    st.download_button(
                        label="📱 LinkedIn Post (.md)",
                        data=f"# LinkedIn Post\n\n{social_content['linkedin_post']}",
                        file_name=f"{SessionManager.get('project_name', 'blog')}_linkedin.md",
                        mime="text/markdown",
                        key="dl_linkedin_individual"
                    )
                
                if social_content.get('x_post'):
                    st.download_button(
                        label="🐦 Twitter/X Post (.md)",
                        data=f"# X (Twitter) Post\n\n{social_content['x_post']}",
                        file_name=f"{SessionManager.get('project_name', 'blog')}_twitter.md",
                        mime="text/markdown",
                        key="dl_twitter_individual"
                    )
                
                if social_content.get('newsletter_content'):
                    st.download_button(
                        label="📧 Newsletter (.md)",
                        data=f"# Newsletter Content\n\n{social_content['newsletter_content']}",
                        file_name=f"{SessionManager.get('project_name', 'blog')}_newsletter.md",
                        mime="text/markdown",
                        key="dl_newsletter_individual"
                    )
                
                # Twitter Thread download
                x_thread = social_content.get('x_thread')
                if x_thread:
                    # Format thread for download
                    thread_content = f"# X (Twitter) Thread\n\n"
                    thread_content += f"**Topic:** {x_thread.get('thread_topic', 'N/A')}\n\n"
                    thread_content += f"**Total Tweets:** {x_thread.get('total_tweets', 0)}\n\n"
                    thread_content += "---\n\n"
                    
                    tweets = x_thread.get('tweets', [])
                    for tweet in tweets:
                        tweet_num = tweet.get('tweet_number', 1)
                        tweet_content_text = tweet.get('content', '')
                        char_count = tweet.get('character_count', len(tweet_content_text))
                        
                        thread_content += f"## Tweet {tweet_num} ({char_count} chars)\n\n"
                        thread_content += f"{tweet_content_text}\n\n"
                    
                    st.download_button(
                        label="🧵 Twitter Thread (.md)",
                        data=thread_content,
                        file_name=f"{SessionManager.get('project_name', 'blog')}_twitter_thread.md",
                        mime="text/markdown",
                        key="dl_thread_individual"
                    )
            
            with col2:
                st.markdown("**Complete Package:**")
                
                # Check if we have enough content for a complete package
                has_refined_blog = SessionManager.get('refined_draft') is not None
                has_final_blog = SessionManager.get('final_draft') is not None
                
                if has_refined_blog or has_final_blog:
                    # Complete blog package download
                    package = create_complete_blog_package()
                    if package:
                        zip_data = create_zip_download(package)
                        
                        file_count = len(package)
                        project_name = SessionManager.get('project_name', 'blog_project')
                        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in project_name)
                        
                        st.download_button(
                            label=f"📦 Complete Package ({file_count} files)",
                            data=zip_data,
                            file_name=f"{safe_name}_complete_blog_package.zip",
                            mime="application/zip",
                            key="dl_complete_package",
                            help="Downloads all blog content: original draft, refined version, summary, titles, and social media posts"
                        )
                        
                        with st.expander("📋 Package Contents", expanded=False):
                            st.markdown("This package includes:")
                            for filename in sorted(package.keys()):
                                st.markdown(f"• `{filename}`")
                
                else:
                    st.info("Complete the blog refinement process to unlock the full package download.")
        else:
            st.info("Click 'Generate Social Content' after compiling the draft.")


# --- Main Application Class ---
class BloggingAssistantAPIApp:
    def __init__(self):
        self.session = SessionManager()
        self.sidebar = SidebarUI()
        self.project_hub = ProjectHubUI() # Initialize Project Hub
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

        # --- Authentication ---
        # TEMPORARILY BYPASSED for testing
        # user = require_auth()
        # show_user_profile()
        user = None  # Mock user for testing

        self.sidebar.render() # Render sidebar first for initialization

        # Display global status/error messages prominently
        error_message = SessionManager.get('error_message')
        status_message = SessionManager.get('status_message')
        if error_message:
            st.error(error_message)
        elif status_message and not SessionManager.get('is_initialized'): # Show status only if not initialized
             st.info(status_message)

        # Show current project context with progress
        current_project_name = SessionManager.get('current_project_name')
        current_project_id = SessionManager.get('current_project_id')

        # If no project is selected, show the Project Hub
        if not current_project_id:
            self.project_hub.render()
            return # Stop rendering the rest of the app

        if current_project_name:
            st.markdown(f"### 📝 Current Project: **{current_project_name}**")

            # Show project progress if we have an API client and project ID
            if hasattr(st.session_state, 'blog_api_client') and current_project_id:
                try:
                    progress_data = asyncio.run(
                        st.session_state.blog_api_client.get_project_progress(current_project_id)
                    )

                    # Display progress metrics
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        st.metric("Progress", f"{progress_data.get('progress_percentage', 0):.0f}%")

                    with col2:
                        milestones = progress_data.get('milestones', {})
                        completed = sum(1 for v in milestones.values() if v)
                        total = len(milestones)
                        st.metric("Milestones", f"{completed}/{total}")

                    with col3:
                        st.metric("Cost", f"${progress_data.get('total_cost', 0):.4f}")

                    with col4:
                        duration = progress_data.get('workflow_duration_seconds', 0)
                        if duration:
                            hours = int(duration // 3600)
                            minutes = int((duration % 3600) // 60)
                            st.metric("Time", f"{hours}h {minutes}m")
                        else:
                            st.metric("Time", "0h 0m")

                    # Progress bar
                    st.progress(progress_data.get('progress_percentage', 0) / 100)

                except Exception as e:
                    logger.debug(f"Failed to load project progress: {e}")
                    # Don't show error - progress is optional

            st.markdown("---")

        if SessionManager.get('is_initialized'):
            # Create tabs with progress indicators
            tab_labels = self._get_tab_labels_with_progress()
            tab_outline, tab_draft, tab_refine, tab_social = st.tabs(tab_labels)

            with tab_outline:
                self.outline_generator.render()

            with tab_draft:
                self.blog_draft.render()

            with tab_refine:
                self.refinement.render()

            with tab_social:
                self.social_posts.render()
        else:
            # Optionally show a placeholder if not initialized
            st.markdown("---")
            st.info("⬅️ Please configure and initialize the assistant using the sidebar.")
    
    def _get_tab_labels_with_progress(self):
        """Generate tab labels with progress indicators."""
        # Check completion status for each milestone
        has_outline = SessionManager.get('generated_outline') is not None
        has_draft = SessionManager.get('final_draft') is not None
        has_refined = SessionManager.get('refined_draft') is not None
        has_social = SessionManager.get('social_content') is not None
        
        # Generate labels with status indicators
        labels = [
            f"1. Outline {'✅' if has_outline else '⏳'}",
            f"2. Blog Draft {'✅' if has_draft else '⏳'}",
            f"3. Refine & Finalize {'✅' if has_refined else '⏳'}",
            f"4. Social Posts {'✅' if has_social else '⏳'}"
        ]
        
        return labels


# --- Application Entry Point ---
if __name__ == "__main__":
    app = BloggingAssistantAPIApp()
    app.run()
