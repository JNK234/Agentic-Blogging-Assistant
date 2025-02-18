import streamlit as st
import os
import sys
sys.path.append(".")


from pathlib import Path
from dotenv import load_dotenv
from root.backend.models import ModelFactory

load_dotenv()


# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'model' not in st.session_state:
    st.session_state.model = None

# Set page config
st.set_page_config(
    page_title="Agentic Blogging Assistant",
    page_icon="📝",
    layout="wide"
)

# Constants
UPLOAD_PATH = Path("root/data/uploads")

def save_uploaded_files(blog_name: str, notebook_file, markdown_file):
    """Save uploaded files to the appropriate directory."""
    # Create blog project directory
    blog_dir = UPLOAD_PATH / blog_name
    blog_dir.mkdir(parents=True, exist_ok=True)
    
    print(blog_dir)
    
    # Save files if they were uploaded
    saved_files = []
    if notebook_file is not None:
        notebook_path = blog_dir / notebook_file.name
        with open(notebook_path, "wb") as f:
            f.write(notebook_file.getbuffer())
        saved_files.append(f"Notebook: {notebook_file.name}")
            
    if markdown_file is not None:
        markdown_path = blog_dir / markdown_file.name
        with open(markdown_path, "wb") as f:
            f.write(markdown_file.getbuffer())
        saved_files.append(f"Markdown: {markdown_file.name}")
            
    return saved_files

# Title in sidebar
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
                saved_files = save_uploaded_files(blog_name, notebook_file, markdown_file)
            
            # Initialize the LLM model
            with st.spinner("Initializing LLM..."):
                try:
                    st.session_state.model = ModelFactory.create_model(llm_provider)
                    st.sidebar.success("Assistant initialized successfully!")
                    st.sidebar.write("Project Details:")
                    st.sidebar.write(f"- Blog Name: {blog_name}")
                    st.sidebar.write(f"- LLM Provider: {llm_provider}")
                    for file in saved_files:
                        st.sidebar.write(f"✓ {file}")
                except ValueError as e:
                    st.sidebar.error(f"Failed to initialize LLM: {str(e)}")
                    st.session_state.model = None
                
        except Exception as e:
            st.sidebar.error(f"An error occurred: {str(e)}")

# Chat interface in main area
if st.session_state.model:
    st.title("Chat with Your Assistant")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Type your message here..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.model.generate(st.session_state.messages)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
                st.markdown(response.content)
else:
    st.info("Please configure and initialize your assistant using the sidebar.")
