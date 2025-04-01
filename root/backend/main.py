"""
FastAPI application for blog content processing, outline generation, and blog draft generation.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid # For generating unique job IDs
from cachetools import TTLCache # For simple in-memory state cache

from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from root.backend.agents.social_media_agent import SocialMediaAgent # Added import
from root.backend.agents.outline_generator.state import FinalOutline
from root.backend.utils.serialization import serialize_object
from root.backend.models.model_factory import ModelFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BlogAPI")

app = FastAPI(title="Agentic Blogging Assistant API")

# Constants
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
UPLOAD_DIRECTORY = os.path.join(ROOT_DIR, "data/uploads")
SUPPORTED_EXTENSIONS = {".ipynb", ".md", ".py"}
CACHE_DIRECTORY = os.path.join(ROOT_DIR, "data/cache")

# Initialize directories
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(CACHE_DIRECTORY, exist_ok=True)

# Agent cache to avoid recreating agents for each request
agent_cache = {}

# In-memory cache for job states (outline, content) with a TTL (e.g., 1 hour)
# Adjust maxsize and ttl as needed
state_cache = TTLCache(maxsize=100, ttl=3600)

@app.post("/upload/{project_name}")
async def upload_files(
    project_name: str,
    files: List[UploadFile] = File(...)
) -> JSONResponse:
    """Upload files for a specific project."""
    try:
        # Create project directory
        project_dir = Path(UPLOAD_DIRECTORY) / project_name
        project_dir.mkdir(parents=True, exist_ok=True)
        
        uploaded_files = []
        for file in files:
            if not file.filename:
                continue
                
            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in SUPPORTED_EXTENSIONS:
                return JSONResponse(
                    content={
                        "error": f"Unsupported file type: {file_extension}. "
                        f"Supported types: {', '.join(SUPPORTED_EXTENSIONS)}"
                    },
                    status_code=400
                )
            
            # Clean filename to prevent path traversal
            safe_filename = os.path.basename(file.filename)
            file_path = project_dir / safe_filename
            
            # Read file content
            content = await file.read()
            
            # Write content to file
            with open(file_path, "wb") as f:
                f.write(content)
                
            uploaded_files.append(str(file_path))
            
        if not uploaded_files:
            return JSONResponse(
                content={"error": "No valid files were uploaded"},
                status_code=400
            )
            
        return JSONResponse(
            content={
                "message": "Files uploaded successfully",
                "project": project_name,
                "files": uploaded_files
            }
        )
    except Exception as e:
        logger.exception(f"Upload failed: {str(e)}")
        return JSONResponse(
            content={"error": f"Upload failed: {str(e)}"},
            status_code=500
        )

async def get_or_create_agents(model_name: str):
    """Get or create agents for the specified model."""
    cache_key = f"agents_{model_name}"
    
    if cache_key in agent_cache:
        return agent_cache[cache_key]
    
    try:
        # Create model instance
        model_factory = ModelFactory()
        model = model_factory.create_model(model_name.lower())
        
        # Create and initialize agents
        content_parser = ContentParsingAgent(model)
        await content_parser.initialize()
        
        outline_agent = OutlineGeneratorAgent(model, content_parser)
        await outline_agent.initialize()
        
        draft_agent = BlogDraftGeneratorAgent(model, content_parser)
        await draft_agent.initialize()

        social_agent = SocialMediaAgent(model) # Added social agent
        await social_agent.initialize()
        
        # Cache the agents
        agent_cache[cache_key] = {
            "model": model,
            "content_parser": content_parser,
            "outline_agent": outline_agent,
            "draft_agent": draft_agent,
            "social_agent": social_agent # Added social agent to cache
        }
        
        return agent_cache[cache_key]
    except Exception as e:
        logger.exception(f"Failed to create agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create agents: {str(e)}")

@app.post("/process_files/{project_name}")
async def process_files(
    project_name: str,
    model_name: str = Form(...),
    file_paths: List[str] = Form(...),
) -> JSONResponse:
    """Process files and store in vector database."""
    try:
        logger.info(f"Processing files for project {project_name} with model {model_name}")
        logger.info(f"File paths: {file_paths}")
        
        # Get or create agents
        agents = await get_or_create_agents(model_name)
        content_parser = agents["content_parser"]
        
        result = {}
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.error(f"File not found: {file_path}")
                return JSONResponse(
                    content={"error": f"File not found: {file_path}"},
                    status_code=404
                )
                
            # Process the file
            logger.info(f"Processing file: {file_path}")
            content_hash = await content_parser.process_file_with_graph(file_path, project_name)
            logger.info(f"File processed with hash: {content_hash}")
            result[file_path] = content_hash
            
        return JSONResponse(
            content={
                "message": "Files processed successfully",
                "project": project_name,
                "file_hashes": result
            }
        )
    except Exception as e:
        logger.exception(f"File processing failed: {str(e)}")
        return JSONResponse(
            content={"error": f"File processing failed: {str(e)}"},
            status_code=500
        )

@app.post("/generate_outline/{project_name}")
async def generate_outline(
    project_name: str,
    model_name: str = Form(...),
    notebook_hash: Optional[str] = Form(None),
    markdown_hash: Optional[str] = Form(None),
    user_guidelines: Optional[str] = Form(None) # Added
) -> JSONResponse:
    """Generate a blog outline for processed content."""
    try:
        # Allow either notebook_hash or markdown_hash (or both)
        if not notebook_hash and not markdown_hash:
            return JSONResponse(
                content={"error": "At least one content hash is required"},
                status_code=400
            )
        
        # Get or create agents
        agents = await get_or_create_agents(model_name)
        outline_agent = agents["outline_agent"]

        # Generate outline - returns a dict (outline or error), content, content, cached_status
        outline_result, notebook_content, markdown_content, was_cached = await outline_agent.generate_outline(
            project_name=project_name,
            notebook_hash=notebook_hash,
            markdown_hash=markdown_hash,
            user_guidelines=user_guidelines # Pass guidelines to agent
        )

        # Check if the agent returned an error dictionary
        if isinstance(outline_result, dict) and "error" in outline_result:
            logger.error(f"Outline generation failed: {outline_result}")
            # Return the structured error from the agent directly
            return JSONResponse(
                content=serialize_object(outline_result), # Serialize the error dict
                status_code=500 # Or potentially 400 depending on error type
            )

        # If no error, outline_result should be the outline data dictionary
        if not isinstance(outline_result, dict) or not outline_result:
             # This case should ideally not happen if the agent returns structured errors
             logger.error(f"Unexpected outline result format: {outline_result}")
             return JSONResponse(
                content={"error": "Internal server error: Unexpected outline format from agent"},
                status_code=500
            )

        # We now have the validated outline data directly
        outline_data = outline_result

        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Store the state in the cache
        state_cache[job_id] = {
            "outline": outline_data, # Store parsed data
            "notebook_content": notebook_content,
            "markdown_content": markdown_content,
            "project_name": project_name,
            "model_name": model_name,
            "generated_sections": {} # Initialize dict to store generated sections later
        }
        logger.info(f"Stored initial state for job_id: {job_id}")

        # Return the job ID and the outline itself (for immediate display)
        # Do not return the large content strings anymore
        return JSONResponse(
            content=serialize_object({
                "job_id": job_id,
                "outline": outline_data # Return the parsed outline data
            })
        )

    except Exception as e:
        logger.exception(f"Outline generation failed: {str(e)}")
        
        # Provide detailed error information
        error_detail = {
            "error": f"Outline generation failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )

@app.post("/generate_draft/{project_name}")
async def generate_draft(
    project_name: str,
    model_name: str = Form(...),
    outline: str = Form(...),
    notebook_content: str = Form(...),
    markdown_content: str = Form(...),
) -> JSONResponse:
    """Generate a complete blog draft from an outline."""
    try:
        # Parse inputs
        try:
            outline_data = json.loads(outline)
            notebook_data = json.loads(notebook_content)
            markdown_data = json.loads(markdown_content)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format: {str(e)}")
            return JSONResponse(
                content={"error": f"Invalid JSON format: {str(e)}"},
                status_code=400
            )
            
        # Get or create agents
        agents = await get_or_create_agents(model_name)
        draft_agent = agents["draft_agent"]
        
        # Generate blog draft
        outline_obj = FinalOutline.model_validate(outline_data)
        draft = await draft_agent.generate_draft(
            project_name=project_name,
            outline=outline_obj,
            notebook_content=notebook_data,
            markdown_content=markdown_data
        )
        
        if not draft:
            return JSONResponse(
                content={"error": "Failed to generate blog draft"},
                status_code=500
            )
        
        return JSONResponse(
            content=serialize_object({
                "draft": draft
            })
        )
        
    except Exception as e:
        logger.exception(f"Draft generation failed: {str(e)}")
        
        # Provide detailed error information
        error_detail = {
            "error": f"Draft generation failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )

@app.post("/generate_section/{project_name}")
async def generate_section(
    project_name: str, # Keep project_name for potential future use/logging
    job_id: str = Form(...), # Use job_id instead of outline/content
    section_index: int = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """Generate a single section of a blog draft using cached state."""
    try:
        # Retrieve state from cache
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
                status_code=404
            )

        # Extract data from state
        outline_data = job_state["outline"]
        notebook_data = job_state["notebook_content"] # Already parsed/loaded content
        markdown_data = job_state["markdown_content"] # Already parsed/loaded content
        model_name = job_state["model_name"] # Get model name from state

        # Validate section index against the retrieved outline
        if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": f"Invalid section index: {section_index}"},
                status_code=400
            )
            
        # Get current section from the retrieved outline
        section = outline_data["sections"][section_index]

        # Get or create agents using model_name from state
        agents = await get_or_create_agents(model_name)
        draft_agent = agents["draft_agent"]

        # Generate section using retrieved data
        section_content = await draft_agent.generate_section(
            project_name=project_name,
            section=section,
            outline=outline_data,
            notebook_content=notebook_data,
            markdown_content=markdown_data,
            current_section_index=section_index,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold
        )

        if not section_content:
            return JSONResponse(
                content={"error": f"Failed to generate section: {section.get('title', 'Unknown')}"},
                status_code=500
            )

        # --- Enhancement: Store generated section in state cache ---
        try:
            # Ensure the job state still exists before updating
            if job_id in state_cache:
                state_cache[job_id]["generated_sections"][section_index] = {
                    "title": section.get("title", "Unknown"),
                    "content": section_content
                }
                # Re-insert to update TTL (optional, depends on cachetools version/behavior)
                # state_cache[job_id] = state_cache[job_id]
                logger.info(f"Stored generated content for section {section_index} in job_id: {job_id}")
            else:
                 logger.warning(f"Job state for {job_id} expired before section could be stored.")
                 # Decide if this should be an error or just a warning
        except Exception as cache_update_err:
            # Log error but don't fail the request just because caching failed
            logger.error(f"Failed to update cache for job {job_id}, section {section_index}: {cache_update_err}")
        # --- End Enhancement ---

        return JSONResponse(
            content=serialize_object({
                "job_id": job_id, # Return job_id for consistency
                "section_title": section.get("title", "Unknown"),
                "section_content": section_content,
                "section_index": section_index
            })
        )

    except Exception as e:
        logger.exception(f"Section generation failed: {str(e)}")
        
        # Provide detailed error information
        error_detail = {
            "error": f"Section generation failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )

@app.post("/regenerate_section_with_feedback/{project_name}")
async def regenerate_section(
    project_name: str, # Keep project_name for potential future use/logging
    job_id: str = Form(...), # Use job_id instead of outline/content/model_name
    section_index: int = Form(...),
    feedback: str = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """Regenerate a section with user feedback using cached state."""
    try:
        # Retrieve state from cache
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
                status_code=404
            )

        # Extract data from state
        outline_data = job_state["outline"]
        notebook_data = job_state["notebook_content"]
        markdown_data = job_state["markdown_content"]
        model_name = job_state["model_name"] # Get model name from state

        # Validate section index against the retrieved outline
        if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": f"Invalid section index: {section_index}"},
                status_code=400
            )
            
        # Get current section from the retrieved outline
        section = outline_data["sections"][section_index]

        # Get or create agents using model_name from state
        agents = await get_or_create_agents(model_name)
        draft_agent = agents["draft_agent"]

        # Regenerate section with feedback using retrieved data
        new_content = await draft_agent.regenerate_section_with_feedback(
            project_name=project_name,
            section=section,
            outline=outline_data,
            notebook_content=notebook_data,
            markdown_content=markdown_data,
            feedback=feedback,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold
        )

        if not new_content:
            return JSONResponse(
                content={"error": f"Failed to regenerate section: {section.get('title', 'Unknown')}"},
                status_code=500
            )

        # --- Enhancement: Update generated section in state cache ---
        try:
            # Ensure the job state still exists before updating
            if job_id in state_cache:
                state_cache[job_id]["generated_sections"][section_index] = {
                    "title": section.get("title", "Unknown"),
                    "content": new_content # Store the regenerated content
                }
                # Re-insert to update TTL (optional)
                # state_cache[job_id] = state_cache[job_id]
                logger.info(f"Updated stored content for section {section_index} in job_id: {job_id} after feedback.")
            else:
                 logger.warning(f"Job state for {job_id} expired before regenerated section could be stored.")
        except Exception as cache_update_err:
             # Log error but don't fail the request just because caching failed
            logger.error(f"Failed to update cache for job {job_id}, section {section_index} after feedback: {cache_update_err}")
        # --- End Enhancement ---

        return JSONResponse(
            content=serialize_object({
                "job_id": job_id, # Return job_id
                "section_title": section.get("title", "Unknown"),
                "section_content": new_content,
                "section_index": section_index,
                "feedback_addressed": True
            })
        )

    except Exception as e:
        logger.exception(f"Section regeneration failed: {str(e)}")
        
        # Use our serialization utility to ensure error responses are also serializable
        
        
        # Provide detailed error information
        error_detail = {
            "error": f"Section regeneration failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )

@app.post("/compile_draft/{project_name}")
async def compile_draft(
    project_name: str, # Keep project_name for potential future use/logging
    job_id: str = Form(...) # Use job_id instead of outline/sections
) -> JSONResponse:
    """Compile a final blog draft using cached state."""
    try:
        # Retrieve state from cache
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}. Please generate outline and sections first."},
                status_code=404
            )

        # Extract data from state
        outline_data = job_state["outline"]
        generated_sections_dict = job_state.get("generated_sections", {})

        # Prepare sections_data in the correct order
        num_outline_sections = len(outline_data.get("sections", []))
        sections_data = []
        missing_sections = []
        for i in range(num_outline_sections):
            if i in generated_sections_dict:
                sections_data.append(generated_sections_dict[i])
            else:
                missing_sections.append(i)

        # Validate all sections were generated and retrieved
        if missing_sections:
            logger.error(f"Missing generated content for sections {missing_sections} in job {job_id}")
            return JSONResponse(
                content={"error": f"Missing content for sections: {', '.join(map(str, missing_sections))}. Please generate all sections first."},
                status_code=400
            )

        # Original validation (redundant if above check passes, but safe to keep)
        if len(sections_data) != len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": "Number of sections does not match outline"},
                status_code=400
            )
            
        # Compile blog draft
        # Start with blog title and metadata
        blog_parts = [
            f"# {outline_data['title']}\n",
            f"**Difficulty Level**: {outline_data['difficulty_level']}\n",
            "\n## Prerequisites\n"
        ]
        
        # Add prerequisites
        if isinstance(outline_data["prerequisites"], dict):
            # Add required knowledge
            if "required_knowledge" in outline_data["prerequisites"]:
                blog_parts.append("\n### Required Knowledge\n")
                for item in outline_data["prerequisites"]["required_knowledge"]:
                    blog_parts.append(f"- {item}\n")
                    
            # Add recommended tools
            if "recommended_tools" in outline_data["prerequisites"]:
                blog_parts.append("\n### Recommended Tools\n")
                for tool in outline_data["prerequisites"]["recommended_tools"]:
                    blog_parts.append(f"- {tool}\n")
                    
            # Add setup instructions
            if "setup_instructions" in outline_data["prerequisites"]:
                blog_parts.append("\n### Setup Instructions\n")
                for instruction in outline_data["prerequisites"]["setup_instructions"]:
                    blog_parts.append(f"- {instruction}\n")
        else:
            # Handle string prerequisites
            blog_parts.append(f"{outline_data['prerequisites']}\n")
            
        # Add table of contents using the prepared sections_data
        blog_parts.append("\n## Table of Contents\n")
        for i, section_data in enumerate(sections_data):
            # Use section title from the generated data, fallback to outline if needed
            title = section_data.get("title", outline_data["sections"][i].get("title", f"Section {i+1}"))
            blog_parts.append(f"{i+1}. [{title}](#section-{i+1})\n")

        blog_parts.append("\n")
        
        # Add each section using the prepared sections_data
        for i, section_data in enumerate(sections_data):
            # Use section title from the generated data, fallback to outline if needed
            title = section_data.get("title", outline_data["sections"][i].get("title", f"Section {i+1}"))
            content = section_data.get("content", "*Error: Content not found*")
            # Add section anchor and title
            blog_parts.extend([
                f"<a id='section-{i+1}'></a>\n",
                f"## {title}\n",
                f"{content}\n\n"
            ])

        # Add conclusion if available in the outline
        if 'conclusion' in outline_data and outline_data['conclusion']:
            blog_parts.extend([
                "## Conclusion\n",
                f"{outline_data['conclusion']}\n\n"
            ])
        
        # Combine all parts
        final_draft = "\n".join(blog_parts)

        # --- Enhancement: Store final draft in cache ---
        try:
            if job_id in state_cache:
                state_cache[job_id]["final_draft"] = final_draft
                # Re-insert to update TTL (optional)
                # state_cache[job_id] = state_cache[job_id]
                logger.info(f"Stored final draft in cache for job_id: {job_id}")
            else:
                logger.warning(f"Job state for {job_id} expired before final draft could be stored.")
        except Exception as cache_update_err:
            logger.error(f"Failed to update cache with final draft for job {job_id}: {cache_update_err}")
        # --- End Enhancement ---

        # Use our serialization utility to ensure proper JSON serialization
        return JSONResponse(
            content=serialize_object({
                "job_id": job_id, # Return job_id
                "draft": final_draft
            })
        )

        # --- Optional: Cleanup state after successful compilation ---
        # Consider delaying cleanup or making it optional if the draft is needed for social posts
        # try:
        #     if job_id in state_cache:
        #         del state_cache[job_id]
        #         logger.info(f"Cleared state for completed job_id: {job_id}")
        # except Exception as cache_clear_err:
        #     logger.error(f"Failed to clear cache for job {job_id} after compilation: {cache_clear_err}")
        # --- End Optional Cleanup ---

    except Exception as e:
        logger.exception(f"Draft compilation failed: {str(e)}")
        
        # Use our serialization utility to ensure error responses are also serializable
        
        
        # Provide detailed error information
        error_detail = {
            "error": f"Draft compilation failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )

@app.post("/generate_social_content/{project_name}")
async def generate_social_content(
    project_name: str, # Keep project_name for potential future use/logging
    job_id: str = Form(...) # Use job_id to retrieve compiled draft and model
) -> JSONResponse:
    """Generate social media content (LinkedIn, X, Newsletter) from a compiled draft."""
    try:
        # Retrieve state from cache
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}. Please compile draft first."},
                status_code=404
            )

        # Check if final draft exists in the state
        final_draft = job_state.get("final_draft")
        if not final_draft:
            logger.error(f"Final draft not found in cache for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Final draft not found for job_id: {job_id}. Please compile the draft first."},
                status_code=400 # Bad request, draft needs compilation
            )

        # Extract necessary info from state
        model_name = job_state.get("model_name")
        outline_data = job_state.get("outline", {})
        blog_title = outline_data.get("title", "Blog Post") # Get title from outline

        if not model_name:
             logger.error(f"Model name not found in cache for job_id: {job_id}")
             return JSONResponse(
                content={"error": "Model name missing from job state."},
                status_code=500
            )

        # Get or create agents using model_name from state
        agents = await get_or_create_agents(model_name)
        social_agent = agents.get("social_agent")

        if not social_agent:
            logger.error(f"SocialMediaAgent not found for model {model_name}")
            return JSONResponse(
                content={"error": "Social media agent could not be initialized."},
                status_code=500
            )

        # Generate social content
        logger.info(f"Generating social content for job_id: {job_id}")
        social_content = await social_agent.generate_content(
            blog_content=final_draft,
            blog_title=blog_title
        )

        if not social_content:
            logger.error(f"Failed to generate social content for job_id: {job_id}")
            return JSONResponse(
                content={"error": "Failed to generate social media content."},
                status_code=500
            )

        # Return the generated content
        return JSONResponse(
            content=serialize_object({
                "job_id": job_id,
                "social_content": social_content # Contains breakdown, linkedin, x, newsletter
            })
        )

    except Exception as e:
        logger.exception(f"Social content generation failed: {str(e)}")
        error_detail = {
            "error": f"Social content generation failed: {str(e)}",
            "type": str(type(e).__name__),
            "details": str(e)
        }
        return JSONResponse(
            content=serialize_object(error_detail),
            status_code=500
        )


@app.delete("/project/{project_name}")
async def delete_project(project_name: str) -> JSONResponse:
    """Delete a project and its associated content."""
    try:
        project_dir = Path(UPLOAD_DIRECTORY) / project_name
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
            
            # --- Enhancement: Clear related job states from cache on project deletion ---
            keys_to_delete = [
                job_id for job_id, state in state_cache.items()
                if state.get("project_name") == project_name
            ]
            for key in keys_to_delete:
                try:
                    del state_cache[key]
                    logger.info(f"Cleared cached job state {key} during deletion of project {project_name}")
                except KeyError:
                    pass # Already gone, ignore
            # --- End Enhancement ---

            # Clear vector store content (existing logic)
            for agents in agent_cache.values():
                if "content_parser" in agents:
                    agents["content_parser"].clear_project_content(project_name)

            return JSONResponse(
                content={"message": f"Project '{project_name}' deleted successfully"}
            )
        else:
            return JSONResponse(
                content={"error": f"Project '{project_name}' not found"},
                status_code=404
            )
    except Exception as e:
        logger.exception(f"Project deletion failed: {str(e)}")
        return JSONResponse(
            content={"error": f"Project deletion failed: {str(e)}"},
            status_code=500
        )

@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"})
