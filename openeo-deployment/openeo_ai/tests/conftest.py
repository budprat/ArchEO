# ABOUTME: Pytest fixtures for OpenEO AI tests.
# Provides reusable test fixtures for mocking APIs, creating test data, and setup.

"""
Pytest configuration and fixtures for OpenEO AI tests.

Provides:
- Mock Anthropic client
- Test process graphs
- Sample spatial/temporal extents
- Mock STAC responses
- Session fixtures
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def test_config():
    """Test configuration settings."""
    return {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "max_turns": 10,
        "openeo_url": "http://localhost:8000/openeo/1.1.0",
        "stac_api_url": "https://earth-search.aws.element84.com/v1/",
        "sqlite_path": ":memory:",
    }


@pytest.fixture
def mock_env(test_config, monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-api-key")
    monkeypatch.setenv("OPENEO_URL", test_config["openeo_url"])
    monkeypatch.setenv("STAC_API_URL", test_config["stac_api_url"])
    monkeypatch.setenv("OPENEO_AI_DB", test_config["sqlite_path"])
    return test_config


# ============================================================================
# Process Graph Fixtures
# ============================================================================

@pytest.fixture
def simple_process_graph():
    """Simple process graph with just load_collection and save_result."""
    return {
        "load1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": {
                    "west": 11.0,
                    "south": 46.0,
                    "east": 11.1,
                    "north": 46.1
                },
                "temporal_extent": ["2024-06-01", "2024-06-30"],
                "bands": ["red", "nir"]
            }
        },
        "save1": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "load1"},
                "format": "GTiff"
            },
            "result": True
        }
    }


@pytest.fixture
def ndvi_process_graph():
    """NDVI calculation process graph."""
    return {
        "load1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": {
                    "west": 11.0,
                    "south": 46.0,
                    "east": 11.1,
                    "north": 46.1
                },
                "temporal_extent": ["2024-06-01", "2024-06-30"],
                "bands": ["red", "nir"]
            }
        },
        "ndvi1": {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": "load1"},
                "nir": "nir",
                "red": "red"
            }
        },
        "reduce1": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "ndvi1"},
                "dimension": "time",
                "reducer": {
                    "process_graph": {
                        "mean1": {
                            "process_id": "mean",
                            "arguments": {"data": {"from_parameter": "data"}},
                            "result": True
                        }
                    }
                }
            }
        },
        "save1": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "reduce1"},
                "format": "GTiff"
            },
            "result": True
        }
    }


@pytest.fixture
def invalid_process_graph():
    """Invalid process graph for testing validation."""
    return {
        "load1": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "bands": ["B04", "B08"]  # Invalid band names
            }
            # Missing spatial_extent
        },
        "ndvi1": {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": "unknown_node"}  # Invalid reference
            }
        }
        # Missing result node
    }


@pytest.fixture
def cyclic_process_graph():
    """Process graph with circular reference."""
    return {
        "node1": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "node2"},
                "y": 1
            }
        },
        "node2": {
            "process_id": "multiply",
            "arguments": {
                "x": {"from_node": "node1"},
                "y": 2
            },
            "result": True
        }
    }


# ============================================================================
# Spatial/Temporal Fixtures
# ============================================================================

@pytest.fixture
def sample_spatial_extent():
    """Sample spatial extent for testing."""
    return {
        "west": 11.0,
        "south": 46.0,
        "east": 11.1,
        "north": 46.1
    }


@pytest.fixture
def large_spatial_extent():
    """Large spatial extent that should trigger warnings."""
    return {
        "west": -10.0,
        "south": 35.0,
        "east": 10.0,
        "north": 55.0
    }


@pytest.fixture
def sample_temporal_extent():
    """Sample temporal extent for testing."""
    return ["2024-06-01", "2024-06-30"]


@pytest.fixture
def long_temporal_extent():
    """Long temporal extent that should trigger warnings."""
    start = datetime.now() - timedelta(days=730)
    end = datetime.now()
    return [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for testing without API calls."""
    mock_client = AsyncMock()

    # Create mock response
    mock_response = MagicMock()
    mock_response.content = [
        MagicMock(type="text", text="I'll help you with that analysis.")
    ]
    mock_response.stop_reason = "end_turn"

    mock_client.messages.create = AsyncMock(return_value=mock_response)

    return mock_client


@pytest.fixture
def mock_anthropic_tool_response():
    """Mock Anthropic response with tool use."""
    mock_response = MagicMock()

    # Tool use block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_123"
    tool_block.name = "openeo_list_collections"
    tool_block.input = {}

    mock_response.content = [tool_block]
    mock_response.stop_reason = "tool_use"

    return mock_response


@pytest.fixture
def mock_stac_collections():
    """Mock STAC collections response."""
    return {
        "collections": [
            {
                "id": "sentinel-2-l2a",
                "title": "Sentinel-2 Level-2A",
                "description": "Sentinel-2 atmospherically corrected imagery",
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [["2015-06-27", None]]}
                }
            },
            {
                "id": "landsat-c2-l2",
                "title": "Landsat Collection 2 Level-2",
                "description": "Landsat surface reflectance",
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [["1982-08-22", None]]}
                }
            },
            {
                "id": "cop-dem-glo-30",
                "title": "Copernicus DEM 30m",
                "description": "Copernicus Digital Elevation Model 30m",
                "extent": {
                    "spatial": {"bbox": [[-180, -90, 180, 90]]},
                    "temporal": {"interval": [["2021-04-22", "2021-04-22"]]}
                }
            }
        ]
    }


@pytest.fixture
def mock_stac_search_response():
    """Mock STAC search response."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "S2A_MSIL2A_20240615T101021_N0510_R022_T32TQM_20240615T142056",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[10.5, 45.5], [11.5, 45.5], [11.5, 46.5], [10.5, 46.5], [10.5, 45.5]]]
                },
                "properties": {
                    "datetime": "2024-06-15T10:10:21Z",
                    "eo:cloud_cover": 15.2
                },
                "assets": {
                    "red": {"href": "https://example.com/red.tif"},
                    "nir": {"href": "https://example.com/nir.tif"}
                }
            }
        ]
    }


# ============================================================================
# Tool Input Fixtures
# ============================================================================

@pytest.fixture
def generate_graph_input(sample_spatial_extent, sample_temporal_extent):
    """Input for openeo_generate_graph tool."""
    return {
        "description": "Calculate NDVI for vegetation monitoring",
        "collection": "sentinel-2-l2a",
        "spatial_extent": sample_spatial_extent,
        "temporal_extent": sample_temporal_extent,
        "output_format": "GTiff"
    }


@pytest.fixture
def create_job_input(simple_process_graph):
    """Input for openeo_create_job tool."""
    return {
        "title": "Test NDVI Job",
        "process_graph": simple_process_graph,
        "description": "Test job for unit tests"
    }


@pytest.fixture
def viz_map_input(tmp_path):
    """Input for viz_show_map tool."""
    # Create a dummy GeoTIFF path
    geotiff_path = tmp_path / "test_result.tif"
    geotiff_path.touch()
    return {
        "geotiff_path": str(geotiff_path),
        "title": "Test Map",
        "colormap": "viridis"
    }


# ============================================================================
# Error Fixtures
# ============================================================================

@pytest.fixture
def validation_error():
    """Sample validation error."""
    return ValueError("Missing required argument 'id' in load_collection")


@pytest.fixture
def network_error():
    """Sample network error."""
    return ConnectionError("Failed to connect to STAC API")


@pytest.fixture
def data_quality_error():
    """Sample data quality error."""
    return ValueError("No data found for the specified extent and time range")


# ============================================================================
# Session Fixtures
# ============================================================================

@pytest.fixture
def sample_session():
    """Sample session data."""
    return {
        "session_id": "test-session-123",
        "user_id": "test-user",
        "created_at": datetime.now().isoformat(),
        "context": {
            "messages": [
                {"role": "user", "content": "Calculate NDVI for Kerala"},
                {"role": "assistant", "content": "I'll help you calculate NDVI for Kerala."}
            ]
        }
    }


@pytest.fixture
def sample_messages():
    """Sample message history."""
    return [
        {"role": "user", "content": "What collections are available?"},
        {"role": "assistant", "content": "Let me check the available collections."},
        {"role": "user", "content": "Show me Sentinel-2 data for Mumbai."}
    ]


# ============================================================================
# Async Test Helpers
# ============================================================================

@pytest.fixture
def event_loop_policy():
    """Configure event loop for async tests."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# ============================================================================
# Cleanup Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_singletons():
    """Reset module-level singletons between tests."""
    from openeo_ai.utils import error_handler, schema_validator

    # Reset error handler singleton
    error_handler._default_handler = None

    # Reset schema validator singleton
    schema_validator._default_validator = None

    yield

    # Cleanup after test
    error_handler._default_handler = None
    schema_validator._default_validator = None
