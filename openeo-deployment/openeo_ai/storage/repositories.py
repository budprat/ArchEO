# ABOUTME: Repository pattern implementation for async database operations.
# Provides CRUD and search for sessions, process graphs, tags, and execution history.

"""
Repository classes for OpenEO AI storage.

Provides data access layer for AI sessions, process graphs, tags,
and execution history.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, update, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import AISession, SavedProcessGraph, Tag, ExecutionHistory


class SessionRepository:
    """Repository for AI session management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        title: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AISession:
        """Create a new AI session."""
        session = AISession(
            user_id=user_id,
            title=title,
            context=context or {},
            messages=[]
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get(self, session_id: uuid.UUID) -> Optional[AISession]:
        """Get session by ID."""
        result = await self.db.execute(
            select(AISession).where(AISession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        active_only: bool = True
    ) -> List[AISession]:
        """Get sessions for a user."""
        query = select(AISession).where(AISession.user_id == user_id)

        if active_only:
            query = query.where(AISession.is_active == True)

        query = query.order_by(AISession.updated_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_context(
        self,
        session_id: uuid.UUID,
        context: Dict[str, Any]
    ) -> Optional[AISession]:
        """Update session context."""
        session = await self.get(session_id)
        if session:
            # Merge new context with existing
            current_context = session.context or {}
            current_context.update(context)
            session.context = current_context
            await self.db.commit()
            await self.db.refresh(session)
        return session

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str
    ) -> Optional[AISession]:
        """Add a message to session history."""
        session = await self.get(session_id)
        if session:
            messages = session.messages or []
            messages.append({
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat()
            })
            session.messages = messages
            await self.db.commit()
            await self.db.refresh(session)
        return session

    async def delete(self, session_id: uuid.UUID) -> bool:
        """Soft delete a session."""
        result = await self.db.execute(
            update(AISession)
            .where(AISession.id == session_id)
            .values(is_active=False)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def hard_delete(self, session_id: uuid.UUID) -> bool:
        """Permanently delete a session."""
        result = await self.db.execute(
            delete(AISession).where(AISession.id == session_id)
        )
        await self.db.commit()
        return result.rowcount > 0


class ProcessGraphRepository:
    """Repository for saved process graphs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        name: str,
        process_graph: Dict[str, Any],
        description: Optional[str] = None,
        is_public: bool = False,
        tags: Optional[List[str]] = None
    ) -> SavedProcessGraph:
        """Create a new saved process graph."""
        pg = SavedProcessGraph(
            user_id=user_id,
            name=name,
            description=description,
            process_graph=process_graph,
            is_public=is_public
        )

        # Add tags if provided
        if tags:
            tag_repo = TagRepository(self.db)
            for tag_name in tags:
                tag = await tag_repo.get_or_create(tag_name)
                pg.tags.append(tag)

        self.db.add(pg)
        await self.db.commit()
        await self.db.refresh(pg)
        return pg

    async def get(self, pg_id: uuid.UUID) -> Optional[SavedProcessGraph]:
        """Get process graph by ID."""
        result = await self.db.execute(
            select(SavedProcessGraph)
            .options(selectinload(SavedProcessGraph.tags))
            .where(SavedProcessGraph.id == pg_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[SavedProcessGraph]:
        """Get process graphs for a user."""
        result = await self.db.execute(
            select(SavedProcessGraph)
            .options(selectinload(SavedProcessGraph.tags))
            .where(SavedProcessGraph.user_id == user_id)
            .order_by(SavedProcessGraph.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def search(
        self,
        user_id: str,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        include_public: bool = True,
        limit: int = 50,
        offset: int = 0
    ) -> List[SavedProcessGraph]:
        """Search process graphs."""
        stmt = select(SavedProcessGraph).options(
            selectinload(SavedProcessGraph.tags)
        )

        # Filter by ownership or public
        if include_public:
            stmt = stmt.where(
                or_(
                    SavedProcessGraph.user_id == user_id,
                    SavedProcessGraph.is_public == True
                )
            )
        else:
            stmt = stmt.where(SavedProcessGraph.user_id == user_id)

        # Filter by search query
        if query:
            search_term = f"%{query}%"
            stmt = stmt.where(
                or_(
                    SavedProcessGraph.name.ilike(search_term),
                    SavedProcessGraph.description.ilike(search_term)
                )
            )

        # Filter by tags
        if tags:
            stmt = stmt.join(SavedProcessGraph.tags).where(Tag.name.in_(tags))

        stmt = stmt.order_by(SavedProcessGraph.use_count.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    async def update(
        self,
        pg_id: uuid.UUID,
        **kwargs
    ) -> Optional[SavedProcessGraph]:
        """Update a process graph."""
        pg = await self.get(pg_id)
        if pg:
            for key, value in kwargs.items():
                if hasattr(pg, key) and key not in ('id', 'created_at'):
                    setattr(pg, key, value)
            await self.db.commit()
            await self.db.refresh(pg)
        return pg

    async def increment_use_count(self, pg_id: uuid.UUID) -> None:
        """Increment the use count for a process graph."""
        await self.db.execute(
            update(SavedProcessGraph)
            .where(SavedProcessGraph.id == pg_id)
            .values(use_count=SavedProcessGraph.use_count + 1)
        )
        await self.db.commit()

    async def delete(self, pg_id: uuid.UUID) -> bool:
        """Delete a process graph."""
        result = await self.db.execute(
            delete(SavedProcessGraph).where(SavedProcessGraph.id == pg_id)
        )
        await self.db.commit()
        return result.rowcount > 0


class TagRepository:
    """Repository for tags."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        name: str,
        description: Optional[str] = None
    ) -> Tag:
        """Create a new tag."""
        tag = Tag(name=name.lower(), description=description)
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def get(self, tag_id: uuid.UUID) -> Optional[Tag]:
        """Get tag by ID."""
        result = await self.db.execute(
            select(Tag).where(Tag.id == tag_id)
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Tag]:
        """Get tag by name."""
        result = await self.db.execute(
            select(Tag).where(Tag.name == name.lower())
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        name: str,
        description: Optional[str] = None
    ) -> Tag:
        """Get existing tag or create new one."""
        tag = await self.get_by_name(name)
        if not tag:
            tag = await self.create(name, description)
        return tag

    async def list_all(self) -> List[Tag]:
        """List all tags."""
        result = await self.db.execute(
            select(Tag).order_by(Tag.name)
        )
        return list(result.scalars().all())

    async def list_popular(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List popular tags with usage count."""
        result = await self.db.execute(
            select(
                Tag,
                func.count(SavedProcessGraph.id).label('count')
            )
            .join(Tag.process_graphs)
            .group_by(Tag.id)
            .order_by(func.count(SavedProcessGraph.id).desc())
            .limit(limit)
        )
        return [
            {"tag": row[0].to_dict(), "count": row[1]}
            for row in result.all()
        ]

    async def delete(self, tag_id: uuid.UUID) -> bool:
        """Delete a tag."""
        result = await self.db.execute(
            delete(Tag).where(Tag.id == tag_id)
        )
        await self.db.commit()
        return result.rowcount > 0


class ExecutionHistoryRepository:
    """Repository for execution history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        process_graph: Dict[str, Any],
        session_id: Optional[uuid.UUID] = None
    ) -> ExecutionHistory:
        """Create a new execution history record."""
        history = ExecutionHistory(
            user_id=user_id,
            process_graph=process_graph,
            session_id=session_id,
            status="pending"
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)
        return history

    async def get(self, history_id: uuid.UUID) -> Optional[ExecutionHistory]:
        """Get execution history by ID."""
        result = await self.db.execute(
            select(ExecutionHistory).where(ExecutionHistory.id == history_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        history_id: uuid.UUID,
        status: str,
        result_path: Optional[str] = None,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ) -> Optional[ExecutionHistory]:
        """Update execution status."""
        history = await self.get(history_id)
        if history:
            history.status = status
            if result_path:
                history.result_path = result_path
            if error_message:
                history.error_message = error_message
            if execution_time_ms:
                history.execution_time_ms = execution_time_ms
            if status in ("completed", "failed"):
                history.completed_at = datetime.utcnow()
            await self.db.commit()
            await self.db.refresh(history)
        return history

    async def get_by_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[ExecutionHistory]:
        """Get execution history for a user."""
        query = select(ExecutionHistory).where(
            ExecutionHistory.user_id == user_id
        )

        if status:
            query = query.where(ExecutionHistory.status == status)

        query = query.order_by(ExecutionHistory.created_at.desc())
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_session(
        self,
        session_id: uuid.UUID
    ) -> List[ExecutionHistory]:
        """Get execution history for a session."""
        result = await self.db.execute(
            select(ExecutionHistory)
            .where(ExecutionHistory.session_id == session_id)
            .order_by(ExecutionHistory.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get execution statistics for a user."""
        # Total executions
        total_result = await self.db.execute(
            select(func.count(ExecutionHistory.id))
            .where(ExecutionHistory.user_id == user_id)
        )
        total = total_result.scalar()

        # By status
        status_result = await self.db.execute(
            select(
                ExecutionHistory.status,
                func.count(ExecutionHistory.id)
            )
            .where(ExecutionHistory.user_id == user_id)
            .group_by(ExecutionHistory.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}

        # Average execution time
        avg_time_result = await self.db.execute(
            select(func.avg(ExecutionHistory.execution_time_ms))
            .where(ExecutionHistory.user_id == user_id)
            .where(ExecutionHistory.execution_time_ms.isnot(None))
        )
        avg_time = avg_time_result.scalar()

        return {
            "total_executions": total,
            "by_status": by_status,
            "average_execution_time_ms": float(avg_time) if avg_time else None
        }
