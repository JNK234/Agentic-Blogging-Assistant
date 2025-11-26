# ABOUTME: Supabase-based project manager service with section persistence and cost tracking
# ABOUTME: Mirrors SQLProjectManager API using Supabase PostgreSQL backend for scalable cloud storage

"""
Supabase-based ProjectManager service for persistent project tracking.
"""

import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json

from backend.config.supabase_client import get_supabase_client

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


class SupabaseProjectManager:
    """
    Supabase-based project lifecycle and milestone tracking.

    Features:
    - Section-level persistence with batch operations
    - Granular cost tracking per operation
    - Atomic operations with per-project locking
    - Full state hydration for project resume
    - Cloud-based PostgreSQL storage via Supabase
    """

    def __init__(self):
        """
        Initialize SupabaseProjectManager with Supabase client.
        """
        self.supabase = get_supabase_client()
        self.project_locks = {}  # Per-project async locks
        logger.info("SupabaseProjectManager initialized")

    async def _get_lock(self, project_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific project."""
        if project_id not in self.project_locks:
            self.project_locks[project_id] = asyncio.Lock()
        return self.project_locks[project_id]

    def _convert_uuid_to_str(self, data: Any) -> Any:
        """
        Convert UUID objects to strings recursively.

        Args:
            data: Data that may contain UUID objects

        Returns:
            Data with UUIDs converted to strings
        """
        if isinstance(data, dict):
            return {k: self._convert_uuid_to_str(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_uuid_to_str(item) for item in data]
        elif hasattr(data, '__class__') and data.__class__.__name__ == 'UUID':
            return str(data)
        else:
            return data

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[str]:
        """
        Parse and validate ISO timestamp string.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            Validated timestamp string or None
        """
        if not timestamp_str:
            return None
        try:
            # Validate it's a proper ISO format
            datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return timestamp_str
        except (ValueError, AttributeError):
            return None

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
            project_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()

            result = self.supabase.table("projects").insert({
                "id": project_id,
                "name": project_name,
                "status": ProjectStatus.ACTIVE.value,
                "metadata": metadata or {},
                "created_at": now,
                "updated_at": now
            }).execute()

            if not result.data:
                raise Exception("Failed to create project: no data returned")

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
            result = self.supabase.table("projects").select("*").eq("id", project_id).execute()

            if not result.data:
                logger.warning(f"Project {project_id} not found")
                return None

            project = result.data[0]
            # Convert UUIDs to strings and format for API compatibility
            project = self._convert_uuid_to_str(project)

            return {
                "id": project.get("id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "created_at": self._parse_timestamp(project.get("created_at")),
                "updated_at": self._parse_timestamp(project.get("updated_at")),
                "archived_at": self._parse_timestamp(project.get("archived_at")),
                "completed_at": self._parse_timestamp(project.get("completed_at")),
                "metadata": project.get("metadata", {})
            }

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
            result = self.supabase.table("projects").select("*").eq(
                "name", project_name
            ).eq("status", ProjectStatus.ACTIVE.value).execute()

            if not result.data:
                return None

            project = result.data[0]
            project = self._convert_uuid_to_str(project)

            return {
                "id": project.get("id"),
                "name": project.get("name"),
                "status": project.get("status"),
                "created_at": self._parse_timestamp(project.get("created_at")),
                "updated_at": self._parse_timestamp(project.get("updated_at")),
                "archived_at": self._parse_timestamp(project.get("archived_at")),
                "completed_at": self._parse_timestamp(project.get("completed_at")),
                "metadata": project.get("metadata", {})
            }

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
            query = self.supabase.table("projects").select("*")

            if status:
                # Support both string and enum values
                status_value = status if isinstance(status, str) else status.value
                query = query.eq("status", status_value)

            result = query.order("updated_at", desc=True).execute()

            projects = []
            for p in result.data:
                p = self._convert_uuid_to_str(p)
                projects.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "status": p.get("status"),
                    "created_at": self._parse_timestamp(p.get("created_at")),
                    "updated_at": self._parse_timestamp(p.get("updated_at")),
                    "archived_at": self._parse_timestamp(p.get("archived_at")),
                    "completed_at": self._parse_timestamp(p.get("completed_at")),
                    "metadata": p.get("metadata", {})
                })

            return projects

        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
            return []

    async def archive_project(self, project_id: str) -> bool:
        """Archive a project."""
        try:
            async with await self._get_lock(project_id):
                now = datetime.utcnow().isoformat()

                result = self.supabase.table("projects").update({
                    "status": ProjectStatus.ARCHIVED.value,
                    "archived_at": now
                }).eq("id", project_id).execute()

                if not result.data:
                    return False

            logger.info(f"Archived project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive project {project_id}: {e}")
            return False

    async def delete_project(self, project_id: str, permanent: bool = False) -> bool:
        """Delete or soft-delete a project."""
        try:
            async with await self._get_lock(project_id):
                if permanent:
                    result = self.supabase.table("projects").delete().eq("id", project_id).execute()
                    logger.info(f"Permanently deleted project {project_id}")
                else:
                    result = self.supabase.table("projects").update({
                        "status": ProjectStatus.DELETED.value
                    }).eq("id", project_id).execute()
                    logger.info(f"Soft deleted project {project_id}")

                if not result.data:
                    return False

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
                # Check if project exists
                project_result = self.supabase.table("projects").select("id").eq("id", project_id).execute()
                if not project_result.data:
                    logger.error(f"Project {project_id} not found")
                    return False

                # Check if milestone already exists
                existing_result = self.supabase.table("milestones").select("*").eq(
                    "project_id", project_id
                ).eq("type", milestone_type.value).execute()

                now = datetime.utcnow().isoformat()

                if existing_result.data:
                    # Update existing milestone
                    self.supabase.table("milestones").update({
                        "data": data,
                        "metadata": metadata or {},
                        "created_at": now
                    }).eq("project_id", project_id).eq("type", milestone_type.value).execute()
                else:
                    # Create new milestone
                    self.supabase.table("milestones").insert({
                        "project_id": project_id,
                        "type": milestone_type.value,
                        "data": data,
                        "metadata": metadata or {},
                        "created_at": now
                    }).execute()

                # Update project's updated_at
                self.supabase.table("projects").update({
                    "updated_at": now
                }).eq("id", project_id).execute()

            logger.info(f"Saved milestone {milestone_type.value} for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save milestone for project {project_id}: {e}")
            return False

    async def load_milestone(self, project_id: str, milestone_type: MilestoneType) -> Optional[Dict[str, Any]]:
        """Load a specific milestone for a project."""
        try:
            result = self.supabase.table("milestones").select("*").eq(
                "project_id", project_id
            ).eq("type", milestone_type.value).execute()

            if not result.data:
                logger.warning(f"Milestone {milestone_type.value} not found for project {project_id}")
                return None

            milestone = result.data[0]
            milestone = self._convert_uuid_to_str(milestone)

            return {
                "id": milestone.get("id"),
                "project_id": milestone.get("project_id"),
                "type": milestone.get("type"),
                "created_at": self._parse_timestamp(milestone.get("created_at")),
                "data": milestone.get("data", {}),
                "metadata": milestone.get("metadata", {})
            }

        except Exception as e:
            logger.error(f"Failed to load milestone for project {project_id}: {e}")
            return None

    async def get_latest_milestone(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest milestone for a project."""
        try:
            result = self.supabase.table("milestones").select("*").eq(
                "project_id", project_id
            ).order("created_at", desc=True).limit(1).execute()

            if not result.data:
                return None

            milestone = result.data[0]
            milestone = self._convert_uuid_to_str(milestone)

            return {
                "id": milestone.get("id"),
                "project_id": milestone.get("project_id"),
                "type": milestone.get("type"),
                "created_at": self._parse_timestamp(milestone.get("created_at")),
                "data": milestone.get("data", {}),
                "metadata": milestone.get("metadata", {})
            }

        except Exception as e:
            logger.error(f"Failed to get latest milestone for project {project_id}: {e}")
            return None

    async def get_milestones(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all milestones for a project."""
        try:
            result = self.supabase.table("milestones").select("*").eq(
                "project_id", project_id
            ).order("created_at").execute()

            milestones = []
            for m in result.data:
                m = self._convert_uuid_to_str(m)
                milestones.append({
                    "id": m.get("id"),
                    "project_id": m.get("project_id"),
                    "type": m.get("type"),
                    "created_at": self._parse_timestamp(m.get("created_at")),
                    "data": m.get("data", {}),
                    "metadata": m.get("metadata", {})
                })

            return milestones

        except Exception as e:
            logger.error(f"Failed to get milestones for project {project_id}: {e}")
            return []

    # ==================== Section Management ====================

    async def save_sections(self, project_id: str, sections: List[Dict[str, Any]]) -> bool:
        """
        Batch update all sections using upsert for transaction safety.

        Args:
            project_id: Project UUID
            sections: List of section dictionaries

        Returns:
            Success boolean
        """
        try:
            async with await self._get_lock(project_id):
                # Build section records for upsert
                section_records = []
                for section_data in sections:
                    record = {
                        "project_id": project_id,
                        "section_index": section_data.get('section_index'),
                        "title": section_data.get('title'),
                        "content": section_data.get('content'),
                        "status": section_data.get('status', SectionStatus.PENDING.value),
                        "cost_delta": section_data.get('cost_delta', 0.0),
                        "input_tokens": section_data.get('input_tokens', 0),
                        "output_tokens": section_data.get('output_tokens', 0),
                        "updated_at": datetime.utcnow().isoformat()
                    }
                    # Add outline_hash if provided (for version tracking)
                    if section_data.get('outline_hash'):
                        record["outline_hash"] = section_data.get('outline_hash')
                    section_records.append(record)

                if section_records:
                    # Upsert sections - if (project_id, section_index) exists, update; otherwise insert
                    # This is safer than delete-then-insert as it won't lose data on partial failure
                    self.supabase.table("sections").upsert(
                        section_records,
                        on_conflict="project_id,section_index"
                    ).execute()

                # Delete sections that are no longer in the list
                current_indices = [s.get('section_index') for s in sections if s.get('section_index') is not None]
                if current_indices:
                    # Get existing sections
                    existing = self.supabase.table("sections").select("section_index").eq(
                        "project_id", project_id
                    ).execute()
                    existing_indices = [s.get('section_index') for s in existing.data]

                    # Delete sections not in current list
                    indices_to_delete = [i for i in existing_indices if i not in current_indices]
                    for idx in indices_to_delete:
                        self.supabase.table("sections").delete().eq(
                            "project_id", project_id
                        ).eq("section_index", idx).execute()

                # Update project's updated_at
                now = datetime.utcnow().isoformat()
                self.supabase.table("projects").update({
                    "updated_at": now
                }).eq("id", project_id).execute()

            logger.info(f"Saved {len(sections)} sections for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save sections for project {project_id}: {e}")
            return False

    async def load_sections(self, project_id: str) -> List[Dict[str, Any]]:
        """Load all sections for a project."""
        try:
            result = self.supabase.table("sections").select("*").eq(
                "project_id", project_id
            ).order("section_index").execute()

            sections = []
            for s in result.data:
                s = self._convert_uuid_to_str(s)
                sections.append({
                    "id": s.get("id"),
                    "project_id": s.get("project_id"),
                    "section_index": s.get("section_index"),
                    "title": s.get("title"),
                    "content": s.get("content"),
                    "status": s.get("status"),
                    "cost_delta": s.get("cost_delta", 0.0),
                    "input_tokens": s.get("input_tokens", 0),
                    "output_tokens": s.get("output_tokens", 0),
                    "updated_at": self._parse_timestamp(s.get("updated_at"))
                })

            return sections

        except Exception as e:
            logger.error(f"Failed to load sections for project {project_id}: {e}")
            return []

    async def update_section_status(self, project_id: str, section_index: int,
                                   status: str, cost_delta: float = None) -> bool:
        """Update status of a specific section."""
        try:
            # Validate status is a valid SectionStatus value
            valid_statuses = [s.value for s in SectionStatus]
            if status not in valid_statuses:
                logger.error(f"Invalid section status: {status}. Valid values: {valid_statuses}")
                return False

            async with await self._get_lock(project_id):
                update_data = {
                    "status": status,
                    "updated_at": datetime.utcnow().isoformat()
                }

                if cost_delta is not None:
                    update_data["cost_delta"] = cost_delta

                result = self.supabase.table("sections").update(update_data).eq(
                    "project_id", project_id
                ).eq("section_index", section_index).execute()

                if not result.data:
                    logger.error(f"Section {section_index} not found for project {project_id}")
                    return False

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
            # Validate project exists before tracking cost
            project = await self.get_project(project_id)
            if not project:
                logger.error(f"Cannot track cost for non-existent project: {project_id}")
                return False

            self.supabase.table("cost_tracking").insert({
                "project_id": project_id,
                "agent_name": agent_name,
                "operation": operation,
                "model_used": model_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost": cost,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }).execute()

            logger.info(f"Tracked cost ${cost:.6f} for {agent_name}/{operation} in project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to track cost: {e}")
            return False

    async def get_cost_summary(self, project_id: str) -> Dict[str, Any]:
        """Get cost summary for a project."""
        try:
            # Get all cost records for the project
            result = self.supabase.table("cost_tracking").select("*").eq(
                "project_id", project_id
            ).execute()

            if not result.data:
                return {
                    "total_cost": 0.0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "cost_by_agent": {},
                    "cost_by_model": {}
                }

            # Calculate totals
            total_cost = 0.0
            total_input_tokens = 0
            total_output_tokens = 0
            cost_by_agent = {}
            cost_by_model = {}

            for record in result.data:
                cost_val = float(record.get("cost", 0.0))
                total_cost += cost_val
                total_input_tokens += record.get("input_tokens", 0)
                total_output_tokens += record.get("output_tokens", 0)

                # Aggregate by agent
                agent = record.get("agent_name")
                if agent:
                    cost_by_agent[agent] = cost_by_agent.get(agent, 0.0) + cost_val

                # Aggregate by model
                model = record.get("model_used")
                if model:
                    cost_by_model[model] = cost_by_model.get(model, 0.0) + cost_val

            return {
                "total_cost": total_cost,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "cost_by_agent": cost_by_agent,
                "cost_by_model": cost_by_model
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
            # Get all cost records
            result = self.supabase.table("cost_tracking").select("*").eq(
                "project_id", project_id
            ).order("created_at").execute()

            # Get summary
            summary = await self.get_cost_summary(project_id)

            # Build timeline
            timeline = []
            cumulative_cost = 0.0
            for cost_record in result.data:
                cumulative_cost += cost_record.get("cost", 0.0)
                timeline.append({
                    "timestamp": self._parse_timestamp(cost_record.get("created_at")),
                    "agent": cost_record.get("agent_name"),
                    "operation": cost_record.get("operation"),
                    "cost": cost_record.get("cost", 0.0),
                    "cumulative_cost": cumulative_cost
                })

            return {
                "summary": summary,
                "timeline": timeline,
                "total_operations": len(result.data)
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
            # Get project
            project = await self.get_project(project_id)
            if not project:
                return None

            # Get all milestones
            milestones_list = await self.get_milestones(project_id)
            milestones = {m["type"]: m for m in milestones_list}

            # Get all sections
            sections = await self.load_sections(project_id)

            # Get cost summary
            cost_summary = await self.get_cost_summary(project_id)

            # Determine next step
            milestone_types = [m["type"] for m in milestones_list]
            next_step = self._determine_next_step(milestone_types)

            # Calculate progress
            progress = self._calculate_progress(milestones_list, sections)

            return {
                "project": project,
                "milestones": milestones,
                "sections": sections,
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
            # Get milestones
            milestones_list = await self.get_milestones(project_id)

            # Get sections
            sections = await self.load_sections(project_id)

            return self._calculate_progress(milestones_list, sections)

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

        # Convert to set for O(1) lookup performance
        milestone_set = set(milestone_types)

        if MilestoneType.FILES_UPLOADED.value in milestone_set and \
             MilestoneType.OUTLINE_GENERATED.value not in milestone_set:
            return "generate_outline"
        elif MilestoneType.OUTLINE_GENERATED.value in milestone_set and \
             MilestoneType.DRAFT_COMPLETED.value not in milestone_set:
            return "generate_draft"
        elif MilestoneType.DRAFT_COMPLETED.value in milestone_set and \
             MilestoneType.BLOG_REFINED.value not in milestone_set:
            return "refine_blog"
        elif MilestoneType.BLOG_REFINED.value in milestone_set and \
             MilestoneType.SOCIAL_GENERATED.value not in milestone_set:
            return "generate_social"
        else:
            return "completed"

    def _calculate_progress(self, milestones: List[Dict], sections: List[Dict]) -> Dict[str, Any]:
        """Calculate overall progress percentage."""
        # Milestone progress (50% of total)
        total_milestones = 5  # Total possible milestones
        completed_milestones = len(milestones)
        milestone_progress = (completed_milestones / total_milestones) * 50

        # Section progress (50% of total)
        if sections:
            completed_sections = sum(1 for s in sections if s.get("status") == SectionStatus.COMPLETED.value)
            section_progress = (completed_sections / len(sections)) * 50
        else:
            section_progress = 0

        # Milestone status
        milestone_status = {}
        milestone_types = [m.get("type") for m in milestones]
        for mt in MilestoneType:
            milestone_status[mt.value] = {
                "completed": mt.value in milestone_types
            }

        return {
            "percentage": int(milestone_progress + section_progress),
            "milestones": milestone_status,
            "sections": {
                "completed": sum(1 for s in sections if s.get("status") == SectionStatus.COMPLETED.value),
                "total": len(sections)
            }
        }

    # ==================== Blog Completion ====================

    async def save_completed_blog(self, project_id: str, title: str, content: str,
                                 word_count: int, total_cost: float,
                                 generation_time: int, metadata: Dict = None) -> bool:
        """Save a completed blog."""
        try:
            # Check if already exists
            existing_result = self.supabase.table("completed_blogs").select("*").eq(
                "project_id", project_id
            ).execute()

            now = datetime.utcnow().isoformat()

            if existing_result.data:
                # Update existing
                existing = existing_result.data[0]
                self.supabase.table("completed_blogs").update({
                    "title": title,
                    "final_content": content,
                    "word_count": word_count,
                    "total_cost": total_cost,
                    "generation_time_seconds": generation_time,
                    "version": existing.get("version", 1) + 1,
                    "metadata": metadata or {}
                }).eq("project_id", project_id).execute()
            else:
                # Create new
                self.supabase.table("completed_blogs").insert({
                    "project_id": project_id,
                    "title": title,
                    "final_content": content,
                    "word_count": word_count,
                    "total_cost": total_cost,
                    "generation_time_seconds": generation_time,
                    "metadata": metadata or {},
                    "created_at": now
                }).execute()

            # Update project completed_at
            self.supabase.table("projects").update({
                "completed_at": now
            }).eq("id", project_id).execute()

            logger.info(f"Saved completed blog for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save completed blog: {e}")
            return False

    # ==================== Export Operations ====================

    async def export_project_json(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Export project data in JSON format.

        Args:
            project_id: Project UUID

        Returns:
            Project data dict or None on error
        """
        try:
            # Get full project state
            project_state = await self.resume_project(project_id)
            return project_state

        except Exception as e:
            logger.error(f"Failed to export project {project_id} as JSON: {e}")
            return None

    async def export_project_markdown(self, project_id: str) -> Optional[str]:
        """
        Export project data in Markdown format.

        Args:
            project_id: Project UUID

        Returns:
            Markdown string or None on error
        """
        try:
            # Get full project state
            project_state = await self.resume_project(project_id)
            if not project_state:
                return None

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

        except Exception as e:
            logger.error(f"Failed to export project {project_id} as markdown: {e}")
            return None

    async def export_project(self, project_id: str, format: str = "json") -> Optional[Any]:
        """
        Export project data in specified format.

        Args:
            project_id: Project UUID
            format: Export format (json, markdown)

        Returns:
            Exported data or None on error
        """
        if format == "json":
            return await self.export_project_json(project_id)
        elif format == "markdown":
            return await self.export_project_markdown(project_id)
        else:
            logger.error(f"Unsupported export format: {format}")
            return None

    # ==================== Update Metadata ====================

    async def update_metadata(self, project_id: str, metadata: Dict[str, Any]) -> bool:
        """Update project metadata."""
        try:
            async with await self._get_lock(project_id):
                # Get current project
                project = await self.get_project(project_id)
                if not project:
                    return False

                # Merge metadata
                current_metadata = project.get("metadata", {})
                current_metadata.update(metadata)

                # Update project
                self.supabase.table("projects").update({
                    "metadata": current_metadata,
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("id", project_id).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to update metadata for project {project_id}: {e}")
            return False
