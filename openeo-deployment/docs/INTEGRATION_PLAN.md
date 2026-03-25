# OpenEO FastAPI Dask Datacube Processing Integration Plan

## Executive Summary

This document provides a detailed integration plan for implementing full datacube processing capabilities in the OpenEO FastAPI deployment using Dask, xarray, and the openeo-processes-dask library.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Current State Analysis](#2-current-state-analysis)
3. [Components to Implement](#3-components-to-implement)
4. [Implementation Plan](#4-implementation-plan)
5. [Code Structure](#5-code-structure)
6. [Detailed Implementation Guide](#6-detailed-implementation-guide)
7. [Testing Strategy](#7-testing-strategy)
8. [Deployment Considerations](#8-deployment-considerations)

---

## 1. Architecture Overview

### Process Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT REQUEST                                 │
│  POST /openeo/1.1.0/result (sync) OR POST /jobs/{id}/results (batch)   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI LAYER                                    │
│  OpenEOApi → JobsRegister.process_sync_job() / start_job()             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      VALIDATION LAYER                                    │
│  ProcessRegister.validate_user_process_graph()                          │
│  └→ resolve_process_graph() [openeo-pg-parser-networkx]                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      EXECUTION ENGINE (TO IMPLEMENT)                     │
│  ProcessGraphExecutor                                                    │
│  ├─ Parse: OpenEOProcessGraph(resolved_graph)                           │
│  ├─ Order: NetworkX topological sort                                    │
│  ├─ Execute: For each node, call process implementation                 │
│  └─ Compute: result.compute() → triggers Dask                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      DASK PROCESSING                                     │
│  ├─ load_collection → xarray.DataArray with Dask chunks                │
│  ├─ filter_* → Lazy spatial/temporal subsetting                        │
│  ├─ reduce_dimension → Aggregation operations                           │
│  ├─ apply → Element-wise transformations                                │
│  └─ save_result → Output to GeoTIFF/NetCDF/JSON                        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      OUTPUT                                              │
│  Sync: Return directly as HTTP response                                 │
│  Batch: Save to storage, update job status in database                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Library | Purpose |
|-----------|---------|---------|
| Process Graph Parsing | `openeo-pg-parser-networkx` | Parse JSON → NetworkX DAG |
| Process Specifications | `openeo-processes-dask.specs` | 157 OpenEO process definitions |
| Process Implementations | `openeo-processes-dask.process_implementations` | Dask/xarray implementations |
| Data Loading | `odc.stac`, `pystac-client` | Load from STAC/COGs |
| Array Operations | `xarray`, `dask.array` | Lazy multidimensional arrays |
| Spatial Operations | `rioxarray`, `geopandas` | Geospatial processing |

---

## 2. Current State Analysis

### What's Implemented ✅

| Component | Status | Location |
|-----------|--------|----------|
| API Endpoints | ✅ Complete | `openeo_fastapi/api/app.py` |
| Process Registry | ✅ Complete | `openeo_fastapi/client/processes.py` |
| Process Validation | ✅ Complete | `openeo_pg_parser_networkx` |
| Job Metadata CRUD | ✅ Complete | `openeo_fastapi/client/jobs.py` |
| STAC Proxy | ✅ Complete | `openeo_fastapi/client/collections.py` |
| Authentication | ✅ Complete | `openeo_fastapi/client/auth.py` |
| Database Models | ✅ Complete | `openeo_fastapi/client/psql/` |
| 157 Process Specs | ✅ Complete | `openeo_processes_dask.specs` |
| Core Process Impls | ✅ Partial | `openeo_processes_dask.process_implementations` |

### What's NOT Implemented ❌

| Component | Status | Location | Priority |
|-----------|--------|----------|----------|
| `process_sync_job()` | ❌ Returns 501 | `jobs.py:390` | **P0** |
| `start_job()` | ❌ Returns 501 | `jobs.py:334` | **P0** |
| `get_results()` | ❌ Returns 501 | `jobs.py:315` | **P1** |
| `cancel_job()` | ❌ Returns 501 | `jobs.py:353` | **P2** |
| `get_logs()` | ❌ Returns 501 | `jobs.py:298` | **P2** |
| `load_collection` impl | ❌ Missing | N/A | **P0** |
| Execution Engine | ❌ Missing | N/A | **P0** |
| Result Storage | ❌ Missing | N/A | **P1** |
| Background Task Queue | ❌ Missing | N/A | **P1** |

---

## 3. Components to Implement

### 3.1 Process Graph Executor (P0)

**Purpose**: Execute OpenEO process graphs using Dask

**File**: `/Users/macbookpro/openeo-deployment/openeo_app/execution/executor.py`

```python
class ProcessGraphExecutor:
    """Execute OpenEO process graphs using Dask."""

    def __init__(
        self,
        process_registry: ProcessRegistry,
        stac_api_url: str,
        dask_client: Optional[Client] = None,
    ):
        self.process_registry = process_registry
        self.stac_api_url = stac_api_url
        self.dask_client = dask_client or Client(processes=False)
        self._results = {}  # Node results cache

    def execute(
        self,
        process_graph: dict,
        parameters: dict = None,
    ) -> xr.DataArray:
        """
        Execute a process graph and return results.

        Steps:
        1. Parse process graph into NetworkX DAG
        2. Resolve all process references
        3. Execute nodes in topological order
        4. Trigger Dask computation
        5. Return final result
        """
        pass

    def _execute_node(self, node_id: str, node_data: dict) -> Any:
        """Execute a single process node."""
        pass

    def _resolve_arguments(self, arguments: dict) -> dict:
        """Resolve from_node references to actual values."""
        pass
```

### 3.2 Load Collection Implementation (P0)

**Purpose**: Bridge between collection IDs and STAC data loading

**File**: `/Users/macbookpro/openeo-deployment/openeo_app/processes/load_collection.py`

```python
def load_collection(
    id: str,
    spatial_extent: Optional[dict] = None,
    temporal_extent: Optional[list] = None,
    bands: Optional[list[str]] = None,
    properties: Optional[dict] = None,
) -> xr.DataArray:
    """
    Load a collection by ID.

    Maps collection ID to STAC URL and delegates to load_stac().
    """
    pass
```

### 3.3 Custom Jobs Register (P0)

**Purpose**: Override job execution methods with actual implementations

**File**: `/Users/macbookpro/openeo-deployment/openeo_app/registers/jobs.py`

```python
class ExecutableJobsRegister(JobsRegister):
    """Jobs register with actual execution capabilities."""

    def __init__(self, settings, links, executor: ProcessGraphExecutor):
        super().__init__(settings, links)
        self.executor = executor

    def process_sync_job(self, body: JobsRequest, user: User) -> Response:
        """Execute synchronous job and return results."""
        pass

    def start_job(self, job_id: uuid.UUID, user: User) -> Response:
        """Start batch job execution."""
        pass

    def get_results(self, job_id: uuid.UUID, user: User) -> Response:
        """Retrieve completed job results."""
        pass
```

### 3.4 Result Storage (P1)

**Purpose**: Store job results for later retrieval

**File**: `/Users/macbookpro/openeo-deployment/openeo_app/storage/results.py`

```python
class ResultStorage:
    """Manage job result storage."""

    def __init__(self, base_path: str = "/tmp/openeo_results"):
        self.base_path = Path(base_path)

    def save_result(
        self,
        job_id: uuid.UUID,
        data: xr.DataArray,
        format: str = "GTiff",
    ) -> str:
        """Save result and return path."""
        pass

    def get_result(self, job_id: uuid.UUID) -> Path:
        """Get result file path."""
        pass

    def delete_result(self, job_id: uuid.UUID) -> bool:
        """Delete result files."""
        pass
```

### 3.5 Background Task Queue (P1)

**Purpose**: Execute batch jobs asynchronously

**Options**:
1. **asyncio.create_task()** - Simple, built-in
2. **Celery** - Production-grade, distributed
3. **APScheduler** - Lightweight scheduler
4. **Dask Distributed** - Native Dask integration

---

## 4. Implementation Plan

### Phase 1: Core Execution (Week 1)

| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create execution module structure | `openeo_app/execution/__init__.py` |
| 1.2 | Implement ProcessGraphExecutor | `openeo_app/execution/executor.py` |
| 1.3 | Implement load_collection | `openeo_app/processes/load_collection.py` |
| 1.4 | Create custom JobsRegister | `openeo_app/registers/jobs.py` |
| 1.5 | Wire up in app.py | `openeo_app/app.py` |
| 1.6 | Test sync execution | `tests/test_execution.py` |

### Phase 2: Batch Processing (Week 2)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Implement result storage | `openeo_app/storage/results.py` |
| 2.2 | Add background task execution | `openeo_app/execution/tasks.py` |
| 2.3 | Implement start_job() | `openeo_app/registers/jobs.py` |
| 2.4 | Implement get_results() | `openeo_app/registers/jobs.py` |
| 2.5 | Add job status updates | Database integration |
| 2.6 | Test batch execution | `tests/test_batch.py` |

### Phase 3: Production Features (Week 3)

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Implement cancel_job() | `openeo_app/registers/jobs.py` |
| 3.2 | Implement get_logs() | `openeo_app/registers/jobs.py` |
| 3.3 | Add cost estimation | `openeo_app/registers/jobs.py` |
| 3.4 | Configure Dask cluster | `openeo_app/execution/cluster.py` |
| 3.5 | Add output format handlers | `openeo_app/execution/formats.py` |
| 3.6 | Production testing | Full workflow tests |

---

## 5. Code Structure

### Proposed Directory Structure

```
/Users/macbookpro/openeo-deployment/openeo_app/
├── __init__.py
├── app.py                      # Modified: Use custom registers
├── revise.py
├── psql/
│   └── ... (existing)
│
├── execution/                  # NEW: Execution engine
│   ├── __init__.py
│   ├── executor.py            # ProcessGraphExecutor
│   ├── tasks.py               # Background task management
│   ├── cluster.py             # Dask cluster configuration
│   └── formats.py             # Output format handlers (GTiff, NetCDF, etc.)
│
├── processes/                  # NEW: Custom process implementations
│   ├── __init__.py
│   ├── load_collection.py     # load_collection implementation
│   └── custom/                # Additional custom processes
│       └── __init__.py
│
├── registers/                  # NEW: Custom endpoint registers
│   ├── __init__.py
│   ├── jobs.py                # ExecutableJobsRegister
│   └── collections.py         # Optional: Custom collection handling
│
└── storage/                    # NEW: Result storage
    ├── __init__.py
    ├── results.py             # Result file management
    └── logs.py                # Execution log storage
```

---

## 6. Detailed Implementation Guide

### 6.1 ProcessGraphExecutor Implementation

```python
# /Users/macbookpro/openeo-deployment/openeo_app/execution/executor.py

from typing import Any, Optional, Callable
import uuid
import xarray as xr
import numpy as np
from dask.distributed import Client

from openeo_pg_parser_networkx import OpenEOProcessGraph
from openeo_pg_parser_networkx.process_registry import ProcessRegistry
from openeo_processes_dask.process_implementations import *
from openeo_processes_dask.process_implementations.cubes import *

# Import our custom load_collection
from openeo_app.processes.load_collection import load_collection


class ProcessGraphExecutor:
    """
    Execute OpenEO process graphs using Dask.

    This executor:
    1. Parses process graphs into execution DAGs
    2. Resolves process references and arguments
    3. Executes processes in topological order
    4. Handles Dask lazy computation
    """

    def __init__(
        self,
        process_registry: ProcessRegistry,
        stac_api_url: str,
        dask_client: Optional[Client] = None,
    ):
        self.process_registry = process_registry
        self.stac_api_url = stac_api_url
        self.dask_client = dask_client

        # Map process IDs to implementations
        self._process_implementations = self._build_process_map()

        # Runtime state
        self._results = {}
        self._execution_context = {}

    def _build_process_map(self) -> dict[str, Callable]:
        """Build mapping from process ID to implementation function."""
        return {
            # Data Loading
            "load_collection": load_collection,
            "load_stac": load_stac,

            # Filtering
            "filter_bbox": filter_bbox,
            "filter_temporal": filter_temporal,
            "filter_bands": filter_bands,

            # Reduction
            "reduce_dimension": reduce_dimension,
            "aggregate_temporal": aggregate_temporal,
            "aggregate_spatial": aggregate_spatial,

            # Application
            "apply": apply,
            "apply_dimension": apply_dimension,

            # Math operations
            "add": add,
            "subtract": subtract,
            "multiply": multiply,
            "divide": divide,
            "normalized_difference": normalized_difference,

            # Comparison
            "gt": gt,
            "lt": lt,
            "eq": eq,
            "neq": neq,
            "between": between,

            # Logic
            "and_": and_,
            "or_": or_,
            "not_": not_,
            "if_": if_,

            # Aggregation
            "mean": mean,
            "median": median,
            "min": min,
            "max": max,
            "sum": sum,
            "sd": sd,
            "variance": variance,

            # Array
            "array_element": array_element,
            "first": first,
            "last": last,

            # Output
            "save_result": save_result,

            # ... add more as needed
        }

    def execute(
        self,
        process_graph: dict,
        parameters: dict = None,
    ) -> xr.DataArray:
        """
        Execute a process graph and return results.

        Args:
            process_graph: OpenEO process graph dict
            parameters: Optional parameters for the graph

        Returns:
            xarray.DataArray with computation results
        """
        # Reset state
        self._results = {}
        self._execution_context = parameters or {}

        # Parse process graph
        pg = OpenEOProcessGraph(pg_data=process_graph)

        # Get execution order (topological sort)
        execution_order = list(pg.G.nodes())

        # Execute each node
        for node_id in execution_order:
            node_data = pg.G.nodes[node_id]
            result = self._execute_node(node_id, node_data)
            self._results[node_id] = result

        # Find result node
        result_node = self._find_result_node(pg)
        final_result = self._results.get(result_node)

        # Trigger computation if still lazy
        if hasattr(final_result, 'compute'):
            final_result = final_result.compute()

        return final_result

    def _execute_node(self, node_id: str, node_data: dict) -> Any:
        """Execute a single process node."""
        process_id = node_data.get('process_id')
        arguments = node_data.get('arguments', {})

        # Resolve argument references
        resolved_args = self._resolve_arguments(arguments)

        # Get implementation
        impl = self._process_implementations.get(process_id)
        if impl is None:
            raise ValueError(f"No implementation for process: {process_id}")

        # Handle callback processes (reduce_dimension, apply, etc.)
        if 'reducer' in resolved_args:
            resolved_args['reducer'] = self._create_callback(
                resolved_args['reducer']
            )
        if 'process' in resolved_args:
            resolved_args['process'] = self._create_callback(
                resolved_args['process']
            )

        # Execute
        try:
            result = impl(**resolved_args)
            return result
        except Exception as e:
            raise RuntimeError(
                f"Error executing {process_id} at {node_id}: {e}"
            )

    def _resolve_arguments(self, arguments: dict) -> dict:
        """Resolve from_node references to actual values."""
        resolved = {}

        for key, value in arguments.items():
            if isinstance(value, dict):
                if 'from_node' in value:
                    # Reference to another node's result
                    ref_node = value['from_node']
                    resolved[key] = self._results.get(ref_node)
                elif 'from_parameter' in value:
                    # Reference to input parameter
                    param_name = value['from_parameter']
                    resolved[key] = self._execution_context.get(param_name)
                elif 'process_graph' in value:
                    # Nested process graph (callback)
                    resolved[key] = value
                else:
                    # Nested dict, recurse
                    resolved[key] = self._resolve_arguments(value)
            elif isinstance(value, list):
                resolved[key] = [
                    self._resolve_arguments({'v': v})['v']
                    if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                resolved[key] = value

        return resolved

    def _create_callback(self, callback_graph: dict) -> Callable:
        """Create a callable from a callback process graph."""
        def callback_fn(data, context=None):
            # Create sub-executor for callback
            sub_executor = ProcessGraphExecutor(
                process_registry=self.process_registry,
                stac_api_url=self.stac_api_url,
            )
            # Inject data as 'x' parameter
            params = {'x': data}
            if context:
                params.update(context)

            pg = callback_graph.get('process_graph', callback_graph)
            return sub_executor.execute(pg, params)

        return callback_fn

    def _find_result_node(self, pg: OpenEOProcessGraph) -> str:
        """Find the result node in the process graph."""
        for node_id in pg.G.nodes():
            node = pg.G.nodes[node_id]
            if node.get('result', False):
                return node_id

        # If no explicit result, return last node
        return list(pg.G.nodes())[-1]
```

### 6.2 Load Collection Implementation

```python
# /Users/macbookpro/openeo-deployment/openeo_app/processes/load_collection.py

from typing import Optional, Union
import xarray as xr

from openeo_processes_dask.process_implementations.cubes.load import load_stac
from openeo_processes_dask.process_implementations.cubes._filter import (
    filter_bbox,
    filter_temporal,
    filter_bands,
)


# Collection ID to STAC URL mapping
COLLECTION_STAC_MAP = {
    # AWS Earth Search
    "sentinel-2-l2a": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a",
    "sentinel-2-l1c": "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l1c",
    "sentinel-1-grd": "https://earth-search.aws.element84.com/v1/collections/sentinel-1-grd",
    "landsat-c2-l2": "https://earth-search.aws.element84.com/v1/collections/landsat-c2-l2",
    "cop-dem-glo-30": "https://earth-search.aws.element84.com/v1/collections/cop-dem-glo-30",
    "cop-dem-glo-90": "https://earth-search.aws.element84.com/v1/collections/cop-dem-glo-90",
    "naip": "https://earth-search.aws.element84.com/v1/collections/naip",
}


def load_collection(
    id: str,
    spatial_extent: Optional[dict] = None,
    temporal_extent: Optional[list] = None,
    bands: Optional[list[str]] = None,
    properties: Optional[dict] = None,
) -> xr.DataArray:
    """
    Load a collection by its ID.

    This implementation maps collection IDs to STAC URLs and delegates
    to load_stac() for actual data loading.

    Args:
        id: Collection identifier (e.g., "sentinel-2-l2a")
        spatial_extent: Bounding box dict with west, south, east, north, crs
        temporal_extent: List of [start, end] datetime strings
        bands: List of band names to load
        properties: Additional STAC query properties

    Returns:
        xarray.DataArray with requested data (lazy Dask array)
    """
    # Get STAC URL for collection
    stac_url = COLLECTION_STAC_MAP.get(id)

    if stac_url is None:
        raise ValueError(
            f"Unknown collection: {id}. "
            f"Available collections: {list(COLLECTION_STAC_MAP.keys())}"
        )

    # Convert spatial_extent to BoundingBox format
    bbox = None
    if spatial_extent:
        bbox = {
            "west": spatial_extent.get("west"),
            "south": spatial_extent.get("south"),
            "east": spatial_extent.get("east"),
            "north": spatial_extent.get("north"),
            "crs": spatial_extent.get("crs", "EPSG:4326"),
        }

    # Convert temporal_extent
    temporal = None
    if temporal_extent:
        temporal = temporal_extent

    # Load data via STAC
    data = load_stac(
        url=stac_url,
        spatial_extent=bbox,
        temporal_extent=temporal,
        bands=bands,
        properties=properties,
    )

    return data


def register_collection(collection_id: str, stac_url: str):
    """Register a new collection mapping."""
    COLLECTION_STAC_MAP[collection_id] = stac_url


def get_available_collections() -> list[str]:
    """Get list of available collection IDs."""
    return list(COLLECTION_STAC_MAP.keys())
```

### 6.3 Custom Jobs Register

```python
# /Users/macbookpro/openeo-deployment/openeo_app/registers/jobs.py

import uuid
import asyncio
from typing import Optional
from datetime import datetime
from pathlib import Path

from fastapi import Depends, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse

from openeo_fastapi.client.jobs import JobsRegister
from openeo_fastapi.client.auth import Authenticator, User
from openeo_fastapi.api.models import JobsRequest, Job
from openeo_fastapi.api.types import Status, Error
from openeo_fastapi.client.psql.engine import Filter, get, modify

from openeo_app.execution.executor import ProcessGraphExecutor
from openeo_app.storage.results import ResultStorage


class ExecutableJobsRegister(JobsRegister):
    """
    Extended JobsRegister with actual execution capabilities.

    This register overrides the stub methods (501 responses) with
    real implementations using the ProcessGraphExecutor.
    """

    def __init__(
        self,
        settings,
        links,
        executor: ProcessGraphExecutor,
        storage: Optional[ResultStorage] = None,
    ):
        super().__init__(settings, links)
        self.executor = executor
        self.storage = storage or ResultStorage()
        self._running_jobs = {}  # Track running async jobs

    def process_sync_job(
        self,
        body: JobsRequest,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Execute a synchronous job and return results immediately.

        POST /openeo/1.1.0/result
        """
        try:
            # Extract process graph
            process_graph = body.process.process_graph

            # Execute
            result = self.executor.execute(
                process_graph=process_graph,
                parameters={},
            )

            # Determine output format
            output_format = self._get_output_format(process_graph)

            # Return appropriate response
            if output_format == "GTiff":
                return self._return_geotiff(result)
            elif output_format == "netCDF":
                return self._return_netcdf(result)
            elif output_format == "JSON":
                return self._return_json(result)
            else:
                # Default: GeoTIFF
                return self._return_geotiff(result)

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=Error(
                    code="ProcessingError",
                    message=str(e),
                ),
            )

    def start_job(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Start batch job processing.

        POST /openeo/1.1.0/jobs/{job_id}/results
        """
        # Get job from database
        job = get(Job, Filter(must={"job_id": str(job_id)}))

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(code="JobNotFound", message=f"Job {job_id} not found"),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(code="Forbidden", message="Not authorized"),
            )

        # Check if already running
        if job.status in [Status.running, Status.queued]:
            raise HTTPException(
                status_code=400,
                detail=Error(code="JobAlreadyStarted", message="Job is already running"),
            )

        # Update status to queued
        job.status = Status.queued
        modify(job)

        # Start background execution
        asyncio.create_task(
            self._execute_job_async(job, user)
        )

        return Response(status_code=202)

    async def _execute_job_async(self, job: Job, user: User):
        """Execute job in background."""
        try:
            # Update status to running
            job.status = Status.running
            modify(job)

            # Execute process graph
            result = self.executor.execute(
                process_graph=job.process.process_graph,
                parameters={},
            )

            # Save results
            output_format = self._get_output_format(job.process.process_graph)
            result_path = self.storage.save_result(
                job_id=job.job_id,
                data=result,
                format=output_format,
            )

            # Update job status
            job.status = Status.finished
            modify(job)

        except Exception as e:
            # Update status to error
            job.status = Status.error
            modify(job)

            # Log error
            self.storage.save_log(
                job_id=job.job_id,
                level="error",
                message=str(e),
            )

    def get_results(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Get results of a completed job.

        GET /openeo/1.1.0/jobs/{job_id}/results
        """
        # Get job
        job = get(Job, Filter(must={"job_id": str(job_id)}))

        if job is None:
            raise HTTPException(status_code=404)

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(status_code=403)

        # Check status
        if job.status != Status.finished:
            raise HTTPException(
                status_code=400,
                detail=Error(
                    code="JobNotFinished",
                    message=f"Job status is {job.status}",
                ),
            )

        # Get result file
        result_path = self.storage.get_result(job_id)

        if result_path is None or not result_path.exists():
            raise HTTPException(
                status_code=404,
                detail=Error(code="ResultNotFound", message="Result file not found"),
            )

        return FileResponse(
            path=result_path,
            filename=result_path.name,
            media_type=self._get_media_type(result_path),
        )

    def logs(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Get job execution logs.

        GET /openeo/1.1.0/jobs/{job_id}/logs
        """
        # Get job
        job = get(Job, Filter(must={"job_id": str(job_id)}))

        if job is None:
            raise HTTPException(status_code=404)

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(status_code=403)

        # Get logs
        logs = self.storage.get_logs(job_id)

        return {"logs": logs, "links": []}

    def cancel_job(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Cancel a running job.

        DELETE /openeo/1.1.0/jobs/{job_id}/results
        """
        # Get job
        job = get(Job, Filter(must={"job_id": str(job_id)}))

        if job is None:
            raise HTTPException(status_code=404)

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(status_code=403)

        # Check if running
        if job.status not in [Status.running, Status.queued]:
            raise HTTPException(
                status_code=400,
                detail=Error(code="JobNotRunning", message="Job is not running"),
            )

        # Cancel (implementation depends on task queue)
        # For now, just update status
        job.status = Status.canceled
        modify(job)

        return Response(status_code=204)

    # Helper methods

    def _get_output_format(self, process_graph: dict) -> str:
        """Extract output format from save_result node."""
        for node_id, node in process_graph.items():
            if node.get("process_id") == "save_result":
                return node.get("arguments", {}).get("format", "GTiff")
        return "GTiff"

    def _return_geotiff(self, data) -> Response:
        """Return data as GeoTIFF."""
        import io
        import rioxarray

        buffer = io.BytesIO()
        data.rio.to_raster(buffer, driver="GTiff")
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="image/tiff",
            headers={"Content-Disposition": "attachment; filename=result.tif"},
        )

    def _return_netcdf(self, data) -> Response:
        """Return data as NetCDF."""
        import io

        buffer = io.BytesIO()
        data.to_netcdf(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/x-netcdf",
            headers={"Content-Disposition": "attachment; filename=result.nc"},
        )

    def _return_json(self, data) -> Response:
        """Return data as JSON."""
        import json

        # Convert to dict/list
        if hasattr(data, 'to_dict'):
            result = data.to_dict()
        elif hasattr(data, 'tolist'):
            result = data.tolist()
        else:
            result = str(data)

        return Response(
            content=json.dumps(result),
            media_type="application/json",
        )

    def _get_media_type(self, path: Path) -> str:
        """Get media type from file extension."""
        suffix = path.suffix.lower()
        return {
            ".tif": "image/tiff",
            ".tiff": "image/tiff",
            ".nc": "application/x-netcdf",
            ".json": "application/json",
            ".png": "image/png",
        }.get(suffix, "application/octet-stream")
```

### 6.4 Updated app.py

```python
# /Users/macbookpro/openeo-deployment/openeo_app/app.py

from fastapi import FastAPI

from openeo_fastapi.api.app import OpenEOApi
from openeo_fastapi.api.types import Billing, FileFormat, GisDataType, Link, Plan
from openeo_fastapi.client.core import OpenEOCore
from openeo_fastapi.client.settings import AppSettings

# Import custom components
from openeo_app.execution.executor import ProcessGraphExecutor
from openeo_app.registers.jobs import ExecutableJobsRegister
from openeo_app.storage.results import ResultStorage


# Initialize settings
settings = AppSettings()

# Initialize executor
executor = ProcessGraphExecutor(
    process_registry=None,  # Will be set by OpenEOCore
    stac_api_url=str(settings.STAC_API_URL),
)

# Initialize storage
storage = ResultStorage(base_path="/tmp/openeo_results")

# Create custom jobs register
jobs_register = ExecutableJobsRegister(
    settings=settings,
    links=[],
    executor=executor,
    storage=storage,
)

# Define formats
formats = [
    FileFormat(
        title="GeoTiff",
        gis_data_types=[GisDataType("raster")],
        parameters={},
    ),
    FileFormat(
        title="netCDF",
        gis_data_types=[GisDataType("raster")],
        parameters={},
    ),
    FileFormat(
        title="JSON",
        gis_data_types=[GisDataType("vector"), GisDataType("raster")],
        parameters={},
    ),
]

# Define links
links = [
    Link(
        href="https://github.com/eodcgmbh/openeo-fastapi",
        rel="about",
        type="text/html",
        title="OpenEO FastAPI Documentation",
    )
]

# Create OpenEO client with custom jobs register
client = OpenEOCore(
    input_formats=formats,
    output_formats=formats,
    links=links,
    billing=Billing(
        currency="credits",
        default_plan="free",
        plans=[Plan(name="free", description="Free tier", paid=False)],
    ),
    jobs=jobs_register,  # Use our custom register
)

# Update executor with process registry from client
executor.process_registry = client.processes.process_registry

# Create API
api = OpenEOApi(client=client, app=FastAPI())

# Export app
app = api.app
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
# tests/test_executor.py

import pytest
import xarray as xr
import numpy as np

from openeo_app.execution.executor import ProcessGraphExecutor


class TestProcessGraphExecutor:

    def test_simple_math(self):
        """Test simple math operations."""
        pg = {
            "add1": {
                "process_id": "add",
                "arguments": {"x": 1, "y": 2},
                "result": True,
            }
        }

        executor = ProcessGraphExecutor(...)
        result = executor.execute(pg)

        assert result == 3

    def test_load_collection(self):
        """Test load_collection process."""
        pg = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": "sentinel-2-l2a",
                    "spatial_extent": {
                        "west": 11.0, "east": 11.5,
                        "south": 46.0, "north": 46.5,
                    },
                    "temporal_extent": ["2021-01-01", "2021-01-10"],
                    "bands": ["B04"],
                },
                "result": True,
            }
        }

        executor = ProcessGraphExecutor(...)
        result = executor.execute(pg)

        assert isinstance(result, xr.DataArray)
```

### 7.2 Integration Tests

```python
# tests/test_integration.py

import pytest
from fastapi.testclient import TestClient

from openeo_app.app import app


class TestSyncJobExecution:

    def test_ndvi_calculation(self):
        """Test NDVI calculation workflow."""
        client = TestClient(app)

        process_graph = {
            "process_graph": {
                "load": {
                    "process_id": "load_collection",
                    "arguments": {
                        "id": "sentinel-2-l2a",
                        "spatial_extent": {...},
                        "temporal_extent": [...],
                        "bands": ["B04", "B08"],
                    },
                },
                "ndvi": {
                    "process_id": "normalized_difference",
                    "arguments": {
                        "x": {"from_node": "load"},
                        "y": {"from_node": "load"},
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
        }

        response = client.post(
            "/openeo/1.1.0/result",
            json=process_graph,
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/tiff"
```

---

## 8. Deployment Considerations

### 8.1 Dask Configuration

```python
# For local development
from dask.distributed import Client, LocalCluster

cluster = LocalCluster(
    n_workers=4,
    threads_per_worker=2,
    memory_limit="4GB",
)
client = Client(cluster)

# For production (Kubernetes)
from dask_kubernetes import KubeCluster

cluster = KubeCluster.from_yaml("dask-worker.yaml")
cluster.scale(10)
client = Client(cluster)
```

### 8.2 Environment Variables

```bash
# Add to .env
export DASK_SCHEDULER_ADDRESS="tcp://localhost:8786"
export RESULT_STORAGE_PATH="/data/openeo_results"
export MAX_CONCURRENT_JOBS="10"
export JOB_TIMEOUT_SECONDS="3600"
```

### 8.3 Resource Limits

```yaml
# kubernetes deployment
resources:
  limits:
    memory: "8Gi"
    cpu: "4"
  requests:
    memory: "4Gi"
    cpu: "2"
```

---

## Summary

### Implementation Checklist

- [ ] **Phase 1**: Core Execution
  - [ ] Create `execution/` module
  - [ ] Implement `ProcessGraphExecutor`
  - [ ] Implement `load_collection`
  - [ ] Create `ExecutableJobsRegister`
  - [ ] Update `app.py`
  - [ ] Test sync execution

- [ ] **Phase 2**: Batch Processing
  - [ ] Implement result storage
  - [ ] Add background tasks
  - [ ] Implement `start_job()`
  - [ ] Implement `get_results()`
  - [ ] Test batch execution

- [ ] **Phase 3**: Production
  - [ ] Implement `cancel_job()`
  - [ ] Implement `get_logs()`
  - [ ] Configure Dask cluster
  - [ ] Add monitoring
  - [ ] Load testing

### Key Files to Create

```
openeo_app/
├── execution/
│   ├── __init__.py
│   └── executor.py          # ProcessGraphExecutor
├── processes/
│   ├── __init__.py
│   └── load_collection.py   # load_collection impl
├── registers/
│   ├── __init__.py
│   └── jobs.py              # ExecutableJobsRegister
└── storage/
    ├── __init__.py
    └── results.py           # ResultStorage
```

---

*Plan created on February 4, 2026*
