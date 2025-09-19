"""
FastAPI application for blog content processing, outline generation, and blog draft generation.
"""
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
import os
import json
import sys
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import uuid # For generating unique job IDs
from cachetools import TTLCache # For simple in-memory state cache
from datetime import datetime
 
current_file_path = Path(".")
sys.path.append("")

from root.backend.agents.outline_generator_agent import OutlineGeneratorAgent
from root.backend.agents.content_parsing_agent import ContentParsingAgent
from root.backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from root.backend.agents.social_media_agent import SocialMediaAgent
from root.backend.agents.blog_refinement_agent import BlogRefinementAgent # Updated import path
from root.backend.agents.outline_generator.state import FinalOutline
from root.backend.agents.blog_refinement.state import RefinementResult, TitleOption # Combined import
from root.backend.utils.serialization import serialize_object
from root.backend.models.model_factory import ModelFactory
from root.backend.services.vector_store_service import VectorStoreService # Added
from root.backend.services.persona_service import PersonaService # Added
from root.backend.services.project_manager import ProjectManager, MilestoneType, ProjectStatus # Added
from root.backend.services.cost_aggregator import CostAggregator

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

# In-memory cache for job states (outline, content hashes, model name) with a TTL
# Sections are now cached persistently in VectorStoreService
# Extended TTL to 6 hours to accommodate longer user workflows
state_cache = TTLCache(maxsize=100, ttl=21600)  # 6 hours = 21600 seconds

# Initialize ProjectManager for persistent project tracking
project_manager = ProjectManager()

def refresh_job_cache(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve job state and refresh its TTL by re-inserting it into cache.
    Returns the job state if found, None otherwise.
    """
    job_state = state_cache.get(job_id)
    if job_state:
        # Re-insert to refresh TTL
        state_cache[job_id] = job_state
        logger.info(f"Refreshed cache TTL for job_id: {job_id}")
    return job_state

@app.get("/validate_job/{job_id}")
async def validate_job(job_id: str) -> JSONResponse:
    """Validate if a job exists and refresh its cache."""
    job_state = refresh_job_cache(job_id)
    if job_state:
        return JSONResponse(
            content={
                "valid": True,
                "job_id": job_id,
                "has_outline": bool(job_state.get("outline")),
                "has_refined_draft": bool(job_state.get("refined_draft")),
                "project_name": job_state.get("project_name")
            }
        )
    else:
        return JSONResponse(
            content={
                "valid": False,
                "job_id": job_id,
                "error": "Job not found or expired",
                "suggestion": "Please regenerate the outline to restart the workflow."
            },
            status_code=404
        )

@app.post("/upload/{project_name}")
async def upload_files(
    project_name: str,
    files: Optional[List[UploadFile]] = File(None),
    model_name: Optional[str] = Form(None),
    persona: Optional[str] = Form(None)
) -> JSONResponse:
    """Upload files for a specific project and create a project entry."""
    try:
        # Validate inputs
        if not files or len(files) == 0:
            return JSONResponse(
                content={"error": "No valid files were uploaded"},
                status_code=400
            )
        
        # Validate project name
        if not project_name or not project_name.strip():
            return JSONResponse(
                content={"error": "Project name cannot be empty"},
                status_code=400
            )
            
        # Sanitize project name for filesystem safety
        safe_project_name = project_name.strip()[:100]  # Limit length
        
        # Create project directory
        project_dir = Path(UPLOAD_DIRECTORY) / safe_project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        uploaded_files = []
        valid_files = [f for f in files if f.filename and f.filename.strip()]
        
        if not valid_files:
            return JSONResponse(
                content={"error": "No valid files provided - all files have empty names"},
                status_code=400
            )
        
        for file in valid_files:

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
        
        # Create project in ProjectManager
        metadata = {
            "model_name": model_name,
            "persona": persona,
            "upload_directory": str(project_dir)
        }
        project_id = project_manager.create_project(project_name, metadata)
        
        # Save files_uploaded milestone
        milestone_data = {
            "files": uploaded_files,
            "file_count": len(uploaded_files),
            "upload_time": datetime.now().isoformat()
        }
        project_manager.save_milestone(
            project_id,
            MilestoneType.FILES_UPLOADED,
            milestone_data
        )
        
        logger.info(f"Created project {project_id} with {len(uploaded_files)} uploaded files")

        return JSONResponse(
            content={
                "message": "Files uploaded successfully",
                "project": project_name,
                "project_id": project_id,
                "files": uploaded_files
            }
        )
    except Exception as e:
        logger.exception(f"Upload failed: {str(e)}")
        return JSONResponse(
            content={"error": f"Upload failed: {str(e)}"},
            status_code=500
        )

async def get_or_create_agents(model_name: str, specific_model: Optional[str] = None):
    """Get or create agents for the specified model."""
    # Include specific model in cache key if provided
    cache_key = f"agents_{model_name}_{specific_model or 'default'}"

    if cache_key in agent_cache:
        return agent_cache[cache_key]

    try:
        # Create model instance
        model_factory = ModelFactory()
        model = model_factory.create_model(model_name.lower(), specific_model)

        # Create and initialize agents
        content_parser = ContentParsingAgent(model)
        await content_parser.initialize()

        # Instantiate VectorStoreService (it might become a singleton later if needed)
        vector_store = VectorStoreService() # Instantiate VectorStoreService here
        
        # Instantiate PersonaService for consistent writer voice
        persona_service = PersonaService()

        outline_agent = OutlineGeneratorAgent(model, content_parser, vector_store, persona_service) # Pass persona_service
        await outline_agent.initialize()

        # Pass vector_store and persona_service to BlogDraftGeneratorAgent
        draft_agent = BlogDraftGeneratorAgent(model, content_parser, vector_store, persona_service)
        await draft_agent.initialize()

        refinement_agent = BlogRefinementAgent(model, persona_service)
        await refinement_agent.initialize()

        social_agent = SocialMediaAgent(model, persona_service)
        await social_agent.initialize()

        # Cache the agents
        agent_cache[cache_key] = {
            "model": model,
            "content_parser": content_parser,
            "outline_agent": outline_agent,
            "draft_agent": draft_agent,
            "refinement_agent": refinement_agent, # Added refinement agent to cache
            "social_agent": social_agent,
            "vector_store": vector_store # Also cache vector store instance if needed elsewhere
        }

        return agent_cache[cache_key]
    except Exception as e:
        logger.exception(f"Failed to create agents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create agents: {str(e)}")
    
@app.get("/debug_job/{job_id}")
async def debug_job(job_id: str):
    """Debug endpoint to see job state."""
    job_state = state_cache.get(job_id)
    if not job_state:
        return {"error": "Job not found"}
    
    outline = job_state.get('outline', {})
    sections = job_state.get('generated_sections', {})
    
    return {
        "job_id": job_id,
        "outline_title": outline.get('title', 'Unknown'),
        "total_sections_expected": len(outline.get('sections', [])),
        "sections_generated": list(sections.keys()),
        "sections_count": len(sections),
        "has_final_draft": 'final_draft' in job_state,
        "has_refined_draft": 'refined_draft' in job_state,
        "all_keys": list(job_state.keys())
    }

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
    user_guidelines: Optional[str] = Form(None), # Added
    length_preference: Optional[str] = Form(None), # Added
    custom_length: Optional[int] = Form(None), # Added
    writing_style: Optional[str] = Form(None), # Added
    persona_style: Optional[str] = Form("neuraforge"), # Added persona selection
    specific_model: Optional[str] = Form(None) # Added specific model selection
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
        agents = await get_or_create_agents(model_name, specific_model)
        outline_agent = agents["outline_agent"]

        # Initialize cost tracking for this workflow
        job_id = str(uuid.uuid4())
        cost_aggregator = CostAggregator()
        cost_aggregator.start_workflow(project_id=job_id)

        # Generate outline - returns a dict (outline or error), content, content, cached_status
        outline_result, notebook_content, markdown_content, was_cached = await outline_agent.generate_outline(
            project_name=project_name,
            notebook_hash=notebook_hash,
            markdown_hash=markdown_hash,
            user_guidelines=user_guidelines, # Pass guidelines to agent
            length_preference=length_preference, # Pass length preference
            custom_length=custom_length, # Pass custom length
            writing_style=writing_style, # Pass writing style
            cost_aggregator=cost_aggregator,
            project_id=job_id
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

        # Generate outline hash for caching/tracking
        import hashlib
        outline_str = json.dumps(outline_data, sort_keys=True)
        outline_hash = hashlib.sha256(outline_str.encode()).hexdigest()[:16]

        cost_summary = cost_aggregator.get_workflow_summary()
        cost_call_history = list(cost_aggregator.call_history)

        # Store the state in the cache (still use in-memory cache for job state)
        state_cache[job_id] = {
            "outline": outline_data, # Store parsed data
            "outline_hash": outline_hash,
            "notebook_content": notebook_content,
            "markdown_content": markdown_content,
            "project_name": project_name,
            "model_name": model_name,
            "persona": persona_style,  # Store persona style selected by user
            "writing_style": writing_style,  # Keep for backward compatibility
            "specific_model": specific_model,
            "cost_aggregator": cost_aggregator,
            "cost_summary": cost_summary,
            "cost_call_history": cost_call_history,
            "job_id": job_id
        }
        logger.info(f"Stored initial state for job_id: {job_id}")
        
        # Check if we have a project_id in the request or need to find it
        # Look for existing project by name
        projects = project_manager.list_projects(status=ProjectStatus.ACTIVE)
        project_id = None
        for project in projects:
            if project.get("name") == project_name:
                project_id = project.get("id")
                break
        
        # Save outline milestone if project exists
        if project_id:
            milestone_data = {
                "outline": outline_data,
                "outline_hash": outline_hash,
                "job_id": job_id,
                "model_name": model_name,
                "specific_model": specific_model,
                "persona": writing_style,
                "user_guidelines": user_guidelines,
                "length_preference": length_preference,
                "custom_length": custom_length,
                "was_cached": was_cached
            }
            milestone_metadata = {
                "cost_summary": cost_summary,
                "cost_call_history": cost_call_history
            }

            project_manager.save_milestone(
                project_id,
                MilestoneType.OUTLINE_GENERATED,
                milestone_data,
                metadata=milestone_metadata
            )
            
            # Update project metadata
            project_manager.update_metadata(project_id, {
                "model_name": model_name,
                "specific_model": specific_model,
                "persona": writing_style,
                "latest_job_id": job_id,
                "cost_summary": cost_summary,
                "cost_call_history": cost_call_history
            })
            
            # Add project_id to state cache
            state_cache[job_id]["project_id"] = project_id
            cost_aggregator.current_workflow["project_id"] = project_id
            state_cache[job_id]["cost_summary"] = cost_summary
            state_cache[job_id]["cost_call_history"] = cost_call_history

            logger.info(f"Saved outline milestone for project {project_id}")

        # Return the job ID and the outline itself (for immediate display)
        return JSONResponse(
            content=serialize_object({
                "job_id": job_id,
                "project_id": project_id,
                "outline": outline_data, # Return the parsed outline data
                "cost_summary": cost_summary
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
        
        
@app.get("/job_status/{job_id}")
async def get_job_status(job_id: str) -> JSONResponse:
    """Get the current status of a job for debugging."""
    try:
        # Use refresh to extend TTL when checking status
        job_state = refresh_job_cache(job_id)
        if not job_state:
            return JSONResponse(
                content={
                    "error": "Job not found", 
                    "job_id": job_id,
                    "suggestion": "Job may have expired. Please regenerate the outline."
                },
                status_code=404
            )
        
        outline = job_state.get('outline', {})
        total_sections = len(outline.get('sections', []))
        generated_sections = job_state.get('generated_sections', {})
        completed_sections = len(generated_sections)
        
        return JSONResponse(content={
            "job_id": job_id,
            "project_name": job_state.get('project_name'),
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "missing_sections": [i for i in range(total_sections) if i not in generated_sections],
            "has_final_draft": bool(job_state.get('final_draft')),
            "has_refined_draft": bool(job_state.get('refined_draft')),
            "status": job_state.get('status_message', 'unknown'),
            "outline_title": outline.get('title', 'Unknown'),
            # Include actual content for frontend resume
            "has_outline": bool(outline),
            "outline": outline,
            "final_draft": job_state.get('final_draft'),
            "refined_draft": job_state.get('refined_draft'),
            "summary": job_state.get('summary'),
            "title_options": job_state.get('title_options'),
            "social_content": job_state.get('social_content'),
            "generated_sections": job_state.get('generated_sections', {}),
            "cost_summary": job_state.get('cost_summary'),
            "cost_call_history": job_state.get('cost_call_history', [])
        })
    except Exception as e:
        logger.exception(f"Error getting job status: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to get job status: {str(e)}"},
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
    # This endpoint seems less used now with section-by-section generation,
    # but keep it functional if needed. It doesn't involve section caching directly.
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

        cost_aggregator = CostAggregator()
        workflow_id = f"adhoc-{uuid.uuid4()}"
        cost_aggregator.start_workflow(project_id=workflow_id)

        # Generate blog draft
        outline_obj = FinalOutline.model_validate(outline_data)
        draft = await draft_agent.generate_draft(
            project_name=project_name,
            outline=outline_obj,
            notebook_content=notebook_data,
            markdown_content=markdown_data,
            cost_aggregator=cost_aggregator,
            project_id=workflow_id
        )

        if not draft:
            return JSONResponse(
                content={"error": "Failed to generate blog draft"},
                status_code=500
            )

        return JSONResponse(
            content=serialize_object({
                "draft": draft,
                "cost_summary": cost_aggregator.get_workflow_summary()
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

# @app.post("/generate_section/{project_name}")
# async def generate_section(
#     project_name: str, # Keep project_name for potential future use/logging
#     job_id: str = Form(...), # Use job_id instead of outline/content
#     section_index: int = Form(...),
#     max_iterations: int = Form(3),
#     quality_threshold: float = Form(0.8)
# ) -> JSONResponse:
#     """Generate a single section of a blog draft, using persistent cache via agent."""
#     try:
#         # Retrieve state from cache (still needed for outline, content, model)
#         job_state = state_cache.get(job_id)
#         if not job_state:
#             logger.error(f"Job state not found for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
#                 status_code=404
#             )

#         # Extract data from state
#         outline_data = job_state["outline"]
#         notebook_data = job_state.get("notebook_content") # Use .get for safety
#         markdown_data = job_state.get("markdown_content") # Use .get for safety
#         model_name = job_state["model_name"]

#         # Validate section index against the retrieved outline
#         if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
#             return JSONResponse(
#                 content={"error": f"Invalid section index: {section_index}"},
#                 status_code=400
#             )

#         # Get current section from the retrieved outline
#         section = outline_data["sections"][section_index]
#         section_title = section.get("title", f"Section {section_index + 1}") # Get title for response

#         # Get or create agents using model_name from state
#         agents = await get_or_create_agents(model_name)
#         draft_agent = agents["draft_agent"]

#         # Call the agent's generate_section method, which now handles caching internally
#         # Pass the full outline dictionary for hashing, remove job_id from direct call (agent uses outline_hash)
#         # It returns a tuple: (content, was_cached)
#         section_content, was_cached = await draft_agent.generate_section(
#             project_name=project_name,
#             # job_id is not directly used by agent.generate_section for cache key anymore
#             section=section,
#             # job_id=job_id, # No longer passed directly for caching logic
#             outline=outline_data, # The full outline dict for hashing
#             notebook_content=notebook_data, # Pass potentially None content
#             markdown_content=markdown_data, # Pass potentially None content
#             current_section_index=section_index,
#             max_iterations=max_iterations,
#             quality_threshold=quality_threshold,
#             use_cache=True # Explicitly enable cache usage in the agent
#         )

#         # Check if agent returned content
#         if section_content is None:
#             # Agent handles logging errors internally now
#             return JSONResponse(
#                 content={"error": f"Failed to generate or retrieve section: {section_title}"},
#                 status_code=500
#             )

#         # Agent now handles storing in persistent cache if it was generated (was_cached=False)
#         # No need to update state_cache here for section content anymore

#         # Return the result from the agent
#         return JSONResponse(
#             content=serialize_object({
#                 "job_id": job_id,
#                 "section_title": section_title,
#                 "section_content": section_content,
#                 "section_index": section_index,
#                 "was_cached": was_cached # Pass the flag from the agent
#             })
#         )

#     except Exception as e:
#         logger.exception(f"Section generation failed: {str(e)}")

#         # Provide detailed error information
#         error_detail = {
#             "error": f"Section generation failed: {str(e)}",
#             "type": str(type(e).__name__),
#             "details": str(e)
#         }

#         return JSONResponse(
#             content=serialize_object(error_detail),
#             status_code=500
#         )

@app.post("/generate_section/{project_name}")
async def generate_section(
    project_name: str,
    job_id: str = Form(...),
    section_index: int = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """Generate a single section and store it in job state immediately."""
    try:
        # Validate job exists
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
                status_code=404
            )

        # Ensure cost tracking is available and rehydrate if needed
        cost_aggregator = job_state.get("cost_aggregator")
        if not cost_aggregator:
            cost_aggregator = CostAggregator()
            target_project = job_state.get("project_id", job_id)
            cost_aggregator.start_workflow(project_id=target_project)

            existing_history = job_state.get("cost_call_history") or []
            if not existing_history and job_state.get("project_id"):
                project_record = project_manager.get_project(job_state["project_id"])
                if project_record:
                    existing_history = project_record.get("metadata", {}).get("cost_call_history", [])

            if existing_history:
                for call in existing_history:
                    try:
                        cost_aggregator.record_cost(call)
                    except Exception as err:
                        logger.warning(f"Failed to replay cost record during section resume: {err}")

            job_state["cost_aggregator"] = cost_aggregator
            job_state["cost_summary"] = cost_aggregator.get_workflow_summary()
            job_state["cost_call_history"] = list(cost_aggregator.call_history)

        if job_state.get("project_id"):
            cost_aggregator.current_workflow["project_id"] = job_state["project_id"]

        previous_summary = job_state.get("cost_summary")
        previous_total_cost = previous_summary.get("total_cost", 0.0) if previous_summary else 0.0
        previous_total_tokens = previous_summary.get("total_tokens", 0) if previous_summary else 0

        # Extract data from state
        outline_data = job_state["outline"]
        notebook_data = job_state.get("notebook_content")
        markdown_data = job_state.get("markdown_content")
        model_name = job_state["model_name"]
        specific_model = job_state.get("specific_model")

        # Validate section index
        if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": f"Invalid section index: {section_index}"},
                status_code=400
            )

        # Get current section
        section = outline_data["sections"][section_index]
        section_title = section.get("title", f"Section {section_index + 1}")

        # Check if section already exists in job state
        generated_sections = job_state.get('generated_sections', {})
        if section_index in generated_sections:
            logger.info(f"Section {section_index} already exists in job state, returning cached version")
            cached_section = generated_sections[section_index]
            return JSONResponse(
                content={
                    "job_id": job_id,
                    "section_title": cached_section.get("title", section_title),
                    "section_content": cached_section.get("content"),
                    "section_index": section_index,
                    "was_cached": True
                }
            )

        # Generate new section
        agents = await get_or_create_agents(model_name, specific_model)
        draft_agent = agents["draft_agent"]

        # Generate section content
        section_result, was_cached = await draft_agent.generate_section(
            project_name=project_name,
            section=section,
            outline=outline_data,
            notebook_content=notebook_data,
            markdown_content=markdown_data,
            current_section_index=section_index,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
            use_cache=True,
            cost_aggregator=cost_aggregator,
            project_id=job_state.get("project_id", job_id),
            persona=job_state.get("persona", "neuraforge")  # Pass persona from job state
        )

        if section_result is None:
            return JSONResponse(
                content={"error": f"Failed to generate section: {section_title}"},
                status_code=500
            )

        # Extract content and image placeholders from result
        if isinstance(section_result, dict):
            section_content = section_result.get("content")
            image_placeholders = section_result.get("image_placeholders", [])
        else:
            # Backward compatibility for old cache format
            section_content = section_result
            image_placeholders = []

        # Store in job state immediately
        if 'generated_sections' not in job_state:
            job_state['generated_sections'] = {}

        job_state['generated_sections'][section_index] = {
            "title": section_title,
            "content": section_content,
            "image_placeholders": image_placeholders,  # Include image placeholders
            "generated_at": datetime.now().isoformat()
        }

        updated_summary = cost_aggregator.get_workflow_summary()
        updated_history = list(cost_aggregator.call_history)
        job_state["cost_summary"] = updated_summary
        job_state["cost_call_history"] = updated_history

        section_cost_delta = updated_summary.get("total_cost", 0.0) - previous_total_cost
        section_tokens_delta = updated_summary.get("total_tokens", 0) - previous_total_tokens
        job_state['generated_sections'][section_index]["cost_delta"] = section_cost_delta
        job_state['generated_sections'][section_index]["token_delta"] = section_tokens_delta
        job_state['generated_sections'][section_index]["cost_snapshot"] = updated_summary

        project_id_in_state = job_state.get("project_id")
        if project_id_in_state:
            project_manager.update_metadata(project_id_in_state, {
                "cost_summary": updated_summary,
                "cost_call_history": updated_history,
                "latest_job_id": job_id
            })

        logger.info(f"Stored section {section_index} in job state for job_id: {job_id}")

        return JSONResponse(
            content={
                "job_id": job_id,
                "section_title": section_title,
                "section_content": section_content,
                "image_placeholders": image_placeholders,  # Include image placeholders in response
                "section_index": section_index,
                "was_cached": was_cached,
                "cost_summary": updated_summary,
                "section_cost": section_cost_delta,
                "section_tokens": section_tokens_delta
            }
        )

    except Exception as e:
        logger.exception(f"Section generation failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Section generation failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )

# @app.post("/regenerate_section_with_feedback/{project_name}")
# async def regenerate_section(
#     project_name: str, # Keep project_name for potential future use/logging
#     job_id: str = Form(...), # Use job_id instead of outline/content/model_name
#     section_index: int = Form(...),
#     feedback: str = Form(...),
#     max_iterations: int = Form(3),
#     quality_threshold: float = Form(0.8)
# ) -> JSONResponse:
#     """Regenerate a section with user feedback, updating persistent cache via agent."""
#     try:
#         # Retrieve state from cache (still needed for outline, content, model)
#         job_state = state_cache.get(job_id)
#         if not job_state:
#             logger.error(f"Job state not found for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
#                 status_code=404
#             )

#         # Extract data from state
#         outline_data = job_state["outline"]
#         notebook_data = job_state.get("notebook_content") # Use .get
#         markdown_data = job_state.get("markdown_content") # Use .get
#         model_name = job_state["model_name"]

#         # Validate section index against the retrieved outline
#         if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
#             return JSONResponse(
#                 content={"error": f"Invalid section index: {section_index}"},
#                 status_code=400
#             )

#         # Get current section from the retrieved outline
#         section = outline_data["sections"][section_index]

#         # Get or create agents using model_name from state
#         agents = await get_or_create_agents(model_name)
#         draft_agent = agents["draft_agent"]

#         # Regenerate section with feedback using retrieved data
#         # job_id is not directly used by agent.regenerate_section_with_feedback for cache key
#         new_content = await draft_agent.regenerate_section_with_feedback(
#             project_name=project_name,
#             section=section,
#             outline=outline_data, # Agent will hash this
#             notebook_content=notebook_data, # Pass potentially None
#             markdown_content=markdown_data, # Pass potentially None
#             feedback=feedback,
#             max_iterations=max_iterations,
#             quality_threshold=quality_threshold
#         )

#         if not new_content:
#             # Agent handles logging errors internally
#             return JSONResponse(
#                 content={"error": f"Failed to regenerate section: {section.get('title', 'Unknown')}"},
#                 status_code=500
#             )

#         # Agent now handles updating the persistent cache internally after regeneration
#         # No need to update state_cache here

#         return JSONResponse(
#             content=serialize_object({
#                 "job_id": job_id, # Return job_id
#                 "section_title": section.get("title", "Unknown"),
#                 "section_content": new_content,
#                 "section_index": section_index,
#                 "feedback_addressed": True # Indicate feedback was processed
#             })
#         )

#     except Exception as e:
#         logger.exception(f"Section regeneration failed: {str(e)}")

#         # Provide detailed error information
#         error_detail = {
#             "error": f"Section regeneration failed: {str(e)}",
#             "type": str(type(e).__name__),
#             "details": str(e)
#         }

#         return JSONResponse(
#             content=serialize_object(error_detail),
#             status_code=500
#         )

@app.post("/regenerate_section_with_feedback/{project_name}")
async def regenerate_section(
    project_name: str,
    job_id: str = Form(...),
    section_index: int = Form(...),
    feedback: str = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """Regenerate a section with user feedback and update job state."""
    try:
        # Validate job exists
        job_state = state_cache.get(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={"error": f"Job state not found for job_id: {job_id}"},
                status_code=404
            )

        # Ensure cost tracking is available
        cost_aggregator = job_state.get("cost_aggregator")
        if not cost_aggregator:
            cost_aggregator = CostAggregator()
            target_project = job_state.get("project_id", job_id)
            cost_aggregator.start_workflow(project_id=target_project)

            existing_history = job_state.get("cost_call_history") or []
            if not existing_history and job_state.get("project_id"):
                project_record = project_manager.get_project(job_state["project_id"])
                if project_record:
                    existing_history = project_record.get("metadata", {}).get("cost_call_history", [])

            if existing_history:
                for call in existing_history:
                    try:
                        cost_aggregator.record_cost(call)
                    except Exception as err:
                        logger.warning(f"Failed to replay cost record during section resume: {err}")

            job_state["cost_aggregator"] = cost_aggregator
            job_state["cost_summary"] = cost_aggregator.get_workflow_summary()
            job_state["cost_call_history"] = list(cost_aggregator.call_history)

        if job_state.get("project_id"):
            cost_aggregator.current_workflow["project_id"] = job_state["project_id"]

        previous_summary = job_state.get("cost_summary")
        previous_total_cost = previous_summary.get("total_cost", 0.0) if previous_summary else 0.0
        previous_total_tokens = previous_summary.get("total_tokens", 0) if previous_summary else 0

        # Extract data from state
        outline_data = job_state["outline"]
        notebook_data = job_state.get("notebook_content")
        markdown_data = job_state.get("markdown_content")
        model_name = job_state["model_name"]

        # Validate section index
        if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": f"Invalid section index: {section_index}"},
                status_code=400
            )

        # Get current section
        section = outline_data["sections"][section_index]
        section_title = section.get("title", f"Section {section_index + 1}")

        # Get agents
        agents = await get_or_create_agents(model_name)
        draft_agent = agents["draft_agent"]

        # Regenerate section with feedback
        new_content = await draft_agent.regenerate_section_with_feedback(
            project_name=project_name,
            section=section,
            outline=outline_data,
            notebook_content=notebook_data,
            markdown_content=markdown_data,
            feedback=feedback,
            max_iterations=max_iterations,
            quality_threshold=quality_threshold,
            cost_aggregator=cost_aggregator,
            project_id=job_state.get("project_id", job_id)
        )

        if not new_content:
            return JSONResponse(
                content={"error": f"Failed to regenerate section: {section_title}"},
                status_code=500
            )

        # Update job state immediately
        if 'generated_sections' not in job_state:
            job_state['generated_sections'] = {}
        
        job_state['generated_sections'][section_index] = {
            "title": section_title,
            "content": new_content,
            "regenerated_at": datetime.now().isoformat(),
            "feedback_provided": feedback[:100] + "..." if len(feedback) > 100 else feedback
        }

        updated_summary = cost_aggregator.get_workflow_summary()
        updated_history = list(cost_aggregator.call_history)
        job_state["cost_summary"] = updated_summary
        job_state["cost_call_history"] = updated_history

        section_cost_delta = updated_summary.get("total_cost", 0.0) - previous_total_cost
        section_tokens_delta = updated_summary.get("total_tokens", 0) - previous_total_tokens
        job_state['generated_sections'][section_index]["cost_delta"] = section_cost_delta
        job_state['generated_sections'][section_index]["token_delta"] = section_tokens_delta
        job_state['generated_sections'][section_index]["cost_snapshot"] = updated_summary

        project_id_in_state = job_state.get("project_id")
        if project_id_in_state:
            project_manager.update_metadata(project_id_in_state, {
                "cost_summary": updated_summary,
                "cost_call_history": updated_history,
                "latest_job_id": job_id
            })
        
        logger.info(f"Updated section {section_index} in job state with feedback")

        return JSONResponse(
            content={
                "job_id": job_id,
                "section_title": section_title,
                "section_content": new_content,
                "section_index": section_index,
                "feedback_addressed": True,
                "cost_summary": updated_summary,
                "section_cost": section_cost_delta,
                "section_tokens": section_tokens_delta
            }
        )

    except Exception as e:
        logger.exception(f"Section regeneration failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Section regeneration failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )


# @app.post("/compile_draft/{project_name}")
# async def compile_draft(
#     project_name: str, # Keep project_name for potential future use/logging
#     job_id: str = Form(...) # Use job_id instead of outline/sections
# ) -> JSONResponse:
#     """Compile a final blog draft using cached section data."""
#     logger.info(f"Starting draft compilation for job_id: {job_id}")
#     try:
#         # Retrieve state from cache (for outline, model, etc.)
#         job_state = state_cache.get(job_id)
#         if not job_state:
#             logger.error(f"Job state (outline info) not found for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Job state not found for job_id: {job_id}. Please generate outline first."},
#                 status_code=404
#             )

#         # Extract data from state
#         outline_data = job_state["outline"]
#         model_name = job_state["model_name"] # Needed to get vector_store instance
#         num_outline_sections = len(outline_data.get("sections", []))
#         generated_sections_dict = {} # Will be populated from cache
#         missing_sections = []
#         all_sections_retrieved = True

#         # Attempt to retrieve all sections from VectorStore cache using outline_hash
#         try:
#             agents = await get_or_create_agents(model_name) # Get agents to access vector_store and hashing logic
#             vector_store = agents["vector_store"]
#             # Need access to the agent's cache key logic or replicate it
#             # Assuming BlogDraftGeneratorAgent has a static or accessible method for this
#             # If not, this part needs adjustment based on how the key is generated/accessed
            
#             # Get the draft_agent to use its hashing and key generation methods
#             agents = await get_or_create_agents(model_name)
#             draft_agent = agents["draft_agent"]
#             vector_store = agents["vector_store"] # Get the shared vector_store

#             outline_hash = draft_agent._hash_outline_for_cache(outline_data)
#             draft_agent = agents["draft_agent"] # Need agent instance for hashing method

#             # Generate the outline hash needed for retrieval
#             outline_hash = draft_agent._hash_outline_for_cache(outline_data)

#             for i in range(num_outline_sections):
#                 cache_key = draft_agent._create_section_cache_key(project_name, outline_hash, i)
#                 # Use the agent's method to create the consistent cache key
#                 cache_key = draft_agent._create_section_cache_key(project_name, outline_hash, i)
#                 cached_section_json = vector_store.retrieve_section_cache(
#                     cache_key=cache_key,
#                     project_name=project_name,
#                     outline_hash=outline_hash, # Use outline_hash for retrieval
#                     section_index=i
#                 )
#                 if cached_section_json:
#                     try:
#                         cached_data = json.loads(cached_section_json)
#                         generated_sections_dict[i] = cached_data # Populate dict from persistent cache
#                     except json.JSONDecodeError:
#                         logger.warning(f"Failed to parse cached JSON for section {i} during compilation. Marking as missing.")
#                         missing_sections.append(i)
#                         all_sections_retrieved = False
#                 else:
#                     logger.warning(f"Section {i} not found in persistent cache for outline {outline_hash}.")
#                     missing_sections.append(i)
#                     all_sections_retrieved = False
#         except Exception as retrieval_err:
#              logger.exception(f"Error retrieving sections from VectorStore during compilation: {retrieval_err}") # Use logger.exception
#              return JSONResponse(
#                 content={"error": "Failed to retrieve section data for compilation."},
#                 status_code=500
#             )

#         # Validate all sections were retrieved
#         if not all_sections_retrieved:
#             logger.error(f"Missing generated content (in VectorStore) for sections {missing_sections} for outline {outline_hash}")
#             return JSONResponse(
#                 content={"error": f"Missing content (in VectorStore) for sections: {', '.join(map(str, missing_sections))}. Please ensure all sections were generated."},
#                 status_code=400
#             )

#         # Prepare sections_data in the correct order from the populated dict
#         sections_data = [generated_sections_dict[i] for i in range(num_outline_sections)]


#         # Compile blog draft (logic remains the same)
#         blog_parts = [
#             f"# {outline_data['title']}\n",
#             f"**Difficulty Level**: {outline_data['difficulty_level']}\n",
#             "\n## Prerequisites\n"
#         ]
#         if isinstance(outline_data["prerequisites"], dict):
#             if "required_knowledge" in outline_data["prerequisites"]:
#                 blog_parts.append("\n### Required Knowledge\n")
#                 for item in outline_data["prerequisites"]["required_knowledge"]:
#                     blog_parts.append(f"- {item}\n")
#             if "recommended_tools" in outline_data["prerequisites"]:
#                 blog_parts.append("\n### Recommended Tools\n")
#                 for tool in outline_data["prerequisites"]["recommended_tools"]:
#                     blog_parts.append(f"- {tool}\n")
#             if "setup_instructions" in outline_data["prerequisites"]:
#                 blog_parts.append("\n### Setup Instructions\n")
#                 for instruction in outline_data["prerequisites"]["setup_instructions"]:
#                     blog_parts.append(f"- {instruction}\n")
#         else:
#             blog_parts.append(f"{outline_data['prerequisites']}\n")

#         blog_parts.append("\n## Table of Contents\n")
#         for i, section_data in enumerate(sections_data):
#             title = section_data.get("title", outline_data["sections"][i].get("title", f"Section {i+1}"))
#             blog_parts.append(f"{i+1}. [{title}](#section-{i+1})\n")

#         blog_parts.append("\n")

#         for i, section_data in enumerate(sections_data):
#             title = section_data.get("title", outline_data["sections"][i].get("title", f"Section {i+1}"))
#             content = section_data.get("content", "*Error: Content not found*")
#             blog_parts.extend([
#                 f"<a id='section-{i+1}'></a>\n",
#                 f"## {title}\n",
#                 f"{content}\n\n"
#             ])

#         if 'conclusion' in outline_data and outline_data['conclusion']:
#             blog_parts.extend([
#                 "## Conclusion\n",
#                 f"{outline_data['conclusion']}\n\n"
#             ])

#         final_draft = "\n".join(blog_parts)
#         logger.info(f"Successfully assembled final_draft content for job_id: {job_id}.")

#         # Store final draft in state_cache and save to file (existing logic)
#         draft_saved_to_file = False
#         try:
#             if job_id in state_cache:
#                 state_cache[job_id]["final_draft"] = final_draft
#                 logger.info(f"Stored final draft in state_cache for job_id: {job_id}")

#                 project_dir = Path(UPLOAD_DIRECTORY) / project_name
#                 project_dir.mkdir(parents=True, exist_ok=True)
#                 safe_project_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in project_name)
#                 draft_filename = f"{safe_project_name}_compiled_draft.md"
#                 draft_filepath = project_dir / draft_filename
#                 try:
#                     with open(draft_filepath, "w", encoding="utf-8") as f:
#                         f.write(final_draft)
#                     logger.info(f"Saved compiled draft to: {draft_filepath}")
#                     draft_saved_to_file = True
#                 except IOError as io_err:
#                     logger.error(f"Failed to save compiled draft to file {draft_filepath}: {io_err}")

#             else:
#                 logger.warning(f"Job state for {job_id} expired before final draft could be stored or saved.")
#         except Exception as cache_update_err:
#             logger.error(f"Failed to update state_cache/save file for job {job_id}: {cache_update_err}")

#         response_content = {
#             "job_id": job_id,
#             "draft": final_draft,
#             "draft_saved": draft_saved_to_file
#         }
#         return JSONResponse(content=serialize_object(response_content))

#     except Exception as e:
#         logger.exception(f"Draft compilation failed: {str(e)}")
#         error_detail = {
#             "error": f"Draft compilation failed: {str(e)}",
#             "type": str(type(e).__name__),
#             "details": str(e)
#         }
#         return JSONResponse(
#             content=serialize_object(error_detail),
#             status_code=500
#         )


# @app.post("/refine_blog/{project_name}")
# async def refine_blog(
#     project_name: str, # Keep project_name for potential future use/logging
#     job_id: str = Form(...), # Still needed to get model_name from job_state
#     compiled_draft: str = Form(...) # Add compiled_draft directly to the request
# ) -> JSONResponse:
#     """Refine a compiled blog draft using the BlogRefinementAgent."""
#     try:
#         # Retrieve state from cache (still needed for model_name)
#         job_state = state_cache.get(job_id)
#         if not job_state:
#             logger.error(f"Job state not found for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Job state not found for job_id: {job_id}. Outline/model info missing."},
#                 status_code=404
#             )

#         # The 'compiled_draft' parameter from the Form(...) is used directly.
#         # No need to check job_state.get("final_draft") anymore.
#         if not compiled_draft: # This check is for the Form parameter itself.
#             logger.error(f"Compiled draft not provided in the request for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": "Compiled draft must be provided in the request."},
#                 status_code=400 
#             )

#         # Extract model name from state
#         model_name = job_state.get("model_name")
#         if not model_name:
#              logger.error(f"Model name not found in cache for job_id: {job_id}")
#              return JSONResponse(
#                 content={"error": "Model name missing from job state."},
#                 status_code=500
#             )

#         # Get or create agents using model_name from state
#         agents = await get_or_create_agents(model_name)
#         refinement_agent = agents.get("refinement_agent")

#         if not refinement_agent:
#             logger.error(f"BlogRefinementAgent not found for model {model_name}")
#             return JSONResponse(
#                 content={"error": "Blog refinement agent could not be initialized."},
#                 status_code=500
#             )

#         # Run the refinement process using the graph
#         logger.info(f"Refining blog draft for job_id: {job_id} using graph...")
#         # Call the graph execution method instead of the old 'refine'
#         refinement_result: Optional[RefinementResult] = await refinement_agent.refine_blog_with_graph(
#             blog_draft=compiled_draft
#         )

#         if not refinement_result:
#             logger.error(f"Failed to refine blog draft for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": "Failed to refine blog draft."},
#                 status_code=500
#             )

#         # --- Enhancement: Store refinement results in cache ---
#         try:
#             if job_id in state_cache:
#                 state_cache[job_id]["refined_draft"] = refinement_result.refined_draft
#                 state_cache[job_id]["summary"] = refinement_result.summary
#                 state_cache[job_id]["title_options"] = refinement_result.title_options
#                 logger.info(f"Stored refinement results in cache for job_id: {job_id}")
#             else:
#                 logger.warning(f"Job state for {job_id} expired before refinement results could be stored.")
#         except Exception as cache_update_err:
#             logger.error(f"Failed to update cache with refinement results for job {job_id}: {cache_update_err}")
#         # --- End Enhancement ---

#         # Return the refinement results
#         return JSONResponse(
#             content=serialize_object({
#                 "job_id": job_id,
#                 "refined_draft": refinement_result.refined_draft,
#                 "summary": refinement_result.summary,
#                 "title_options": refinement_result.title_options
#             })
#         )

#     except Exception as e:
#         logger.exception(f"Blog refinement failed: {str(e)}")
#         error_detail = {
#             "error": f"Blog refinement failed: {str(e)}",
#             "type": str(type(e).__name__),
#             "details": str(e)
#         }
#         return JSONResponse(
#             content=serialize_object(error_detail),
#             status_code=500
#         )


# @app.post("/generate_social_content/{project_name}")
# async def generate_social_content(
#     project_name: str, # Keep project_name for potential future use/logging
#     job_id: str = Form(...) # Use job_id to retrieve refined draft and model
# ) -> JSONResponse:
#     """Generate social media content (LinkedIn, X, Newsletter) from a REFINED draft."""
#     try:
#         # Retrieve state from cache
#         job_state = state_cache.get(job_id)
#         if not job_state:
#             logger.error(f"Job state not found for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Job state not found for job_id: {job_id}. Please refine draft first."},
#                 status_code=404
#             )

#         # Check if REFINED draft exists in the state
#         refined_draft = job_state.get("refined_draft")
#         if not refined_draft:
#             logger.error(f"Refined draft not found in cache for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": f"Refined draft not found for job_id: {job_id}. Please refine the draft first."},
#                 status_code=400 # Bad request, draft needs refinement
#             )

#         # Extract necessary info from state
#         model_name = job_state.get("model_name")
#         # Use one of the generated titles if available, otherwise fallback
#         title_options = job_state.get("title_options", [])
#         # Ensure title_options[0] is the correct type before accessing .title
#         blog_title = title_options[0].title if title_options and isinstance(title_options[0], TitleOption) else job_state.get("outline", {}).get("title", "Blog Post")


#         if not model_name:
#              logger.error(f"Model name not found in cache for job_id: {job_id}")
#              return JSONResponse(
#                 content={"error": "Model name missing from job state."},
#                 status_code=500
#             )

#         # Get or create agents using model_name from state
#         agents = await get_or_create_agents(model_name)
#         social_agent = agents.get("social_agent")

#         if not social_agent:
#             logger.error(f"SocialMediaAgent not found for model {model_name}")
#             return JSONResponse(
#                 content={"error": "Social media agent could not be initialized."},
#                 status_code=500
#             )

#         # Generate social content using the REFINED draft
#         logger.info(f"Generating social content for job_id: {job_id} using refined draft.")
#         social_content = await social_agent.generate_content(
#             blog_content=refined_draft, # Use refined draft here
#             blog_title=blog_title
#         )

#         if not social_content:
#             logger.error(f"Failed to generate social content for job_id: {job_id}")
#             return JSONResponse(
#                 content={"error": "Failed to generate social media content."},
#                 status_code=500
#             )

#         # Return the generated content
#         return JSONResponse(
#             content=serialize_object({
#                 "job_id": job_id,
#                 "social_content": social_content # Contains breakdown, linkedin, x, newsletter
#             })
#         )

#     except Exception as e:
#         logger.exception(f"Social content generation failed: {str(e)}")
#         error_detail = {
#             "error": f"Social content generation failed: {str(e)}",
#             "type": str(type(e).__name__),
#             "details": str(e)
#         }
#         return JSONResponse(
#             content=serialize_object(error_detail),
#             status_code=500
#         )

@app.post("/compile_draft/{project_name}")
async def compile_draft(
    project_name: str,
    job_id: str = Form(...)
) -> JSONResponse:
    """Compile final blog draft from sections stored in job state."""
    logger.info(f"Starting draft compilation for job_id: {job_id}")
    try:
        # Retrieve job state and refresh cache TTL
        job_state = refresh_job_cache(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={
                    "error": f"Job state not found for job_id: {job_id}",
                    "details": "Job state may have expired. Please regenerate the outline and draft.",
                    "suggestion": "Try generating a new outline to restart the workflow."
                },
                status_code=404
            )

        # Extract data from state
        outline_data = job_state["outline"]
        generated_sections = job_state.get('generated_sections', {})
        
        # Validate all sections are generated
        num_outline_sections = len(outline_data.get("sections", []))
        missing_sections = []
        
        for i in range(num_outline_sections):
            if i not in generated_sections:
                missing_sections.append(i)
        
        if missing_sections:
            logger.error(f"Missing sections for compilation: {missing_sections}")
            return JSONResponse(
                content={
                    "error": f"Missing sections: {', '.join(map(str, missing_sections))}. Please generate all sections first.",
                    "missing_sections": missing_sections,
                    "total_sections": num_outline_sections,
                    "completed_sections": len(generated_sections)
                },
                status_code=400
            )

        # Ensure cost tracking is present for final snapshots
        cost_aggregator = job_state.get("cost_aggregator")
        if not cost_aggregator:
            cost_aggregator = CostAggregator()
            target_project = job_state.get("project_id", job_id)
            cost_aggregator.start_workflow(project_id=target_project)
            historical = job_state.get("cost_call_history") or []
            if not historical and job_state.get("project_id"):
                project_record = project_manager.get_project(job_state["project_id"])
                if project_record:
                    historical = project_record.get("metadata", {}).get("cost_call_history", [])
            for call in historical:
                try:
                    cost_aggregator.record_cost(call)
                except Exception as err:
                    logger.warning(f"Failed to replay cost record during compile resume: {err}")
            job_state["cost_aggregator"] = cost_aggregator
        if job_state.get("project_id"):
            cost_aggregator.current_workflow["project_id"] = job_state["project_id"]

        # Compile blog draft
        blog_parts = []
        
        # Add title and metadata
        blog_parts.extend([
            f"# {outline_data['title']}\n",
            f"**Difficulty Level**: {outline_data['difficulty_level']}\n",
            "\n## Prerequisites\n"
        ])
        
        # Add prerequisites
        prerequisites = outline_data["prerequisites"]
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
        else:
            blog_parts.append(f"{prerequisites}\n")

        # Add table of contents
        blog_parts.append("\n## Table of Contents\n")
        for i in range(num_outline_sections):
            section_data = generated_sections[i]
            title = section_data.get("title", f"Section {i+1}")
            blog_parts.append(f"{i+1}. [{title}](#section-{i+1})\n")

        blog_parts.append("\n")

        # Add sections
        for i in range(num_outline_sections):
            section_data = generated_sections[i]
            title = section_data.get("title", f"Section {i+1}")
            content = section_data.get("content", "*Error: Content not found*")
            
            blog_parts.extend([
                f"<a id='section-{i+1}'></a>\n",
                f"## {title}\n",
                f"{content}\n\n"
            ])

        # Add conclusion if available
        if 'conclusion' in outline_data and outline_data['conclusion']:
            blog_parts.extend([
                "## Conclusion\n",
                f"{outline_data['conclusion']}\n\n"
            ])

        final_draft = "".join(blog_parts)
        
        # Store in job state
        job_state["final_draft"] = final_draft
        job_state["compiled_at"] = datetime.now().isoformat()
        job_state["cost_summary"] = cost_aggregator.get_workflow_summary()
        job_state["cost_call_history"] = list(cost_aggregator.call_history)
        
        logger.info(f"Successfully compiled draft for job_id: {job_id}")

        # Save to file
        draft_saved_to_file = False
        try:
            project_dir = Path(UPLOAD_DIRECTORY) / project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            safe_project_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in project_name)
            draft_filename = f"{safe_project_name}_compiled_draft.md"
            draft_filepath = project_dir / draft_filename
            
            with open(draft_filepath, "w", encoding="utf-8") as f:
                f.write(final_draft)
            logger.info(f"Saved compiled draft to: {draft_filepath}")
            draft_saved_to_file = True
        except IOError as io_err:
            logger.error(f"Failed to save compiled draft to file: {io_err}")
        
        # Save draft milestone if project exists
        project_id = job_state.get("project_id")
        if not project_id:
            # Try to find project by name
            projects = project_manager.list_projects(status=ProjectStatus.ACTIVE)
            for project in projects:
                if project.get("name") == project_name:
                    project_id = project.get("id")
                    break
        
        if project_id:
            milestone_data = {
                "compiled_blog": final_draft,
                "job_id": job_id,
                "compiled_at": datetime.now().isoformat(),
                "sections_count": num_outline_sections,
                "word_count": len(final_draft.split()),
                "outline_hash": job_state.get("outline_hash")
            }
            milestone_metadata = {
                "cost_summary": job_state.get("cost_summary"),
                "cost_call_history": job_state.get("cost_call_history")
            }

            project_manager.save_milestone(
                project_id,
                MilestoneType.DRAFT_COMPLETED,
                milestone_data,
                metadata=milestone_metadata
            )

            project_manager.update_metadata(project_id, {
                "cost_summary": job_state.get("cost_summary"),
                "cost_call_history": job_state.get("cost_call_history"),
                "latest_job_id": job_id
            })

            logger.info(f"Saved draft milestone for project {project_id}")

        return JSONResponse(content={
            "job_id": job_id,
            "project_id": project_id,
            "draft": final_draft,
            "draft_saved": draft_saved_to_file,
            "sections_compiled": num_outline_sections,
            "cost_summary": job_state.get("cost_summary")
        })

    except Exception as e:
        logger.exception(f"Draft compilation failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Draft compilation failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )

@app.post("/refine_blog/{project_name}")
async def refine_blog(
    project_name: str,
    job_id: str = Form(...),
    compiled_draft: str = Form(...)
) -> JSONResponse:
    """Refine a compiled blog draft using the BlogRefinementAgent."""
    try:
        # Retrieve job state and refresh cache TTL
        job_state = refresh_job_cache(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={
                    "error": f"Job state not found for job_id: {job_id}",
                    "details": "Job state may have expired. Please regenerate the outline and draft.",
                    "suggestion": "Try generating a new outline to restart the workflow."
                },
                status_code=404
            )

        # Check for compiled draft from request
        if not compiled_draft:
            logger.error(f"Compiled draft not provided in request for job_id: {job_id}")
            return JSONResponse(
                content={
                    "error": f"No compiled draft provided in request for job_id: {job_id}.",
                    "note": "Frontend should send compiled_draft in request body"
                },
                status_code=400
            )

        # Get model and agents
        model_name = job_state.get("model_name")
        specific_model = job_state.get("specific_model")
        if not model_name:
            return JSONResponse(
                content={"error": "Model name missing from job state."},
                status_code=500
            )

        agents = await get_or_create_agents(model_name, specific_model)
        refinement_agent = agents.get("refinement_agent")

        if not refinement_agent:
            return JSONResponse(
                content={"error": "Blog refinement agent could not be initialized."},
                status_code=500
            )

        cost_aggregator = job_state.get("cost_aggregator")
        if not cost_aggregator:
            cost_aggregator = CostAggregator()
            cost_aggregator.start_workflow(project_id=job_id)
            job_state["cost_aggregator"] = cost_aggregator
        if job_state.get("project_id"):
            cost_aggregator.current_workflow["project_id"] = job_state["project_id"]

        # Run refinement
        logger.info(f"Refining blog draft for job_id: {job_id}")
        refinement_result = await refinement_agent.refine_blog_with_graph(
            blog_draft=compiled_draft,
            cost_aggregator=cost_aggregator,
            project_id=job_state.get("project_id", job_id)
        )

        if not refinement_result:
            return JSONResponse(
                content={"error": "Failed to refine blog draft."},
                status_code=500
            )

        # Store results in job state
        job_state["refined_draft"] = refinement_result.refined_draft
        job_state["summary"] = refinement_result.summary
        job_state["title_options"] = [option.model_dump() for option in refinement_result.title_options]
        job_state["refined_at"] = datetime.now().isoformat()
        job_state["cost_summary"] = cost_aggregator.get_workflow_summary()
        job_state["cost_call_history"] = cost_aggregator.call_history
        
        logger.info(f"Successfully refined blog for job_id: {job_id}")
        
        # Save refined blog milestone if project exists
        project_id = job_state.get("project_id")
        if not project_id:
            # Try to find project by name
            projects = project_manager.list_projects(status=ProjectStatus.ACTIVE)
            for project in projects:
                if project.get("name") == project_name:
                    project_id = project.get("id")
                    break
        
        if project_id:
            milestone_data = {
                "refined_content": refinement_result.refined_draft,
                "summary": refinement_result.summary,
                "title_options": job_state["title_options"],
                "job_id": job_id,
                "refined_at": datetime.now().isoformat(),
                "word_count": len(refinement_result.refined_draft.split()),
                "cost_summary": job_state.get("cost_summary")
            }
            milestone_metadata = {
                "cost_summary": job_state.get("cost_summary"),
                "cost_call_history": job_state.get("cost_call_history")
            }

            project_manager.save_milestone(
                project_id,
                MilestoneType.BLOG_REFINED,
                milestone_data,
                metadata=milestone_metadata
            )

            project_manager.update_metadata(project_id, {
                "cost_summary": job_state.get("cost_summary"),
                "cost_call_history": job_state.get("cost_call_history"),
                "latest_job_id": job_id
            })

            logger.info(f"Saved refined blog milestone for project {project_id}")

        return JSONResponse(
            content={
                "job_id": job_id,
                "project_id": project_id,
                "refined_draft": refinement_result.refined_draft,
                "summary": refinement_result.summary,
                "title_options": job_state["title_options"],
                "cost_summary": job_state["cost_summary"]
            }
        )

    except Exception as e:
        logger.exception(f"Blog refinement failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Blog refinement failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )

@app.post("/refine_standalone/{project_name}")
async def refine_standalone(
    project_name: str,
    compiled_draft: str = Form(...),
    model_name: str = Form("gemini"),
    specific_model: Optional[str] = Form(None)
) -> JSONResponse:
    """Refine a blog draft without requiring job state - for resuming after expiry."""
    try:
        logger.info(f"Standalone refinement for project: {project_name}")
        
        # Get or create agents using provided model name
        agents = await get_or_create_agents(model_name, specific_model)
        refinement_agent = agents["refinement_agent"]

        # Run refinement directly without job state
        logger.info(f"Refining blog draft for project: {project_name}")
        refinement_result = await refinement_agent.refine_blog_with_graph(
            blog_draft=compiled_draft
        )

        if not refinement_result:
            return JSONResponse(
                content={"error": "Failed to refine blog draft."},
                status_code=500
            )

        logger.info(f"Successfully refined blog for project: {project_name}")

        return JSONResponse(
            content={
                "project_name": project_name,
                "refined_draft": refinement_result.refined_draft,
                "summary": refinement_result.summary,
                "title_options": [option.model_dump() for option in refinement_result.title_options],
                "status": "completed"
            }
        )

    except Exception as e:
        logger.exception(f"Error in standalone refinement for project {project_name}")
        error_detail = {
            "error": "Standalone blog refinement failed",
            "details": str(e)
        }
        return JSONResponse(
            content=error_detail,
            status_code=500
        )

@app.post("/generate_social_content/{project_name}")
async def generate_social_content(
    project_name: str,
    job_id: str = Form(...)
) -> JSONResponse:
    """Generate social media content from refined draft."""
    try:
        # Retrieve job state and refresh cache TTL
        job_state = refresh_job_cache(job_id)
        if not job_state:
            logger.error(f"Job state not found for job_id: {job_id}")
            return JSONResponse(
                content={
                    "error": f"Job state not found for job_id: {job_id}",
                    "details": "Job state may have expired. Please regenerate the outline and draft.",
                    "suggestion": "Try generating a new outline to restart the workflow."
                },
                status_code=404
            )

        # Check for refined draft
        refined_draft = job_state.get("refined_draft")
        if not refined_draft:
            logger.error(f"Refined draft not found for job_id: {job_id}")
            return JSONResponse(
                content={
                    "error": f"No refined draft found for job_id: {job_id}. Please refine the draft first.",
                    "has_refined_draft": False,
                    "has_final_draft": bool(job_state.get("final_draft"))
                },
                status_code=400
            )

        # Get blog title from title options or outline
        title_options = job_state.get("title_options", [])
        if title_options and isinstance(title_options[0], dict):
            blog_title = title_options[0].get("title", job_state.get("outline", {}).get("title", "Blog Post"))
        else:
            blog_title = job_state.get("outline", {}).get("title", "Blog Post")

        # Get model and agents
        model_name = job_state.get("model_name")
        specific_model = job_state.get("specific_model")
        agents = await get_or_create_agents(model_name, specific_model)
        social_agent = agents.get("social_agent")

        if not social_agent:
            return JSONResponse(
                content={"error": "Social media agent could not be initialized."},
                status_code=500
            )

        # Generate comprehensive social content (including thread)
        logger.info(f"Generating comprehensive social content for job_id: {job_id}")
        social_content = await social_agent.generate_comprehensive_content(
            blog_content=refined_draft,
            blog_title=blog_title,
            persona=job_state.get("persona", "neuraforge")  # Use persona from job state
        )

        if not social_content:
            return JSONResponse(
                content={"error": "Failed to generate social media content."},
                status_code=500
            )

        # Convert to API response format
        social_content_response = social_content.to_api_response()

        # Store in job state
        job_state["social_content"] = social_content_response
        job_state["social_generated_at"] = datetime.now().isoformat()
        
        # Save social media milestone if project exists
        project_id = job_state.get("project_id")
        if not project_id:
            # Try to find project by name
            projects = project_manager.list_projects(status=ProjectStatus.ACTIVE)
            for project in projects:
                if project.get("name") == project_name:
                    project_id = project.get("id")
                    break
        
        if project_id:
            milestone_data = {
                "social_content": social_content_response,
                "job_id": job_id,
                "generated_at": datetime.now().isoformat(),
                "blog_title": blog_title
            }
            
            project_manager.save_milestone(
                project_id,
                MilestoneType.SOCIAL_GENERATED,
                milestone_data
            )
            
            logger.info(f"Saved social media milestone for project {project_id}")

        return JSONResponse(
            content={
                "job_id": job_id,
                "project_id": project_id,
                "social_content": social_content_response
            }
        )

    except Exception as e:
        logger.exception(f"Social content generation failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Social content generation failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )


@app.post("/generate_social_content_standalone/{project_name}")
async def generate_social_content_standalone(
    project_name: str,
    refined_blog_content: str = Form(...),
    model_name: str = Form(...),
    specific_model: Optional[str] = Form(None),
    persona: Optional[str] = Form("neuraforge")  # Add persona parameter
) -> JSONResponse:
    """Generate social media content from refined blog content without requiring job state."""
    try:
        logger.info(f"Generating standalone social content for project: {project_name}")
        
        # Get or create agents using the provided model
        agents = await get_or_create_agents(model_name, specific_model)
        social_agent = agents.get("social_agent")

        if not social_agent:
            return JSONResponse(
                content={"error": "Social media agent could not be initialized."},
                status_code=500
            )

        # Extract blog title from the refined content (try to get first heading)
        blog_title = project_name  # Fallback to project name
        lines = refined_blog_content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                blog_title = line[2:].strip()
                break
            elif line.startswith('## '):
                blog_title = line[3:].strip()
                break

        # Generate comprehensive social content
        logger.info(f"Generating comprehensive social content for standalone project: {project_name}")
        social_content = await social_agent.generate_comprehensive_content(
            blog_content=refined_blog_content,
            blog_title=blog_title,
            persona=persona  # Use persona parameter
        )

        if not social_content:
            return JSONResponse(
                content={"error": "Failed to generate social media content."},
                status_code=500
            )

        # Convert to API response format
        social_content_response = social_content.to_api_response()

        return JSONResponse(
            content={
                "project_name": project_name,
                "social_content": social_content_response
            }
        )

    except Exception as e:
        logger.exception(f"Standalone social content generation failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Standalone social content generation failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
            status_code=500
        )


@app.post("/generate_twitter_thread/{project_name}")
async def generate_twitter_thread(
    project_name: str,
    job_id: str = Form(...)
) -> JSONResponse:
    """Generate Twitter/X thread from refined draft."""
    try:
        # Retrieve job state and refresh cache TTL
        job_state = refresh_job_cache(job_id)
        
        if not job_state:
            return JSONResponse(
                content={
                    "error": "Job not found or expired",
                    "suggestion": "Please regenerate the outline to restart the workflow."
                },
                status_code=404
            )
        
        refined_draft = job_state.get("refined_draft")
        if not refined_draft:
            return JSONResponse(
                content={"error": "Refined draft not found. Please complete blog refinement first."},
                status_code=400
            )
        
        blog_title = job_state.get("outline", {}).get("title", "Blog Post")
        
        # Get model and agents
        model_name = job_state.get("model_name")
        agents = await get_or_create_agents(model_name)
        social_agent = agents.get("social_agent")
        
        if not social_agent:
            return JSONResponse(
                content={"error": "Social media agent could not be initialized."},
                status_code=500
            )
        
        # Generate Twitter thread
        logger.info(f"Generating Twitter thread for job_id: {job_id}")
        twitter_thread = await social_agent.generate_thread(
            blog_content=refined_draft,
            blog_title=blog_title
        )
        
        if not twitter_thread:
            return JSONResponse(
                content={"error": "Failed to generate Twitter thread."},
                status_code=500
            )
        
        # Convert thread to serializable format
        thread_data = {
            "tweets": [tweet.model_dump() for tweet in twitter_thread.tweets],
            "total_tweets": twitter_thread.total_tweets,
            "hook_tweet": twitter_thread.hook_tweet,
            "conclusion_tweet": twitter_thread.conclusion_tweet,
            "thread_topic": twitter_thread.thread_topic,
            "learning_journey": twitter_thread.learning_journey
        }
        
        # Store in job state
        job_state["twitter_thread"] = thread_data
        job_state["thread_generated_at"] = datetime.now().isoformat()
        
        return JSONResponse(
            content={
                "job_id": job_id,
                "twitter_thread": thread_data
            }
        )
        
    except Exception as e:
        logger.exception(f"Twitter thread generation failed: {str(e)}")
        return JSONResponse(
            content={
                "error": f"Twitter thread generation failed: {str(e)}",
                "type": str(type(e).__name__),
                "details": str(e)
            },
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

            # --- Clear Vector Store Caches ---
            try:
                # Get vector store instance (assuming it might be cached or create new)
                # This assumes get_or_create_agents might have cached it, or we create one
                # A better approach might be a singleton VectorStoreService instance
                vector_store = VectorStoreService()
                vector_store.clear_outline_cache(project_name)
                vector_store.clear_section_cache(project_name) # Clear section cache too
                # Also clear content chunks associated with the project
                # This requires content_parser to have a method like clear_project_content
                # Assuming content_parser is accessible or re-instantiated if needed
                # This part depends on how agents/services are managed.
                # For simplicity, let's assume we can get it from the cache if populated
                # This might need refinement based on actual agent/service lifecycle mgmt.
                # Check if agent_cache has been populated for any model
                parser_cleared = False
                for agent_set in agent_cache.values():
                    if "content_parser" in agent_set:
                         # Need a method on ContentParsingAgent to clear by project
                         # Assuming such a method exists or can be added:
                         # await agent_set["content_parser"].clear_project_data(project_name)
                         logger.warning(f"Vector store content chunk clearing for project {project_name} not fully implemented in delete endpoint.")
                         parser_cleared = True
                         break # Assume one parser per model type is enough
                if not parser_cleared:
                    logger.warning(f"Could not find ContentParsingAgent in cache to clear chunks for project {project_name}.")

            except Exception as vs_clear_err:
                 logger.error(f"Error clearing vector store caches for project {project_name}: {vs_clear_err}")
            # --- End Clear Vector Store Caches ---


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


# ==================== PROJECT MANAGEMENT ENDPOINTS ====================

@app.get("/projects")
async def list_projects(status: Optional[str] = None) -> JSONResponse:
    """
    List all projects, optionally filtered by status.
    
    Args:
        status: Optional status filter (active, archived, deleted)
    
    Returns:
        List of project summaries
    """
    try:
        # Convert status string to enum if provided
        status_filter = None
        if status:
            try:
                status_filter = ProjectStatus(status)
            except ValueError:
                return JSONResponse(
                    content={"error": f"Invalid status: {status}. Must be one of: active, archived, deleted"},
                    status_code=400
                )
        
        projects = project_manager.list_projects(status=status_filter)
        
        return JSONResponse(
            content={
                "status": "success",
                "count": len(projects),
                "projects": projects
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        return JSONResponse(
            content={"error": f"Failed to list projects: {str(e)}"},
            status_code=500
        )


@app.get("/project/{project_id}")
async def get_project_details(project_id: str) -> JSONResponse:
    """
    Get detailed information about a specific project.
    
    Args:
        project_id: Project UUID
    
    Returns:
        Project details including milestones
    """
    try:
        project_data = project_manager.get_project(project_id)
        
        if not project_data:
            return JSONResponse(
                content={"error": f"Project {project_id} not found"},
                status_code=404
            )
        
        # Get all milestones
        milestones = {}
        for milestone_type in MilestoneType:
            milestone_data = project_manager.load_milestone(project_id, milestone_type)
            if milestone_data:
                # Don't include full data in listing, just metadata
                milestones[milestone_type.value] = {
                    "created_at": milestone_data.get("created_at"),
                    "metadata": milestone_data.get("metadata", {})
                }
        
        return JSONResponse(
            content={
                "status": "success",
                "project": project_data,
                "milestones": milestones
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to get project details: {str(e)}"},
            status_code=500
        )


@app.post("/project/{project_id}/resume")
async def resume_project(project_id: str) -> JSONResponse:
    """
    Resume a project from its latest milestone.
    
    Args:
        project_id: Project UUID
    
    Returns:
        Resume data including next step and cached state
    """
    try:
        resume_data = project_manager.resume_project(project_id)
        
        if not resume_data:
            return JSONResponse(
                content={"error": f"Project {project_id} not found"},
                status_code=404
            )
        
        project_data = resume_data["project"]
        latest_milestone = resume_data["latest_milestone"]
        next_step = resume_data["next_step"]
        
        # Generate a new job_id for this resume session
        job_id = str(uuid.uuid4())
        
        # Reconstruct state cache entry based on milestones
        job_state = {
            "job_id": job_id,
            "project_id": project_id,
            "project_name": project_data.get("name"),
            "created_at": datetime.now().isoformat(),
            "model_name": project_data.get("metadata", {}).get("model_name"),
            "persona": project_data.get("metadata", {}).get("persona")
        }
        
        # Load outline if available
        outline_milestone = project_manager.load_milestone(project_id, MilestoneType.OUTLINE_GENERATED)
        if outline_milestone:
            outline_data = outline_milestone.get("data", {})
            job_state["outline"] = outline_data  # The outline data is directly in the data field
            job_state["outline_hash"] = outline_milestone.get("metadata", {}).get("outline_hash")
        
        # Load draft if available
        draft_milestone = project_manager.load_milestone(project_id, MilestoneType.DRAFT_COMPLETED)
        if draft_milestone:
            job_state["final_draft"] = draft_milestone.get("data", {}).get("compiled_blog")
        
        # Load refined blog if available
        refined_milestone = project_manager.load_milestone(project_id, MilestoneType.BLOG_REFINED)
        if refined_milestone:
            job_state["refined_draft"] = refined_milestone.get("data", {}).get("refined_content")
            job_state["summary"] = refined_milestone.get("data", {}).get("summary")
            job_state["title_options"] = refined_milestone.get("data", {}).get("title_options")
        
        # Store in state cache for session
        state_cache[job_id] = job_state
        logger.info(f"Resumed project {project_id} with new job_id {job_id}")
        
        return JSONResponse(
            content={
                "status": "success",
                "job_id": job_id,
                "project_id": project_id,
                "project_name": project_data.get("name"),
                "current_milestone": project_data.get("current_milestone"),
                "next_step": next_step,
                "has_outline": bool(job_state.get("outline")),
                "has_draft": bool(job_state.get("final_draft")),
                "has_refined": bool(job_state.get("refined_draft")),
                "cost_summary": job_state.get("cost_summary"),
                "cost_call_history": job_state.get("cost_call_history", [])
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to resume project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to resume project: {str(e)}"},
            status_code=500
        )


@app.delete("/project/{project_id}/permanent")
async def delete_project_permanent(project_id: str) -> JSONResponse:
    """
    Permanently delete a project and all its data.
    
    Args:
        project_id: Project UUID
    
    Returns:
        Success status
    """
    try:
        success = project_manager.delete_project(project_id, permanent=True)
        
        if not success:
            return JSONResponse(
                content={"error": f"Failed to delete project {project_id}"},
                status_code=500
            )
        
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Project {project_id} permanently deleted"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to delete project: {str(e)}"},
            status_code=500
        )


@app.post("/project/{project_id}/archive")
async def archive_project(project_id: str) -> JSONResponse:
    """
    Archive a project (soft delete).
    
    Args:
        project_id: Project UUID
    
    Returns:
        Success status
    """
    try:
        success = project_manager.archive_project(project_id)
        
        if not success:
            return JSONResponse(
                content={"error": f"Failed to archive project {project_id}"},
                status_code=404
            )
        
        return JSONResponse(
            content={
                "status": "success",
                "message": f"Project {project_id} archived"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to archive project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to archive project: {str(e)}"},
            status_code=500
        )


@app.get("/project/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = "json"
) -> Any:
    """
    Export project data in specified format.
    
    Args:
        project_id: Project UUID
        format: Export format (json, markdown, zip)
    
    Returns:
        Exported data in requested format
    """
    try:
        from fastapi.responses import Response, FileResponse
        import tempfile
        
        export_data = project_manager.export_project(project_id, format=format)
        
        if export_data is None:
            return JSONResponse(
                content={"error": f"Project {project_id} not found or export failed"},
                status_code=404
            )
        
        if format == "json":
            return JSONResponse(content=export_data)
        
        elif format == "markdown":
            return Response(
                content=export_data,
                media_type="text/markdown",
                headers={
                    "Content-Disposition": f"attachment; filename=project_{project_id}.md"
                }
            )
        
        elif format == "zip":
            # Write zip data to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                tmp.write(export_data)
                tmp_path = tmp.name
            
            return FileResponse(
                path=tmp_path,
                media_type="application/zip",
                filename=f"project_{project_id}.zip"
            )
        
        else:
            return JSONResponse(
                content={"error": f"Unsupported export format: {format}"},
                status_code=400
            )
            
    except Exception as e:
        logger.error(f"Failed to export project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to export project: {str(e)}"},
            status_code=500
        )

# === New API Endpoints for Enhanced UI Configuration ===

@app.get("/personas")
async def get_personas():
    """Get available personas for output styling."""
    try:
        persona_service = PersonaService()
        # Use the full personas dict instead of list_personas which only returns descriptions
        all_personas = persona_service.personas

        return JSONResponse(content={
            name: {
                "name": persona_data.get("name", name.replace('_', ' ').title()),
                "description": persona_data.get("description", "")
            }
            for name, persona_data in all_personas.items()
        })
    except Exception as e:
        logger.error(f"Failed to get personas: {e}")
        return JSONResponse(
            content={"error": f"Failed to get personas: {str(e)}"},
            status_code=500
        )

@app.get("/models")
async def get_available_models():
    """Get available models organized by provider with specific model options."""
    try:
        # Model configurations mapping
        model_configs = {
            "openai": {
                "name": "OpenAI",
                "models": [
                    {"id": "gpt-5", "name": "GPT-5", "description": "Latest flagship GPT model"},
                    {"id": "gpt-4.1", "name": "GPT-4.1", "description": "High context reasoning with faster latency"},
                    {"id": "gpt-4o", "name": "GPT-4o", "description": "Multimodal 4o general availability"}
                ]
            },
            "claude": {
                "name": "Anthropic Claude",
                "models": [
                    {"id": "claude-opus-4.1", "name": "Claude Opus 4.1", "description": "Most capable Claude for complex tasks"},
                    {"id": "claude-sonnet-4", "name": "Claude Sonnet 4", "description": "Balanced capability and speed"}
                ]
            },
            "gemini": {
                "name": "Google Gemini",
                "models": [
                    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "description": "Advanced reasoning and multimodal"},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "description": "Fast, cost-efficient content generation"}
                ]
            },
            "deepseek": {
                "name": "DeepSeek",
                "models": [
                    {"id": "deepseek-reasoner", "name": "DeepSeek R1", "description": "Reasoning-optimized (R1)"},
                    {"id": "deepseek-chat", "name": "DeepSeek Chat", "description": "General assistant tuned for dialogue"}
                ]
            },
            "openrouter": {
                "name": "OpenRouter",
                "models": [
                    {"id": "x-ai/grok-4", "name": "Grok-4 (via OpenRouter)", "description": "xAI Grok flagship through OpenRouter"},
                    {"id": "openai/gpt-oss-120b", "name": "GPT-OSS 120B (via OpenRouter)", "description": "OpenAI OSS 120B via OpenRouter"},
                    {"id": "qwen/qwen-2.5-72b-instruct", "name": "Qwen 2.5 72B Instruct", "description": "Alibaba Qwen through OpenRouter"},
                    {"id": "qwen/qwen3-next-80b-a3b-thinking", "name": "Qwen3 Next 80B A3B Thinking", "description": "Extended reasoning Qwen via OpenRouter"}
                ]
            }
        }

        return JSONResponse(content={"providers": model_configs})

    except Exception as e:
        logger.error(f"Failed to get model configurations: {e}")
        return JSONResponse(
            content={"error": f"Failed to get model configurations: {str(e)}"},
            status_code=500
        )
