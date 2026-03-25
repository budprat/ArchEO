"""
Phase 2: Process Graph Validation Tests

Test-Driven Development: These tests define the expected behavior
of the process graph validator before implementation.

Tests cover:
- Structural validation
- Process validation
- Data flow validation
- Band validation
- Extent validation
- Resource estimation
- Educational feedback
"""

import pytest
from unittest.mock import Mock, patch


class TestStructuralValidation:
    """Test basic structural validation of process graphs."""

    @pytest.mark.asyncio
    async def test_empty_graph_invalid(self):
        """Empty process graph should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate({})

        assert result["valid"] is False
        assert any("empty" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_non_dict_graph_invalid(self):
        """Non-dictionary process graph should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate([])  # Array instead of dict

        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_missing_result_node_invalid(self):
        """Graph without result node should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("result" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_multiple_result_nodes_warning(self):
        """Graph with multiple result nodes should warn."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"},
                "result": True
            },
            "save": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load"}, "format": "GTiff"},
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should either be invalid or have a warning
        assert not result["valid"] or len(result["warnings"]) > 0


class TestProcessValidation:
    """Test process ID and argument validation."""

    @pytest.mark.asyncio
    async def test_missing_process_id_invalid(self):
        """Node without process_id should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "node1": {
                "arguments": {"x": 1},
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("process_id" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_unknown_process_warning(self):
        """Unknown process should generate warning (not error)."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "node1": {
                "process_id": "completely_unknown_process_xyz",
                "arguments": {},
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Unknown process could be a user-defined process, so just warn
        # Unless we're in strict mode
        assert len(result["warnings"]) > 0 or not result["valid"]

    @pytest.mark.asyncio
    async def test_missing_required_argument_invalid(self):
        """Missing required argument should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {},  # Missing required 'id' argument
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("id" in err.lower() or "required" in err.lower()
                   for err in result["errors"])

    @pytest.mark.asyncio
    async def test_save_result_missing_format_invalid(self):
        """save_result without format should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            },
            "save": {
                "process_id": "save_result",
                "arguments": {"data": {"from_node": "load"}},  # Missing format
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("format" in err.lower() for err in result["errors"])


class TestDataFlowValidation:
    """Test data flow and node reference validation."""

    @pytest.mark.asyncio
    async def test_invalid_from_node_reference(self):
        """Invalid from_node reference should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            },
            "filter": {
                "process_id": "filter_bands",
                "arguments": {
                    "data": {"from_node": "nonexistent"},
                    "bands": ["red"]
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("nonexistent" in err.lower() or "reference" in err.lower()
                   for err in result["errors"])

    @pytest.mark.asyncio
    async def test_circular_reference_invalid(self):
        """Circular references should be invalid."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "node1": {
                "process_id": "add",
                "arguments": {
                    "x": {"from_node": "node2"},
                    "y": 1
                }
            },
            "node2": {
                "process_id": "add",
                "arguments": {
                    "x": {"from_node": "node1"},
                    "y": 2
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("circular" in err.lower() or "cycle" in err.lower()
                   for err in result["errors"])

    @pytest.mark.asyncio
    async def test_nested_from_node_reference(self):
        """Nested from_node references should be validated."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {"id": "sentinel-2-l2a"}
            },
            "reduce": {
                "process_id": "reduce_dimension",
                "arguments": {
                    "data": {"from_node": "load"},
                    "dimension": "time",
                    "reducer": {
                        "process_graph": {
                            "mean": {
                                "process_id": "mean",
                                "arguments": {
                                    "data": {"from_parameter": "data"}
                                },
                                "result": True
                            }
                        }
                    }
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should be valid - nested process graphs with from_parameter are ok
        assert result["valid"] is True


class TestBandValidation:
    """Test band name validation against collection capabilities."""

    @pytest.mark.asyncio
    async def test_invalid_band_name_error(self):
        """Invalid band name for collection should error."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "bands": ["B04", "B08"]  # Should be "red", "nir"
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should warn or error about band names
        has_band_issue = (
            any("band" in err.lower() or "B04" in err for err in result["errors"]) or
            any("band" in warn.lower() or "B04" in warn for warn in result["warnings"])
        )
        assert has_band_issue

    @pytest.mark.asyncio
    async def test_valid_band_names_pass(self):
        """Valid band names should pass validation."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "bands": ["red", "nir"]  # Correct AWS band names
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should not have band-related errors
        band_errors = [e for e in result["errors"] if "band" in e.lower()]
        assert len(band_errors) == 0

    @pytest.mark.asyncio
    async def test_suggest_band_name_correction(self):
        """Should suggest correct band names."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "bands": ["B04"]  # Wrong
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should have a suggestion about using "red" instead
        suggestions_text = " ".join(result.get("suggestions", []))
        assert "red" in suggestions_text.lower() or len(result["suggestions"]) > 0


class TestExtentValidation:
    """Test spatial and temporal extent validation."""

    @pytest.mark.asyncio
    async def test_large_spatial_extent_warning(self):
        """Very large spatial extent should warn."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {
                        "west": 0, "east": 10,  # 10 degrees
                        "south": 40, "north": 50
                    }
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert len(result["warnings"]) > 0
        assert any("large" in warn.lower() or "extent" in warn.lower()
                   for warn in result["warnings"])

    @pytest.mark.asyncio
    async def test_very_large_extent_error(self):
        """Extremely large extent should error or strong warning."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {
                        "west": -180, "east": 180,  # Global!
                        "south": -90, "north": 90
                    }
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should have error or strong warning
        has_extent_issue = (
            len(result["errors"]) > 0 or
            any("timeout" in warn.lower() or "fail" in warn.lower()
                for warn in result["warnings"])
        )
        assert has_extent_issue

    @pytest.mark.asyncio
    async def test_long_temporal_range_warning(self):
        """Very long temporal range should warn."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "temporal_extent": ["2020-01-01", "2024-12-31"]  # 5 years
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert len(result["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_temporal_format_error(self):
        """Invalid temporal format should error."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "temporal_extent": ["not-a-date", "also-not"]
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        assert result["valid"] is False
        assert any("date" in err.lower() or "temporal" in err.lower()
                   for err in result["errors"])


class TestResourceEstimation:
    """Test resource estimation functionality."""

    @pytest.mark.asyncio
    async def test_resource_estimate_included(self, ndvi_process_graph):
        """Validation should include resource estimate."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(ndvi_process_graph)

        assert "resource_estimate" in result
        estimate = result["resource_estimate"]

        # Should have some estimate fields
        assert any(key in estimate for key in [
            "estimated_size_mb", "estimated_time_seconds", "complexity"
        ])

    @pytest.mark.asyncio
    async def test_resource_estimate_scales_with_extent(self):
        """Resource estimate should scale with extent size."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()

        small_graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {
                        "west": 11.0, "east": 11.01,
                        "south": 46.0, "north": 46.01
                    }
                },
                "result": True
            }
        }

        large_graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {
                        "west": 11.0, "east": 12.0,  # 100x larger
                        "south": 46.0, "north": 47.0
                    }
                },
                "result": True
            }
        }

        small_result = await tools.validate(small_graph)
        large_result = await tools.validate(large_graph)

        # Large extent should have larger or equal estimate
        # (implementation may return "unknown" in which case skip comparison)
        small_est = small_result["resource_estimate"]
        large_est = large_result["resource_estimate"]

        if small_est.get("complexity") and large_est.get("complexity"):
            # At minimum, large should not be "low" if small is "high"
            complexity_order = ["low", "medium", "high", "very_high"]
            if small_est["complexity"] in complexity_order and large_est["complexity"] in complexity_order:
                small_idx = complexity_order.index(small_est["complexity"])
                large_idx = complexity_order.index(large_est["complexity"])
                assert large_idx >= small_idx


class TestEducationalSuggestions:
    """Test educational suggestions and feedback."""

    @pytest.mark.asyncio
    async def test_suggest_cloud_masking_for_sentinel(self):
        """Should suggest cloud masking for Sentinel-2."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "bands": ["red", "nir"]
                }
            },
            "ndvi": {
                "process_id": "normalized_difference",
                "arguments": {
                    "x": {"from_node": "load"},
                    "y": {"from_node": "load"}
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        suggestions = " ".join(result.get("suggestions", []))
        assert "cloud" in suggestions.lower() or "scl" in suggestions.lower()

    @pytest.mark.asyncio
    async def test_suggest_temporal_reduction(self):
        """Should suggest temporal reduction when appropriate."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "temporal_extent": ["2024-06-01", "2024-08-31"]  # 3 months
                }
            },
            "save": {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "load"},
                    "format": "GTiff"
                },
                "result": True
            }
        }
        result = await tools.validate(graph)

        suggestions = " ".join(result.get("suggestions", []))
        # Should suggest reduce_dimension over time
        assert "reduce" in suggestions.lower() or "time" in suggestions.lower()

    @pytest.mark.asyncio
    async def test_explain_ndvi_requirements(self):
        """Should explain NDVI band requirements if misconfigured."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "bands": ["red"]  # Missing NIR for NDVI
                }
            },
            "ndvi": {
                "process_id": "ndvi",
                "arguments": {"data": {"from_node": "load"}},
                "result": True
            }
        }
        result = await tools.validate(graph)

        # Should warn about missing NIR band
        all_messages = " ".join(
            result.get("errors", []) +
            result.get("warnings", []) +
            result.get("suggestions", [])
        )
        assert "nir" in all_messages.lower() or "band" in all_messages.lower()


class TestValidationResult:
    """Test validation result structure."""

    @pytest.mark.asyncio
    async def test_result_has_required_fields(self, ndvi_process_graph):
        """Validation result should have all required fields."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(ndvi_process_graph)

        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "suggestions" in result
        assert "resource_estimate" in result

        assert isinstance(result["valid"], bool)
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)
        assert isinstance(result["suggestions"], list)
        assert isinstance(result["resource_estimate"], dict)

    @pytest.mark.asyncio
    async def test_result_serializable(self, ndvi_process_graph):
        """Validation result should be JSON serializable."""
        import json
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(ndvi_process_graph)

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["valid"] == result["valid"]
