# ABOUTME: Comprehensive test suite for SQL-based project management functionality
# ABOUTME: Tests CRUD operations, section management, cost tracking, and concurrency

"""
Test suite for SQLProjectManager and related SQL functionality.
"""

import pytest
import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
import uuid

from root.backend.services.sql_project_manager import (
    SQLProjectManager, MilestoneType, ProjectStatus, SectionStatus
)
from root.backend.models.database import get_db_manager


@pytest.fixture
async def sql_manager():
    """Create a test SQLProjectManager with temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        manager = SQLProjectManager(f"sqlite:///{tmp.name}")
        yield manager
        # Cleanup handled by tempfile


@pytest.fixture
async def sample_project(sql_manager):
    """Create a sample project for testing."""
    project_id = await sql_manager.create_project(
        project_name="Test Project",
        metadata={"test": True, "model": "test-model"}
    )
    return project_id


class TestProjectCRUD:
    """Test project CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_project(self, sql_manager):
        """Test creating a new project."""
        project_id = await sql_manager.create_project(
            project_name="Test Blog",
            metadata={"author": "test"}
        )

        assert project_id is not None
        assert isinstance(project_id, str)
        assert len(project_id) == 36  # UUID length

        # Verify project was created
        project = await sql_manager.get_project(project_id)
        assert project is not None
        assert project["name"] == "Test Blog"
        assert project["status"] == "active"
        assert project["metadata"]["author"] == "test"

    @pytest.mark.asyncio
    async def test_get_project_by_name(self, sql_manager):
        """Test retrieving project by name."""
        project_id = await sql_manager.create_project("Unique Name")

        project = await sql_manager.get_project_by_name("Unique Name")
        assert project is not None
        assert project["id"] == project_id
        assert project["name"] == "Unique Name"

    @pytest.mark.asyncio
    async def test_list_projects(self, sql_manager):
        """Test listing projects with filtering."""
        # Create multiple projects
        id1 = await sql_manager.create_project("Project 1")
        id2 = await sql_manager.create_project("Project 2")
        id3 = await sql_manager.create_project("Project 3")

        # Archive one project
        await sql_manager.archive_project(id2)

        # List active projects
        active_projects = await sql_manager.list_projects(status=ProjectStatus.ACTIVE)
        assert len(active_projects) == 2
        active_ids = [p["id"] for p in active_projects]
        assert id1 in active_ids
        assert id3 in active_ids
        assert id2 not in active_ids

        # List archived projects
        archived_projects = await sql_manager.list_projects(status=ProjectStatus.ARCHIVED)
        assert len(archived_projects) == 1
        assert archived_projects[0]["id"] == id2

    @pytest.mark.asyncio
    async def test_archive_project(self, sql_manager, sample_project):
        """Test archiving a project."""
        success = await sql_manager.archive_project(sample_project)
        assert success is True

        # Verify project is archived
        project = await sql_manager.get_project(sample_project)
        assert project["status"] == "archived"
        assert project["archived_at"] is not None

    @pytest.mark.asyncio
    async def test_delete_project(self, sql_manager, sample_project):
        """Test soft and permanent deletion."""
        # Soft delete
        success = await sql_manager.delete_project(sample_project, permanent=False)
        assert success is True

        project = await sql_manager.get_project(sample_project)
        assert project["status"] == "deleted"

        # Create another project for permanent deletion
        project_id = await sql_manager.create_project("To Delete")
        success = await sql_manager.delete_project(project_id, permanent=True)
        assert success is True

        # Should not exist
        project = await sql_manager.get_project(project_id)
        assert project is None


class TestMilestoneOperations:
    """Test milestone management."""

    @pytest.mark.asyncio
    async def test_save_milestone(self, sql_manager, sample_project):
        """Test saving and loading milestones."""
        # Save files uploaded milestone
        files_data = {
            "files": ["file1.md", "file2.ipynb"],
            "total_size": 1024
        }
        success = await sql_manager.save_milestone(
            sample_project,
            MilestoneType.FILES_UPLOADED,
            files_data,
            metadata={"upload_time": "2024-01-01"}
        )
        assert success is True

        # Load milestone
        milestone = await sql_manager.load_milestone(
            sample_project,
            MilestoneType.FILES_UPLOADED
        )
        assert milestone is not None
        assert milestone["type"] == "files_uploaded"
        assert milestone["data"]["files"] == ["file1.md", "file2.ipynb"]
        assert milestone["metadata"]["upload_time"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_update_milestone(self, sql_manager, sample_project):
        """Test updating existing milestone."""
        # Save initial milestone
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.OUTLINE_GENERATED,
            {"sections": 3}
        )

        # Update with new data
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.OUTLINE_GENERATED,
            {"sections": 5, "difficulty": "intermediate"}
        )

        # Verify update
        milestone = await sql_manager.load_milestone(
            sample_project,
            MilestoneType.OUTLINE_GENERATED
        )
        assert milestone["data"]["sections"] == 5
        assert milestone["data"]["difficulty"] == "intermediate"

    @pytest.mark.asyncio
    async def test_get_latest_milestone(self, sql_manager, sample_project):
        """Test getting the most recent milestone."""
        # Save milestones in order
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.FILES_UPLOADED,
            {"files": []}
        )
        await asyncio.sleep(0.1)  # Ensure different timestamps

        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.OUTLINE_GENERATED,
            {"outline": "test"}
        )

        # Get latest
        latest = await sql_manager.get_latest_milestone(sample_project)
        assert latest is not None
        assert latest["type"] == "outline_generated"


class TestSectionManagement:
    """Test section-level operations."""

    @pytest.mark.asyncio
    async def test_save_sections(self, sql_manager, sample_project):
        """Test batch saving sections."""
        sections = [
            {
                "section_index": 0,
                "title": "Introduction",
                "content": "Welcome to the blog",
                "status": "completed",
                "cost_delta": 0.001,
                "input_tokens": 100,
                "output_tokens": 200
            },
            {
                "section_index": 1,
                "title": "Main Content",
                "content": "This is the main section",
                "status": "generating",
                "cost_delta": 0.002,
                "input_tokens": 150,
                "output_tokens": 300
            }
        ]

        success = await sql_manager.save_sections(sample_project, sections)
        assert success is True

        # Load sections
        loaded = await sql_manager.load_sections(sample_project)
        assert len(loaded) == 2
        assert loaded[0]["title"] == "Introduction"
        assert loaded[0]["status"] == "completed"
        assert loaded[1]["title"] == "Main Content"
        assert loaded[1]["cost_delta"] == 0.002

    @pytest.mark.asyncio
    async def test_update_section_status(self, sql_manager, sample_project):
        """Test updating individual section status."""
        # Save initial sections
        sections = [
            {"section_index": 0, "title": "Intro", "status": "pending"},
            {"section_index": 1, "title": "Body", "status": "pending"}
        ]
        await sql_manager.save_sections(sample_project, sections)

        # Update status
        success = await sql_manager.update_section_status(
            sample_project,
            section_index=0,
            status="completed",
            cost_delta=0.005
        )
        assert success is True

        # Verify update
        loaded = await sql_manager.load_sections(sample_project)
        assert loaded[0]["status"] == "completed"
        assert loaded[0]["cost_delta"] == 0.005
        assert loaded[1]["status"] == "pending"  # Unchanged

    @pytest.mark.asyncio
    async def test_section_atomicity(self, sql_manager, sample_project):
        """Test atomic section updates."""
        # Save initial sections
        initial = [
            {"section_index": 0, "title": "A", "content": "Content A"},
            {"section_index": 1, "title": "B", "content": "Content B"}
        ]
        await sql_manager.save_sections(sample_project, initial)

        # Replace with new sections atomically
        new = [
            {"section_index": 0, "title": "X", "content": "Content X"},
            {"section_index": 1, "title": "Y", "content": "Content Y"},
            {"section_index": 2, "title": "Z", "content": "Content Z"}
        ]
        await sql_manager.save_sections(sample_project, new)

        # Verify complete replacement
        loaded = await sql_manager.load_sections(sample_project)
        assert len(loaded) == 3
        assert loaded[0]["title"] == "X"
        assert loaded[1]["title"] == "Y"
        assert loaded[2]["title"] == "Z"


class TestCostTracking:
    """Test cost tracking functionality."""

    @pytest.mark.asyncio
    async def test_track_cost(self, sql_manager, sample_project):
        """Test recording operation costs."""
        # Track multiple operations
        await sql_manager.track_cost(
            sample_project,
            agent_name="OutlineGenerator",
            operation="generate_outline",
            input_tokens=500,
            output_tokens=1000,
            cost=0.015,
            model_used="gpt-4"
        )

        await sql_manager.track_cost(
            sample_project,
            agent_name="BlogDraftGenerator",
            operation="generate_section",
            input_tokens=1000,
            output_tokens=2000,
            cost=0.030,
            model_used="gpt-4"
        )

        # Get summary
        summary = await sql_manager.get_cost_summary(sample_project)
        assert summary["total_cost"] == 0.045
        assert summary["total_input_tokens"] == 1500
        assert summary["total_output_tokens"] == 3000
        assert summary["cost_by_agent"]["OutlineGenerator"] == 0.015
        assert summary["cost_by_agent"]["BlogDraftGenerator"] == 0.030
        assert summary["cost_by_model"]["gpt-4"] == 0.045

    @pytest.mark.asyncio
    async def test_cost_analysis(self, sql_manager, sample_project):
        """Test detailed cost analysis."""
        # Track operations over time
        for i in range(3):
            await sql_manager.track_cost(
                sample_project,
                agent_name=f"Agent{i}",
                operation=f"op{i}",
                input_tokens=100 * (i + 1),
                output_tokens=200 * (i + 1),
                cost=0.01 * (i + 1),
                model_used="test-model"
            )

        # Get analysis
        analysis = await sql_manager.get_cost_analysis(sample_project)
        assert analysis["total_operations"] == 3
        assert len(analysis["timeline"]) == 3

        # Check cumulative costs
        timeline = analysis["timeline"]
        assert timeline[0]["cumulative_cost"] == 0.01
        assert timeline[1]["cumulative_cost"] == 0.03  # 0.01 + 0.02
        assert timeline[2]["cumulative_cost"] == 0.06  # 0.01 + 0.02 + 0.03


class TestProjectResume:
    """Test project resume and progress functionality."""

    @pytest.mark.asyncio
    async def test_resume_project(self, sql_manager, sample_project):
        """Test complete project state restoration."""
        # Set up project state
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.FILES_UPLOADED,
            {"files": ["test.md"]}
        )
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.OUTLINE_GENERATED,
            {"sections": ["intro", "body", "conclusion"]}
        )

        sections = [
            {"section_index": 0, "title": "Intro", "status": "completed"},
            {"section_index": 1, "title": "Body", "status": "completed"},
            {"section_index": 2, "title": "Conclusion", "status": "pending"}
        ]
        await sql_manager.save_sections(sample_project, sections)

        await sql_manager.track_cost(
            sample_project, "test", "test", 100, 200, 0.003
        )

        # Resume project
        state = await sql_manager.resume_project(sample_project)
        assert state is not None
        assert state["project"]["id"] == sample_project
        assert len(state["milestones"]) == 2
        assert len(state["sections"]) == 3
        assert state["cost_summary"]["total_cost"] == 0.003
        assert state["next_step"] == "generate_draft"
        assert state["progress"]["percentage"] == 46  # 2 milestones + 2 completed sections

    @pytest.mark.asyncio
    async def test_progress_calculation(self, sql_manager, sample_project):
        """Test progress percentage calculation."""
        # No progress initially
        progress = await sql_manager.get_progress(sample_project)
        assert progress["percentage"] == 0

        # Add milestones (50% of total progress)
        await sql_manager.save_milestone(
            sample_project, MilestoneType.FILES_UPLOADED, {}
        )
        await sql_manager.save_milestone(
            sample_project, MilestoneType.OUTLINE_GENERATED, {}
        )

        progress = await sql_manager.get_progress(sample_project)
        assert progress["percentage"] == 20  # 2/5 milestones * 50%

        # Add sections (other 50% of progress)
        sections = [
            {"section_index": 0, "status": "completed"},
            {"section_index": 1, "status": "completed"},
            {"section_index": 2, "status": "pending"},
            {"section_index": 3, "status": "pending"}
        ]
        await sql_manager.save_sections(sample_project, sections)

        progress = await sql_manager.get_progress(sample_project)
        assert progress["percentage"] == 45  # 20% (milestones) + 25% (2/4 sections * 50%)


class TestCompletedBlog:
    """Test completed blog tracking."""

    @pytest.mark.asyncio
    async def test_save_completed_blog(self, sql_manager, sample_project):
        """Test saving and updating completed blog."""
        # Save blog
        success = await sql_manager.save_completed_blog(
            sample_project,
            title="My Test Blog",
            content="This is the final blog content...",
            word_count=500,
            total_cost=0.125,
            generation_time=300,
            metadata={"keywords": ["test", "blog"]}
        )
        assert success is True

        # Verify project marked as completed
        project = await sql_manager.get_project(sample_project)
        assert project["completed_at"] is not None

        # Update blog (version should increment)
        success = await sql_manager.save_completed_blog(
            sample_project,
            title="My Updated Blog",
            content="This is the updated content...",
            word_count=600,
            total_cost=0.150,
            generation_time=350,
            metadata={"keywords": ["test", "blog", "updated"]}
        )
        assert success is True


class TestConcurrency:
    """Test concurrent operations and locking."""

    @pytest.mark.asyncio
    async def test_concurrent_section_updates(self, sql_manager, sample_project):
        """Test that concurrent section updates don't conflict."""
        async def update_sections(suffix: str):
            sections = [
                {"section_index": 0, "title": f"Title {suffix}"},
                {"section_index": 1, "title": f"Title {suffix}"}
            ]
            await sql_manager.save_sections(sample_project, sections)

        # Run concurrent updates
        await asyncio.gather(
            update_sections("A"),
            update_sections("B"),
            update_sections("C")
        )

        # Verify one set won (no corruption)
        sections = await sql_manager.load_sections(sample_project)
        assert len(sections) == 2
        # All sections should have the same suffix (atomic replacement)
        suffix = sections[0]["title"].split()[-1]
        assert all(s["title"].endswith(suffix) for s in sections)

    @pytest.mark.asyncio
    async def test_project_lock_isolation(self, sql_manager):
        """Test that locks are per-project."""
        project1 = await sql_manager.create_project("Project 1")
        project2 = await sql_manager.create_project("Project 2")

        # These should run in parallel without blocking
        start = datetime.now()
        await asyncio.gather(
            sql_manager.save_sections(project1, [{"section_index": 0}]),
            sql_manager.save_sections(project2, [{"section_index": 0}])
        )
        duration = (datetime.now() - start).total_seconds()

        # Should complete quickly (parallel execution)
        assert duration < 0.5  # Both operations together should be fast


class TestExportOperations:
    """Test project export functionality."""

    @pytest.mark.asyncio
    async def test_export_json(self, sql_manager, sample_project):
        """Test exporting project as JSON."""
        # Set up some data
        await sql_manager.save_milestone(
            sample_project, MilestoneType.OUTLINE_GENERATED, {"test": "data"}
        )

        # Export
        data = await sql_manager.export_project(sample_project, format="json")
        assert data is not None
        assert data["project"]["id"] == sample_project
        assert "milestones" in data
        assert "sections" in data
        assert "cost_summary" in data

    @pytest.mark.asyncio
    async def test_export_markdown(self, sql_manager, sample_project):
        """Test exporting project as Markdown."""
        # Set up refined blog
        await sql_manager.save_milestone(
            sample_project,
            MilestoneType.BLOG_REFINED,
            {"refined_content": "# Final Blog\n\nThis is the content."}
        )

        # Export
        content = await sql_manager.export_project(sample_project, format="markdown")
        assert content is not None
        assert isinstance(content, str)
        assert "Final Blog" in content
        assert "This is the content" in content


class TestBackwardCompatibility:
    """Test backward compatibility features."""

    @pytest.mark.asyncio
    async def test_get_project_by_name_or_id(self, sql_manager):
        """Test that both name and ID lookups work."""
        project_id = await sql_manager.create_project("Unique Project Name")

        # Lookup by ID
        project1 = await sql_manager.get_project(project_id)
        assert project1 is not None

        # Lookup by name
        project2 = await sql_manager.get_project_by_name("Unique Project Name")
        assert project2 is not None

        # Should be the same project
        assert project1["id"] == project2["id"]

    @pytest.mark.asyncio
    async def test_metadata_updates(self, sql_manager, sample_project):
        """Test metadata merge functionality."""
        # Initial metadata
        await sql_manager.update_metadata(
            sample_project,
            {"key1": "value1", "key2": "value2"}
        )

        # Update with new keys (should merge)
        await sql_manager.update_metadata(
            sample_project,
            {"key2": "updated", "key3": "value3"}
        )

        # Verify merge
        project = await sql_manager.get_project(sample_project)
        metadata = project["metadata"]
        assert metadata["key1"] == "value1"  # Preserved
        assert metadata["key2"] == "updated"  # Updated
        assert metadata["key3"] == "value3"  # Added
        assert metadata["test"] is True  # From fixture