# ABOUTME: Database models and schema for SQL-based project management system
# ABOUTME: Defines SQLAlchemy ORM models for projects, milestones, sections, cost tracking, and completed blogs

"""
Database models for the project management system using SQLAlchemy ORM.
"""

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Text,
    DateTime, ForeignKey, Index, UniqueConstraint, JSON, Boolean
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()


class Project(Base):
    """Core project tracking table."""
    __tablename__ = 'projects'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    status = Column(String(50), default='active')  # active, archived, deleted
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    archived_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    project_metadata = Column(JSON, default=dict)

    # Relationships
    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="project", cascade="all, delete-orphan")
    cost_tracking = relationship("CostTracking", back_populates="project", cascade="all, delete-orphan")
    completed_blog = relationship("CompletedBlog", back_populates="project", uselist=False)

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.project_metadata or {}
        }


class Milestone(Base):
    """Milestone tracking table for workflow stages."""
    __tablename__ = 'milestones'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False)  # files_uploaded, outline_generated, etc.
    created_at = Column(DateTime, default=func.current_timestamp())
    data = Column(JSON, default=dict)
    project_metadata = Column(JSON, default=dict)

    # Relationships
    project = relationship("Project", back_populates="milestones")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_project_milestone', 'project_id', 'type'),
    )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "type": self.type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "data": self.data or {},
            "metadata": self.project_metadata or {}
        }


class Section(Base):
    """Section-level persistence for blog content."""
    __tablename__ = 'sections'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    section_index = Column(Integer, nullable=False)
    title = Column(String(255))
    content = Column(Text)
    status = Column(String(50), default='pending')  # pending, generating, completed, failed
    cost_delta = Column(Float, default=0.0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    # Relationships
    project = relationship("Project", back_populates="sections")

    # Constraints
    __table_args__ = (
        UniqueConstraint('project_id', 'section_index', name='uq_project_section'),
    )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "section_index": self.section_index,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "cost_delta": self.cost_delta,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class CostTracking(Base):
    """Granular cost tracking per operation."""
    __tablename__ = 'cost_tracking'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    agent_name = Column(String(100))
    operation = Column(String(100))
    model_used = Column(String(100))
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    created_at = Column(DateTime, default=func.current_timestamp())
    project_metadata = Column(JSON, default=dict)

    # Relationships
    project = relationship("Project", back_populates="cost_tracking")

    # Index for efficient queries
    __table_args__ = (
        Index('idx_project_costs', 'project_id', 'created_at'),
    )

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "agent_name": self.agent_name,
            "operation": self.operation,
            "model_used": self.model_used,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost": self.cost,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.project_metadata or {}
        }


class CompletedBlog(Base):
    """Tracking for completed blogs."""
    __tablename__ = 'completed_blogs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String(36), ForeignKey('projects.id'), nullable=False)
    title = Column(String(255))
    final_content = Column(Text)
    word_count = Column(Integer)
    total_cost = Column(Float)
    generation_time_seconds = Column(Integer)
    published_url = Column(String(500))
    status = Column(String(50), default='draft')  # draft, published, archived
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=func.current_timestamp())
    published_at = Column(DateTime, nullable=True)
    project_metadata = Column(JSON, default=dict)

    # Relationships
    project = relationship("Project", back_populates="completed_blog")

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "word_count": self.word_count,
            "total_cost": self.total_cost,
            "generation_time_seconds": self.generation_time_seconds,
            "published_url": self.published_url,
            "status": self.status,
            "version": self.version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "metadata": self.project_metadata or {}
        }


class DatabaseManager:
    """Manager class for database operations."""

    def __init__(self, db_url="sqlite:///data/projects.db"):
        """Initialize database connection."""
        import os
        from pathlib import Path

        # If using default SQLite database, ensure it's in root/data
        if db_url == "sqlite:///data/projects.db":
            # Get the root directory (two levels up from backend/models/)
            root_dir = Path(__file__).parent.parent.parent
            db_path = root_dir / "data" / "projects.db"
            db_url = f"sqlite:///{db_path.absolute()}"

        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all tables in the database."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self):
        """Drop all tables in the database."""
        Base.metadata.drop_all(bind=self.engine)

    def get_session(self):
        """Get a new database session."""
        return self.SessionLocal()

    def init_database(self):
        """Initialize database with tables."""
        import os
        from pathlib import Path

        # Get the root directory and ensure data directory exists
        root_dir = Path(__file__).parent.parent.parent
        db_path = root_dir / "data" / "projects.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create tables
        self.create_tables()
        print(f"Database initialized at {db_path.absolute()}")


# Singleton instance
_db_manager = None

def get_db_manager(db_url="sqlite:///data/projects.db"):
    """Get or create database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_url)
    return _db_manager