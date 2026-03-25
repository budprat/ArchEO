# ABOUTME: Unit tests for validation utilities.
# Tests process graph validation, schema validation, and error classification.

"""
Unit tests for validation utilities.

Tests:
- ValidationTools from validation_tools.py
- SchemaValidator from schema_validator.py
- Process graph structure validation
- Band name validation
- Temporal format validation
- Extent size validation
"""

import json
import pytest
from datetime import datetime, timedelta

from openeo_ai.tools.validation_tools import ValidationTools, ValidationResult
from openeo_ai.utils.schema_validator import (
    SchemaValidator,
    SchemaValidationResult,
    SchemaValidationError,
    validate_process_graph,
    validate_tool_input,
    deep_validate_graph,
)


# ============================================================================
# ValidationTools Tests
# ============================================================================

class TestValidationTools:
    """Tests for ValidationTools class."""

    @pytest.fixture
    def validator(self):
        """Create ValidationTools instance."""
        return ValidationTools()

    @pytest.mark.asyncio
    async def test_validate_simple_graph(self, validator, simple_process_graph):
        """Test validation of a simple valid graph."""
        result = await validator.validate(simple_process_graph)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_ndvi_graph(self, validator, ndvi_process_graph):
        """Test validation of NDVI calculation graph."""
        result = await validator.validate(ndvi_process_graph)

        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_empty_graph(self, validator):
        """Test validation rejects empty graph."""
        result = await validator.validate({})

        assert result["valid"] is False
        assert any("empty" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_non_dict(self, validator):
        """Test validation rejects non-dict input."""
        result = await validator.validate("not a dict")

        assert result["valid"] is False
        assert any("dictionary" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_missing_process_id(self, validator):
        """Test validation catches missing process_id."""
        pg = {
            "node1": {
                "arguments": {"x": 1}
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("process_id" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_missing_result_node(self, validator):
        """Test validation catches missing result node."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("result" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_multiple_result_nodes(self, validator):
        """Test validation catches multiple result nodes."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"},
                "result": True
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("multiple" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_invalid_reference(self, validator):
        """Test validation catches invalid node references."""
        pg = {
            "save1": {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "nonexistent"},
                    "format": "GTiff"
                },
                "result": True
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("unknown node" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_circular_reference(self, validator, cyclic_process_graph):
        """Test validation catches circular references."""
        result = await validator.validate(cyclic_process_graph)

        assert result["valid"] is False
        assert any("circular" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_missing_required_argument(self, validator):
        """Test validation catches missing required arguments."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {}  # Missing 'id'
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("missing required" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_band_names(self, validator):
        """Test validation warns about old-style band names."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1},
                    "bands": ["B04", "B08"]  # Old-style names
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = await validator.validate(pg)

        # Should have warnings or errors about band names
        all_messages = result["errors"] + result["warnings"]
        assert any("band" in m.lower() for m in all_messages)

    @pytest.mark.asyncio
    async def test_validate_large_extent_warning(self, validator):
        """Test validation warns about large extents."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 0, "south": 40, "east": 20, "north": 60},  # Very large
                    "temporal_extent": ["2024-01-01", "2024-12-31"]
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = await validator.validate(pg)

        assert any("large" in w.lower() or "extent" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_temporal_format(self, validator):
        """Test validation catches invalid date formats."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "temporal_extent": ["invalid-date", "2024-06-30"]
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = await validator.validate(pg)

        assert result["valid"] is False
        assert any("date" in e.lower() or "format" in e.lower() for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_generates_suggestions(self, validator):
        """Test validation generates useful suggestions."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1},
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

        result = await validator.validate(pg)

        # Should have suggestions about cloud masking or time reduction
        assert len(result["suggestions"]) > 0

    @pytest.mark.asyncio
    async def test_validate_resource_estimate(self, validator, simple_process_graph):
        """Test validation provides resource estimates."""
        result = await validator.validate(simple_process_graph)

        assert "resource_estimate" in result
        assert "complexity" in result["resource_estimate"]


# ============================================================================
# SchemaValidator Tests
# ============================================================================

class TestSchemaValidator:
    """Tests for SchemaValidator class."""

    @pytest.fixture
    def schema_validator(self):
        """Create SchemaValidator instance."""
        return SchemaValidator()

    def test_validate_process_graph_structure(self, schema_validator, simple_process_graph):
        """Test basic structure validation."""
        result = schema_validator.validate_process_graph(simple_process_graph)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_process_graph_empty(self, schema_validator):
        """Test empty graph validation."""
        result = schema_validator.validate_process_graph({})

        assert result.valid is False
        assert any("empty" in e.message.lower() for e in result.errors)

    def test_validate_process_graph_non_dict(self, schema_validator):
        """Test non-dict input."""
        result = schema_validator.validate_process_graph([1, 2, 3])

        assert result.valid is False
        assert any("object" in e.message.lower() for e in result.errors)

    def test_validate_tool_input_valid(self, schema_validator, generate_graph_input):
        """Test valid tool input validation."""
        result = schema_validator.validate_tool_input(
            "openeo_generate_graph",
            generate_graph_input
        )

        assert result.valid is True

    def test_validate_tool_input_missing_fields(self, schema_validator):
        """Test missing required fields."""
        result = schema_validator.validate_tool_input(
            "openeo_generate_graph",
            {"description": "Test only"}
        )

        assert result.valid is False
        # Should report missing collection, spatial_extent, temporal_extent
        error_paths = [e.path for e in result.errors]
        assert len(error_paths) >= 3

    def test_validate_tool_input_unknown_tool(self, schema_validator):
        """Test validation for unknown tool."""
        result = schema_validator.validate_tool_input(
            "unknown_tool",
            {"some": "input"}
        )

        # Should pass basic validation for unknown tools
        assert result.valid is True

    def test_deep_validate_valid_graph(self, schema_validator, simple_process_graph):
        """Test deep validation of valid graph."""
        result = schema_validator.deep_validate(simple_process_graph)

        assert result.valid is True

    def test_deep_validate_invalid_collection(self, schema_validator):
        """Test deep validation catches invalid collection."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "invalid-collection-xyz",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1}
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = schema_validator.deep_validate(pg)

        # Should warn about unknown collection
        assert any("unknown collection" in w.lower() for w in result.warnings)

    def test_deep_validate_invalid_bands(self, schema_validator):
        """Test deep validation catches invalid bands."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1},
                    "bands": ["invalid_band", "another_invalid"]
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = schema_validator.deep_validate(pg)

        assert result.valid is False
        assert any("band" in e.message.lower() for e in result.errors)

    def test_validation_result_to_user_message(self):
        """Test ValidationResult formatting."""
        result = SchemaValidationResult(
            valid=False,
            errors=[
                SchemaValidationError(path="$.load1.arguments.id", message="Missing required field")
            ],
            warnings=["Large extent detected"]
        )

        message = result.to_user_message()

        assert "Validation Failed" in message
        assert "Missing required" in message
        assert "Large extent" in message

    def test_validation_result_to_dict(self):
        """Test ValidationResult serialization."""
        result = SchemaValidationResult(
            valid=True,
            warnings=["Consider adding cloud masking"]
        )

        data = result.to_dict()

        assert data["valid"] is True
        assert len(data["warnings"]) == 1
        assert len(data["errors"]) == 0


# ============================================================================
# Convenience Function Tests
# ============================================================================

class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_validate_process_graph_function(self, simple_process_graph):
        """Test validate_process_graph function."""
        result = validate_process_graph(simple_process_graph)

        assert isinstance(result, SchemaValidationResult)
        assert result.valid is True

    def test_validate_tool_input_function(self, generate_graph_input):
        """Test validate_tool_input function."""
        result = validate_tool_input("openeo_generate_graph", generate_graph_input)

        assert isinstance(result, SchemaValidationResult)
        assert result.valid is True

    def test_deep_validate_graph_function(self, simple_process_graph):
        """Test deep_validate_graph function."""
        result = deep_validate_graph(simple_process_graph)

        assert isinstance(result, SchemaValidationResult)


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_nested_from_node_references(self):
        """Test deeply nested from_node references."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": 11, "south": 46, "east": 11.1, "north": 46.1}
                }
            },
            "reduce1": {
                "process_id": "reduce_dimension",
                "arguments": {
                    "data": {"from_node": "load1"},
                    "dimension": "time",
                    "reducer": {
                        "process_graph": {
                            "mean1": {
                                "process_id": "mean",
                                "arguments": {
                                    "data": {"from_parameter": "data"}
                                },
                                "result": True
                            }
                        }
                    }
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "reduce1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = validate_process_graph(pg)
        assert result.valid is True

    def test_array_from_node_references(self):
        """Test from_node in array arguments."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            },
            "load2": {
                "process_id": "load_collection",
                "arguments": {"id": "cop-dem-glo-30"}
            },
            "merge1": {
                "process_id": "merge_cubes",
                "arguments": {
                    "cube1": {"from_node": "load1"},
                    "cube2": {"from_node": "load2"}
                },
                "result": True
            }
        }

        result = validate_process_graph(pg)
        # Missing spatial extents but structure should be valid
        assert len([e for e in result.errors if "unknown node" in e.message.lower()]) == 0

    def test_null_temporal_extent(self):
        """Test null values in temporal extent."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "temporal_extent": [None, "2024-06-30"]  # Open start
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = validate_process_graph(pg)
        # Should handle null gracefully
        assert not any("null" in e.message.lower() for e in result.errors if "format" not in e.message.lower())

    def test_extreme_coordinates(self):
        """Test validation with extreme coordinates."""
        pg = {
            "load1": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {"west": -180, "south": -90, "east": 180, "north": 90}
                }
            },
            "save1": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load1"}, "format": "GTiff"},
                "result": True
            }
        }

        result = deep_validate_graph(pg)
        # Should warn about global extent
        assert any("large" in w.lower() for w in result.warnings)
