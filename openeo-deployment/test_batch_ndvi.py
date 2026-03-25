#!/usr/bin/env python3
"""Test batch job endpoint with NDVI vegetation analysis on Sentinel-2 L2A.

This test:
1. Creates a batch job for NDVI calculation
2. Starts the job
3. Monitors status until completion
4. Retrieves and validates results
"""

import base64
import json
import time
import requests
import sys

# Configuration
BASE_URL = "http://localhost:8000/openeo/1.1.0"
AUTH_HEADER = {"Authorization": f"Basic {base64.b64encode(b'testuser:testpass').decode()}"}

# Small area in Northern Italy (agricultural region - good for NDVI)
# Approximately 0.01 x 0.01 degrees = ~1km x 1km
SPATIAL_EXTENT = {
    "west": 11.35,
    "south": 46.45,
    "east": 11.36,
    "north": 46.46,
    "crs": "EPSG:4326"
}

# Short temporal extent - summer 2024 (3 acquisitions max)
TEMPORAL_EXTENT = ["2024-07-01", "2024-07-15"]

# Process graph for NDVI calculation using reduce_dimension
# NDVI = (NIR - RED) / (NIR + RED)
PROCESS_GRAPH = {
    "process_graph": {
        "load": {
            "process_id": "load_collection",
            "arguments": {
                "id": "sentinel-2-l2a",
                "spatial_extent": SPATIAL_EXTENT,
                "temporal_extent": TEMPORAL_EXTENT,
                "bands": ["red", "nir"]  # AWS Earth Search band names
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
}


def print_status(msg, status="INFO"):
    """Print status message."""
    icons = {"INFO": "\u2139\ufe0f ", "OK": "\u2705", "ERROR": "\u274c", "WAIT": "\u23f3"}
    print(f"{icons.get(status, '')} {msg}")


def create_batch_job():
    """Create a new batch job."""
    print_status("Creating batch job for NDVI analysis...")

    response = requests.post(
        f"{BASE_URL}/jobs",
        headers={**AUTH_HEADER, "Content-Type": "application/json"},
        json={
            "title": "NDVI Vegetation Analysis",
            "description": "Calculate mean NDVI over small area in Italy",
            "process": PROCESS_GRAPH,
        }
    )

    if response.status_code == 201:
        # Get job ID from Location header
        location = response.headers.get("Location", "")
        job_id = location.split("/")[-1] if location else response.headers.get("OpenEO-Identifier")
        print_status(f"Job created: {job_id}", "OK")
        return job_id
    else:
        print_status(f"Failed to create job: {response.status_code}", "ERROR")
        print(response.text)
        return None


def start_job(job_id):
    """Start a batch job."""
    print_status(f"Starting job {job_id}...")

    response = requests.post(
        f"{BASE_URL}/jobs/{job_id}/results",
        headers=AUTH_HEADER
    )

    if response.status_code == 202:
        print_status("Job started successfully", "OK")
        return True
    else:
        print_status(f"Failed to start job: {response.status_code}", "ERROR")
        print(response.text)
        return False


def get_job_status(job_id):
    """Get job status."""
    response = requests.get(
        f"{BASE_URL}/jobs/{job_id}",
        headers=AUTH_HEADER
    )

    if response.status_code == 200:
        return response.json()
    return None


def wait_for_completion(job_id, timeout=300, poll_interval=5):
    """Wait for job to complete."""
    print_status(f"Waiting for job completion (timeout: {timeout}s)...", "WAIT")

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout:
        job = get_job_status(job_id)

        if job:
            status = job.get("status")

            if status != last_status:
                print_status(f"Status: {status}")
                last_status = status

            if status == "finished":
                elapsed = time.time() - start_time
                print_status(f"Job completed in {elapsed:.1f}s", "OK")
                return True
            elif status == "error":
                print_status("Job failed!", "ERROR")
                return False
            elif status == "canceled":
                print_status("Job was canceled", "ERROR")
                return False

        time.sleep(poll_interval)

    print_status(f"Timeout after {timeout}s", "ERROR")
    return False


def get_job_logs(job_id):
    """Get job logs."""
    response = requests.get(
        f"{BASE_URL}/jobs/{job_id}/logs",
        headers=AUTH_HEADER
    )

    if response.status_code == 200:
        return response.json()
    return None


def get_results(job_id):
    """Get job results."""
    print_status("Retrieving results...")

    response = requests.get(
        f"{BASE_URL}/jobs/{job_id}/results",
        headers=AUTH_HEADER
    )

    if response.status_code == 200:
        # Save result to file
        result_path = f"/tmp/ndvi_result_{job_id}.tif"
        with open(result_path, "wb") as f:
            f.write(response.content)

        print_status(f"Results saved to {result_path}", "OK")
        print_status(f"Result size: {len(response.content)} bytes")

        return result_path
    else:
        print_status(f"Failed to get results: {response.status_code}", "ERROR")
        print(response.text)
        return None


def validate_result(result_path):
    """Validate the NDVI result."""
    print_status("Validating NDVI result...")

    try:
        import rioxarray
        import numpy as np

        data = rioxarray.open_rasterio(result_path)

        print_status(f"Shape: {data.shape}")
        print_status(f"CRS: {data.rio.crs}")

        # Get statistics
        values = data.values
        valid_values = values[~np.isnan(values)]

        if len(valid_values) > 0:
            min_val = np.min(valid_values)
            max_val = np.max(valid_values)
            mean_val = np.mean(valid_values)

            print_status(f"NDVI range: [{min_val:.3f}, {max_val:.3f}]")
            print_status(f"NDVI mean: {mean_val:.3f}")

            # Validate NDVI is in expected range
            if -1.0 <= min_val and max_val <= 1.0:
                print_status("NDVI values in valid range [-1, 1]", "OK")
            else:
                print_status(f"NDVI values outside expected range!", "ERROR")
                return False

            # Check for typical vegetation values
            if mean_val > 0.2:
                print_status("Vegetation detected (mean NDVI > 0.2)", "OK")
            else:
                print_status(f"Low vegetation signal (mean NDVI = {mean_val:.3f})")

            return True
        else:
            print_status("No valid data in result!", "ERROR")
            return False

    except Exception as e:
        print_status(f"Validation error: {e}", "ERROR")
        return False


def main():
    """Run the complete batch job test."""
    print("=" * 60)
    print("OpenEO Batch Job Test: NDVI Vegetation Analysis")
    print("=" * 60)
    print(f"Area: {SPATIAL_EXTENT}")
    print(f"Period: {TEMPORAL_EXTENT}")
    print("=" * 60)

    # Step 1: Create job
    job_id = create_batch_job()
    if not job_id:
        sys.exit(1)

    # Step 2: Start job
    if not start_job(job_id):
        sys.exit(1)

    # Step 3: Wait for completion
    if not wait_for_completion(job_id, timeout=300):
        # Print logs on failure
        logs = get_job_logs(job_id)
        if logs:
            print("\nJob logs:")
            for log in logs.get("logs", [])[-10:]:
                print(f"  [{log.get('level', 'info').upper()}] {log.get('message', '')}")
        sys.exit(1)

    # Step 4: Get logs
    logs = get_job_logs(job_id)
    if logs:
        print("\nJob logs:")
        for log in logs.get("logs", []):
            level = log.get("level", "info").upper()
            msg = log.get("message", "")
            data = log.get("data", {})
            print(f"  [{level}] {msg}")
            if data:
                for k, v in data.items():
                    print(f"         {k}: {v}")

    # Step 5: Get results
    result_path = get_results(job_id)
    if not result_path:
        sys.exit(1)

    # Step 6: Validate results
    print("\n" + "=" * 60)
    if validate_result(result_path):
        print("=" * 60)
        print_status("TEST PASSED!", "OK")
        print("=" * 60)
    else:
        print("=" * 60)
        print_status("TEST FAILED!", "ERROR")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
