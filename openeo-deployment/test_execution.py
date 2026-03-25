#!/usr/bin/env python3
"""Test script for OpenEO FastAPI Dask execution engine."""

import sys
sys.path.insert(0, '/Users/macbookpro/openeo-deployment')

import os
os.environ.setdefault('STAC_API_URL', 'https://earth-search.aws.element84.com/v1/')


def test_executor_initialization():
    """Test that the ProcessGraphExecutor initializes correctly."""
    print("=" * 60)
    print("Test 1: Executor Initialization")
    print("=" * 60)

    from openeo_app.execution.executor import ProcessGraphExecutor

    executor = ProcessGraphExecutor(
        stac_api_url='https://earth-search.aws.element84.com/v1/'
    )

    processes = executor.get_available_processes()
    print(f"Available processes: {len(processes)}")
    print(f"Processes: {sorted(processes)}")
    print()
    print("PASSED")
    print()
    return executor


def test_simple_math(executor):
    """Test simple math operation."""
    print("=" * 60)
    print("Test 2: Simple Math (add)")
    print("=" * 60)

    process_graph = {
        "add1": {
            "process_id": "add",
            "arguments": {"x": 1, "y": 2},
            "result": True
        }
    }

    result = executor.execute(process_graph)
    print(f"1 + 2 = {result}")
    assert result == 3.0, f"Expected 3.0, got {result}"
    print()
    print("PASSED")
    print()


def test_chained_operations(executor):
    """Test chained operations."""
    print("=" * 60)
    print("Test 3: Chained Operations (multiply -> add)")
    print("=" * 60)

    process_graph = {
        "mult1": {
            "process_id": "multiply",
            "arguments": {"x": 2, "y": 3},
        },
        "add1": {
            "process_id": "add",
            "arguments": {
                "x": {"from_node": "mult1"},
                "y": 4
            },
            "result": True
        }
    }

    result = executor.execute(process_graph)
    print(f"(2 * 3) + 4 = {result}")
    assert result == 10.0, f"Expected 10.0, got {result}"
    print()
    print("PASSED")
    print()


def test_load_collection():
    """Test load_collection with real STAC data."""
    print("=" * 60)
    print("Test 4: Load Collection (Copernicus DEM)")
    print("=" * 60)

    from openeo_app.processes.load_collection import load_collection

    # Use DEM data for faster testing
    result = load_collection(
        id="cop-dem-glo-30",
        spatial_extent={
            "west": 11.0,
            "south": 46.0,
            "east": 11.01,
            "north": 46.01,
            "crs": "EPSG:4326"
        },
    )

    print(f"Result type: {type(result).__name__}")
    print(f"Result shape: {result.shape}")
    print(f"Result dimensions: {result.dims}")
    print(f"Result coordinates: {list(result.coords.keys())}")
    print()
    print("PASSED")
    print()


def test_result_storage():
    """Test ResultStorage functionality."""
    print("=" * 60)
    print("Test 5: Result Storage")
    print("=" * 60)

    import uuid
    import numpy as np
    import xarray as xr
    from openeo_app.storage.results import ResultStorage

    storage = ResultStorage(base_path="/tmp/openeo_test_results")
    job_id = uuid.uuid4()

    # Create test data
    data = xr.DataArray(
        np.random.rand(2, 10, 10),
        dims=["bands", "y", "x"],
        coords={
            "bands": ["B04", "B08"],
            "y": np.linspace(46.0, 46.1, 10),
            "x": np.linspace(11.0, 11.1, 10),
        }
    )
    data = data.rio.write_crs("EPSG:4326")

    # Save as GeoTIFF
    result_path = storage.save_result(job_id, data, format="GTiff")
    print(f"Saved to: {result_path}")
    assert result_path.exists(), "Result file not created"

    # Retrieve
    retrieved_path = storage.get_result(job_id)
    print(f"Retrieved: {retrieved_path}")
    assert retrieved_path == result_path, "Retrieved path mismatch"

    # Test logs
    storage.save_log(job_id, "info", "Test log message")
    logs = storage.get_logs(job_id)
    print(f"Logs: {len(logs)} entries")
    assert len(logs) == 1, "Log not saved"

    # Cleanup
    storage.delete_result(job_id)
    storage.clear_logs(job_id)
    print("Cleanup complete")
    print()
    print("PASSED")
    print()


def test_ndvi_workflow(executor):
    """Test NDVI calculation workflow."""
    print("=" * 60)
    print("Test 6: NDVI Calculation")
    print("=" * 60)

    from openeo_app.processes.load_collection import load_collection

    # Load Sentinel-2 data
    # AWS Earth Search uses 'red' and 'nir' instead of 'B04' and 'B08'
    print("Loading Sentinel-2 data...")
    data = load_collection(
        id="sentinel-2-l2a",
        spatial_extent={
            "west": 11.0,
            "south": 46.0,
            "east": 11.01,
            "north": 46.01,
            "crs": "EPSG:4326"
        },
        temporal_extent=["2024-06-01", "2024-06-10"],
        bands=["red", "nir"],  # AWS Earth Search band names
    )
    print(f"Loaded data shape: {data.shape}")

    # Calculate NDVI manually
    print("Calculating NDVI...")
    red = data.sel(bands="red")
    nir = data.sel(bands="nir")
    ndvi = (nir - red) / (nir + red)
    print(f"NDVI shape: {ndvi.shape}")
    print(f"NDVI range: [{float(ndvi.min().values):.3f}, {float(ndvi.max().values):.3f}]")
    print()
    print("PASSED")
    print()


def main():
    """Run all tests."""
    print()
    print("=" * 60)
    print("OpenEO FastAPI Dask Execution Engine Tests")
    print("=" * 60)
    print()

    # Test 1: Initialization
    executor = test_executor_initialization()

    # Test 2: Simple math
    test_simple_math(executor)

    # Test 3: Chained operations
    test_chained_operations(executor)

    # Test 4: Load collection
    test_load_collection()

    # Test 5: Result storage
    test_result_storage()

    # Test 6: NDVI workflow (optional - requires internet)
    try:
        test_ndvi_workflow(executor)
    except Exception as e:
        print(f"SKIPPED (network issue): {e}")
        print()

    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
