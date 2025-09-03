# ABOUTME: ProjectManager service for persistent project tracking and milestone management
# ABOUTME: Handles project lifecycle from creation to export with filesystem-based storage

import os
import json
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

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


class ProjectManager:
    """
    Manages project lifecycle and milestone tracking with filesystem-based persistence.
    
    Features:
    - Create/load/delete projects
    - Save/load milestones at each stage
    - Atomic write operations for data safety
    - Export projects in multiple formats
    - Project resumption from any milestone
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize ProjectManager with base directory for project storage.
        
        Args:
            base_dir: Base directory path for project storage. 
                     Defaults to root/data/projects/
        """
        if base_dir is None:
            # Default to root/data/projects/
            current_dir = Path(__file__).parent.parent.parent  # Go up to root/
            self.base_dir = current_dir / "data" / "projects"
        else:
            self.base_dir = Path(base_dir)
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ProjectManager initialized with base directory: {self.base_dir}")
    
    def _get_project_path(self, project_id: str) -> Path:
        """Get the directory path for a specific project."""
        return self.base_dir / project_id
    
    def _atomic_write(self, file_path: Path, data: Any) -> None:
        """
        Atomically write JSON data to file using temp file + rename.
        
        Args:
            file_path: Target file path
            data: Data to serialize as JSON
        """
        # Write to temporary file first
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix='.tmp_',
            suffix='.json'
        )
        
        try:
            # Write data to temp file
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Atomically rename temp file to target
            Path(temp_path).replace(file_path)
            
        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except:
                pass
            raise e
    
    def create_project(self, project_name: str, metadata: Dict[str, Any] = None) -> str:
        """
        Create a new project with unique ID.
        
        Args:
            project_name: Human-readable project name
            metadata: Optional metadata (model, persona, etc.)
        
        Returns:
            Project ID (UUID string)
        """
        try:
            # Generate unique project ID
            project_id = str(uuid.uuid4())
            project_path = self._get_project_path(project_id)
            
            # Create project directory
            project_path.mkdir(parents=True, exist_ok=True)
            
            # Create project metadata
            project_data = {
                "id": project_id,
                "name": project_name,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "status": ProjectStatus.ACTIVE.value,
                "current_milestone": None,
                "milestones": {},
                "metadata": metadata or {}
            }
            
            # Save project.json
            project_file = project_path / "project.json"
            self._atomic_write(project_file, project_data)
            
            logger.info(f"Created project {project_name} with ID {project_id}")
            return project_id
            
        except Exception as e:
            logger.error(f"Failed to create project {project_name}: {e}")
            raise
    
    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load project data by ID.
        
        Args:
            project_id: Project UUID
        
        Returns:
            Project data dict or None if not found
        """
        try:
            project_path = self._get_project_path(project_id)
            project_file = project_path / "project.json"
            
            if not project_file.exists():
                logger.warning(f"Project {project_id} not found")
                return None
            
            with open(project_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            return None
    
    def list_projects(self, status: Optional[ProjectStatus] = None) -> List[Dict[str, Any]]:
        """
        List all projects, optionally filtered by status.
        
        Args:
            status: Optional status filter
        
        Returns:
            List of project summaries
        """
        projects = []
        
        try:
            for project_dir in self.base_dir.iterdir():
                if not project_dir.is_dir():
                    continue
                
                project_file = project_dir / "project.json"
                if not project_file.exists():
                    continue
                
                try:
                    with open(project_file, 'r') as f:
                        project_data = json.load(f)
                    
                    # Apply status filter if provided
                    if status and project_data.get("status") != status.value:
                        continue
                    
                    # Create summary
                    projects.append({
                        "id": project_data.get("id"),
                        "name": project_data.get("name"),
                        "created_at": project_data.get("created_at"),
                        "updated_at": project_data.get("updated_at"),
                        "status": project_data.get("status"),
                        "current_milestone": project_data.get("current_milestone")
                    })
                    
                except Exception as e:
                    logger.warning(f"Could not read project {project_dir.name}: {e}")
            
            # Sort by updated_at, newest first
            projects.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to list projects: {e}")
        
        return projects
    
    def save_milestone(self, project_id: str, milestone_type: MilestoneType, 
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
            # Load project
            project_data = self.get_project(project_id)
            if not project_data:
                logger.error(f"Project {project_id} not found")
                return False
            
            project_path = self._get_project_path(project_id)
            
            # Prepare milestone data
            milestone_data = {
                "type": milestone_type.value,
                "created_at": datetime.now().isoformat(),
                "data": data,
                "metadata": metadata or {}
            }
            
            # Save milestone file
            milestone_file = project_path / f"{milestone_type.value}.json"
            self._atomic_write(milestone_file, milestone_data)
            
            # Update project metadata
            project_data["updated_at"] = datetime.now().isoformat()
            project_data["current_milestone"] = milestone_type.value
            project_data["milestones"][milestone_type.value] = {
                "saved_at": milestone_data["created_at"],
                "file": f"{milestone_type.value}.json"
            }
            
            # Save updated project.json
            project_file = project_path / "project.json"
            self._atomic_write(project_file, project_data)
            
            logger.info(f"Saved milestone {milestone_type.value} for project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save milestone for project {project_id}: {e}")
            return False
    
    def load_milestone(self, project_id: str, milestone_type: MilestoneType) -> Optional[Dict[str, Any]]:
        """
        Load a specific milestone for a project.
        
        Args:
            project_id: Project UUID
            milestone_type: Type of milestone to load
        
        Returns:
            Milestone data or None if not found
        """
        try:
            project_path = self._get_project_path(project_id)
            milestone_file = project_path / f"{milestone_type.value}.json"
            
            if not milestone_file.exists():
                logger.warning(f"Milestone {milestone_type.value} not found for project {project_id}")
                return None
            
            with open(milestone_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Failed to load milestone for project {project_id}: {e}")
            return None
    
    def get_latest_milestone(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest milestone for a project.
        
        Args:
            project_id: Project UUID
        
        Returns:
            Latest milestone data or None
        """
        try:
            project_data = self.get_project(project_id)
            if not project_data:
                return None
            
            current_milestone = project_data.get("current_milestone")
            if not current_milestone:
                return None
            
            # Load the milestone data
            milestone_type = MilestoneType(current_milestone)
            return self.load_milestone(project_id, milestone_type)
            
        except Exception as e:
            logger.error(f"Failed to get latest milestone for project {project_id}: {e}")
            return None
    
    def delete_project(self, project_id: str, permanent: bool = False) -> bool:
        """
        Delete or soft-delete a project.
        
        Args:
            project_id: Project UUID
            permanent: If True, permanently delete files. If False, mark as deleted.
        
        Returns:
            Success boolean
        """
        try:
            project_path = self._get_project_path(project_id)
            
            if permanent:
                # Permanently delete project directory
                if project_path.exists():
                    shutil.rmtree(project_path)
                    logger.info(f"Permanently deleted project {project_id}")
                return True
            else:
                # Soft delete - just update status
                project_data = self.get_project(project_id)
                if not project_data:
                    return False
                
                project_data["status"] = ProjectStatus.DELETED.value
                project_data["updated_at"] = datetime.now().isoformat()
                
                project_file = project_path / "project.json"
                self._atomic_write(project_file, project_data)
                
                logger.info(f"Soft deleted project {project_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete project {project_id}: {e}")
            return False
    
    def archive_project(self, project_id: str) -> bool:
        """
        Archive a project (mark as archived).
        
        Args:
            project_id: Project UUID
        
        Returns:
            Success boolean
        """
        try:
            project_data = self.get_project(project_id)
            if not project_data:
                return False
            
            project_data["status"] = ProjectStatus.ARCHIVED.value
            project_data["updated_at"] = datetime.now().isoformat()
            project_data["archived_at"] = datetime.now().isoformat()
            
            project_path = self._get_project_path(project_id)
            project_file = project_path / "project.json"
            self._atomic_write(project_file, project_data)
            
            logger.info(f"Archived project {project_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to archive project {project_id}: {e}")
            return False
    
    def export_project(self, project_id: str, format: str = "json") -> Optional[Any]:
        """
        Export project data in specified format.
        
        Args:
            project_id: Project UUID
            format: Export format (json, markdown, zip)
        
        Returns:
            Exported data or None on error
        """
        try:
            project_data = self.get_project(project_id)
            if not project_data:
                return None
            
            if format == "json":
                # Export complete project data as JSON
                export_data = {
                    "project": project_data,
                    "milestones": {}
                }
                
                # Load all milestones
                for milestone_type in MilestoneType:
                    milestone_data = self.load_milestone(project_id, milestone_type)
                    if milestone_data:
                        export_data["milestones"][milestone_type.value] = milestone_data
                
                return export_data
            
            elif format == "markdown":
                # Export as formatted Markdown
                md_content = []
                md_content.append(f"# {project_data.get('name', 'Untitled Project')}\n")
                md_content.append(f"**Project ID**: {project_id}\n")
                md_content.append(f"**Created**: {project_data.get('created_at', 'Unknown')}\n")
                md_content.append(f"**Status**: {project_data.get('status', 'Unknown')}\n\n")
                
                # Add refined blog content if available
                refined_milestone = self.load_milestone(project_id, MilestoneType.BLOG_REFINED)
                if refined_milestone:
                    content = refined_milestone.get("data", {}).get("refined_content", "")
                    md_content.append(content)
                else:
                    # Try draft content
                    draft_milestone = self.load_milestone(project_id, MilestoneType.DRAFT_COMPLETED)
                    if draft_milestone:
                        content = draft_milestone.get("data", {}).get("compiled_blog", "")
                        md_content.append(content)
                
                return "\n".join(md_content)
            
            elif format == "zip":
                # Create ZIP archive of project directory
                import zipfile
                from io import BytesIO
                
                buffer = BytesIO()
                project_path = self._get_project_path(project_id)
                
                with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file_path in project_path.rglob('*'):
                        if file_path.is_file():
                            arc_name = file_path.relative_to(project_path)
                            zf.write(file_path, arc_name)
                
                buffer.seek(0)
                return buffer.getvalue()
            
            else:
                logger.error(f"Unsupported export format: {format}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to export project {project_id}: {e}")
            return None
    
    def resume_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get project state for resumption.
        
        Args:
            project_id: Project UUID
        
        Returns:
            Resume data including project info and latest milestone
        """
        try:
            project_data = self.get_project(project_id)
            if not project_data:
                return None
            
            # Get latest milestone
            latest_milestone = self.get_latest_milestone(project_id)
            
            # Prepare resume data
            resume_data = {
                "project": project_data,
                "latest_milestone": latest_milestone,
                "next_step": self._determine_next_step(project_data)
            }
            
            return resume_data
            
        except Exception as e:
            logger.error(f"Failed to resume project {project_id}: {e}")
            return None
    
    def _determine_next_step(self, project_data: Dict[str, Any]) -> str:
        """
        Determine the next step based on current milestone.
        
        Args:
            project_data: Project metadata
        
        Returns:
            Next step identifier
        """
        current_milestone = project_data.get("current_milestone")
        
        if not current_milestone:
            return "upload_files"
        elif current_milestone == MilestoneType.FILES_UPLOADED.value:
            return "generate_outline"
        elif current_milestone == MilestoneType.OUTLINE_GENERATED.value:
            return "generate_draft"
        elif current_milestone == MilestoneType.DRAFT_COMPLETED.value:
            return "refine_blog"
        elif current_milestone == MilestoneType.BLOG_REFINED.value:
            return "generate_social"
        else:
            return "completed"
    
    def update_metadata(self, project_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update project metadata.
        
        Args:
            project_id: Project UUID
            metadata: Metadata to merge with existing
        
        Returns:
            Success boolean
        """
        try:
            project_data = self.get_project(project_id)
            if not project_data:
                return False
            
            # Merge metadata
            project_data["metadata"].update(metadata)
            project_data["updated_at"] = datetime.now().isoformat()
            
            # Save updated project
            project_path = self._get_project_path(project_id)
            project_file = project_path / "project.json"
            self._atomic_write(project_file, project_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update metadata for project {project_id}: {e}")
            return False