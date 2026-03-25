# ABOUTME: Unit tests for OpenEO AI tools.
# Tests tool functions, error handling, and integration with Claude SDK.

"""
Unit tests for OpenEO AI tools.

Tests:
- Tool execution and response formatting
- Error handling in tool functions
- Integration with validation and error handler
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from openeo_ai.utils.error_handler import (
    ErrorHandler,
    ErrorType,
    Severity,
    handle_error,
    check_oversight,
)
from openeo_ai.utils.schema_validator import (
    validate_tool_input,
    validate_process_graph,
)


# ============================================================================
# Error Handler Tests
# ============================================================================

class TestErrorHandler:
    """Tests for error handler functionality."""

    def test_classify_validation_error(self):
        """Test classification of validation errors."""
        handler = ErrorHandler()

        errors = [
            ValueError("missing required argument 'id'"),
            ValueError("invalid format for date"),
            TypeError("expected string, got int"),
        ]

        for error in errors:
            result = handler.classify_error(error)
            assert result == ErrorType.VALIDATION, f"Failed for: {error}"

    def test_classify_network_error(self):
        """Test classification of network errors."""
        handler = ErrorHandler()

        errors = [
            ConnectionError("Failed to connect"),
            OSError("Network unreachable"),
            Exception("connection refused"),
        ]

        for error in errors:
            result = handler.classify_error(error)
            assert result == ErrorType.NETWORK, f"Failed for: {error}"

    def test_classify_data_quality_error(self):
        """Test classification of data quality errors."""
        handler = ErrorHandler()

        errors = [
            ValueError("no data found"),
            Exception("empty result"),
            ValueError("no items returned from STAC"),
        ]

        for error in errors:
            result = handler.classify_error(error)
            assert result == ErrorType.DATA_QUALITY, f"Failed for: {error}"

    def test_classify_permission_error(self):
        """Test classification of permission errors."""
        handler = ErrorHandler()

        errors = [
            PermissionError("permission denied"),
            Exception("access denied"),
            Exception("unauthorized"),
        ]

        for error in errors:
            result = handler.classify_error(error)
            assert result == ErrorType.PERMISSION, f"Failed for: {error}"

    def test_classify_resource_error(self):
        """Test classification of resource errors."""
        handler = ErrorHandler()

        errors = [
            MemoryError("out of memory"),
            Exception("memory limit exceeded"),
            Exception("request too large"),
        ]

        for error in errors:
            result = handler.classify_error(error)
            assert result == ErrorType.RESOURCE, f"Failed for: {error}"

    def test_get_severity(self):
        """Test severity assignment."""
        handler = ErrorHandler()

        assert handler.get_severity(ErrorType.VALIDATION) == Severity.WARNING
        assert handler.get_severity(ErrorType.DATA_QUALITY) == Severity.WARNING
        assert handler.get_severity(ErrorType.NETWORK) == Severity.ERROR
        assert handler.get_severity(ErrorType.PERMISSION) == Severity.CRITICAL
        assert handler.get_severity(ErrorType.RESOURCE) == Severity.CRITICAL

    def test_handle_exception(self, validation_error):
        """Test handling an exception."""
        handler = ErrorHandler()

        result = handler.handle_exception(validation_error)

        assert result.error_type == ErrorType.VALIDATION
        assert result.severity == Severity.WARNING
        assert "missing required" in result.message.lower()
        assert len(result.suggestions) > 0

    def test_handle_exception_with_context(self, validation_error):
        """Test handling with context."""
        from openeo_ai.utils.error_handler import ErrorContext

        handler = ErrorHandler()
        context = ErrorContext(
            tool_name="openeo_generate_graph",
            tool_input={"description": "test"}
        )

        result = handler.handle_exception(validation_error, context)

        assert result.context == context
        assert result.context.tool_name == "openeo_generate_graph"

    def test_requires_oversight_large_extent(self):
        """Test oversight requirement for large extents."""
        handler = ErrorHandler()

        tool_input = {
            "spatial_extent": {
                "west": -10,
                "south": 30,
                "east": 10,
                "north": 50  # 20 degrees wide
            }
        }

        needs_oversight, reason = handler.requires_oversight("openeo_start_job", tool_input)
        assert needs_oversight is True
        assert "extent" in reason.lower()

    def test_requires_oversight_normal_extent(self):
        """Test no oversight for normal extents."""
        handler = ErrorHandler()

        tool_input = {
            "spatial_extent": {
                "west": 11.0,
                "south": 46.0,
                "east": 11.1,
                "north": 46.1  # 0.1 degrees
            }
        }

        needs_oversight, reason = handler.requires_oversight("openeo_start_job", tool_input)
        assert needs_oversight is False

    def test_to_dict(self, validation_error):
        """Test conversion to dictionary."""
        handler = ErrorHandler()
        result = handler.handle_exception(validation_error)

        result_dict = result.to_dict()

        assert "error_type" in result_dict
        assert "severity" in result_dict
        assert "message" in result_dict
        assert "suggestions" in result_dict
        assert result_dict["error_type"] == "validation"

    def test_to_user_message(self, validation_error):
        """Test conversion to user message."""
        handler = ErrorHandler()
        result = handler.handle_exception(validation_error)

        message = result.to_user_message()

        assert "Validation Error" in message
        assert "Suggestions" in message


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_handle_error(self, validation_error):
        """Test handle_error function."""
        result = handle_error(
            validation_error,
            tool_name="openeo_validate_graph",
            operation="validating process graph"
        )

        assert result.error_type == ErrorType.VALIDATION
        assert result.context.tool_name == "openeo_validate_graph"

    def test_check_oversight(self):
        """Test check_oversight function."""
        needs_oversight, reason = check_oversight(
            "openeo_start_job",
            {"spatial_extent": {"west": -10, "south": 30, "east": 10, "north": 50}}
        )
        assert needs_oversight is True

        needs_oversight, reason = check_oversight(
            "openeo_list_collections",
            {}
        )
        assert needs_oversight is False


# ============================================================================
# Schema Validator Tests
# ============================================================================

class TestSchemaValidator:
    """Tests for schema validation functionality."""

    def test_validate_process_graph_valid(self, simple_process_graph):
        """Test validation of valid process graph."""
        result = validate_process_graph(simple_process_graph)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_process_graph_invalid(self, invalid_process_graph):
        """Test validation of invalid process graph."""
        result = validate_process_graph(invalid_process_graph)

        assert result.valid is False
        assert len(result.errors) > 0

    def test_validate_process_graph_missing_result(self):
        """Test validation catches missing result node."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            }
        }

        result = validate_process_graph(pg)

        assert result.valid is False
        error_messages = [e.message for e in result.errors]
        assert any("result" in m.lower() for m in error_messages)

    def test_validate_process_graph_circular(self, cyclic_process_graph):
        """Test validation catches circular references."""
        result = validate_process_graph(cyclic_process_graph)

        assert result.valid is False
        error_messages = [e.message for e in result.errors]
        assert any("circular" in m.lower() for m in error_messages)

    def test_validate_tool_input_valid(self, generate_graph_input):
        """Test validation of valid tool input."""
        result = validate_tool_input("openeo_generate_graph", generate_graph_input)

        assert result.valid is True

    def test_validate_tool_input_missing_required(self):
        """Test validation catches missing required fields."""
        tool_input = {
            "description": "Calculate NDVI"
            # Missing: collection, spatial_extent, temporal_extent
        }

        result = validate_tool_input("openeo_generate_graph", tool_input)

        assert result.valid is False
        assert len(result.errors) >= 3  # At least 3 missing fields

    def test_validate_tool_input_invalid_extent(self):
        """Test validation of invalid spatial extent."""
        tool_input = {
            "description": "Test",
            "collection": "sentinel-2-l2a",
            "spatial_extent": {
                "west": 200,  # Invalid: > 180
                "south": 46,
                "east": 11,
                "north": 47
            },
            "temporal_extent": ["2024-01-01", "2024-01-31"]
        }

        result = validate_tool_input("openeo_generate_graph", tool_input)

        # Should have validation error for west > 180
        assert result.valid is False or len(result.warnings) > 0


class TestDeepValidation:
    """Tests for deep semantic validation."""

    def test_deep_validate_invalid_bands(self):
        """Test deep validation catches invalid band names."""
        from openeo_ai.utils.schema_validator import deep_validate_graph

        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1},
                    "temporal_extent": ["2024-06-01", "2024-06-30"],
                    "bands": ["B04", "B08"]  # Old-style band names
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = deep_validate_graph(pg)

        # Should catch invalid bands
        assert result.valid is False
        error_messages = [e.message for e in result.errors]
        assert any("band" in m.lower() for m in error_messages)

    def test_deep_validate_invalid_date(self):
        """Test deep validation catches invalid date format."""
        from openeo_ai.utils.schema_validator import deep_validate_graph

        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1},
                    "temporal_extent": ["June 1 2024", "2024-06-30"]  # Invalid format
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = deep_validate_graph(pg)

        # Should catch invalid date format
        error_messages = [e.message for e in result.errors]
        assert any("date" in m.lower() or "format" in m.lower() for m in error_messages)

    def test_deep_validate_large_extent_warning(self):
        """Test deep validation warns about large extents."""
        from openeo_ai.utils.schema_validator import deep_validate_graph

        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 0, "south": 40, "east": 10, "north": 50},  # 10 degrees
                    "temporal_extent": ["2024-06-01", "2024-06-30"],
                    "bands": ["red", "nir"]
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = deep_validate_graph(pg)

        # Should warn about large extent
        assert any("large" in w.lower() or "extent" in w.lower() for w in result.warnings)


# ============================================================================
# Integration Tests
# ============================================================================

class TestToolExecution:
    """Integration tests for tool execution."""

    @pytest.mark.asyncio
    async def test_validate_graph_tool(self, simple_process_graph):
        """Test the validate_graph tool function."""
        from openeo_ai.tools.validation_tools import validate_graph_tool

        result = await validate_graph_tool({"process_graph": simple_process_graph})

        assert "content" in result
        content = result["content"]
        assert len(content) > 0

        # Parse the JSON response
        text = content[0].get("text", "{}")
        data = json.loads(text)
        assert "valid" in data
        assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_graph_tool_invalid(self, invalid_process_graph):
        """Test validate_graph tool with invalid input."""
        from openeo_ai.tools.validation_tools import validate_graph_tool

        result = await validate_graph_tool({"process_graph": invalid_process_graph})

        content = result["content"]
        text = content[0].get("text", "{}")
        data = json.loads(text)

        assert data["valid"] is False
        assert len(data["errors"]) > 0


class TestToolWithErrorHandler:
    """Test tools integrated with error handler."""

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test that tool errors are properly handled."""
        from openeo_ai.utils.error_handler import ErrorHandler, ErrorContext

        handler = ErrorHandler()

        # Simulate a tool error
        try:
            raise ValueError("Missing required argument 'id'")
        except Exception as e:
            context = ErrorContext(
                tool_name="openeo_create_job",
                tool_input={"title": "Test"}
            )
            result = handler.handle_exception(e, context)

            assert result.error_type == ErrorType.VALIDATION
            assert result.context.tool_name == "openeo_create_job"
            assert len(result.suggestions) > 0
