# ABOUTME: SQLAlchemy models for AI sessions, process graphs, tags, and history.
# Defines database schema with relationships and indexes for efficient queries.

"""
SQLAlchemy models for OpenEO AI storage.

Extends the existing PostgreSQL schema with tables for:
- AI sessions and conversation history
- Saved process graphs library
- Tags for organization
- Execution history for analytics
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, Integer,
    ForeignKey, JSON, Table, Index, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


# Association table for many-to-many relationship between process graphs and tags
process_graph_tags = Table(
    'process_graph_tags',
    Base.metadata,
    Column('process_graph_id', UUID(as_uuid=True), ForeignKey('saved_process_graphs.id'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('tags.id'), primary_key=True)
)


class AISession(Base):
    """
    AI conversation session.

    Stores conversation context and history for each user session.
    """
    __tablename__ = 'ai_sessions'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    messages: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    execution_history: Mapped[List["ExecutionHistory"]] = relationship(
        "ExecutionHistory",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_ai_sessions_user_updated', 'user_id', 'updated_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "title": self.title,
            "context": self.context,
            "messages": self.messages,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active
        }


class SavedProcessGraph(Base):
    """
    Saved process graph for reuse.

    Allows users to save, share, and reuse process graphs.
    """
    __tablename__ = 'saved_process_graphs'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    process_graph: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    tags: Mapped[List["Tag"]] = relationship(
        "Tag",
        secondary=process_graph_tags,
        back_populates="process_graphs"
    )

    __table_args__ = (
        Index('ix_saved_process_graphs_user_name', 'user_id', 'name'),
        Index('ix_saved_process_graphs_public', 'is_public'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "process_graph": self.process_graph,
            "is_public": self.is_public,
            "use_count": self.use_count,
            "tags": [tag.name for tag in self.tags],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class Tag(Base):
    """
    Tag for organizing process graphs.
    """
    __tablename__ = 'tags'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    process_graphs: Mapped[List["SavedProcessGraph"]] = relationship(
        "SavedProcessGraph",
        secondary=process_graph_tags,
        back_populates="tags"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat()
        }


class SavedResult(Base):
    """
    Permanently saved job result for later retrieval.

    Stores metadata about saved GeoTIFF results and their visualization settings.
    Files are stored on disk at ~/.openeo_jobs/results/{save_id}/.
    """
    __tablename__ = 'saved_results'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    save_id: Mapped[str] = mapped_column(String(8), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    result_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bounds: Mapped[Optional[List]] = mapped_column(JSON, nullable=True)
    colormap: Mapped[str] = mapped_column(String(50), nullable=False, default="viridis")
    vmin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vmax: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    __table_args__ = (
        Index('ix_saved_results_created', 'created_at'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "save_id": self.save_id,
            "title": self.title,
            "result_path": self.result_path,
            "original_path": self.original_path,
            "bounds": self.bounds,
            "colormap": self.colormap,
            "vmin": self.vmin,
            "vmax": self.vmax,
            "size_bytes": self.size_bytes,
            "source_query": self.source_query,
            "job_id": self.job_id,
            "created_at": self.created_at.isoformat(),
        }


class ExecutionHistory(Base):
    """
    Execution history for analytics and debugging.

    Tracks all process graph executions with timing and results.
    """
    __tablename__ = 'execution_history'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('ai_sessions.id'),
        nullable=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    process_graph: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    result_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    session: Mapped[Optional["AISession"]] = relationship(
        "AISession",
        back_populates="execution_history"
    )

    __table_args__ = (
        Index('ix_execution_history_user_created', 'user_id', 'created_at'),
        Index('ix_execution_history_status', 'status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": str(self.id),
            "session_id": str(self.session_id) if self.session_id else None,
            "user_id": self.user_id,
            "process_graph": self.process_graph,
            "status": self.status,
            "result_path": self.result_path,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "tokens_used": self.tokens_used,
            "cost_estimate": self.cost_estimate,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
