# ABOUTME: API v2 endpoints using project_id pattern with SQL backend
# ABOUTME: Provides section management, cost tracking, and project operations with backward compatibility

"""
API v2 endpoints for project management with SQL backend.
Implements project_id pattern while maintaining backward compatibility.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging
import os

from backend.services.supabase_project_manager import SupabaseProjectManager, MilestoneType, ProjectStatus, SectionStatus
from backend.services.cost_aggregator import CostAggregator
from backend.agents.outline_generator.state import FinalOutline
from backend.utils.serialization import serialize_object

logger = logging.getLogger("APIv2")

# Create router for v2 API
router = APIRouter(prefix="/api/v2", tags=["v2"])

# Initialize services
sql_manager = SupabaseProjectManager()  # Keep variable name for compatibility
cost_aggregator = CostAggregator()

# ==================== Pydantic Models ====================

class ProjectCreate(BaseModel):
    """Project creation request."""
    name: str = Field(..., description="Project name")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SectionUpdate(BaseModel):
    """Section update model."""
    section_index: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: str = "pending"
    cost_delta: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0

class CostTrackRequest(BaseModel):
    """Cost tracking request."""
    agent_name: str
    operation: str
    input_tokens: int
    output_tokens: int
    cost: float
    model_used: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MilestoneData(BaseModel):
    """Milestone data model."""
    type: str
    data: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)

# ==================== Project CRUD Endpoints ====================

@router.post("/projects")
async def create_project(request: Request, project_data: ProjectCreate) -> JSONResponse:
    """
    Create a new project with unique ID.

    Returns:
        Project ID and details
    """
    try:
        # Get authenticated user from request state (set by auth middleware)
        user = getattr(request.state, 'user', None)
        user_id = user.get('id') if user else None
        
        project_id = await sql_manager.create_project(
            project_name=project_data.name,
            metadata=project_data.metadata,
            user_id=user_id  # Pass authenticated user ID for RLS
        )

        return JSONResponse(content={
            "status": "success",
            "project_id": project_id,
            "name": project_data.name,
            "message": f"Project created successfully"
        })

    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects")
async def list_projects(status: Optional[str] = None) -> JSONResponse:
    """
    List all projects with optional status filter.

    Args:
        status: Optional filter (active, archived, deleted)

    Returns:
        List of projects with progress and cost info
    """
    try:
        # Parse status if provided
        project_status = None
        if status:
            try:
                project_status = ProjectStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Get projects
        projects = await sql_manager.list_projects(status=project_status)

        # Enrich with progress and cost for active projects
        enriched_projects = []
        for project in projects:
            if project["status"] == ProjectStatus.ACTIVE.value:
                # Get progress
                progress = await sql_manager.get_progress(project["id"])
                project["progress"] = progress["percentage"]

                # Get cost summary
                cost_summary = await sql_manager.get_cost_summary(project["id"])
                project["total_cost"] = cost_summary["total_cost"]

            enriched_projects.append(project)

        return JSONResponse(content={
            "status": "success",
            "projects": enriched_projects,
            "count": len(enriched_projects)
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> JSONResponse:
    """
    Get project details by ID.

    Args:
        project_id: Project UUID

    Returns:
        Project details with progress and cost
    """
    try:
        project = await sql_manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Get complete project state
        progress = await sql_manager.get_progress(project_id)
        cost_summary = await sql_manager.get_cost_summary(project_id)

        # Get all milestones
        milestones = {}
        for milestone_type in MilestoneType:
            milestone_data = await sql_manager.load_milestone(project_id, milestone_type)
            if milestone_data:
                milestones[milestone_type.value] = milestone_data

        # Get sections if they exist
        sections = await sql_manager.load_sections(project_id) or []

        # Determine next step based on completed milestones
        milestone_set = set(milestones.keys())

        if "social_generated" in milestone_set:
            next_step = "completed"
        elif "blog_refined" in milestone_set:
            next_step = "social_generation"
        elif "draft_completed" in milestone_set:
            next_step = "blog_refinement"
        elif "outline_generated" in milestone_set:
            next_step = "blog_drafting"
        elif "files_uploaded" in milestone_set:
            next_step = "outline_generation"
        else:
            next_step = "file_upload"

        return JSONResponse(content={
            "status": "success",
            "project": project,
            "progress": progress,
            "cost_summary": cost_summary,
            "milestones": milestones,
            "sections": sections,
            "next_step": next_step
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, permanent: bool = False) -> JSONResponse:
    """
    Delete or archive a project.

    Args:
        project_id: Project UUID
        permanent: If true, permanently delete; otherwise soft delete

    Returns:
        Success status
    """
    try:
        success = await sql_manager.delete_project(project_id, permanent=permanent)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")

        action = "permanently deleted" if permanent else "archived"
        return JSONResponse(content={
            "status": "success",
            "message": f"Project {action} successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Section Management Endpoints ====================

@router.put("/projects/{project_id}/sections")
async def update_sections(project_id: str, sections: List[SectionUpdate]) -> JSONResponse:
    """
    Batch update all sections for a project.

    Args:
        project_id: Project UUID
        sections: List of sections to update

    Returns:
        Update status
    """
    try:
        # Convert to dict format
        section_dicts = [s.dict() for s in sections]

        # Save sections
        success = await sql_manager.save_sections(project_id, section_dicts)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save sections")

        # Track the operation cost (minimal for metadata operation)
        await sql_manager.track_cost(
            project_id=project_id,
            agent_name="api",
            operation="section_batch_update",
            input_tokens=0,
            output_tokens=0,
            cost=0.0,
            metadata={"sections_count": len(sections)}
        )

        return JSONResponse(content={
            "status": "success",
            "sections_updated": len(sections),
            "message": f"Successfully updated {len(sections)} sections"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update sections for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/sections")
async def get_sections(project_id: str) -> JSONResponse:
    """
    Get all sections for a project.

    Args:
        project_id: Project UUID

    Returns:
        List of sections with status
    """
    try:
        sections = await sql_manager.load_sections(project_id)

        # Calculate section stats
        completed = sum(1 for s in sections if s["status"] == SectionStatus.COMPLETED.value)
        total_cost = sum(s.get("cost_delta", 0) for s in sections)

        return JSONResponse(content={
            "status": "success",
            "sections": sections,
            "stats": {
                "total": len(sections),
                "completed": completed,
                "pending": sum(1 for s in sections if s["status"] == SectionStatus.PENDING.value),
                "generating": sum(1 for s in sections if s["status"] == SectionStatus.GENERATING.value),
                "failed": sum(1 for s in sections if s["status"] == SectionStatus.FAILED.value),
                "total_cost": total_cost
            }
        })

    except Exception as e:
        logger.error(f"Failed to get sections for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/projects/{project_id}/sections/{section_index}/status")
async def update_section_status(
    project_id: str,
    section_index: int,
    status: str,
    cost_delta: Optional[float] = None
) -> JSONResponse:
    """
    Update status of a specific section.

    Args:
        project_id: Project UUID
        section_index: Section index
        status: New status
        cost_delta: Optional cost update

    Returns:
        Update status
    """
    try:
        success = await sql_manager.update_section_status(
            project_id=project_id,
            section_index=section_index,
            status=status,
            cost_delta=cost_delta
        )

        if not success:
            raise HTTPException(status_code=404, detail="Section not found")

        return JSONResponse(content={
            "status": "success",
            "message": f"Section {section_index} status updated to {status}"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update section status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Cost Tracking Endpoints ====================

@router.post("/projects/{project_id}/costs")
async def track_cost(project_id: str, request: CostTrackRequest) -> JSONResponse:
    """
    Track cost for an operation.

    Args:
        project_id: Project UUID
        request: Cost tracking details

    Returns:
        Success status
    """
    try:
        success = await sql_manager.track_cost(
            project_id=project_id,
            agent_name=request.agent_name,
            operation=request.operation,
            input_tokens=request.input_tokens,
            output_tokens=request.output_tokens,
            cost=request.cost,
            model_used=request.model_used,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to track cost")

        return JSONResponse(content={
            "status": "success",
            "message": f"Cost tracked: ${request.cost:.6f}"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to track cost: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/costs")
async def get_cost_summary(project_id: str) -> JSONResponse:
    """
    Get cost summary for a project.

    Args:
        project_id: Project UUID

    Returns:
        Cost summary with breakdown
    """
    try:
        cost_summary = await sql_manager.get_cost_summary(project_id)

        return JSONResponse(content={
            "status": "success",
            "cost_summary": cost_summary
        })

    except Exception as e:
        logger.error(f"Failed to get cost summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/costs/analysis")
async def get_cost_analysis(project_id: str) -> JSONResponse:
    """
    Get detailed cost analysis with timeline.

    Args:
        project_id: Project UUID

    Returns:
        Detailed cost analysis
    """
    try:
        analysis = await sql_manager.get_cost_analysis(project_id)

        return JSONResponse(content={
            "status": "success",
            "analysis": analysis
        })

    except Exception as e:
        logger.error(f"Failed to get cost analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Progress and Resume Endpoints ====================

@router.get("/projects/{project_id}/progress")
async def get_progress(project_id: str) -> JSONResponse:
    """
    Get real-time progress with cost tracking.

    Args:
        project_id: Project UUID

    Returns:
        Progress information with costs
    """
    try:
        progress = await sql_manager.get_progress(project_id)
        costs = await sql_manager.get_cost_summary(project_id)

        return JSONResponse(content={
            "status": "success",
            "overall_progress": progress["percentage"],
            "milestones": progress["milestones"],
            "sections": progress["sections"],
            "cost_summary": costs
        })

    except Exception as e:
        logger.error(f"Failed to get progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/resume")
async def resume_project(project_id: str) -> JSONResponse:
    """
    Resume a project with complete state restoration.

    Args:
        project_id: Project UUID

    Returns:
        Complete project state for resumption
    """
    try:
        state = await sql_manager.resume_project(project_id)
        if not state:
            raise HTTPException(status_code=404, detail="Project not found")

        # Add milestones to project object for frontend compatibility
        project_with_milestones = state["project"].copy()
        project_with_milestones["milestones"] = state["milestones"]
        logger.info(f"DEBUG: Added milestones to project. Keys in project object: {list(project_with_milestones.keys())}")
        
        return JSONResponse(content={
            "status": "success",
            "project_id": project_id,
            "project": project_with_milestones,
            "progress": state["progress"],
            "next_step": state["next_step"],
            "cost_to_date": state["cost_summary"]["total_cost"],
            "milestones_completed": list(state["milestones"].keys()),
            "sections_status": {
                "total": len(state["sections"]),
                "completed": sum(1 for s in state["sections"] if s["status"] == "completed")
            }
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Milestone Endpoints ====================

@router.post("/projects/{project_id}/milestones")
async def save_milestone(project_id: str, milestone: MilestoneData) -> JSONResponse:
    """
    Save a milestone for a project.

    Args:
        project_id: Project UUID
        milestone: Milestone data

    Returns:
        Success status
    """
    try:
        # Parse milestone type
        try:
            milestone_type = MilestoneType(milestone.type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid milestone type: {milestone.type}")

        success = await sql_manager.save_milestone(
            project_id=project_id,
            milestone_type=milestone_type,
            data=milestone.data,
            metadata=milestone.metadata
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to save milestone")

        return JSONResponse(content={
            "status": "success",
            "message": f"Milestone {milestone.type} saved successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/milestones/{milestone_type}")
async def get_milestone(project_id: str, milestone_type: str) -> JSONResponse:
    """
    Get a specific milestone for a project.

    Args:
        project_id: Project UUID
        milestone_type: Milestone type

    Returns:
        Milestone data
    """
    try:
        # Parse milestone type
        try:
            mt = MilestoneType(milestone_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid milestone type: {milestone_type}")

        milestone = await sql_manager.load_milestone(project_id, mt)
        if not milestone:
            raise HTTPException(status_code=404, detail="Milestone not found")

        return JSONResponse(content={
            "status": "success",
            "milestone": milestone
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get milestone: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Outline Regeneration Endpoints ====================

@router.post("/projects/{project_name}/outline/regenerate")
async def regenerate_outline_with_feedback(
    project_name: str,
    feedback_content: str = Form(...),
    focus_area: Optional[str] = Form(None),
    previous_version_id: Optional[str] = Form(None),
    model_name: Optional[str] = Form(None),
    specific_model: Optional[str] = Form(None),
    user_guidelines: Optional[str] = Form(None),
    length_preference: Optional[str] = Form(None),
    custom_length: Optional[int] = Form(None),
    writing_style: Optional[str] = Form(None),
    persona: Optional[str] = Form("neuraforge")
) -> JSONResponse:
    """
    Regenerate an outline with user feedback and version management.

    Args:
        project_name: Name of the project
        feedback_content: User feedback for regeneration
        focus_area: Area of focus (structure, content, flow, technical_level)
        previous_version_id: ID of the previous outline version
        model_name: Model provider to use
        specific_model: Specific model name
        user_guidelines: Optional user-provided guidelines
        length_preference: Optional length preference
        custom_length: Optional custom length
        writing_style: Optional writing style
        persona: Optional persona for generation

    Returns:
        New outline with version information
    """
    try:
        # Import required services and agents
        from backend.agents.outline_generator_agent import OutlineGeneratorAgent
        from backend.agents.content_parsing_agent import ContentParsingAgent
        from backend.services.vector_store_service import VectorStoreService
        from backend.services.persona_service import PersonaService
        from backend.models.model_factory import ModelFactory

        # Get project by name to get project_id
        project = await sql_manager.get_project_by_name(project_name)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

        project_id = project["id"]

        # Get or create model
        model_factory = ModelFactory()
        if not model_name:
            # Use project's existing model or default
            model_name = project["metadata"].get("model_name", "gpt-4")
        model = model_factory.create_model(model_name.lower(), specific_model)

        # Initialize required services
        content_parser = ContentParsingAgent(model)
        await content_parser.initialize()

        vector_store = VectorStoreService()
        persona_service = PersonaService()

        # Create outline agent with SQL project manager for version management
        outline_agent = OutlineGeneratorAgent(model, content_parser, vector_store, persona_service, sql_manager)
        await outline_agent.initialize()

        # Initialize cost tracking
        cost_aggregator = CostAggregator()
        cost_aggregator.start_workflow(project_id=project_id)

        # Get latest file hashes if not provided
        files_milestone = await sql_manager.load_milestone(project_id, MilestoneType.FILES_UPLOADED)
        file_hashes = files_milestone.get("data", {}).get("file_hashes", {}) if files_milestone else {}

        # Determine which hashes to use
        notebook_hash = None
        markdown_hash = None
        for file_path, file_hash in file_hashes.items():
            if file_path.endswith('.ipynb'):
                notebook_hash = file_hash
            elif file_path.endswith('.md'):
                markdown_hash = file_hash

        # Regenerate outline with feedback
        start_time = datetime.now()
        new_outline, version_info, success = await outline_agent.regenerate_with_feedback(
            project_name=project_name,
            feedback_content=feedback_content,
            focus_area=focus_area,
            previous_version_id=previous_version_id,
            model_name=model_name,
            notebook_hash=notebook_hash,
            markdown_hash=markdown_hash,
            user_guidelines=user_guidelines,
            length_preference=length_preference,
            custom_length=custom_length,
            writing_style=writing_style,
            persona=persona,
            cost_aggregator=cost_aggregator,
            project_id=project_id
        )

        if not success or not new_outline:
            raise HTTPException(status_code=500, detail="Failed to regenerate outline with feedback")

        # Calculate duration and get cost summary
        duration = (datetime.now() - start_time).total_seconds()
        cost_summary = cost_aggregator.get_workflow_summary()

        # Get next version number for unified handling
        version_number = await sql_manager.get_next_version_number(project_id)

        # Store the feedback ID if we have one
        feedback_id = None
        if previous_version_id:
            feedback_id = f"feedback_for_{previous_version_id}"

        await sql_manager.save_outline_version(
            project_id=project_id,
            outline_data=new_outline,
            version_number=version_number,
            feedback_id=feedback_id
        )

        # Save feedback if previous version ID provided
        if previous_version_id:
            await sql_manager.save_outline_feedback(
                outline_version_id=previous_version_id,
                content=feedback_content,
                focus_area=focus_area
            )

        # Update project metadata with new outline
        await sql_manager.update_metadata(project_id, {
            "model_name": model_name,
            "specific_model": specific_model,
            "persona": persona
        })

        # Save outline generated milestone
        milestone_data = {
            "outline": new_outline,
            "model_name": model_name,
            "specific_model": specific_model,
            "persona": persona,
            "user_guidelines": user_guidelines,
            "length_preference": length_preference,
            "custom_length": custom_length,
            "was_regenerated": True,
            "feedback_content": feedback_content,
            "focus_area": focus_area,
            "previous_version_id": previous_version_id
        }

        await sql_manager.save_milestone(
            project_id=project_id,
            milestone_type=MilestoneType.OUTLINE_GENERATED,
            data=milestone_data,
            metadata={
                "cost_summary": cost_summary,
                "duration_seconds": duration,
                "version_number": version_number
            }
        )

        logger.info(f"Successfully regenerated outline for project {project_name} (version {version_number})")

        # Get total versions for unified response
        all_versions = await sql_manager.get_outline_versions(project_id)
        total_versions = len(all_versions)

        return JSONResponse(content={
            "status": "success",
            "project_id": project_id,
            "project_name": project_name,
            "outline": new_outline,
            "version_info": {
                "version_number": version_number,
                "version_id": str(version_number),  # Use version number as ID
                "total_versions": total_versions,
                "is_latest": True
            },
            "cost_summary": cost_summary,
            "duration_seconds": duration
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate outline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_name}/outline/versions")
async def get_outline_versions(project_name: str) -> JSONResponse:
    """
    Retrieve all outline versions for a project.

    Args:
        project_name: Name of the project

    Returns:
        List of outline versions with basic information
    """
    try:
        # Get project by name
        project = await sql_manager.get_project_by_name(project_name)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

        project_id = project["id"]

        # Get all outline versions
        versions = await sql_manager.get_outline_versions(project_id)

        # Format response with basic info
        version_list = []
        for version in versions:
            version_info = {
                "version_id": version.get("id"),
                "version_number": version.get("version_number"),
                "created_at": version.get("created_at"),
                "outline_hash": version.get("outline_hash"),
                "model_used": version.get("model_used"),
                "metadata": version.get("metadata", {})
            }

            # Include outline preview (title and section count)
            outline_data = version.get("outline_data", {})
            if outline_data:
                version_info["outline_preview"] = {
                    "title": outline_data.get("title", "Untitled"),
                    "section_count": len(outline_data.get("sections", [])),
                    "difficulty_level": outline_data.get("difficulty_level"),
                    "has_prerequisites": bool(outline_data.get("prerequisites"))
                }

            version_list.append(version_info)

        # Sort by version number descending
        version_list.sort(key=lambda x: x["version_number"], reverse=True)

        logger.info(f"Retrieved {len(version_list)} outline versions for project {project_name}")

        return JSONResponse(content={
            "status": "success",
            "project_id": project_id,
            "project_name": project_name,
            "versions": version_list,
            "total_versions": len(version_list)
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get outline versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Export Endpoints ====================

@router.get("/projects/{project_id}/export")
async def export_project(project_id: str, format: str = "json") -> Any:
    """
    Export project data in specified format.

    Args:
        project_id: Project UUID
        format: Export format (json, markdown)

    Returns:
        Exported data
    """
    try:
        data = await sql_manager.export_project(project_id, format=format)
        if not data:
            raise HTTPException(status_code=404, detail="Project not found")

        if format == "json":
            return JSONResponse(content=data)
        elif format == "markdown":
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=data)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export project: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Backward Compatibility ====================

@router.get("/projects/by-name/{project_name}")
async def get_project_by_name(project_name: str) -> JSONResponse:
    """
    Get project by name (backward compatibility).

    Args:
        project_name: Project name

    Returns:
        Project details
    """
    try:
        project = await sql_manager.get_project_by_name(project_name)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Add progress and cost
        progress = await sql_manager.get_progress(project["id"])
        cost_summary = await sql_manager.get_cost_summary(project["id"])

        project["progress"] = progress
        project["cost_summary"] = cost_summary

        return JSONResponse(content={
            "status": "success",
            "project": project
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project by name {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cost Analytics & Reporting Endpoints ====================
# NOTE: Advanced reporting endpoints removed during Supabase migration.
# These endpoints relied on CostAnalyticsService which used SQLite.
# TODO: Reimplement using Supabase with proper analytics queries.
# Removed endpoints:
#   - GET /reports/costs/weekly
#   - GET /reports/costs/monthly
#   - GET /reports/costs/trends
#   - GET /reports/costs/summary
#   - GET /reports/costs/compare