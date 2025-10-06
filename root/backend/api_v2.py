# ABOUTME: API v2 endpoints using project_id pattern with SQL backend
# ABOUTME: Provides section management, cost tracking, and project operations with backward compatibility

"""
API v2 endpoints for project management with SQL backend.
Implements project_id pattern while maintaining backward compatibility.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid
import logging
import os

from backend.services.sql_project_manager import SQLProjectManager, MilestoneType, ProjectStatus, SectionStatus
from backend.services.cost_aggregator import CostAggregator
from backend.agents.outline_generator.state import FinalOutline
from backend.utils.serialization import serialize_object

logger = logging.getLogger("APIv2")

# Create router for v2 API
router = APIRouter(prefix="/api/v2", tags=["v2"])

# Initialize services
sql_manager = SQLProjectManager()
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
async def create_project(request: ProjectCreate) -> JSONResponse:
    """
    Create a new project with unique ID.

    Returns:
        Project ID and details
    """
    try:
        project_id = await sql_manager.create_project(
            project_name=request.name,
            metadata=request.metadata
        )

        return JSONResponse(content={
            "status": "success",
            "project_id": project_id,
            "name": request.name,
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

        # Add progress and cost
        progress = await sql_manager.get_progress(project_id)
        cost_summary = await sql_manager.get_cost_summary(project_id)

        project["progress"] = progress
        project["cost_summary"] = cost_summary

        return JSONResponse(content={
            "status": "success",
            "project": project
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

        # Generate a job ID for cache
        job_id = str(uuid.uuid4())

        # Store in job cache for compatibility with existing workflow
        # Import at runtime to avoid circular import
        import main
        main.state_cache[job_id] = {
            "project_id": project_id,
            "project_name": state["project"]["name"],
            "outline": state["milestones"].get(MilestoneType.OUTLINE_GENERATED.value, {}).get("data"),
            "sections": state["sections"],
            "refined_draft": state["milestones"].get(MilestoneType.BLOG_REFINED.value, {}).get("data"),
            "metadata": state["project"].get("metadata", {})
        }

        return JSONResponse(content={
            "status": "success",
            "job_id": job_id,
            "project": state["project"],
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