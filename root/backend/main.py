"""
FastAPI application for blog content processing, outline generation, and blog draft generation.
"""
import os
import json
import sys
import logging
import uuid
from pathlib import Path

# Configure Python path for absolute imports from root
backend_dir = Path(__file__).parent
root_dir = backend_dir.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
    print(f"Added to Python path: {root_dir}")

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import ValidationError

from backend.agents.outline_generator_agent import OutlineGeneratorAgent
from backend.agents.content_parsing_agent import ContentParsingAgent
from backend.agents.blog_draft_generator_agent import BlogDraftGeneratorAgent
from backend.agents.social_media_agent import SocialMediaAgent
from backend.agents.blog_refinement_agent import BlogRefinementAgent # Updated import path
from backend.agents.outline_generator.state import FinalOutline
from backend.agents.blog_refinement.state import RefinementResult, TitleOption # Combined import
from backend.utils.serialization import serialize_object
from backend.models.model_factory import ModelFactory
from backend.models.generation_config import TitleGenerationConfig, SocialMediaConfig # Added
from backend.services.vector_store_service import VectorStoreService # Added
from backend.services.persona_service import PersonaService # Added
from backend.services.supabase_project_manager import SupabaseProjectManager, MilestoneType # Supabase-based project manager
from backend.services.cost_aggregator import CostAggregator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BlogAPI")

# API Key for authentication (loaded from environment, set via GCP Secret Manager)
QUIBO_API_KEY = os.getenv('QUIBO_API_KEY', '')


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key on all requests except health check."""

    async def dispatch(self, request: Request, call_next):
        # Skip auth for health check (needed for Cloud Run health probes)
        if request.url.path == "/health":
            return await call_next(request)

        # Skip auth if no API key is configured (local development)
        if not QUIBO_API_KEY:
            return await call_next(request)

        # Validate API key
        api_key = request.headers.get("X-API-Key")
        if not api_key or api_key != QUIBO_API_KEY:
            logger.warning(f"Invalid or missing API key for path: {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"}
            )

        return await call_next(request)


app = FastAPI(title="Agentic Blogging Assistant API")

# Add API key authentication middleware
app.add_middleware(APIKeyAuthMiddleware)

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

# Initialize SupabaseProjectManager for Supabase-based project tracking
sql_project_manager = SupabaseProjectManager()  # Keep variable name for compatibility

async def load_workflow_state(project_id: str) -> Optional[Dict[str, Any]]:
    """
    Load complete workflow state from SQL project manager.

    This replaces the TTL cache lookup and reconstructs the workflow
    state from SQL milestones and sections.

    Args:
        project_id: Project UUID

    Returns:
        Complete workflow state dictionary or None if project not found
    """
    project_data = await sql_project_manager.resume_project(project_id)
    if not project_data:
        return None

    # Reconstruct workflow state from milestones
    state = {
        "project_id": project_id,
        "project_name": project_data["project"]["name"],
        "model_name": project_data["project"]["metadata"].get("model_name"),
        "persona": project_data["project"]["metadata"].get("persona"),
        "specific_model": project_data["project"]["metadata"].get("specific_model"),
    }

    # Load milestones
    milestones = project_data["milestones"]

    if "outline_generated" in milestones:
        m = milestones["outline_generated"]
        state["outline"] = m["data"]["outline"]
        state["outline_hash"] = m["data"].get("outline_hash")

        # Fallback: Load model_name, specific_model, and persona from milestone data if not in project metadata
        if not state["model_name"]:
            state["model_name"] = m["data"].get("model_name")
        if not state["specific_model"]:
            state["specific_model"] = m["data"].get("specific_model")
        if not state["persona"]:
            state["persona"] = m["data"].get("persona")

    if "draft_completed" in milestones:
        m = milestones["draft_completed"]
        state["final_draft"] = m["data"].get("compiled_blog")
        state["compiled_at"] = m["created_at"]

    if "blog_refined" in milestones:
        m = milestones["blog_refined"]
        state["refined_draft"] = m["data"].get("refined_content")
        state["summary"] = m["data"].get("summary")
        state["title_options"] = m["data"].get("title_options")

    if "social_generated" in milestones:
        # Social content is nested under "social_content" key within the milestone data
        state["social_content"] = milestones["social_generated"]["data"].get("social_content")

    # Load sections from SQL Sections table with full metadata
    state["generated_sections"] = {
        s["section_index"]: {
            "title": s["title"],
            "content": s["content"],
            "status": s["status"],
            "cost_delta": s.get("cost_delta", 0.0),
            "input_tokens": s.get("input_tokens", 0),
            "output_tokens": s.get("output_tokens", 0),
            "updated_at": s.get("updated_at"),
            "outline_hash": s.get("outline_hash")
        }
        for s in project_data["sections"]
    }

    # Load cost tracking
    state["cost_summary"] = project_data["cost_summary"]

    return state


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

        # Create project metadata with default model_name if not provided
        metadata = {
            "model_name": model_name or "gpt-4",  # Default to gpt-4 if not specified
            "persona": persona,
            "upload_directory": str(project_dir),
            "uploaded_files": [os.path.basename(f) for f in uploaded_files]
        }

        # Create project in SQL database FIRST
        sql_project_id = None
        try:
            sql_project_id = await sql_project_manager.create_project(
                project_name=safe_project_name,
                metadata=metadata
            )

            # Save FILES_UPLOADED milestone
            milestone_data = {
                "files": uploaded_files,
                "file_count": len(uploaded_files),
                "upload_time": datetime.now().isoformat()
            }
            await sql_project_manager.save_milestone(
                project_id=sql_project_id,
                milestone_type=MilestoneType.FILES_UPLOADED,
                data=milestone_data
            )

            logger.info(f"Created SQL project {sql_project_id} with {len(uploaded_files)} uploaded files")
        except Exception as e:
            logger.warning(f"Failed to create SQL project (non-blocking): {e}")
            # If SQL project creation fails, we still need a project ID
            if sql_project_id is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create project in database"
                )

        # Legacy duplicate project creation removed - SQL manager is now single source of truth
        logger.info(f"Created SQL project {sql_project_id} with {len(uploaded_files)} uploaded files")

        return JSONResponse(
            content={
                "message": "Files uploaded successfully",
                "project_name": safe_project_name,
                "project_id": sql_project_id,
                "job_id": sql_project_id,  # Alias for backward compatibility
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

        # Pass vector_store, persona_service, and sql_project_manager to BlogDraftGeneratorAgent
        draft_agent = BlogDraftGeneratorAgent(model, content_parser, vector_store, persona_service, sql_project_manager)
        await draft_agent.initialize()

        refinement_agent = BlogRefinementAgent(model, persona_service)
        await refinement_agent.initialize()

        social_agent = SocialMediaAgent(model, persona_service, sql_project_manager)
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
        start_time = datetime.now()
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

        # Persist file hashes to Supabase for resume functionality
        project = await sql_project_manager.get_project_by_name(project_name)
        if project:
            project_id = project["id"]
            # Update the files_uploaded milestone with file hashes
            existing_milestone = await sql_project_manager.load_milestone(
                project_id, MilestoneType.FILES_UPLOADED
            )
            if existing_milestone:
                # Update existing milestone data with file hashes
                milestone_data = existing_milestone.get("data", {})
                milestone_data["file_hashes"] = result
                milestone_data["processed_at"] = datetime.now().isoformat()
                
                # Calculate processing duration
                duration = (datetime.now() - start_time).total_seconds()
                
                await sql_project_manager.save_milestone(
                    project_id=project_id,
                    milestone_type=MilestoneType.FILES_UPLOADED,
                    data=milestone_data,
                    metadata={"duration_seconds": duration}
                )
                logger.info(f"Persisted {len(result)} file hashes for project {project_id}")

        return JSONResponse(
            content={
                "message": "Files processed successfully",
                "project": project_name,
                "file_hashes": result,
                "duration_seconds": duration
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
        # project_id will be determined from the project lookup
        cost_aggregator = CostAggregator()

        # Get project from SQL manager (returns dict)
        project = await sql_project_manager.get_project_by_name(project_name)
        project_id = project["id"] if project else None

        if project_id:
            cost_aggregator.start_workflow(project_id=project_id)

        # Generate outline - returns a dict (outline or error), content, content, cached_status
        start_time = datetime.now()
        outline_result, notebook_content, markdown_content, was_cached = await outline_agent.generate_outline(
            project_name=project_name,
            notebook_hash=notebook_hash,
            markdown_hash=markdown_hash,
            user_guidelines=user_guidelines, # Pass guidelines to agent
            length_preference=length_preference, # Pass length preference
            custom_length=custom_length, # Pass custom length
            writing_style=writing_style, # Pass writing style
            persona=persona_style, # Pass persona selection
            cost_aggregator=cost_aggregator,
            project_id=project_id if project_id else None
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

        # Save outline milestone to SQL if project exists
        if project_id:
            milestone_data = {
                "outline": outline_data,
                "outline_hash": outline_hash,
                "model_name": model_name,
                "specific_model": specific_model,
                "persona": persona_style,
                "user_guidelines": user_guidelines,
                "length_preference": length_preference,
                "custom_length": custom_length,
                "was_cached": was_cached
            }
            milestone_metadata = {
                "cost_summary": cost_summary,
                "cost_call_history": cost_call_history
            }

            # Update SQL project metadata (primary storage)
            await sql_project_manager.update_metadata(project_id, {
                "model_name": model_name,
                "specific_model": specific_model,
                "persona": persona_style
            })

            # Save milestone to SQL database (primary storage - legacy duplicate save removed)
            # Calculate generation duration
            duration = (datetime.now() - start_time).total_seconds()

            await sql_project_manager.save_milestone(
                project_id=project_id,
                milestone_type=MilestoneType.OUTLINE_GENERATED,
                data=milestone_data,
                metadata={
                    "model": model_name,
                    "duration_seconds": duration
                }
            )

            logger.info(f"Saved outline milestone for project {project_id}")

        # Return project_id instead of job_id
        return JSONResponse(
            content=serialize_object({
                "project_id": project_id,
                "outline": outline_data,
                "cost_summary": cost_summary,
                "duration_seconds": duration
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
        
        
@app.get("/project_status/{project_id}")
async def get_project_status(project_id: str) -> JSONResponse:
    """Get the current status of a project."""
    try:
        state = await load_workflow_state(project_id)
        if not state:
            return JSONResponse(
                content={
                    "error": "Project not found",
                    "project_id": project_id,
                    "suggestion": "Project may not exist. Please check the project ID."
                },
                status_code=404
            )

        outline = state.get('outline', {})
        total_sections = len(outline.get('sections', []))
        generated_sections = state.get('generated_sections', {})
        completed_sections = len(generated_sections)

        return JSONResponse(content={
            "project_id": project_id,
            "project_name": state.get('project_name'),
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "missing_sections": [i for i in range(total_sections) if i not in generated_sections],
            "has_final_draft": bool(state.get('final_draft')),
            "has_refined_draft": bool(state.get('refined_draft')),
            "outline_title": outline.get('title', 'Unknown'),
            # Include actual content for frontend resume
            "has_outline": bool(outline),
            "outline": outline,
            "final_draft": state.get('final_draft'),
            "refined_draft": state.get('refined_draft'),
            "summary": state.get('summary'),
            "title_options": state.get('title_options'),
            "social_content": state.get('social_content'),
            "generated_sections": state.get('generated_sections', {}),
            "cost_summary": state.get('cost_summary')
        })
    except Exception as e:
        logger.exception(f"Error getting project status: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to get project status: {str(e)}"},
            status_code=500
        )


@app.get("/resume/{project_id}")
async def resume_project_endpoint(project_id: str) -> JSONResponse:
    """
    Get complete project state for resumption.
    Returns all data needed to rehydrate the frontend session.
    """
    try:
        state = await load_workflow_state(project_id)
        if not state:
            return JSONResponse(
                content={"error": "Project not found"},
                status_code=404
            )
        
        # Ensure all necessary fields for frontend hydration are present
        response_data = {
            "project_id": project_id,
            "project_name": state.get('project_name'),
            "model_name": state.get('model_name'),
            "persona": state.get('persona'),
            "specific_model": state.get('specific_model'),
            "outline": state.get('outline'),
            "outline_hash": state.get('outline_hash'),
            "final_draft": state.get('final_draft'),
            "refined_draft": state.get('refined_draft'),
            "summary": state.get('summary'),
            "title_options": state.get('title_options'),
            "social_content": state.get('social_content'),
            "generated_sections": state.get('generated_sections', {}),
            "cost_summary": state.get('cost_summary'),
            # Add any other fields needed by SessionManager
        }
        return JSONResponse(content=response_data)
    except Exception as e:
        logger.exception(f"Error resuming project: {str(e)}")
        return JSONResponse(
            content={"error": f"Failed to resume project: {str(e)}"},
            status_code=500
        )



@app.post("/generate_section/{project_name}")
async def generate_section(
    project_name: str,
    section_index: int = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """Generate a single section and store it in SQL database immediately."""
    try:
        # Find project_id from project_name
        project_data = await sql_project_manager.get_project_by_name(project_name)
        if not project_data:
            logger.error(f"Project not found: {project_name}")
            return JSONResponse(
                content={"error": f"Project not found: {project_name}. Please generate outline first."},
                status_code=404
            )

        project_id = project_data["id"]

        # Load workflow state from SQL
        state = await load_workflow_state(project_id)
        if not state:
            logger.error(f"Workflow state not found for project: {project_name}")
            return JSONResponse(
                content={"error": f"Workflow state not found for project: {project_name}"},
                status_code=404
            )

        # Ensure cost tracking is available and rehydrate if needed
        cost_aggregator = CostAggregator()
        cost_aggregator.start_workflow(project_id=project_id)

        # Load existing cost history
        existing_history = state.get("cost_summary", {}).get("call_history", [])
        if existing_history:
            for call in existing_history:
                try:
                    cost_aggregator.record_cost(call)
                except Exception as err:
                    logger.warning(f"Failed to replay cost record during section resume: {err}")

        previous_summary = state.get("cost_summary", {})
        previous_total_cost = previous_summary.get("total_cost", 0.0)
        previous_total_tokens = previous_summary.get("total_tokens", 0)

        # Extract data from state
        outline_data = state["outline"]
        notebook_data = state.get("notebook_content")
        markdown_data = state.get("markdown_content")
        model_name = state["model_name"]
        specific_model = state.get("specific_model")

        # Validate section index
        if section_index < 0 or section_index >= len(outline_data.get("sections", [])):
            return JSONResponse(
                content={"error": f"Invalid section index: {section_index}"},
                status_code=400
            )

        # Get current section
        section = outline_data["sections"][section_index]
        section_title = section.get("title", f"Section {section_index + 1}")

        # Get generated sections from state
        generated_sections = state.get('generated_sections', {})

        # Check if section already exists in SQL
        if section_index in generated_sections:
            logger.info(f"Section {section_index} already exists in SQL, returning cached version")
            cached_section = generated_sections[section_index]
            return JSONResponse(
                content={
                    "project_id": project_id,
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
            project_id=project_id,
            persona=state.get("persona", "neuraforge")
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

        # Section saving to SQL is already handled by the agent
        # Update cost tracking in SQL
        updated_summary = cost_aggregator.get_workflow_summary()
        section_cost_delta = updated_summary.get("total_cost", 0.0) - previous_total_cost
        section_tokens_delta = updated_summary.get("total_tokens", 0) - previous_total_tokens

        await sql_project_manager.update_metadata(project_id, {
            "cost_summary": updated_summary,
            "cost_call_history": list(cost_aggregator.call_history)
        })

        logger.info(f"Stored section {section_index} in SQL for project: {project_name}")

        return JSONResponse(
            content={
                "project_id": project_id,
                "section_title": section_title,
                "section_content": section_content,
                "image_placeholders": image_placeholders,
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

@app.post("/regenerate_section_with_feedback/{project_name}")
async def regenerate_section(
    project_name: str,
    job_id: str = Form(...),
    section_index: int = Form(...),
    feedback: str = Form(...),
    max_iterations: int = Form(3),
    quality_threshold: float = Form(0.8)
) -> JSONResponse:
    """
    Regenerate a section with user feedback.

    DEPRECATED: This endpoint needs migration to use project_id instead of job_id.
    Use the v2 API endpoints for section management instead.
    """
    logger.warning(f"regenerate_section_with_feedback endpoint is deprecated - needs migration to use project_id instead of job_id")
    return JSONResponse(
        content={
            "error": "This endpoint is deprecated and needs migration to use project_id",
            "suggestion": "Use /api/v2/projects/{project_id}/sections endpoint instead"
        },
        status_code=501  # Not Implemented
    )


@app.post("/compile_draft/{project_name}")
async def compile_draft(
    project_name: str,
    job_id: str = Form(...)
) -> JSONResponse:
    """Compile final blog draft from sections stored in SQL project manager."""
    logger.info(f"Starting draft compilation for job_id (project_id): {job_id}")
    try:
        # Load project data from SQL project manager
        job_state = await load_workflow_state(job_id)
        if not job_state:
            logger.error(f"Project not found: {job_id}")
            return JSONResponse(
                content={
                    "error": f"Project not found for job_id: {job_id}",
                    "details": "Project may not exist. Please regenerate the outline and draft.",
                    "suggestion": "Try generating a new outline to restart the workflow."
                },
                status_code=404
            )

        # Extract data from state
        outline_data = job_state.get("outline")
        if not outline_data:
            logger.error(f"No outline found for project: {job_id}")
            return JSONResponse(
                content={"error": "Outline not found. Please generate an outline first."},
                status_code=400
            )

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

        # Initialize cost tracking for compilation
        cost_aggregator = CostAggregator()
        cost_aggregator.start_workflow(project_id=job_id)

        # Load existing cost history if available
        existing_cost_history = job_state.get("cost_call_history") or []
        for call in existing_cost_history:
            try:
                cost_aggregator.record_cost(call)
            except Exception as err:
                logger.warning(f"Failed to replay cost record during compile: {err}")

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

        logger.info(f"Successfully compiled draft for job_id: {job_id} (length: {len(final_draft)} chars)")

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
        
        # Save draft milestone to SQL project manager
        cost_summary = cost_aggregator.get_workflow_summary()
        cost_call_history = list(cost_aggregator.call_history)

        milestone_data = {
            "compiled_blog": final_draft,
            "job_id": job_id,
            "compiled_at": datetime.now().isoformat(),
            "sections_count": num_outline_sections,
            "word_count": len(final_draft.split()),
            "outline_hash": job_state.get("outline_hash"),
            "sections": generated_sections
        }
        milestone_metadata = {
            "cost_summary": cost_summary,
            "cost_call_history": cost_call_history
        }

        try:
            await sql_project_manager.save_milestone(
                project_id=job_id,
                milestone_type=MilestoneType.DRAFT_COMPLETED,
                data=milestone_data,
                metadata=milestone_metadata
            )
            logger.info(f"Saved draft milestone for project {job_id}")
        except Exception as save_err:
            logger.warning(f"Failed to save draft milestone: {save_err}")

        return JSONResponse(content={
            "job_id": job_id,
            "project_id": job_id,
            "draft": final_draft,
            "draft_saved": draft_saved_to_file,
            "sections_compiled": num_outline_sections,
            "cost_summary": cost_summary
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
    compiled_draft: str = Form(...),
    title_config: Optional[str] = Form(None),  # JSON string for title configuration
    social_config: Optional[str] = Form(None)  # JSON string for social media configuration
) -> JSONResponse:
    """Refine a compiled blog draft using the BlogRefinementAgent with optional configuration."""
    try:
        # DEBUG: Log incoming request details
        logger.info(f"=== REFINE BLOG REQUEST ===")
        logger.info(f"Project name: {project_name}")
        logger.info(f"Job ID (project_id): {job_id}")
        logger.info(f"Compiled draft length: {len(compiled_draft) if compiled_draft else 0}")

        # Check for compiled draft from request
        if not compiled_draft:
            logger.error(f"Compiled draft not provided in request for project: {job_id}")
            return JSONResponse(
                content={
                    "error": f"No compiled draft provided in request.",
                    "note": "Frontend should send compiled_draft in request body"
                },
                status_code=400
            )

        # Load project data from SQL project manager to get model info
        project_data = await sql_project_manager.resume_project(job_id)
        if not project_data:
            logger.error(f"Project not found: {job_id}")
            return JSONResponse(
                content={
                    "error": f"Project not found for job_id: {job_id}",
                    "details": "Please ensure the project exists."
                },
                status_code=404
            )

        # Extract model info from project metadata
        model_name = project_data["project"]["metadata"].get("model_name", "gemini")
        specific_model = project_data["project"]["metadata"].get("specific_model")

        logger.info(f"Using model: {model_name}, specific_model: {specific_model}")

        # Get or create agents
        agents = await get_or_create_agents(model_name, specific_model)
        refinement_agent = agents.get("refinement_agent")

        if not refinement_agent:
            return JSONResponse(
                content={"error": "Blog refinement agent could not be initialized."},
                status_code=500
            )

        # Initialize cost aggregator for this refinement
        cost_aggregator = CostAggregator()
        cost_aggregator.start_workflow(project_id=job_id)

        # Parse configuration if provided
        title_generation_config = None
        social_media_config = None

        if title_config:
            try:
                title_config_dict = json.loads(title_config)
                title_generation_config = TitleGenerationConfig(**title_config_dict)
                logger.info(f"Using custom title config: {title_generation_config.num_titles} titles")
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Failed to parse title config: {e}")

        if social_config:
            try:
                social_config_dict = json.loads(social_config)
                social_media_config = SocialMediaConfig(**social_config_dict)
                logger.info(f"Using custom social media config")
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning(f"Failed to parse social config: {e}")

        # Run refinement with configuration
        logger.info(f"Refining blog draft for job_id: {job_id}")
        refinement_result = await refinement_agent.refine_blog_with_graph(
            blog_draft=compiled_draft,
            cost_aggregator=cost_aggregator,
            project_id=job_id,  # Use job_id as project_id
            title_config=title_generation_config,
            social_config=social_media_config
        )

        if not refinement_result:
            return JSONResponse(
                content={"error": "Failed to refine blog draft."},
                status_code=500
            )

        # Get cost summary after refinement
        cost_summary = cost_aggregator.get_workflow_summary()
        cost_call_history = list(cost_aggregator.call_history)
        title_options_list = [option.model_dump() for option in refinement_result.title_options]

        logger.info(f"Successfully refined blog for job_id: {job_id}")

        # Save refined blog milestone to SQL project manager
        try:
            milestone_data = {
                "refined_content": refinement_result.refined_draft,
                "summary": refinement_result.summary,
                "title_options": title_options_list,
                "job_id": job_id,
                "refined_at": datetime.now().isoformat(),
                "word_count": len(refinement_result.refined_draft.split()),
                "cost_summary": cost_summary
            }
            milestone_metadata = {
                "cost_summary": cost_summary,
                "cost_call_history": cost_call_history
            }

            # Save to SQL project manager
            await sql_project_manager.save_milestone(
                project_id=job_id,
                milestone_type=MilestoneType.BLOG_REFINED,
                data=milestone_data,
                metadata=milestone_metadata
            )

            logger.info(f"Saved refined blog milestone for project {job_id}")
        except Exception as milestone_err:
            logger.warning(f"Failed to save milestone: {milestone_err}")

        return JSONResponse(
            content={
                "job_id": job_id,
                "project_id": job_id,
                "refined_draft": refinement_result.refined_draft,
                "summary": refinement_result.summary,
                "title_options": title_options_list,
                "cost_summary": cost_summary
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
    project_name: str
) -> JSONResponse:
    """Generate social media content from refined draft."""
    try:
        # Find project_id from project_name using SQL project manager
        project = await sql_project_manager.get_project_by_name(project_name)
        project_id = project.get("id") if project else None

        if not project_id:
            logger.error(f"Project not found: {project_name}")
            return JSONResponse(
                content={
                    "error": f"Project '{project_name}' not found",
                    "details": "Please ensure the project exists and is active.",
                },
                status_code=404
            )

        # Load workflow state from SQL
        workflow_state = await load_workflow_state(project_id)
        if not workflow_state:
            logger.error(f"Workflow state not found for project: {project_name}")
            return JSONResponse(
                content={
                    "error": f"Workflow state not found for project: {project_name}",
                    "details": "Please regenerate the outline and draft.",
                },
                status_code=404
            )

        # Check for refined draft
        refined_draft = workflow_state.get("refined_draft")
        if not refined_draft:
            logger.error(f"Refined draft not found for project: {project_name}")
            return JSONResponse(
                content={
                    "error": f"No refined draft found for project: {project_name}. Please refine the draft first.",
                    "has_refined_draft": False,
                    "has_final_draft": bool(workflow_state.get("final_draft"))
                },
                status_code=400
            )

        # Get blog title from title options or outline
        title_options = workflow_state.get("title_options", [])
        if title_options and isinstance(title_options[0], dict):
            blog_title = title_options[0].get("title", workflow_state.get("outline", {}).get("title", "Blog Post"))
        else:
            blog_title = workflow_state.get("outline", {}).get("title", "Blog Post")

        # Get model and agents
        model_name = workflow_state.get("model_name")
        specific_model = workflow_state.get("specific_model")
        agents = await get_or_create_agents(model_name, specific_model)
        social_agent = agents.get("social_agent")

        if not social_agent:
            return JSONResponse(
                content={"error": "Social media agent could not be initialized."},
                status_code=500
            )

        # Generate comprehensive social content (including thread)
        logger.info(f"Generating comprehensive social content for project: {project_name}")
        social_content = await social_agent.generate_comprehensive_content(
            blog_content=refined_draft,
            blog_title=blog_title,
            persona=workflow_state.get("persona", "neuraforge")
        )

        if not social_content:
            return JSONResponse(
                content={"error": "Failed to generate social media content."},
                status_code=500
            )

        # Convert to API response format
        social_content_response = social_content.to_api_response()

        # Save social media milestone to SQL
        milestone_data = {
            "social_content": social_content_response,
            "generated_at": datetime.now().isoformat(),
            "blog_title": blog_title
        }

        await sql_project_manager.save_milestone(
            project_id,
            MilestoneType.SOCIAL_GENERATED,
            milestone_data
        )

        logger.info(f"Saved social media milestone for project {project_id}")

        # Save to completed_blogs table - this marks the blog as fully complete
        word_count = len(refined_draft.split())
        cost_summary = workflow_state.get("cost_summary", {})
        total_cost = cost_summary.get("total_cost", 0.0)

        # Calculate generation time from project creation
        project_created = project.get("created_at")
        generation_time = 0
        if project_created:
            try:
                if isinstance(project_created, str):
                    created_dt = datetime.fromisoformat(project_created.replace('Z', '+00:00'))
                else:
                    created_dt = project_created
                generation_time = int((datetime.now(created_dt.tzinfo) - created_dt).total_seconds())
            except Exception as e:
                logger.warning(f"Could not calculate generation time: {e}")

        await sql_project_manager.save_completed_blog(
            project_id=project_id,
            title=blog_title,
            content=refined_draft,
            word_count=word_count,
            total_cost=total_cost,
            generation_time=generation_time,
            metadata={
                "model_name": workflow_state.get("model_name"),
                "specific_model": workflow_state.get("specific_model"),
                "persona": workflow_state.get("persona"),
                "has_social_content": True
            }
        )

        logger.info(f"Saved completed blog for project {project_id}: {blog_title} ({word_count} words)")

        return JSONResponse(
            content={
                "project_id": project_id,
                "project_name": project_name,
                "social_content": social_content_response,
                "blog_completed": True,
                "word_count": word_count,
                "total_cost": total_cost
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
        # Use SQL project manager for consistent storage
        projects = await sql_project_manager.list_projects(status=status)

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
        # Use SQL project manager for consistent storage
        project_data = await sql_project_manager.get_project(project_id)

        if not project_data:
            return JSONResponse(
                content={"error": f"Project {project_id} not found"},
                status_code=404
            )

        # Get all milestones from SQL database
        milestones = {}
        for milestone_type in MilestoneType:
            milestone_data = await sql_project_manager.load_milestone(project_id, milestone_type)
            if milestone_data:
                milestones[milestone_type.value] = {
                    "created_at": milestone_data.get("created_at"),
                    "metadata": milestone_data.get("metadata", {}),
                    "data": milestone_data.get("data", {})
                }

        # Get cost summary from Supabase
        cost_summary = await sql_project_manager.get_cost_summary(project_id)

        return JSONResponse(
            content={
                "status": "success",
                "project": project_data,
                "milestones": milestones,
                "cost_summary": cost_summary
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
    Resume a project from its latest milestone with COMPLETE state restoration.

    Uses load_workflow_state() as single source of truth to ensure all data
    (outline, sections, drafts, costs) is properly restored.

    Args:
        project_id: Project UUID

    Returns:
        Complete resume data including all content and resume position
    """
    try:
        # Use load_workflow_state() as SINGLE SOURCE OF TRUTH
        state = await load_workflow_state(project_id)

        if not state:
            return JSONResponse(
                content={"error": f"Project {project_id} not found"},
                status_code=404
            )

        # Get project data for additional metadata
        project_data = await sql_project_manager.get_project(project_id)

        # Get milestones for files_uploaded data (file hashes, etc.)
        files_milestone = await sql_project_manager.load_milestone(
            project_id, MilestoneType.FILES_UPLOADED
        )

        # Extract outline for section counting
        outline = state.get("outline", {})
        outline_sections = outline.get("sections", []) if outline else []
        total_sections = len(outline_sections)

        # Get generated sections from state (loaded from sections table)
        generated_sections = state.get("generated_sections", {})
        completed_sections = len([
            s for s in generated_sections.values()
            if s.get("status") == "completed"
        ])

        # Calculate resume position - which section to generate next
        resume_from_section = None
        if total_sections > 0 and completed_sections < total_sections:
            resume_from_section = completed_sections

        # Determine current milestone and next step
        milestones_data = await sql_project_manager.get_milestones(project_id)
        milestone_types = [m.get("type") for m in milestones_data]

        # Determine current milestone (most advanced)
        milestone_priority = [
            "social_generated", "blog_refined", "draft_completed",
            "outline_generated", "files_uploaded"
        ]
        current_milestone = "files_uploaded"
        for m in milestone_priority:
            if m in milestone_types:
                current_milestone = m
                break

        # Determine next step based on current state
        if "social_generated" in milestone_types:
            next_step = "completed"
        elif "blog_refined" in milestone_types:
            next_step = "social_generation"
        elif "draft_completed" in milestone_types:
            next_step = "blog_refinement"
        elif "outline_generated" in milestone_types:
            if completed_sections < total_sections:
                next_step = "section_generation"
            else:
                next_step = "compile_draft"
        else:
            next_step = "outline_generation"

        # Get cost data from outline_generated milestone metadata (most complete)
        outline_milestone = await sql_project_manager.load_milestone(
            project_id, MilestoneType.OUTLINE_GENERATED
        )
        cost_call_history = []
        if outline_milestone:
            cost_call_history = outline_milestone.get("metadata", {}).get("cost_call_history", [])

        # Calculate progress percentage
        progress = await sql_project_manager.get_progress(project_id)

        logger.info(f"Resumed project {project_id} with {completed_sections}/{total_sections} sections")

        return JSONResponse(
            content={
                "status": "success",
                "project_id": project_id,
                "project_name": state.get("project_name"),

                # Configuration
                "model_name": state.get("model_name"),
                "specific_model": state.get("specific_model"),
                "persona": state.get("persona"),

                # Progress tracking
                "current_milestone": current_milestone,
                "next_step": next_step,
                "progress_percentage": progress.get("percentage", 0),

                # Section progress
                "total_sections": total_sections,
                "completed_sections": completed_sections,
                "resume_from_section": resume_from_section,

                # File data
                "uploaded_files": files_milestone.get("data", {}).get("files", []) if files_milestone else {},
                "processed_file_hashes": files_milestone.get("data", {})
            }
        )

    except Exception as e:
        logger.exception(f"Failed to resume project {project_id}: {e}")
        return JSONResponse(
            content={"error": f"Failed to resume project: {str(e)}"},
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
    """Get available models organized by provider with specific model options.

    Model data is loaded from models/registry.py - the single source of truth.
    """
    try:
        # Import from the single source of truth
        from backend.models.registry import get_api_models_response

        return JSONResponse(content=get_api_models_response())

    except Exception as e:
        logger.error(f"Failed to get model configurations: {e}")
        return JSONResponse(
            content={"error": f"Failed to get model configurations: {str(e)}"},
            status_code=500
        )


# Include v2 API routes
import sys
from pathlib import Path

# Add project root to path for absolute imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    logger.info(f"Added to Python path for v2 API: {project_root}")

try:
    # Import v2 API router using absolute import
    from backend.api_v2 import router as api_v2_router
    app.include_router(api_v2_router)
    logger.info(f"API v2 routes loaded successfully! Routes: {len(api_v2_router.routes)}")
    logger.info(f"V2 API prefix: {api_v2_router.prefix}")
except Exception as e:
    logger.error(f"CRITICAL: Could not load API v2 routes: {e}")
    logger.error(f"Python path: {sys.path[:3]}")
    logger.error(f"Current dir: {Path.cwd()}")
    logger.error(f"API v2 file exists: {Path(__file__).parent / 'api_v2.py'} - {(Path(__file__).parent / 'api_v2.py').exists()}")
    import traceback
    traceback.print_exc()
    # Continue without v2 routes for backward compatibility
