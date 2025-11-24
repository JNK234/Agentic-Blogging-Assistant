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

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
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
        state["social_content"] = milestones["social_generated"]["data"]

    # Load sections from SQL Sections table
    state["generated_sections"] = {
        s["section_index"]: {
            "title": s["title"],
            "content": s["content"],
            "status": s["status"]
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
        # project_id will be determined from the project lookup
        cost_aggregator = CostAggregator()

        # Get project from SQL manager (returns dict)
        project = await sql_project_manager.get_project_by_name(project_name)
        project_id = project["id"] if project else None

        if project_id:
            cost_aggregator.start_workflow(project_id=project_id)

        # Generate outline - returns a dict (outline or error), content, content, cached_status
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
            await sql_project_manager.save_milestone(
                project_id=project_id,
                milestone_type=MilestoneType.OUTLINE_GENERATED,
                data=milestone_data,
                metadata=milestone_metadata
            )

            logger.info(f"Saved outline milestone for project {project_id}")

        # Return project_id instead of job_id
        return JSONResponse(
            content=serialize_object({
                "project_id": project_id,
                "outline": outline_data,
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

        # Check if section already exists in SQL
        generated_sections = state.get('generated_sections', {})
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

        return JSONResponse(
            content={
                "project_id": project_id,
                "project_name": project_name,
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
    project_name: str
) -> JSONResponse:
    """Generate Twitter/X thread from refined draft."""
    try:
        # Find project_id from project_name
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
                    "suggestion": "Please regenerate the outline to restart the workflow."
                },
                status_code=404
            )
        
        refined_draft = workflow_state.get("refined_draft")
        if not refined_draft:
            return JSONResponse(
                content={"error": "Refined draft not found. Please complete blog refinement first."},
                status_code=400
            )
        
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
        
        # Generate Twitter thread
        logger.info(f"Generating Twitter thread for project: {project_name}")
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
        
        return JSONResponse(
            content={
                "project_id": project_id,
                "project_name": project_name,
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
        # Use SQL project manager for consistent storage
        project_data = await sql_project_manager.get_project(project_id)

        if not project_data:
            return JSONResponse(
                content={"error": f"Project {project_id} not found"},
                status_code=404
            )

        # Get all milestones
        milestones = {}
        for milestone_type in MilestoneType:
            milestone_data = await sql_project_manager.load_milestone(project_id, milestone_type)
            if milestone_data:
                milestones[milestone_type.value] = milestone_data

        # Determine next step based on latest milestone
        latest_milestone = project_data.get("current_milestone", "files_uploaded")
        next_step_map = {
            "files_uploaded": "outline_generation",
            "outline_generated": "blog_drafting",
            "draft_completed": "blog_refinement",
            "blog_refined": "social_generation",
            "social_generated": "completed"
        }
        next_step = next_step_map.get(latest_milestone, "outline_generation")

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
        if "outline_generated" in milestones:
            outline_data = milestones["outline_generated"].get("data", {})
            job_state["outline"] = outline_data.get("outline")
            job_state["outline_hash"] = outline_data.get("outline_hash")

        # Load draft if available
        if "draft_completed" in milestones:
            draft_data = milestones["draft_completed"].get("data", {})
            job_state["final_draft"] = draft_data.get("compiled_blog")
            job_state["generated_sections"] = draft_data.get("sections", {})

        # Load refined blog if available
        if "blog_refined" in milestones:
            refined_data = milestones["blog_refined"].get("data", {})
            job_state["refined_draft"] = refined_data.get("refined_content")
            job_state["summary"] = refined_data.get("summary")
            job_state["title_options"] = refined_data.get("title_options")

        # REMOVED: Store in state cache for session
        # No longer needed - using SQL-only persistence via load_workflow_state()
        # state_cache[job_id] = job_state
        logger.info(f"Resumed project {project_id} (cache storage removed, using SQL-only)")

        return JSONResponse(
            content={
                "status": "success",
                "job_id": job_id,
                "project_id": project_id,
                "project_name": project_data.get("name"),
                "current_milestone": latest_milestone,
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
        success = await sql_project_manager.delete_project(project_id, permanent=True)

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
        success = await sql_project_manager.archive_project(project_id)

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

        export_data = await sql_project_manager.export_project(project_id, format=format)
        
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
