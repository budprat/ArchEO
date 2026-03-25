"""Shared test fixtures for the OpenEO deployment test suite.

Provides mock objects, sample data, and temporary directories so tests
can run without network access, PostgreSQL, or other external services.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
import xarray as xr


# ---------------------------------------------------------------------------
# Temporary directory fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_results_dir(tmp_path):
    """Create a temporary directory for result storage."""
    results_dir = tmp_path / "openeo_results"
    results_dir.mkdir()
    return results_dir


@pytest.fixture
def sample_job_id():
    """Return a deterministic job UUID for testing."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


# ---------------------------------------------------------------------------
# Sample xarray data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_dataarray():
    """Create a small xarray DataArray with realistic EO-like values."""
    data = np.random.default_rng(42).uniform(0.0, 1.0, size=(3, 10, 10))
    return xr.DataArray(
        data,
        dims=["bands", "y", "x"],
        coords={
            "bands": ["red", "nir", "blue"],
            "y": np.linspace(46.0, 46.1, 10),
            "x": np.linspace(11.0, 11.1, 10),
        },
    )


@pytest.fixture
def sample_dataset():
    """Create a small xarray Dataset with two variables."""
    rng = np.random.default_rng(42)
    return xr.Dataset(
        {
            "ndvi": xr.DataArray(rng.uniform(-1, 1, (10, 10)), dims=["y", "x"]),
            "evi": xr.DataArray(rng.uniform(-1, 1, (10, 10)), dims=["y", "x"]),
        }
    )


@pytest.fixture
def all_nan_dataarray():
    """Create a DataArray filled with NaN values."""
    return xr.DataArray(np.full((10, 10), np.nan), dims=["y", "x"])


# ---------------------------------------------------------------------------
# Sample spatial / temporal extents
# ---------------------------------------------------------------------------

@pytest.fixture
def small_spatial_extent():
    """A small spatial extent around Innsbruck, Austria."""
    return {"west": 11.0, "south": 46.0, "east": 11.1, "north": 46.1}


@pytest.fixture
def large_spatial_extent():
    """A large spatial extent spanning most of India."""
    return {"west": 68.0, "south": 8.0, "east": 97.0, "north": 37.0}


@pytest.fixture
def sample_temporal_extent():
    """A one-month temporal extent."""
    return ["2024-06-01", "2024-06-30"]


# ---------------------------------------------------------------------------
# Sample process graphs
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_add_graph():
    """A minimal process graph that adds two numbers."""
    return {
        "add1": {
            "process_id": "add",
            "arguments": {"x": 3, "y": 5},
            "result": True,
        }
    }


@pytest.fixture
def ndvi_process_graph(small_spatial_extent, sample_temporal_extent):
    """An NDVI computation process graph."""
    return {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": small_spatial_extent,
                "temporal_extent": sample_temporal_extent,
                "bands": ["red", "nir"],
            },
        },
        "nir": {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": "load"},
                "index": 1,
                "dimension": "bands",
            },
        },
        "red": {
            "process_id": "array_element",
            "arguments": {
                "data": {"from_node": "load"},
                "index": 0,
                "dimension": "bands",
            },
        },
        "ndvi": {
            "process_id": "normalized_difference",
            "arguments": {
                "x": {"from_node": "nir"},
                "y": {"from_node": "red"},
            },
        },
        "save": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "ndvi"},
                "format": "GTiff",
            },
            "result": True,
        },
    }


# ---------------------------------------------------------------------------
# Mock STAC API responses
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_stac_collections_response():
    """Sample STAC collections response."""
    return {
        "collections": [
            {
                "id": "sentinel-2-l2a",
                "title": "Sentinel-2 Level-2A",
                "description": "Atmospherically corrected surface reflectance",
            },
            {
                "id": "landsat-c2-l2",
                "title": "Landsat Collection 2 Level 2",
                "description": "Surface reflectance and temperature",
            },
            {
                "id": "cop-dem-glo-30",
                "title": "Copernicus DEM GLO-30",
                "description": "Global 30m digital elevation model",
            },
        ]
    }


@pytest.fixture
def mock_stac_collection_detail():
    """Sample detailed STAC collection metadata."""
    return {
        "id": "sentinel-2-l2a",
        "title": "Sentinel-2 Level-2A",
        "description": "Atmospherically corrected surface reflectance",
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [["2015-06-27T00:00:00Z", None]]},
        },
        "item_assets": {
            "red": {
                "eo:bands": [
                    {"name": "red", "common_name": "red", "description": "Red band"}
                ]
            },
            "nir": {
                "eo:bands": [
                    {"name": "nir", "common_name": "nir", "description": "NIR band"}
                ]
            },
        },
    }


# ---------------------------------------------------------------------------
# Mock HTTP client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# Mock Nominatim geocoder
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_nominatim_result():
    """A mock geopy Nominatim result."""
    result = MagicMock()
    result.latitude = 48.8566
    result.longitude = 2.3522
    result.address = "Paris, Ile-de-France, France"
    result.raw = {
        "name": "Paris",
        "importance": 0.9,
        "boundingbox": ["48.815573", "48.902145", "2.224199", "2.469920"],
    }
    return result


# ---------------------------------------------------------------------------
# Mock PostgreSQL connection
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_pg_connection():
    """Create a mock PostgreSQL connection."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock()
    conn.cursor.return_value.__exit__ = MagicMock()
    return conn


# ---------------------------------------------------------------------------
# Mock Claude / Anthropic API client
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_claude_client():
    """Create a mock Anthropic/Claude API client."""
    client = MagicMock()
    client.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text="Sample AI response")],
            stop_reason="end_turn",
        )
    )
    return client
