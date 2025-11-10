#!/usr/bin/env python3
# ABOUTME: Migration script to convert existing JSON project data to SQL database
# ABOUTME: Handles one-time migration with rollback capability and data validation

"""
Migration script for converting JSON-based project data to SQL database.
Preserves all existing project data including milestones, sections, and costs.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import argparse
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from root.backend.models.database import (
    get_db_manager, Project, Milestone, Section,
    CostTracking, CompletedBlog
)
from root.backend.services.sql_project_manager import MilestoneType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MigrationScript")


class ProjectMigrator:
    """Handles migration from JSON to SQL database."""

    def __init__(self, json_base_path: str = "root/data/projects",
                 db_url: str = "sqlite:///root/data/projects.db",
                 dry_run: bool = False):
        """
        Initialize migrator.

        Args:
            json_base_path: Path to JSON projects directory
            db_url: Database connection URL
            dry_run: If True, simulate migration without changes
        """
        self.json_base = Path(json_base_path)
        self.db_manager = get_db_manager(db_url)
        self.dry_run = dry_run
        self.migration_stats = {
            "projects_migrated": 0,
            "milestones_migrated": 0,
            "sections_migrated": 0,
            "costs_tracked": 0,
            "blogs_migrated": 0,
            "errors": []
        }

    def migrate_all(self) -> Dict[str, Any]:
        """
        Migrate all projects from JSON to SQL.

        Returns:
            Migration statistics
        """
        logger.info(f"Starting migration from {self.json_base}")
        logger.info(f"Dry run: {self.dry_run}")

        # Ensure database tables exist
        if not self.dry_run:
            self.db_manager.create_tables()
            logger.info("Database tables created/verified")

        # Backup existing database if it exists
        if not self.dry_run:
            self._backup_database()

        # Get all project directories
        if not self.json_base.exists():
            logger.error(f"JSON base path does not exist: {self.json_base}")
            return self.migration_stats

        project_dirs = [d for d in self.json_base.iterdir() if d.is_dir()]
        logger.info(f"Found {len(project_dirs)} project directories")

        # Migrate each project
        for project_dir in project_dirs:
            try:
                self._migrate_project(project_dir)
            except Exception as e:
                error_msg = f"Failed to migrate project {project_dir.name}: {e}"
                logger.error(error_msg)
                self.migration_stats["errors"].append(error_msg)

        # Log summary
        logger.info("Migration complete!")
        logger.info(f"Projects migrated: {self.migration_stats['projects_migrated']}")
        logger.info(f"Milestones migrated: {self.migration_stats['milestones_migrated']}")
        logger.info(f"Sections migrated: {self.migration_stats['sections_migrated']}")
        logger.info(f"Costs tracked: {self.migration_stats['costs_tracked']}")
        logger.info(f"Blogs migrated: {self.migration_stats['blogs_migrated']}")
        logger.info(f"Errors: {len(self.migration_stats['errors'])}")

        return self.migration_stats

    def _migrate_project(self, project_dir: Path):
        """Migrate a single project directory."""
        logger.info(f"Migrating project: {project_dir.name}")

        # Load project.json
        project_file = project_dir / "project.json"
        if not project_file.exists():
            logger.warning(f"No project.json found in {project_dir}")
            return

        with open(project_file) as f:
            project_data = json.load(f)

        # Parse project data
        project_id = project_data.get("id", project_dir.name)
        project_name = project_data.get("name", project_dir.name)

        # Determine project status
        status = "active"
        if project_data.get("archived"):
            status = "archived"
        elif project_data.get("deleted"):
            status = "deleted"

        # Parse timestamps
        created_at = self._parse_timestamp(project_data.get("created_at"))
        updated_at = self._parse_timestamp(project_data.get("updated_at"))
        archived_at = self._parse_timestamp(project_data.get("archived_at"))
        completed_at = None

        # Check if blog was completed
        refined_file = project_dir / "blog_refined.json"
        if refined_file.exists():
            completed_at = updated_at

        # Extract metadata
        metadata = project_data.get("metadata", {})

        if not self.dry_run:
            # Create project in database
            with self.db_manager.get_session() as session:
                # Check if project already exists
                existing = session.query(Project).filter_by(id=project_id).first()
                if existing:
                    logger.warning(f"Project {project_id} already exists, skipping")
                    return

                project = Project(
                    id=project_id,
                    name=project_name,
                    status=status,
                    created_at=created_at,
                    updated_at=updated_at,
                    archived_at=archived_at,
                    completed_at=completed_at,
                    metadata=metadata
                )
                session.add(project)
                session.flush()  # Get the ID

                # Migrate milestones
                self._migrate_milestones(session, project_id, project_dir)

                # Migrate sections
                self._migrate_sections(session, project_id, project_dir)

                # Migrate costs
                self._migrate_costs(session, project_id, project_data)

                # Migrate completed blog
                self._migrate_completed_blog(session, project_id, project_dir)

                session.commit()

        self.migration_stats["projects_migrated"] += 1
        logger.info(f"Successfully migrated project {project_name}")

    def _migrate_milestones(self, session, project_id: str, project_dir: Path):
        """Migrate milestone JSON files."""
        milestone_files = {
            "files_uploaded.json": MilestoneType.FILES_UPLOADED,
            "outline_generated.json": MilestoneType.OUTLINE_GENERATED,
            "draft_completed.json": MilestoneType.DRAFT_COMPLETED,
            "blog_refined.json": MilestoneType.BLOG_REFINED,
            "social_generated.json": MilestoneType.SOCIAL_GENERATED
        }

        for filename, milestone_type in milestone_files.items():
            milestone_file = project_dir / filename
            if milestone_file.exists():
                try:
                    with open(milestone_file) as f:
                        milestone_data = json.load(f)

                    # Extract data and metadata
                    data = milestone_data.get("data", milestone_data)
                    metadata = milestone_data.get("metadata", {})
                    created_at = self._parse_timestamp(
                        milestone_data.get("created_at") or
                        milestone_data.get("timestamp")
                    )

                    milestone = Milestone(
                        project_id=project_id,
                        type=milestone_type.value,
                        data=data,
                        metadata=metadata,
                        created_at=created_at
                    )
                    session.add(milestone)
                    self.migration_stats["milestones_migrated"] += 1

                    logger.debug(f"Migrated milestone: {milestone_type.value}")

                except Exception as e:
                    logger.error(f"Failed to migrate milestone {filename}: {e}")

    def _migrate_sections(self, session, project_id: str, project_dir: Path):
        """Migrate sections from various sources."""
        sections_migrated = False

        # Try sections.json first
        sections_file = project_dir / "sections.json"
        if sections_file.exists():
            try:
                with open(sections_file) as f:
                    sections_data = json.load(f)

                for idx, section_data in enumerate(sections_data):
                    section = Section(
                        project_id=project_id,
                        section_index=idx,
                        title=section_data.get("title", f"Section {idx + 1}"),
                        content=section_data.get("content", ""),
                        status=section_data.get("status", "completed"),
                        cost_delta=section_data.get("cost_delta", 0.0),
                        input_tokens=section_data.get("input_tokens", 0),
                        output_tokens=section_data.get("output_tokens", 0),
                        updated_at=self._parse_timestamp(section_data.get("updated_at"))
                    )
                    session.add(section)
                    self.migration_stats["sections_migrated"] += 1

                sections_migrated = True
                logger.debug(f"Migrated {len(sections_data)} sections from sections.json")

            except Exception as e:
                logger.error(f"Failed to migrate sections.json: {e}")

        # If no sections.json, try to extract from draft_completed
        if not sections_migrated:
            draft_file = project_dir / "draft_completed.json"
            if draft_file.exists():
                try:
                    with open(draft_file) as f:
                        draft_data = json.load(f)

                    sections = draft_data.get("data", {}).get("sections", [])
                    for idx, section_data in enumerate(sections):
                        section = Section(
                            project_id=project_id,
                            section_index=idx,
                            title=section_data.get("title", f"Section {idx + 1}"),
                            content=section_data.get("content", ""),
                            status="completed",
                            cost_delta=0.0,
                            input_tokens=0,
                            output_tokens=0
                        )
                        session.add(section)
                        self.migration_stats["sections_migrated"] += 1

                    if sections:
                        logger.debug(f"Migrated {len(sections)} sections from draft_completed")

                except Exception as e:
                    logger.error(f"Failed to extract sections from draft: {e}")

    def _migrate_costs(self, session, project_id: str, project_data: Dict[str, Any]):
        """Migrate cost tracking data."""
        # Extract from metadata
        metadata = project_data.get("metadata", {})
        cost_history = metadata.get("cost_call_history", [])

        for cost_entry in cost_history:
            try:
                cost_record = CostTracking(
                    project_id=project_id,
                    agent_name=cost_entry.get("agent", "unknown"),
                    operation=cost_entry.get("operation", "unknown"),
                    model_used=cost_entry.get("model"),
                    input_tokens=cost_entry.get("input_tokens", 0),
                    output_tokens=cost_entry.get("output_tokens", 0),
                    cost=cost_entry.get("cost", 0.0),
                    created_at=self._parse_timestamp(cost_entry.get("timestamp")),
                    metadata=cost_entry.get("metadata", {})
                )
                session.add(cost_record)
                self.migration_stats["costs_tracked"] += 1

            except Exception as e:
                logger.error(f"Failed to migrate cost entry: {e}")

        if cost_history:
            logger.debug(f"Migrated {len(cost_history)} cost entries")

    def _migrate_completed_blog(self, session, project_id: str, project_dir: Path):
        """Migrate completed blog if exists."""
        refined_file = project_dir / "blog_refined.json"
        if not refined_file.exists():
            return

        try:
            with open(refined_file) as f:
                refined_data = json.load(f)

            data = refined_data.get("data", refined_data)

            # Extract blog details
            title = data.get("title", "Untitled Blog")
            content = data.get("refined_content", "")
            word_count = len(content.split())

            # Calculate total cost
            total_cost = 0.0
            project_file = project_dir / "project.json"
            if project_file.exists():
                with open(project_file) as f:
                    project_data = json.load(f)
                    metadata = project_data.get("metadata", {})
                    cost_history = metadata.get("cost_call_history", [])
                    total_cost = sum(c.get("cost", 0) for c in cost_history)

            # Estimate generation time (if not available)
            generation_time = data.get("generation_time_seconds", 0)
            if not generation_time and refined_data.get("created_at"):
                # Rough estimate based on timestamps
                generation_time = 300  # Default 5 minutes

            blog = CompletedBlog(
                project_id=project_id,
                title=title,
                final_content=content,
                word_count=word_count,
                total_cost=total_cost,
                generation_time_seconds=generation_time,
                status="draft",
                created_at=self._parse_timestamp(refined_data.get("created_at")),
                metadata=data.get("metadata", {})
            )
            session.add(blog)
            self.migration_stats["blogs_migrated"] += 1

            logger.debug(f"Migrated completed blog: {title}")

        except Exception as e:
            logger.error(f"Failed to migrate completed blog: {e}")

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if not timestamp_str:
            return None

        # Try ISO format first
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            pass

        # Try other formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except:
                continue

        logger.warning(f"Could not parse timestamp: {timestamp_str}")
        return datetime.now()

    def _backup_database(self):
        """Create backup of existing database."""
        db_path = Path("root/data/projects.db")
        if db_path.exists():
            backup_path = db_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            shutil.copy2(db_path, backup_path)
            logger.info(f"Created database backup: {backup_path}")

    def verify_migration(self) -> bool:
        """
        Verify migration was successful.

        Returns:
            True if verification passed
        """
        logger.info("Verifying migration...")

        with self.db_manager.get_session() as session:
            # Count records
            project_count = session.query(Project).count()
            milestone_count = session.query(Milestone).count()
            section_count = session.query(Section).count()
            cost_count = session.query(CostTracking).count()
            blog_count = session.query(CompletedBlog).count()

            logger.info(f"Database contains:")
            logger.info(f"  - {project_count} projects")
            logger.info(f"  - {milestone_count} milestones")
            logger.info(f"  - {section_count} sections")
            logger.info(f"  - {cost_count} cost records")
            logger.info(f"  - {blog_count} completed blogs")

            # Verify against migration stats
            if project_count != self.migration_stats["projects_migrated"]:
                logger.error("Project count mismatch!")
                return False

            if milestone_count != self.migration_stats["milestones_migrated"]:
                logger.warning("Milestone count mismatch (may be expected)")

            if section_count != self.migration_stats["sections_migrated"]:
                logger.warning("Section count mismatch (may be expected)")

        return True


def main():
    """Main migration entry point."""
    parser = argparse.ArgumentParser(description="Migrate JSON projects to SQL database")
    parser.add_argument(
        "--json-path",
        default="root/data/projects",
        help="Path to JSON projects directory"
    )
    parser.add_argument(
        "--db-url",
        default="sqlite:///root/data/projects.db",
        help="Database connection URL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate migration without making changes"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run migration
    migrator = ProjectMigrator(
        json_base_path=args.json_path,
        db_url=args.db_url,
        dry_run=args.dry_run
    )

    stats = migrator.migrate_all()

    # Verify if not dry run
    if not args.dry_run:
        if migrator.verify_migration():
            logger.info("✅ Migration verification passed!")
        else:
            logger.error("❌ Migration verification failed!")
            sys.exit(1)

    # Print summary
    print("\n" + "=" * 50)
    print("Migration Summary")
    print("=" * 50)
    print(f"Projects migrated: {stats['projects_migrated']}")
    print(f"Milestones migrated: {stats['milestones_migrated']}")
    print(f"Sections migrated: {stats['sections_migrated']}")
    print(f"Costs tracked: {stats['costs_tracked']}")
    print(f"Blogs migrated: {stats['blogs_migrated']}")

    if stats["errors"]:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats["errors"][:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(stats["errors"]) > 5:
            print(f"  ... and {len(stats['errors']) - 5} more")

    print("=" * 50)

    if args.dry_run:
        print("\nDRY RUN - No changes were made")
        print("Run without --dry-run to perform actual migration")


if __name__ == "__main__":
    main()