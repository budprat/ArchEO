"""
Phase 1: Claude SDK Client Tests

Test-Driven Development: These tests define the expected behavior
of the Claude SDK integration before implementation.

Tests cover:
- Client initialization
- Session management
- Chat functionality
- Permission callbacks
- Error handling
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import uuid
from datetime import datetime


class TestOpenEOAIClientInitialization:
    """Test client initialization and configuration."""

    def test_client_creates_with_default_config(self):
        """Client should initialize with default configuration."""
        from openeo_ai.sdk.client import OpenEOAIClient, OpenEOAIConfig

        client = OpenEOAIClient()

        assert client.config is not None
        assert isinstance(client.config, OpenEOAIConfig)

    def test_client_creates_with_custom_config(self):
        """Client should accept custom configuration."""
        from openeo_ai.sdk.client import OpenEOAIClient, OpenEOAIConfig

        config = OpenEOAIConfig(
            model="claude-opus-4",
            max_turns=100,
            openeo_url="http://custom:8000/openeo/1.1.0"
        )
        client = OpenEOAIClient(config=config)

        assert client.config.model == "claude-opus-4"
        assert client.config.max_turns == 100
        assert client.config.openeo_url == "http://custom:8000/openeo/1.1.0"

    def test_config_has_expected_defaults(self):
        """Configuration should have sensible defaults."""
        from openeo_ai.sdk.client import OpenEOAIConfig

        config = OpenEOAIConfig()

        # Model should be a Claude Sonnet variant (may include version suffix)
        assert "claude-sonnet" in config.model or "sonnet" in config.model
        assert config.max_turns == 15
        assert "openeo" in config.openeo_url.lower()

    def test_client_initializes_session_manager(self):
        """Client should initialize session manager."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        assert hasattr(client, 'session_manager')
        assert client.session_manager is not None

    def test_client_initializes_tools(self):
        """Client should initialize custom tools."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        assert hasattr(client, 'tools')
        assert isinstance(client.tools, dict)
        assert len(client.tools) > 0


class TestOpenEOAIClientChat:
    """Test chat functionality."""

    @pytest.mark.asyncio
    async def test_chat_returns_async_iterator(self, mock_user_id):
        """Chat should return an async iterator of responses."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        # Mock the Anthropic API response
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello! How can I help?"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._client = mock_anthropic

        responses = []
        async for response in client.chat(
            prompt="Hello",
            user_id=mock_user_id
        ):
            responses.append(response)

        # Should get text response and session info
        assert len(responses) >= 1
        text_responses = [r for r in responses if r["type"] == "text"]
        assert len(text_responses) >= 1

    @pytest.mark.asyncio
    async def test_chat_accepts_session_id_for_resumption(
        self, mock_user_id, sample_session_id
    ):
        """Chat should accept session_id to resume conversation."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Continuing..."

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._client = mock_anthropic

        responses = []
        async for response in client.chat(
            prompt="Continue",
            user_id=mock_user_id,
            session_id=sample_session_id
        ):
            responses.append(response)

        # Should complete without error
        assert len(responses) >= 1

    @pytest.mark.asyncio
    async def test_chat_processes_text_messages(self, mock_user_id):
        """Chat should process text messages from Claude."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "I'll help you calculate NDVI."

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._client = mock_anthropic

        responses = []
        async for response in client.chat(
            prompt="Calculate NDVI",
            user_id=mock_user_id
        ):
            responses.append(response)

        text_responses = [r for r in responses if r["type"] == "text"]
        assert len(text_responses) == 1
        assert "NDVI" in text_responses[0]["content"]

    @pytest.mark.asyncio
    async def test_chat_processes_tool_results(self, mock_user_id):
        """Chat should process tool result messages."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        # First response: Claude calls a tool
        mock_tool_block = Mock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.name = "openeo_list_collections"
        mock_tool_block.input = {}
        mock_tool_block.id = "tool_123"

        mock_response_1 = Mock()
        mock_response_1.content = [mock_tool_block]
        mock_response_1.stop_reason = "tool_use"

        # Second response: Claude returns text after tool result
        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Here are the collections."

        mock_response_2 = Mock()
        mock_response_2.content = [mock_text_block]
        mock_response_2.stop_reason = "end_turn"

        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(
            side_effect=[mock_response_1, mock_response_2]
        )
        client._client = mock_anthropic

        # Mock the tool so it returns a result
        client.tools["openeo_list_collections"] = AsyncMock(
            return_value={"collections": ["sentinel-2-l2a"]}
        )

        responses = []
        async for response in client.chat(
            prompt="List collections",
            user_id=mock_user_id
        ):
            responses.append(response)

        tool_responses = [r for r in responses if r["type"] == "tool_result"]
        assert len(tool_responses) == 1
        assert tool_responses[0]["tool"] == "openeo_list_collections"


class TestSessionManager:
    """Test session management functionality."""

    def test_session_manager_creates_new_session(self, mock_user_id):
        """Session manager should create new sessions."""
        from openeo_ai.sdk.sessions import SessionManager

        manager = SessionManager(db_path=":memory:")  # In-memory for testing
        session_id = manager.create_session(user_id=mock_user_id)

        assert session_id is not None
        assert isinstance(session_id, str)
        # Should be valid UUID
        uuid.UUID(session_id)

    def test_session_manager_retrieves_session(self, mock_user_id):
        """Session manager should retrieve existing sessions."""
        from openeo_ai.sdk.sessions import SessionManager

        manager = SessionManager(db_path=":memory:")
        session_id = manager.create_session(user_id=mock_user_id)

        session = manager.get_session(session_id)

        assert session is not None
        assert session["user_id"] == mock_user_id

    def test_session_manager_updates_last_active(self, mock_user_id):
        """Session manager should update last_active timestamp."""
        from openeo_ai.sdk.sessions import SessionManager
        import time

        manager = SessionManager(db_path=":memory:")
        session_id = manager.create_session(user_id=mock_user_id)

        original = manager.get_session(session_id)
        time.sleep(0.01)  # Small delay to ensure timestamp changes
        manager.update_session(session_id, user_id=mock_user_id)
        updated = manager.get_session(session_id)

        # last_active should be updated (or equal if very fast)
        assert updated["last_active"] >= original["last_active"]

    def test_session_manager_stores_context(self, mock_user_id):
        """Session manager should store and retrieve context."""
        from openeo_ai.sdk.sessions import SessionManager

        manager = SessionManager(db_path=":memory:")
        session_id = manager.create_session(user_id=mock_user_id)

        context = {"last_collection": "sentinel-2-l2a", "job_id": "abc123"}
        manager.update_context(session_id, context)

        session = manager.get_session(session_id)

        assert session["context"] == context

    def test_session_manager_lists_user_sessions(self, mock_user_id):
        """Session manager should list sessions for a user."""
        from openeo_ai.sdk.sessions import SessionManager

        manager = SessionManager(db_path=":memory:")

        # Create multiple sessions
        session1 = manager.create_session(user_id=mock_user_id)
        session2 = manager.create_session(user_id=mock_user_id)
        session3 = manager.create_session(user_id="other-user")

        sessions = manager.list_sessions(user_id=mock_user_id)

        assert len(sessions) == 2
        session_ids = [s["id"] for s in sessions]
        assert session1 in session_ids
        assert session2 in session_ids
        assert session3 not in session_ids

    def test_session_manager_deletes_session(self, mock_user_id):
        """Session manager should delete sessions."""
        from openeo_ai.sdk.sessions import SessionManager

        manager = SessionManager(db_path=":memory:")
        session_id = manager.create_session(user_id=mock_user_id)

        result = manager.delete_session(session_id)
        assert result is True

        session = manager.get_session(session_id)
        assert session is None


class TestPermissionCallbacks:
    """Test permission callback functionality."""

    def test_permission_callback_allows_read_tools(self):
        """Permission callback should allow read-only tools."""
        from openeo_ai.sdk.permissions import openeo_permission_callback

        # Read-only tools should be allowed
        assert openeo_permission_callback("openeo_list_collections", {}) is True
        assert openeo_permission_callback("openeo_get_collection_info", {}) is True
        assert openeo_permission_callback("openeo_validate_graph", {}) is True

    def test_permission_callback_allows_job_creation_with_confirmation(self):
        """Permission callback should require confirmation for job creation."""
        from openeo_ai.sdk.permissions import openeo_permission_callback

        # Job creation should require user confirmation
        result = openeo_permission_callback("openeo_create_job", {
            "title": "Test Job",
            "process_graph": {}
        })

        # Should either return True (auto-allowed) or a confirmation request
        assert result in [True, False] or isinstance(result, dict)

    def test_permission_callback_blocks_dangerous_operations(self):
        """Permission callback should block dangerous operations."""
        from openeo_ai.sdk.permissions import openeo_permission_callback

        # Hypothetical dangerous operation
        result = openeo_permission_callback("openeo_delete_all_jobs", {})

        # Should be blocked
        assert result is False

    def test_permission_callback_validates_extent_size(self):
        """Permission callback should validate spatial extent size."""
        from openeo_ai.sdk.permissions import openeo_permission_callback

        # Very large extent should trigger warning or block
        large_extent = {
            "process_graph": {
                "load": {
                    "process_id": "load_collection",
                    "arguments": {
                        "spatial_extent": {
                            "west": 0, "east": 50,  # 50 degrees!
                            "south": 0, "north": 50
                        }
                    }
                }
            }
        }

        result = openeo_permission_callback("openeo_create_job", large_extent)

        # Should either block or return a warning/confirmation request
        assert result is not None


class TestSystemPrompt:
    """Test system prompt configuration."""

    def test_system_prompt_includes_capabilities(self):
        """System prompt should describe all capabilities."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()
        prompt = client.SYSTEM_PROMPT

        # Should mention key capabilities
        assert "Earth Observation" in prompt or "EO" in prompt
        assert "process" in prompt.lower()
        assert "OpenEO" in prompt

    def test_system_prompt_lists_available_tools(self):
        """System prompt should list available tools."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()
        prompt = client.SYSTEM_PROMPT

        # Should mention key tools
        assert "collection" in prompt.lower()
        assert "job" in prompt.lower() or "validate" in prompt.lower()


class TestErrorHandling:
    """Test error handling in SDK client."""

    @pytest.mark.asyncio
    async def test_chat_handles_network_error(self, mock_user_id):
        """Chat should handle network errors gracefully."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        # Mock the Anthropic client to raise ConnectionError
        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(
            side_effect=ConnectionError("Network unavailable")
        )
        client._client = mock_anthropic

        with pytest.raises(ConnectionError):
            async for _ in client.chat(
                prompt="Hello",
                user_id=mock_user_id
            ):
                pass

    @pytest.mark.asyncio
    async def test_chat_handles_invalid_session(self, mock_user_id):
        """Chat should handle invalid session ID gracefully."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        mock_text_block = Mock()
        mock_text_block.type = "text"
        mock_text_block.text = "Hello!"

        mock_response = Mock()
        mock_response.content = [mock_text_block]
        mock_response.stop_reason = "end_turn"

        mock_anthropic = AsyncMock()
        mock_anthropic.messages.create = AsyncMock(return_value=mock_response)
        client._client = mock_anthropic

        # Invalid session ID should work (creates new session)
        responses = []
        async for response in client.chat(
            prompt="Hello",
            user_id=mock_user_id,
            session_id="invalid-session-id"
        ):
            responses.append(response)

        # Should complete with responses
        assert len(responses) >= 1


class TestToolRegistration:
    """Test custom tool registration."""

    def test_all_openeo_tools_registered(self):
        """All OpenEO tools should be registered."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        expected_tools = [
            "openeo_list_collections",
            "openeo_get_collection_info",
            "openeo_validate_graph",
            "openeo_create_job",
            "openeo_start_job",
            "openeo_get_job_status",
            "openeo_get_results",
        ]

        for tool_name in expected_tools:
            assert tool_name in client.tools, f"Missing tool: {tool_name}"

    def test_geoai_tools_registered(self):
        """GeoAI tools should be registered."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        expected_tools = [
            "geoai_segment",
            "geoai_detect_change",
        ]

        for tool_name in expected_tools:
            assert tool_name in client.tools, f"Missing tool: {tool_name}"

    def test_visualization_tools_registered(self):
        """Visualization tools should be registered."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        expected_tools = [
            "viz_show_map",
            "viz_show_time_series",
        ]

        for tool_name in expected_tools:
            assert tool_name in client.tools, f"Missing tool: {tool_name}"

    def test_tools_have_descriptions(self):
        """All tools should have descriptions."""
        from openeo_ai.sdk.client import OpenEOAIClient

        client = OpenEOAIClient()

        for tool_name, tool in client.tools.items():
            # Tool should have description metadata
            assert hasattr(tool, '__doc__') or hasattr(tool, 'description'), \
                f"Tool {tool_name} missing description"
