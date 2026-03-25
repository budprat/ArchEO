"""
Shared test fixtures for OpenEO AI Assistant tests.

These fixtures provide common test data and mock objects used across
all test modules.
"""

import pytest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
import tempfile
import json

import numpy as np
import xarray as xr


# =============================================================================
# Sample Process Graphs
# =============================================================================

@pytest.fixture
def simple_add_graph():
    """Simple addition process graph."""
    return {
        "add1": {
            "process_id": "add",
            "arguments": {"x": 1, "y": 2},
            "result": True
        }
    }


@pytest.fixture
def ndvi_process_graph():
    """NDVI calculation process graph."""
    return {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": {
                    "west": 11.0,
                    "south": 46.0,
                    "east": 11.01,
                    "north": 46.01
                },
                "temporal_extent": ["2024-06-01", "2024-06-10"],
                "bands": ["red", "nir"]
            }
        },
        "red": {
            "process_id": "filter_bands",
            "arguments": {
                "data": {"from_node": "load"},
                "bands": ["red"]
            }
        },
        "nir": {
            "process_id": "filter_bands",
            "arguments": {
                "data": {"from_node": "load"},
                "bands": ["nir"]
            }
        },
        "ndvi": {
            "process_id": "normalized_difference",
            "arguments": {
                "x": {"from_node": "nir"},
                "y": {"from_node": "red"}
            }
        },
        "save": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "ndvi"},
                "format": "GTiff"
            },
            "result": True
        }
    }


@pytest.fixture
def invalid_process_graph_missing_result():
    """Process graph missing result node."""
    return {
        "load": {
            "process_id": "load_collection",
            "arguments": {"id": "sentinel-2-l2a"}
        }
        # No result: True on any node
    }


@pytest.fixture
def invalid_process_graph_bad_reference():
    """Process graph with bad node reference."""
    return {
        "load": {
            "process_id": "load_collection",
            "arguments": {"id": "sentinel-2-l2a"}
        },
        "filter": {
            "process_id": "filter_bands",
            "arguments": {
                "data": {"from_node": "nonexistent_node"},  # Bad reference
                "bands": ["red"]
            },
            "result": True
        }
    }


@pytest.fixture
def process_graph_large_extent():
    """Process graph with very large spatial extent."""
    return {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": {
                    "west": 0.0,
                    "south": 40.0,
                    "east": 10.0,  # 10 degrees!
                    "north": 50.0
                },
                "temporal_extent": ["2024-01-01", "2024-12-31"]
            },
            "result": True
        }
    }


# =============================================================================
# Mock User
# =============================================================================

@pytest.fixture
def mock_user():
    """Mock OIDC user."""
    return Mock(
        sub="user-123",
        email="test@example.com",
        name="Test User"
    )


@pytest.fixture
def mock_user_id():
    """Simple user ID string."""
    return "user-123"


# =============================================================================
# Mock xarray DataArrays
# =============================================================================

@pytest.fixture
def sample_datacube():
    """Sample xarray DataArray representing a datacube."""
    # Create a simple 4D datacube (bands, time, y, x)
    data = np.random.rand(2, 1, 100, 100).astype(np.float32)

    return xr.DataArray(
        data,
        dims=["bands", "time", "y", "x"],
        coords={
            "bands": ["red", "nir"],
            "time": [np.datetime64("2024-06-01")],
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"crs": "EPSG:4326"}
    )


@pytest.fixture
def sample_ndvi_result():
    """Sample NDVI result DataArray."""
    data = np.random.uniform(-1, 1, (1, 100, 100)).astype(np.float32)

    return xr.DataArray(
        data,
        dims=["time", "y", "x"],
        coords={
            "time": [np.datetime64("2024-06-01")],
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"crs": "EPSG:4326", "description": "NDVI"}
    )


# =============================================================================
# Temporary Storage
# =============================================================================

@pytest.fixture
def temp_storage_path():
    """Temporary directory for test storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_geotiff(temp_storage_path, sample_ndvi_result):
    """Create a temporary GeoTIFF file for testing."""
    import rioxarray  # noqa: F401

    # Set CRS
    sample_ndvi_result = sample_ndvi_result.rio.write_crs("EPSG:4326")

    # Select first time slice for 2D output
    data_2d = sample_ndvi_result.isel(time=0)

    # Save to temp file
    filepath = temp_storage_path / "test_ndvi.tif"
    data_2d.rio.to_raster(str(filepath))

    yield filepath


# =============================================================================
# Mock Executor
# =============================================================================

@pytest.fixture
def mock_executor(sample_ndvi_result):
    """Mock ProcessGraphExecutor."""
    executor = Mock()
    executor.execute = Mock(return_value=sample_ndvi_result)
    executor.execute_lazy = Mock(return_value=sample_ndvi_result)
    executor.get_available_processes = Mock(return_value=[
        "add", "subtract", "multiply", "divide",
        "load_collection", "filter_bands", "filter_bbox",
        "reduce_dimension", "save_result", "ndvi",
        "normalized_difference"
    ])
    executor.has_process = Mock(return_value=True)
    return executor


# =============================================================================
# Mock Result Storage
# =============================================================================

@pytest.fixture
def mock_result_storage(temp_storage_path):
    """Mock ResultStorage."""
    from openeo_app.storage.results import ResultStorage
    return ResultStorage(base_path=str(temp_storage_path))


# =============================================================================
# Database Session Fixtures
# =============================================================================

@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


# =============================================================================
# Job Fixtures
# =============================================================================

@pytest.fixture
def sample_job_id():
    """Sample job UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_job(sample_job_id, ndvi_process_graph):
    """Sample job object."""
    return Mock(
        id=sample_job_id,
        title="Test NDVI Job",
        description="Calculate NDVI for test area",
        process_graph=ndvi_process_graph,
        status="created",
        created_at=datetime.utcnow(),
        user_id="user-123"
    )


# =============================================================================
# Collection Fixtures
# =============================================================================

@pytest.fixture
def available_collections():
    """List of available collections."""
    return [
        {
            "id": "sentinel-2-l2a",
            "title": "Sentinel-2 Level 2A",
            "description": "Atmospherically corrected",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2015-06-27", None]]}
            }
        },
        {
            "id": "cop-dem-glo-30",
            "title": "Copernicus DEM 30m",
            "description": "Global elevation model",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2021-01-01", "2021-12-31"]]}
            }
        },
        {
            "id": "landsat-c2-l2",
            "title": "Landsat Collection 2 Level 2",
            "description": "Surface reflectance",
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["1982-08-22", None]]}
            }
        }
    ]


@pytest.fixture
def sentinel2_bands():
    """Sentinel-2 band information."""
    return {
        "blue": {"common_name": "blue", "wavelength_nm": 490},
        "green": {"common_name": "green", "wavelength_nm": 560},
        "red": {"common_name": "red", "wavelength_nm": 665},
        "nir": {"common_name": "nir", "wavelength_nm": 842},
        "nir08": {"common_name": "nir08", "wavelength_nm": 865},
        "swir16": {"common_name": "swir16", "wavelength_nm": 1610},
        "swir22": {"common_name": "swir22", "wavelength_nm": 2190},
        "scl": {"common_name": "scl", "description": "Scene classification"}
    }


# =============================================================================
# Session Fixtures
# =============================================================================

@pytest.fixture
def sample_session_id():
    """Sample session UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def sample_session(sample_session_id, mock_user_id):
    """Sample AI session."""
    return {
        "id": sample_session_id,
        "user_id": mock_user_id,
        "created_at": datetime.utcnow().isoformat(),
        "last_active": datetime.utcnow().isoformat(),
        "context": {}
    }


# =============================================================================
# Saved Process Graph Fixtures
# =============================================================================

@pytest.fixture
def saved_graph_id():
    """Sample saved graph UUID."""
    return str(uuid.uuid4())


@pytest.fixture
def saved_graph(saved_graph_id, ndvi_process_graph, mock_user_id):
    """Sample saved process graph."""
    return {
        "id": saved_graph_id,
        "name": "NDVI Workflow",
        "description": "Calculate NDVI from Sentinel-2",
        "process_graph": ndvi_process_graph,
        "user_id": mock_user_id,
        "tags": ["ndvi", "sentinel-2", "vegetation"],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


# =============================================================================
# GeoAI Fixtures
# =============================================================================

@pytest.fixture
def sample_segmentation_result():
    """Sample segmentation result."""
    # Class labels: 0=background, 1=vegetation, 2=water, 3=urban
    data = np.random.randint(0, 4, (100, 100)).astype(np.uint8)

    return xr.DataArray(
        data,
        dims=["y", "x"],
        coords={
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"classes": ["background", "vegetation", "water", "urban"]}
    )


@pytest.fixture
def sample_change_detection_result():
    """Sample change detection result."""
    # Binary: 0=no change, 1=change
    data = np.random.binomial(1, 0.1, (100, 100)).astype(np.uint8)

    return xr.DataArray(
        data,
        dims=["y", "x"],
        coords={
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"description": "Binary change mask"}
    )


# =============================================================================
# Visualization Fixtures
# =============================================================================

@pytest.fixture
def sample_map_spec():
    """Sample map component specification."""
    return {
        "type": "map",
        "spec": {
            "title": "NDVI Result",
            "center": [46.005, 11.005],
            "zoom": 12,
            "layers": [
                {
                    "type": "raster",
                    "source": "/tmp/test_ndvi.tif",
                    "colormap": "RdYlGn",
                    "vmin": -1,
                    "vmax": 1,
                    "opacity": 0.8
                }
            ],
            "controls": ["zoom", "layer_toggle", "colorbar"]
        }
    }


@pytest.fixture
def sample_chart_spec():
    """Sample chart component specification."""
    return {
        "type": "chart",
        "spec": {
            "chart_type": "line",
            "title": "NDVI Time Series",
            "data": {
                "x": ["2024-06-01", "2024-06-15", "2024-07-01"],
                "y": [0.45, 0.52, 0.61],
                "name": "Mean NDVI"
            },
            "xaxis": {"title": "Date", "type": "date"},
            "yaxis": {"title": "NDVI"}
        }
    }


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def temp_rgb_geotiff(temp_storage_path):
    """Create a temporary RGB GeoTIFF file (3 bands) for testing."""
    import rioxarray  # noqa: F401

    # Create RGB data (3 bands, 100x100)
    rgb_data = np.random.uniform(0, 255, (3, 100, 100)).astype(np.float32)

    rgb_arr = xr.DataArray(
        rgb_data,
        dims=["band", "y", "x"],
        coords={
            "band": ["red", "green", "blue"],
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"crs": "EPSG:4326"}
    )
    rgb_arr = rgb_arr.rio.write_crs("EPSG:4326")

    # Save to temp file
    filepath = temp_storage_path / "test_rgb.tif"
    rgb_arr.rio.to_raster(str(filepath))

    yield filepath


@pytest.fixture
def temp_comparison_files(temp_storage_path):
    """Create temporary before/after GeoTIFF files for comparison testing."""
    import rioxarray  # noqa: F401

    # Create before data
    before_data = np.random.uniform(0, 1, (100, 100)).astype(np.float32)
    before_arr = xr.DataArray(
        before_data,
        dims=["y", "x"],
        coords={
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"crs": "EPSG:4326"}
    )
    before_arr = before_arr.rio.write_crs("EPSG:4326")

    # Create after data (slightly different)
    after_data = np.random.uniform(0, 1, (100, 100)).astype(np.float32)
    after_arr = xr.DataArray(
        after_data,
        dims=["y", "x"],
        coords={
            "y": np.linspace(46.0, 46.01, 100),
            "x": np.linspace(11.0, 11.01, 100)
        },
        attrs={"crs": "EPSG:4326"}
    )
    after_arr = after_arr.rio.write_crs("EPSG:4326")

    # Save files
    before_path = temp_storage_path / "before.tif"
    after_path = temp_storage_path / "after.tif"

    before_arr.rio.to_raster(str(before_path))
    after_arr.rio.to_raster(str(after_path))

    yield (before_path, after_path)


@pytest.fixture
def mock_env(monkeypatch):
    """Set up mock environment variables."""
    monkeypatch.setenv("STAC_API_URL", "https://earth-search.aws.element84.com/v1/")
    monkeypatch.setenv("RESULT_STORAGE_PATH", "/tmp/openeo_results")
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRESQL_HOST", "localhost")
    monkeypatch.setenv("POSTGRESQL_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "openeo_test")
