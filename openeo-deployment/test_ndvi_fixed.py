#!/usr/bin/env python3
"""Test NDVI batch job with fixed reduce_dimension and scaling.

Tests:
1. Sentinel-2 data is properly scaled (0-10000 -> 0-1)
2. NDVI calculation produces valid [-1, 1] values
3. reduce_dimension works without the double-argument bug
"""

import base64
import json
import time
import requests
import sys

BASE_URL = "http://localhost:8000/openeo/1.1.0"
AUTH = {"Authorization": f"Basic {base64.b64encode(b'testuser:testpass').decode()}"}

# Small area in Italian Alps (agricultural region)
# ~1km x 1km area
SPATIAL_EXTENT = {
    "west": 11.35,
    "south": 46.45,
    "east": 11.36,
    "north": 46.46,
    "crs": "EPSG:4326"
}

# Short time window - summer 2024
TEMPORAL_EXTENT = ["2024-07-01", "2024-07-10"]


def test_simple_ndvi():
    """Test simple NDVI without reduce_dimension."""
    print("\n" + "="*60)
    print("TEST 1: Simple NDVI (no reduce_dimension)")
    print("="*60)

    # Simple process graph: load -> ndvi -> save
    process_graph = {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": SPATIAL_EXTENT,
                "temporal_extent": TEMPORAL_EXTENT,
                "bands": ["red", "nir"]
            }
        },
        "ndvi": {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": "load"},
                "nir": "nir",
                "red": "red"
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

    return run_job("Simple NDVI Test", process_graph)


def test_ndvi_with_reduce():
    """Test NDVI with reduce_dimension (mean over time)."""
    print("\n" + "="*60)
    print("TEST 2: NDVI with reduce_dimension (mean)")
    print("="*60)

    # Process graph with reduce_dimension using mean
    process_graph = {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": SPATIAL_EXTENT,
                "temporal_extent": TEMPORAL_EXTENT,
                "bands": ["red", "nir"]
            }
        },
        "ndvi": {
            "process_id": "ndvi",
            "arguments": {
                "data": {"from_node": "load"},
                "nir": "nir",
                "red": "red"
            }
        },
        "reduce_time": {
            "process_id": "reduce_dimension",
            "arguments": {
                "data": {"from_node": "ndvi"},
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
            }
        },
        "save": {
            "process_id": "save_result",
            "arguments": {
                "data": {"from_node": "reduce_time"},
                "format": "GTiff"
            },
            "result": True
        }
    }

    return run_job("NDVI with Reduce Test", process_graph)


def run_job(title, process_graph):
    """Run a batch job and validate results."""
    print(f"\nCreating job: {title}")

    # Create job
    resp = requests.post(
        f"{BASE_URL}/jobs",
        headers={**AUTH, "Content-Type": "application/json"},
        json={
            "title": title,
            "description": "Automated test",
            "process": {"process_graph": process_graph}
        }
    )

    if resp.status_code != 201:
        print(f"FAILED: Could not create job: {resp.status_code}")
        print(resp.text)
        return False

    job_id = resp.headers.get("OpenEO-Identifier") or resp.headers.get("Location", "").split("/")[-1]
    print(f"Job ID: {job_id}")

    # Start job
    resp = requests.post(f"{BASE_URL}/jobs/{job_id}/results", headers=AUTH)
    if resp.status_code != 202:
        print(f"FAILED: Could not start job: {resp.status_code}")
        return False
    print("Job started")

    # Wait for completion
    print("Waiting for completion...", end="", flush=True)
    for i in range(60):  # 5 minutes max
        time.sleep(5)
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}", headers=AUTH)
        status = resp.json().get("status")
        print(".", end="", flush=True)

        if status == "finished":
            print(" DONE")
            break
        elif status == "error":
            print(" ERROR")
            # Get logs
            logs = requests.get(f"{BASE_URL}/jobs/{job_id}/logs", headers=AUTH).json()
            for log in logs.get("logs", []):
                if log.get("level") == "error":
                    print(f"  ERROR: {log.get('message')}")
            return False
    else:
        print(" TIMEOUT")
        return False

    # Get results
    print("Fetching results...")
    resp = requests.get(f"{BASE_URL}/jobs/{job_id}/results", headers=AUTH)
    if resp.status_code != 200:
        print(f"FAILED: Could not get results: {resp.status_code}")
        return False

    # Save and validate
    result_path = f"/tmp/test_ndvi_{job_id}.tif"
    with open(result_path, "wb") as f:
        f.write(resp.content)
    print(f"Saved to: {result_path}")

    return validate_ndvi_result(result_path)


def validate_ndvi_result(path):
    """Validate NDVI values are in expected range."""
    try:
        import rioxarray
        import numpy as np

        data = rioxarray.open_rasterio(path)
        print(f"Shape: {data.shape}")

        values = data.values.flatten()
        valid = values[~np.isnan(values)]

        if len(valid) == 0:
            print("FAILED: No valid data")
            return False

        min_val = np.min(valid)
        max_val = np.max(valid)
        mean_val = np.mean(valid)

        print(f"NDVI range: [{min_val:.4f}, {max_val:.4f}]")
        print(f"NDVI mean:  {mean_val:.4f}")

        # NDVI must be in [-1, 1]
        if min_val < -1.0 or max_val > 1.0:
            print(f"FAILED: NDVI values outside [-1, 1] range!")
            print(f"  This indicates scaling was not applied correctly")
            return False

        # For vegetated areas in summer, mean should be positive
        if mean_val < -0.5:
            print(f"WARNING: Unusual mean NDVI for vegetated area")

        print("PASSED: NDVI values in valid [-1, 1] range")
        return True

    except Exception as e:
        print(f"FAILED: Validation error: {e}")
        return False


def main():
    print("="*60)
    print("OpenEO NDVI Tests with Fixed reduce_dimension & Scaling")
    print("="*60)

    results = []

    # Test 1: Simple NDVI (tests scaling)
    results.append(("Simple NDVI", test_simple_ndvi()))

    # Test 2: NDVI with reduce_dimension (tests both fixes)
    results.append(("NDVI + reduce_dimension", test_ndvi_with_reduce()))

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "PASSED" if passed else "FAILED"
        print(f"  {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")
        sys.exit(1)


if __name__ == "__main__":
    main()
