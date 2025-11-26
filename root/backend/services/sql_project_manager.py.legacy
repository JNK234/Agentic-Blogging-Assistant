# ABOUTME: SQL-based project manager service with section persistence and cost tracking
# ABOUTME: Handles all project operations using SQLAlchemy ORM with atomic operations and locking

"""
SQL-based ProjectManager service for persistent project tracking with enhanced features.
"""

import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from contextlib import contextmanager
import json

from backend.models.database import (
    get_db_manager, Project, Milestone, Section,
    CostTracking, CompletedBlog
)

logger = logging.getLogger(__name__)


class ProjectStatus(Enum):
    """Project status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MilestoneType(Enum):
    """Milestone type enumeration."""
    FILES_UPLOADED = "files_uploaded"
    OUTLINE_GENERATED = "outline_generated"
    DRAFT_COMPLETED = "draft_completed"
    BLOG_REFINED = "blog_refined"
    SOCIAL_GENERATED = "social_generated"


class SectionStatus(Enum):
    """Section status enumeration."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class SQLProjectManager:
    """
    SQL-based project lifecycle and milestone tracking.

    Features:
    - Section-level persistence with batch operations
    - Granular cost tracking per operation
    - Atomic operations with per-project locking
    - Full state hydration for project resume
    - Backward compatibility with existing API
    """

    def __init__(self, db_url: str = None):
        """
        Initialize SQLProjectManager with database connection.

        Args:
            db_url: Database URL. Defaults to sqlite:///data/projects.db
        """
        self.db_manager = get_db_manager(db_url or "sqlite:///data/projects.db")
        self.db_manager.init_database()
        self.project_locks = {}  # Per-project async locks
        logger.info(f"SQLProjectManager initialized with database")

    @contextmanager
    def get_session(self) -> Session:
        """Get a database session with proper cleanup."""
        session = self.db_manager.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    async def _get_lock(self, project_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific project."""
        if project_id not in self.project_locks:
            self.project_locks[project_id] = asyncio.Lock()
        return self.project_locks[project_id]

    # ==================== Project CRUD Operations ====================

    async def create_project(self, project_name: str, metadata: Dict[str, Any] = None) -> str:
        """
        Create a new project with unique ID.

        Args:
            project_name: Human-readable project name
            metadata: Optional metadata (model, persona, etc.)

        Returns:
            Project ID (UUID string)
        """
        try:
            with self.get_session() as session:
                project = Project(
                    name=project_name,
                    status=ProjectStatus.ACTIVE.value,
                    metadata=metadata or {}
                )
                session.add(project)
                session.flush()
                project_id = project.id

            logger.info(f"Created project {project_name} with ID {project_id}")
            return project_id

        except Exception as e:
            logger.error(f"Failed to create project {project_name}: {e}")
            raise

    async def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load project data by ID.

        Args:
            project_id: Project UUID

        Returns:
            Project data dict or None if not found
        """
        try:
            with self.get_session() as session:
                project = session.query(Project).filter_by(id=project_id).first()
                if not project:
                    logger.warning(f"Project {project_id} not found")
                    return None
                return project.to_dict()

        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            return None

    async def get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Load project data by name (for backward compatibility).

        Args:
            project_name: Project name

        Returns:
            Project data dict or None if not found
        """
        try:
            with self.get_session() as session:
                project = session.query(Project).filter_by(
                    name=project_name,
                    status=ProjectStatus.ACTIVE.value
                ).first()
                if not project:
                    return None
                return project.to_dict()

        except Exception as e:
            logger.error(f"Failed to load project by name {project_name}: {e}")
            return None

    async def list_projects(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List all projects, optionally filtered by status.

        Args:
            status: Optional status filter (string: "active", "archived", "deleted")

        Returns:
            List of project summaries
        """
        try:
            with self.get_session() as session:
                query = session.query(Project)

                if status:
                    # Support both string and enum values
                    status_value = status if isinstance(status, str) else status.value
                    query = query.filter_by(status=status_value)

                projects = query.order_by(Project.updated_at.desc()).all()

                return [p.to_dict() for p in projects]

        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return []

    async def archive_project(self, project_id: str) -> bool:
        """Archive a project."""
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    project = session.query(Project).filter_by(id=project_id).first()
                    if not project:
                        return False

                    project.status = ProjectStatus.ARCHIVED.value
                    project.archived_at = datetime.now()

            logger.info(f"Archived project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive project {project_id}: {e}")
            return False

    async def delete_project(self, project_id: str, permanent: bool = False) -> bool:
        """Delete or soft-delete a project."""
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    project = session.query(Project).filter_by(id=project_id).first()
                    if not project:
                        return False

                    if permanent:
                        session.delete(project)
                        logger.info(f"Permanently deleted project {project_id}")
                    else:
                        project.status = ProjectStatus.DELETED.value
                        logger.info(f"Soft deleted project {project_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False

    # ==================== Milestone Operations ====================

    async def save_milestone(self, project_id: str, milestone_type: MilestoneType,
                            data: Any, metadata: Dict[str, Any] = None) -> bool:
        """
        Save a milestone for a project.

        Args:
            project_id: Project UUID
            milestone_type: Type of milestone
            data: Milestone data to save
            metadata: Optional metadata

        Returns:
            Success boolean
        """
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    # Check if project exists
                    project = session.query(Project).filter_by(id=project_id).first()
                    if not project:
                        logger.error(f"Project {project_id} not found")
                        return False

                    # Check if milestone already exists
                    existing = session.query(Milestone).filter_by(
                        project_id=project_id,
                        type=milestone_type.value
                    ).first()

                    if existing:
                        # Update existing milestone
                        existing.data = data
                        existing.project_metadata = metadata or {}
                        existing.created_at = datetime.now()
                    else:
                        # Create new milestone
                        milestone = Milestone(
                            project_id=project_id,
                            type=milestone_type.value,
                            data=data,
                            metadata=metadata or {}
                        )
                        session.add(milestone)

                    # Update project's updated_at
                    project.updated_at = datetime.now()

            logger.info(f"Saved milestone {milestone_type.value} for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save milestone for project {project_id}: {e}")
            return False

    async def load_milestone(self, project_id: str, milestone_type: MilestoneType) -> Optional[Dict[str, Any]]:
        """Load a specific milestone for a project."""
        try:
            with self.get_session() as session:
                milestone = session.query(Milestone).filter_by(
                    project_id=project_id,
                    type=milestone_type.value
                ).first()

                if not milestone:
                    logger.warning(f"Milestone {milestone_type.value} not found for project {project_id}")
                    return None

                return milestone.to_dict()

        except Exception as e:
            logger.error(f"Failed to load milestone for project {project_id}: {e}")
            return None

    async def get_latest_milestone(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest milestone for a project."""
        try:
            with self.get_session() as session:
                milestone = session.query(Milestone).filter_by(
                    project_id=project_id
                ).order_by(Milestone.created_at.desc()).first()

                if not milestone:
                    return None

                return milestone.to_dict()

        except Exception as e:
            logger.error(f"Failed to get latest milestone for project {project_id}: {e}")
            return None

    # ==================== Section Management ====================

    async def save_sections(self, project_id: str, sections: List[Dict[str, Any]]) -> bool:
        """
        Batch update all sections atomically.

        Args:
            project_id: Project UUID
            sections: List of section dictionaries

        Returns:
            Success boolean
        """
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    # Delete existing sections
                    session.query(Section).filter_by(project_id=project_id).delete()

                    # Insert new sections
                    for section_data in sections:
                        section = Section(
                            project_id=project_id,
                            section_index=section_data.get('section_index'),
                            title=section_data.get('title'),
                            content=section_data.get('content'),
                            status=section_data.get('status', SectionStatus.PENDING.value),
                            cost_delta=section_data.get('cost_delta', 0.0),
                            input_tokens=section_data.get('input_tokens', 0),
                            output_tokens=section_data.get('output_tokens', 0)
                        )
                        session.add(section)

                    # Update project's updated_at
                    project = session.query(Project).filter_by(id=project_id).first()
                    if project:
                        project.updated_at = datetime.now()

            logger.info(f"Saved {len(sections)} sections for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save sections for project {project_id}: {e}")
            return False

    async def load_sections(self, project_id: str) -> List[Dict[str, Any]]:
        """Load all sections for a project."""
        try:
            with self.get_session() as session:
                sections = session.query(Section).filter_by(
                    project_id=project_id
                ).order_by(Section.section_index).all()

                return [s.to_dict() for s in sections]

        except Exception as e:
            logger.error(f"Failed to load sections for project {project_id}: {e}")
            return []

    async def update_section_status(self, project_id: str, section_index: int,
                                   status: str, cost_delta: float = None) -> bool:
        """Update status of a specific section."""
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    section = session.query(Section).filter_by(
                        project_id=project_id,
                        section_index=section_index
                    ).first()

                    if not section:
                        logger.error(f"Section {section_index} not found for project {project_id}")
                        return False

                    section.status = status
                    if cost_delta is not None:
                        section.cost_delta = cost_delta
                    section.updated_at = datetime.now()

            logger.info(f"Updated section {section_index} status to {status} for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update section status: {e}")
            return False

    # ==================== Cost Tracking ====================

    async def track_cost(self, project_id: str, agent_name: str, operation: str,
                        input_tokens: int, output_tokens: int, cost: float,
                        model_used: str = None, metadata: Dict = None) -> bool:
        """
        Track granular cost per operation.

        Args:
            project_id: Project UUID
            agent_name: Name of the agent
            operation: Operation being performed
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cost: Total cost
            model_used: Model used for the operation
            metadata: Additional metadata

        Returns:
            Success boolean
        """
        try:
            with self.get_session() as session:
                cost_record = CostTracking(
                    project_id=project_id,
                    agent_name=agent_name,
                    operation=operation,
                    model_used=model_used,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost=cost,
                    metadata=metadata or {}
                )
                session.add(cost_record)

            logger.info(f"Tracked cost ${cost:.6f} for {agent_name}/{operation} in project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            return False

    async def get_cost_summary(self, project_id: str) -> Dict[str, Any]:
        """Get cost summary for a project."""
        try:
            with self.get_session() as session:
                # Total costs
                totals = session.query(
                    func.sum(CostTracking.cost).label('total_cost'),
                    func.sum(CostTracking.input_tokens).label('total_input_tokens'),
                    func.sum(CostTracking.output_tokens).label('total_output_tokens')
                ).filter_by(project_id=project_id).first()

                # Cost by agent
                agent_costs = session.query(
                    CostTracking.agent_name,
                    func.sum(CostTracking.cost).label('cost')
                ).filter_by(project_id=project_id).group_by(CostTracking.agent_name).all()

                # Cost by model
                model_costs = session.query(
                    CostTracking.model_used,
                    func.sum(CostTracking.cost).label('cost')
                ).filter_by(project_id=project_id).group_by(CostTracking.model_used).all()

                return {
                    "total_cost": float(totals.total_cost or 0),
                    "total_input_tokens": int(totals.total_input_tokens or 0),
                    "total_output_tokens": int(totals.total_output_tokens or 0),
                    "cost_by_agent": {agent: float(cost) for agent, cost in agent_costs},
                    "cost_by_model": {model: float(cost) for model, cost in model_costs if model}
                }

        except Exception as e:
            logger.error(f"Failed to get cost summary: {e}")
            return {
                "total_cost": 0.0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "cost_by_agent": {},
                "cost_by_model": {}
            }

    async def get_cost_analysis(self, project_id: str) -> Dict[str, Any]:
        """Get detailed cost analysis for a project."""
        try:
            with self.get_session() as session:
                # Get all cost records
                costs = session.query(CostTracking).filter_by(
                    project_id=project_id
                ).order_by(CostTracking.created_at).all()

                # Get summary
                summary = await self.get_cost_summary(project_id)

                # Build timeline
                timeline = []
                cumulative_cost = 0.0
                for cost in costs:
                    cumulative_cost += cost.cost
                    timeline.append({
                        "timestamp": cost.created_at.isoformat(),
                        "agent": cost.agent_name,
                        "operation": cost.operation,
                        "cost": cost.cost,
                        "cumulative_cost": cumulative_cost
                    })

                return {
                    "summary": summary,
                    "timeline": timeline,
                    "total_operations": len(costs)
                }

        except Exception as e:
            logger.error(f"Failed to get cost analysis: {e}")
            return {
                "summary": await self.get_cost_summary(project_id),
                "timeline": [],
                "total_operations": 0
            }

    # ==================== Resume and Progress ====================

    async def resume_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete project state for resumption.

        Args:
            project_id: Project UUID

        Returns:
            Complete project state including sections and costs
        """
        try:
            with self.get_session() as session:
                # Get project
                project = session.query(Project).filter_by(id=project_id).first()
                if not project:
                    return None

                # Get all milestones
                milestones = session.query(Milestone).filter_by(
                    project_id=project_id
                ).order_by(Milestone.created_at).all()

                # Get all sections
                sections = session.query(Section).filter_by(
                    project_id=project_id
                ).order_by(Section.section_index).all()

                # Get cost summary
                cost_summary = await self.get_cost_summary(project_id)

                # Determine next step
                milestone_types = [m.type for m in milestones]
                next_step = self._determine_next_step(milestone_types)

                # Calculate progress
                progress = self._calculate_progress(milestones, sections)

                return {
                    "project": project.to_dict(),
                    "milestones": {m.type: m.to_dict() for m in milestones},
                    "sections": [s.to_dict() for s in sections],
                    "cost_summary": cost_summary,
                    "next_step": next_step,
                    "progress": progress
                }

        except Exception as e:
            logger.error(f"Failed to resume project {project_id}: {e}")
            return None

    async def get_progress(self, project_id: str) -> Dict[str, Any]:
        """Get project progress information."""
        try:
            with self.get_session() as session:
                # Get milestones
                milestones = session.query(Milestone).filter_by(
                    project_id=project_id
                ).all()

                # Get sections
                sections = session.query(Section).filter_by(
                    project_id=project_id
                ).all()

                return self._calculate_progress(milestones, sections)

        except Exception as e:
            logger.error(f"Failed to get progress: {e}")
            return {
                "percentage": 0,
                "milestones": {},
                "sections": {"completed": 0, "total": 0}
            }

    def _determine_next_step(self, milestone_types: List[str]) -> str:
        """Determine the next step based on completed milestones."""
        if not milestone_types:
            return "upload_files"
        elif MilestoneType.FILES_UPLOADED.value in milestone_types and \
             MilestoneType.OUTLINE_GENERATED.value not in milestone_types:
            return "generate_outline"
        elif MilestoneType.OUTLINE_GENERATED.value in milestone_types and \
             MilestoneType.DRAFT_COMPLETED.value not in milestone_types:
            return "generate_draft"
        elif MilestoneType.DRAFT_COMPLETED.value in milestone_types and \
             MilestoneType.BLOG_REFINED.value not in milestone_types:
            return "refine_blog"
        elif MilestoneType.BLOG_REFINED.value in milestone_types and \
             MilestoneType.SOCIAL_GENERATED.value not in milestone_types:
            return "generate_social"
        else:
            return "completed"

    def _calculate_progress(self, milestones: List, sections: List) -> Dict[str, Any]:
        """Calculate overall progress percentage."""
        # Milestone progress (50% of total)
        total_milestones = 5  # Total possible milestones
        completed_milestones = len(milestones)
        milestone_progress = (completed_milestones / total_milestones) * 50

        # Section progress (50% of total)
        if sections:
            completed_sections = sum(1 for s in sections if s.status == SectionStatus.COMPLETED.value)
            section_progress = (completed_sections / len(sections)) * 50
        else:
            section_progress = 0

        # Milestone status
        milestone_status = {}
        for mt in MilestoneType:
            milestone_status[mt.value] = {
                "completed": any(m.type == mt.value for m in milestones)
            }

        return {
            "percentage": int(milestone_progress + section_progress),
            "milestones": milestone_status,
            "sections": {
                "completed": sum(1 for s in sections if s.status == SectionStatus.COMPLETED.value),
                "total": len(sections)
            }
        }

    # ==================== Blog Completion ====================

    async def save_completed_blog(self, project_id: str, title: str, content: str,
                                 word_count: int, total_cost: float,
                                 generation_time: int, metadata: Dict = None) -> bool:
        """Save a completed blog."""
        try:
            with self.get_session() as session:
                # Check if already exists
                existing = session.query(CompletedBlog).filter_by(
                    project_id=project_id
                ).first()

                if existing:
                    # Update existing
                    existing.title = title
                    existing.final_content = content
                    existing.word_count = word_count
                    existing.total_cost = total_cost
                    existing.generation_time_seconds = generation_time
                    existing.version += 1
                    existing.project_metadata = metadata or {}
                else:
                    # Create new
                    blog = CompletedBlog(
                        project_id=project_id,
                        title=title,
                        final_content=content,
                        word_count=word_count,
                        total_cost=total_cost,
                        generation_time_seconds=generation_time,
                        metadata=metadata or {}
                    )
                    session.add(blog)

                # Update project completed_at
                project = session.query(Project).filter_by(id=project_id).first()
                if project:
                    project.completed_at = datetime.now()

            logger.info(f"Saved completed blog for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save completed blog: {e}")
            return False

    # ==================== Export Operations ====================

    async def export_project(self, project_id: str, format: str = "json") -> Optional[Any]:
        """
        Export project data in specified format.

        Args:
            project_id: Project UUID
            format: Export format (json, markdown)

        Returns:
            Exported data or None on error
        """
        try:
            # Get full project state
            project_state = await self.resume_project(project_id)
            if not project_state:
                return None

            if format == "json":
                return project_state

            elif format == "markdown":
                # Build markdown content
                md_content = []
                project = project_state["project"]
                md_content.append(f"# {project.get('name', 'Untitled Project')}\n")
                md_content.append(f"**Project ID**: {project_id}\n")
                md_content.append(f"**Created**: {project.get('created_at', 'Unknown')}\n")
                md_content.append(f"**Status**: {project.get('status', 'Unknown')}\n")
                md_content.append(f"**Total Cost**: ${project_state['cost_summary']['total_cost']:.4f}\n\n")

                # Add refined blog content if available
                refined_milestone = project_state["milestones"].get(MilestoneType.BLOG_REFINED.value)
                if refined_milestone:
                    content = refined_milestone.get("data", {}).get("refined_content", "")
                    md_content.append(content)
                else:
                    # Try draft content
                    draft_milestone = project_state["milestones"].get(MilestoneType.DRAFT_COMPLETED.value)
                    if draft_milestone:
                        content = draft_milestone.get("data", {}).get("compiled_blog", "")
                        md_content.append(content)

                return "\n".join(md_content)

            else:
                logger.error(f"Unsupported export format: {format}")
                return None

        except Exception as e:
            logger.error(f"Failed to export project {project_id}: {e}")
            return None

    # ==================== Update Metadata ====================

    async def update_metadata(self, project_id: str, metadata: Dict[str, Any]) -> bool:
        """Update project metadata."""
        try:
            async with await self._get_lock(project_id):
                with self.get_session() as session:
                    project = session.query(Project).filter_by(id=project_id).first()
                    if not project:
                        return False

                    # Merge metadata
                    current_metadata = project.project_metadata or {}
                    current_metadata.update(metadata)
                    project.project_metadata = current_metadata
                    project.updated_at = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Failed to update metadata for project {project_id}: {e}")
            return False