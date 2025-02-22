import streamlit as st
import os
import sys
sys.path.append(".")

from pathlib import Path
from dotenv import load_dotenv
from root.backend.models.model_factory import ModelFactory
from root.backend.agents import BlogDraftGeneratorAgent

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
                'generated_outline': None
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
                                SessionManager.set('model', ModelFactory.create_model(llm_provider))
                                SessionManager.set('outline_agent', ModelFactory.create_model("outline_generator"))
                                SessionManager.set('draft_agent', ModelFactory.create_model("blog_draft_generator"))
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

        if SessionManager.get('generated_outline'):
            self._render_outline(SessionManager.get('generated_outline'))
        else:
            pass

        if generate_outline_button:
            import asyncio
            # def switch_to_blog_draft():
            #     pass

            async def generate():
                if not SessionManager.get('notebook_path') or not SessionManager.get('markdown_path'):
                    st.error("Please upload both Jupyter Notebook and Markdown files first.")
                elif not SessionManager.get('outline_agent'):
                    st.error("Failed to initialize Outline Generator Agent.")
                else:
                    try:
                        with st.spinner("Generating outline..."): # Show spinner while generating outline
                            outline, notebook_content, markdown_content = await SessionManager.get('outline_agent').generate_outline(
                                SessionManager.get('notebook_path'),
                                SessionManager.get('markdown_path'),
                                SessionManager.get('model')
                            )
                            st.success("Outline generated successfully!")
                            
                            # Store the generated outline in session state
                            SessionManager.set('generated_outline', outline)
                            
                            # Render the outline in a structured format
                            self._render_outline(outline)

                    except Exception as e:
                        st.error(f"An error occurred: {type(e).__name__}: {str(e)}")
            asyncio.run(generate())

        # st.button("Continue to Blog Draft", on_click=switch_to_blog_draft)

    def _render_outline(self, outline_data):
        """Render the complete outline."""
        # Handle string input
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
        st.title("Blog Draft Generator")
        
        with st.form("draft_form"):
            st.subheader("Generate Blog Draft")
            generate_draft_button = st.form_submit_button("Generate Draft")
        
        if generate_draft_button:
            import asyncio
            
            async def generate():
                if not SessionManager.get('generated_outline'):
                    st.error("Please generate an outline first.")
                elif not SessionManager.get('notebook_path') or not SessionManager.get('markdown_path'):
                    st.error("Please upload both Jupyter Notebook and Markdown files first.")
                elif not SessionManager.get('draft_agent'):
                    st.error("Failed to initialize Blog Draft Generator Agent.")
                else:
                    try:
                        with st.spinner("Generating draft..."):
                            outline = SessionManager.get('generated_outline')
                            notebook_path = SessionManager.get('notebook_path')
                            markdown_path = SessionManager.get('markdown_path')
                            model = SessionManager.get('model')
                            draft_generator = SessionManager.get('draft_agent')
                            draft = await draft_generator.generate_draft(
                                outline,
                                notebook_path,
                                markdown_path,
                                model
                            )
                            st.success("Draft generated successfully!")
                            st.write(draft)
                    except Exception as e:
                        st.error(f"An error occurred: {type(e).__name__}: {str(e)}")
            asyncio.run(generate())

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
            outline_tab, draft_tab, settings_tab = st.tabs(["Outline Generator", "Blog Draft", "Settings"])
            
            with outline_tab:
                self.outline_generator.render()
            
            with draft_tab:
                self.blog_draft.render()
                
            with settings_tab:
                self.settings.render()
        else:
            st.info("Please configure and initialize your assistant using the sidebar.")

# 7. Application Entry Point
def main():
    app = BloggingAssistant()
    app.run()

if __name__ == "__main__":
    main()
