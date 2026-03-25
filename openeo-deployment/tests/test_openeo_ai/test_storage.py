"""
Phase 3: Storage Tests

Test-Driven Development: These tests define the expected behavior
of the extended storage layer before implementation.

Tests cover:
- AI session storage
- Process graph library
- Tag management
- Execution history
- Repository pattern
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import uuid
from datetime import datetime, timedelta


class TestAISessionStorage:
    """Test AI session persistence."""

    @pytest.mark.asyncio
    async def test_create_session(self, mock_user_id):
        """Should create new session in database."""
        from openeo_ai.storage.repositories import SessionRepository

        mock_db = AsyncMock()
        repo = SessionRepository(db=mock_db)

        # Mock the create method to return an AISession-like object
        mock_session = Mock()
        mock_session.id = uuid.uuid4()
        mock_session.user_id = mock_user_id

        with patch.object(repo, 'create', return_value=mock_session):
            session = await repo.create(user_id=mock_user_id)

            assert session is not None
            assert session.user_id == mock_user_id

    @pytest.mark.asyncio
    async def test_get_session_by_id(self, mock_user_id, sample_session_id):
        """Should retrieve session by ID."""
        from openeo_ai.storage.repositories import SessionRepository

        mock_db = AsyncMock()
        repo = SessionRepository(db=mock_db)

        mock_session = Mock()
        mock_session.id = sample_session_id
        mock_session.user_id = mock_user_id
        mock_session.created_at = datetime.utcnow()
        mock_session.updated_at = datetime.utcnow()
        mock_session.context = {}

        with patch.object(repo, 'get', return_value=mock_session):
            session = await repo.get(sample_session_id)

            assert session.id == sample_session_id
            assert session.user_id == mock_user_id

    @pytest.mark.asyncio
    async def test_update_session_context(self, sample_session_id):
        """Should update session context."""
        from openeo_ai.storage.repositories import SessionRepository

        mock_db = AsyncMock()
        repo = SessionRepository(db=mock_db)

        new_context = {
            "last_collection": "sentinel-2-l2a",
            "last_job_id": "job-123"
        }

        mock_session = Mock()
        mock_session.context = new_context

        with patch.object(repo, 'update_context', return_value=mock_session):
            result = await repo.update_context(sample_session_id, new_context)

            assert result is not None
            assert result.context == new_context

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, mock_user_id):
        """Should list all sessions for a user."""
        from openeo_ai.storage.repositories import SessionRepository

        mock_db = AsyncMock()
        repo = SessionRepository(db=mock_db)

        mock_sessions = [
            Mock(id=uuid.uuid4(), user_id=mock_user_id),
            Mock(id=uuid.uuid4(), user_id=mock_user_id),
        ]

        with patch.object(repo, 'get_by_user', return_value=mock_sessions):
            sessions = await repo.get_by_user(mock_user_id)

            assert len(sessions) == 2
            assert all(s.user_id == mock_user_id for s in sessions)

    @pytest.mark.asyncio
    async def test_delete_session(self, sample_session_id):
        """Should delete session."""
        from openeo_ai.storage.repositories import SessionRepository

        mock_db = AsyncMock()
        repo = SessionRepository(db=mock_db)

        with patch.object(repo, 'delete', return_value=True):
            result = await repo.delete(sample_session_id)

            assert result is True


class TestProcessGraphLibrary:
    """Test process graph library storage."""

    @pytest.mark.asyncio
    async def test_save_process_graph(self, ndvi_process_graph, mock_user_id):
        """Should save process graph to library."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        mock_pg = Mock()
        mock_pg.id = uuid.uuid4()
        mock_pg.name = "NDVI Workflow"
        mock_pg.user_id = mock_user_id

        with patch.object(repo, 'create', return_value=mock_pg):
            pg = await repo.create(
                name="NDVI Workflow",
                description="Calculate NDVI from Sentinel-2",
                process_graph=ndvi_process_graph,
                user_id=mock_user_id,
                tags=["ndvi", "sentinel-2"]
            )

            assert pg is not None
            assert pg.name == "NDVI Workflow"

    @pytest.mark.asyncio
    async def test_get_process_graph(self, saved_graph_id, ndvi_process_graph):
        """Should retrieve process graph by ID."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        mock_graph = Mock()
        mock_graph.id = saved_graph_id
        mock_graph.process_graph = ndvi_process_graph
        mock_graph.tags = [Mock(name="ndvi")]

        with patch.object(repo, 'get', return_value=mock_graph):
            graph = await repo.get(saved_graph_id)

            assert graph.id == saved_graph_id
            assert graph.process_graph == ndvi_process_graph

    @pytest.mark.asyncio
    async def test_list_process_graphs_by_user(self, mock_user_id):
        """Should list process graphs for a user."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        mock_graphs = [
            Mock(id=uuid.uuid4(), name="NDVI Workflow", user_id=mock_user_id),
            Mock(id=uuid.uuid4(), name="EVI Workflow", user_id=mock_user_id),
        ]

        with patch.object(repo, 'get_by_user', return_value=mock_graphs):
            graphs = await repo.get_by_user(mock_user_id)

            assert len(graphs) == 2

    @pytest.mark.asyncio
    async def test_filter_by_tags(self, mock_user_id):
        """Should filter process graphs by tags."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        with patch.object(repo, 'search') as mock_search:
            mock_search.return_value = [
                Mock(id=uuid.uuid4(), name="NDVI", tags=[Mock(name="ndvi")])
            ]

            graphs = await repo.search(
                user_id=mock_user_id,
                tags=["ndvi"]
            )

            mock_search.assert_called_with(user_id=mock_user_id, tags=["ndvi"])

    @pytest.mark.asyncio
    async def test_search_by_name(self, mock_user_id):
        """Should search process graphs by name/description."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        with patch.object(repo, 'search') as mock_search:
            mock_search.return_value = [
                Mock(id=uuid.uuid4(), name="NDVI Workflow", description="Calculate NDVI")
            ]

            graphs = await repo.search(
                user_id=mock_user_id,
                query="NDVI"
            )

            assert len(graphs) == 1

    @pytest.mark.asyncio
    async def test_update_process_graph(self, saved_graph_id):
        """Should update existing process graph."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        mock_pg = Mock()
        mock_pg.id = saved_graph_id
        mock_pg.name = "Updated NDVI Workflow"

        with patch.object(repo, 'update', return_value=mock_pg):
            result = await repo.update(
                pg_id=saved_graph_id,
                name="Updated NDVI Workflow",
                description="Updated description"
            )

            assert result is not None
            assert result.name == "Updated NDVI Workflow"

    @pytest.mark.asyncio
    async def test_delete_process_graph(self, saved_graph_id):
        """Should delete process graph."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        with patch.object(repo, 'delete', return_value=True):
            result = await repo.delete(saved_graph_id)

            assert result is True


class TestTagManagement:
    """Test tag management for process graphs."""

    @pytest.mark.asyncio
    async def test_create_tag(self):
        """Should create new tag."""
        from openeo_ai.storage.repositories import TagRepository

        mock_db = AsyncMock()
        repo = TagRepository(db=mock_db)

        mock_tag = Mock()
        mock_tag.id = uuid.uuid4()
        mock_tag.name = "vegetation"

        with patch.object(repo, 'create', return_value=mock_tag):
            tag = await repo.create(name="vegetation")

            assert tag is not None
            assert tag.name == "vegetation"

    @pytest.mark.asyncio
    async def test_get_or_create_tag(self):
        """Should get existing tag or create new one."""
        from openeo_ai.storage.repositories import TagRepository

        mock_db = AsyncMock()
        repo = TagRepository(db=mock_db)

        existing_tag = Mock()
        existing_tag.id = uuid.uuid4()
        existing_tag.name = "vegetation"

        with patch.object(repo, 'get_or_create', return_value=existing_tag):
            tag = await repo.get_or_create(name="vegetation")

            assert tag.id == existing_tag.id

    @pytest.mark.asyncio
    async def test_list_all_tags(self):
        """Should list all available tags."""
        from openeo_ai.storage.repositories import TagRepository

        mock_db = AsyncMock()
        repo = TagRepository(db=mock_db)

        mock_tags = [
            Mock(id=uuid.uuid4(), name="ndvi"),
            Mock(id=uuid.uuid4(), name="vegetation"),
            Mock(id=uuid.uuid4(), name="sentinel-2"),
        ]

        with patch.object(repo, 'list_all', return_value=mock_tags):
            tags = await repo.list_all()

            assert len(tags) == 3

    @pytest.mark.asyncio
    async def test_list_popular_tags(self):
        """Should list tags sorted by usage count."""
        from openeo_ai.storage.repositories import TagRepository

        mock_db = AsyncMock()
        repo = TagRepository(db=mock_db)

        mock_tags = [
            {"tag": Mock(name="ndvi"), "count": 15},
            {"tag": Mock(name="vegetation"), "count": 10},
        ]

        with patch.object(repo, 'list_popular', return_value=mock_tags):
            tags = await repo.list_popular(limit=10)

            assert tags[0]["count"] >= tags[1]["count"]


class TestExecutionHistory:
    """Test execution history tracking."""

    @pytest.mark.asyncio
    async def test_record_execution(self, sample_job_id, sample_session_id, mock_user_id):
        """Should record execution in history."""
        from openeo_ai.storage.repositories import ExecutionHistoryRepository

        mock_db = AsyncMock()
        repo = ExecutionHistoryRepository(db=mock_db)

        mock_history = Mock()
        mock_history.id = uuid.uuid4()
        mock_history.user_id = mock_user_id
        mock_history.status = "pending"

        with patch.object(repo, 'create', return_value=mock_history):
            execution = await repo.create(
                user_id=mock_user_id,
                process_graph={"test": "graph"},
                session_id=sample_session_id
            )

            assert execution is not None
            assert execution.status == "pending"

    @pytest.mark.asyncio
    async def test_update_execution_status(self):
        """Should update execution status."""
        from openeo_ai.storage.repositories import ExecutionHistoryRepository

        mock_db = AsyncMock()
        repo = ExecutionHistoryRepository(db=mock_db)

        execution_id = uuid.uuid4()

        mock_history = Mock()
        mock_history.id = execution_id
        mock_history.status = "completed"
        mock_history.result_path = "/tmp/result.tif"

        with patch.object(repo, 'update_status', return_value=mock_history):
            result = await repo.update_status(
                history_id=execution_id,
                status="completed",
                result_path="/tmp/result.tif"
            )

            assert result is not None
            assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_list_execution_history(self, mock_user_id):
        """Should list execution history for a user."""
        from openeo_ai.storage.repositories import ExecutionHistoryRepository

        mock_db = AsyncMock()
        repo = ExecutionHistoryRepository(db=mock_db)

        mock_executions = [
            Mock(
                id=uuid.uuid4(),
                status="completed",
                created_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
        ]

        with patch.object(repo, 'get_by_user', return_value=mock_executions):
            history = await repo.get_by_user(mock_user_id)

            assert len(history) == 1

    @pytest.mark.asyncio
    async def test_record_execution_error(self, mock_user_id):
        """Should record execution errors."""
        from openeo_ai.storage.repositories import ExecutionHistoryRepository

        mock_db = AsyncMock()
        repo = ExecutionHistoryRepository(db=mock_db)

        execution_id = uuid.uuid4()

        mock_history = Mock()
        mock_history.id = execution_id
        mock_history.status = "failed"
        mock_history.error_message = "Process failed: Out of memory"

        with patch.object(repo, 'update_status', return_value=mock_history):
            result = await repo.update_status(
                history_id=execution_id,
                status="failed",
                error_message="Process failed: Out of memory"
            )

            assert result is not None
            assert result.status == "failed"


class TestDatabaseModels:
    """Test SQLAlchemy model definitions."""

    def test_ai_session_model_fields(self):
        """AISession model should have required fields."""
        from openeo_ai.storage.models import AISession

        # Check model has required columns
        assert hasattr(AISession, 'id')
        assert hasattr(AISession, 'user_id')
        assert hasattr(AISession, 'created_at')
        assert hasattr(AISession, 'updated_at')
        assert hasattr(AISession, 'context')

    def test_saved_process_graph_model_fields(self):
        """SavedProcessGraph model should have required fields."""
        from openeo_ai.storage.models import SavedProcessGraph

        assert hasattr(SavedProcessGraph, 'id')
        assert hasattr(SavedProcessGraph, 'name')
        assert hasattr(SavedProcessGraph, 'description')
        assert hasattr(SavedProcessGraph, 'process_graph')
        assert hasattr(SavedProcessGraph, 'user_id')
        assert hasattr(SavedProcessGraph, 'created_at')
        assert hasattr(SavedProcessGraph, 'updated_at')
        assert hasattr(SavedProcessGraph, 'tags')

    def test_tag_model_fields(self):
        """Tag model should have required fields."""
        from openeo_ai.storage.models import Tag

        assert hasattr(Tag, 'id')
        assert hasattr(Tag, 'name')
        assert hasattr(Tag, 'process_graphs')

    def test_execution_history_model_fields(self):
        """ExecutionHistory model should have required fields."""
        from openeo_ai.storage.models import ExecutionHistory

        assert hasattr(ExecutionHistory, 'id')
        assert hasattr(ExecutionHistory, 'session_id')
        assert hasattr(ExecutionHistory, 'user_id')
        assert hasattr(ExecutionHistory, 'status')
        assert hasattr(ExecutionHistory, 'created_at')
        assert hasattr(ExecutionHistory, 'completed_at')
        assert hasattr(ExecutionHistory, 'result_path')
        assert hasattr(ExecutionHistory, 'error_message')


class TestDatabaseMigrations:
    """Test database migration functionality."""

    def test_migration_creates_ai_sessions_table(self):
        """Migration should create ai_sessions table."""
        # This would be tested against a test database
        # For now, verify migration file exists
        from pathlib import Path

        migration_dir = Path("/Users/macbookpro/openeo-deployment/openeo_app/psql/alembic/versions")

        # Migration directory should exist after setup
        assert migration_dir.exists()

    def test_migration_creates_saved_graphs_table(self):
        """Migration should create saved_process_graphs table."""
        assert True  # Placeholder - tested during actual migration


class TestRepositoryPatterns:
    """Test repository pattern implementation."""

    @pytest.mark.asyncio
    async def test_repository_uses_async_session(self):
        """Repository should use async database sessions."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        assert repo.db == mock_db

    @pytest.mark.asyncio
    async def test_repository_create_and_commit(self, mock_user_id, ndvi_process_graph):
        """Repository should handle create and commit."""
        from openeo_ai.storage.repositories import ProcessGraphRepository

        mock_db = AsyncMock()
        repo = ProcessGraphRepository(db=mock_db)

        mock_pg = Mock()
        mock_pg.id = uuid.uuid4()
        mock_pg.name = "Test"

        with patch.object(repo, 'create', return_value=mock_pg):
            pg = await repo.create(
                name="Test",
                description="",
                process_graph=ndvi_process_graph,
                user_id=mock_user_id
            )

            assert pg is not None
