# OpenEO FastAPI Deployment Documentation

This document details the complete setup, installation, and Dask-based datacube processing implementation for OpenEO FastAPI on macOS, performed on February 4, 2026.

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Requirements](#2-system-requirements)
3. [Prerequisites Installation](#3-prerequisites-installation)
4. [OpenEO FastAPI Installation](#4-openeo-fastapi-installation)
5. [Project Structure](#5-project-structure)
6. [Configuration](#6-configuration)
7. [Database Setup](#7-database-setup)
8. [Dask Execution Engine](#8-dask-execution-engine)
9. [Key Components Deep Dive](#9-key-components-deep-dive)
10. [STAC Catalog Integration](#10-stac-catalog-integration)
11. [Running the Server](#11-running-the-server)
12. [API Endpoints](#12-api-endpoints)
13. [Testing](#13-testing)
14. [Key Learnings and Gotchas](#14-key-learnings-and-gotchas)
15. [Troubleshooting](#15-troubleshooting)
16. [Quick Reference](#16-quick-reference)

---

## 1. Overview

### What is OpenEO FastAPI?

**OpenEO FastAPI** is a FastAPI-based implementation of the [OpenEO API specification](https://openeo.org/) for Earth Observation data processing. It provides:

- RESTful API endpoints conforming to OpenEO 1.1.0 specification
- STAC catalog integration for data discovery
- Process graph execution for datacube operations
- User authentication via OIDC
- Job management (sync and batch)

### This Deployment

This deployment extends the base OpenEO FastAPI with a **custom Dask-based execution engine** that enables actual datacube processing, not just API stubs.

**Key Features:**
- Real datacube processing using Dask and xarray
- STAC-based data loading from AWS Earth Search
- **136 implemented OpenEO processes** (dynamically loaded from openeo-processes-dask)
- GeoTIFF, NetCDF, JSON, and PNG output formats
- Synchronous and batch job execution

### Connection Details

| Component | URL/Details |
|-----------|-------------|
| **API Server** | http://localhost:8000/openeo/1.1.0/ |
| **STAC Catalog** | https://earth-search.aws.element84.com/v1/ |
| **OIDC Provider** | https://aai.egi.eu/auth/realms/egi |
| **Database** | PostgreSQL 15 @ localhost:5432/openeo |

### Deployment Location

```
/Users/macbookpro/openeo-deployment/
```

### Source Repository

```
https://github.com/eodcgmbh/openeo-fastapi.git
```

---

## 2. System Requirements

| Component | Required Version | Installed Version | Notes |
|-----------|------------------|-------------------|-------|
| macOS | Any recent version | Darwin 25.2.0 | Apple Silicon (M-series) |
| Python | >=3.10, <3.12 | 3.11.14 | Via pyenv |
| PostgreSQL | 13+ | 15.15 | Via Homebrew |
| GDAL | 3.x | 3.12.1 | Via Homebrew |
| Homebrew | Latest | Installed | Package manager |

### Why Python 3.11?

- `openeo-fastapi` requires Python >=3.10
- Python 3.12 has compatibility issues with some dependencies
- pyenv provides easy version management

### Why PostgreSQL 15?

- Required for job and user persistence
- Alembic migrations create the schema
- Can run without auth for local development

---

## 3. Prerequisites Installation

### 3.1 Homebrew (Package Manager)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Apple Silicon PATH setup
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

### 3.2 Python 3.11 via pyenv

```bash
# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.zshrc or ~/.bashrc
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Reload shell and install Python
source ~/.zshrc
pyenv install 3.11
pyenv global 3.11.14
```

**Verify:**
```bash
python --version  # Should show Python 3.11.14
```

### 3.3 PostgreSQL 15

```bash
brew install postgresql@15
brew services start postgresql@15

# CRITICAL: Add to PATH (binaries not in PATH by default!)
echo 'export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# Create database
createdb openeo
```

**Verify:**
```bash
psql -l | grep openeo  # Should show openeo database
```

### 3.4 GDAL (Geospatial Library)

```bash
brew install gdal
```

**Verify:**
```bash
gdal-config --version  # Should show 3.12.1
```

---

## 4. OpenEO FastAPI Installation

### 4.1 Create Deployment Directory

```bash
mkdir -p /Users/macbookpro/openeo-deployment
cd /Users/macbookpro/openeo-deployment
```

### 4.2 Create Virtual Environment

```bash
# Ensure correct Python version
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# Create and activate venv
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
```

### 4.3 Install OpenEO FastAPI

```bash
# Ensure system libraries are in PATH
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql@15/bin:$PATH"

# Install base package
pip install openeo-fastapi
```

### 4.4 Install Additional Dependencies for Execution Engine

```bash
# Core execution dependencies
pip install odc-stac planetary-computer stac-validator

# Handle compatibility issues (see Key Learnings section)
pip install dask-geopandas
pip install 'xvec==0.3.0'  # Specific version required!
pip install Pillow

# Remove problematic package (macOS binary incompatibility)
pip uninstall rqadeforestation -y 2>/dev/null || true
```

### 4.5 Create Project Structure

```bash
source venv/bin/activate
openeo_fastapi new --path /Users/macbookpro/openeo-deployment/openeo_app
```

### 4.6 Installed Package Versions

| Package | Version | Purpose |
|---------|---------|---------|
| openeo-fastapi | 2025.5.1 | Core API framework |
| openeo-processes-dask | 2025.10.1 | Process implementations |
| openeo-pg-parser-networkx | 2024.4.0 | Process graph parsing |
| fastapi | 0.95.2 | Web framework |
| uvicorn | 0.29.0 | ASGI server |
| xarray | 2025.1.1 | N-dimensional arrays |
| dask | 2026.1.1 | Parallel computing |
| rioxarray | 0.19.0 | Geospatial xarray |
| odc-stac | latest | STAC data loading |
| pystac-client | latest | STAC API client |

---

## 5. Project Structure

### Complete Directory Layout

```
/Users/macbookpro/openeo-deployment/
├── .env                          # Environment variables (source this first!)
├── start.sh                      # Server startup script
├── test_execution.py             # Test script for execution engine
├── CLAUDE.md                     # This documentation
├── INTEGRATION_PLAN.md           # Original integration plan
├── STAC_CONFIGURATION.md         # STAC setup documentation
│
├── venv/                         # Python virtual environment
│   ├── bin/
│   ├── lib/python3.11/site-packages/
│   └── ...
│
└── openeo_app/                   # Main application
    ├── __init__.py
    ├── app.py                    # FastAPI application entry point
    ├── revise.py                 # Database revision utilities
    │
    ├── execution/                # ** CUSTOM: Dask execution engine **
    │   ├── __init__.py
    │   └── executor.py           # ProcessGraphExecutor class
    │
    ├── processes/                # ** CUSTOM: Process implementations **
    │   ├── __init__.py
    │   └── load_collection.py    # STAC-based data loading
    │
    ├── registers/                # ** CUSTOM: Extended registers **
    │   ├── __init__.py
    │   └── jobs.py               # ExecutableJobsRegister
    │
    ├── storage/                  # ** CUSTOM: Result storage **
    │   ├── __init__.py
    │   └── results.py            # ResultStorage class
    │
    └── psql/                     # Database configuration
        ├── alembic.ini
        ├── models.py
        └── alembic/
            ├── env.py            # Migration environment
            └── versions/
                └── 862aed8d0722_initial.py
```

### Custom Components (What We Built)

| Directory | File | Purpose |
|-----------|------|---------|
| `execution/` | `executor.py` | Parses and executes OpenEO process graphs using Dask |
| `processes/` | `load_collection.py` | Maps collection IDs to STAC URLs, loads data |
| `registers/` | `jobs.py` | Overrides stub methods with real execution |
| `storage/` | `results.py` | Saves job results and logs to disk |

---

## 6. Configuration

### 6.1 Environment Variables (.env)

**Location:** `/Users/macbookpro/openeo-deployment/.env`

```bash
#!/bin/bash
# OpenEO FastAPI Environment Configuration
# Source this file before running the server!

# System PATH (required for GDAL and PostgreSQL)
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/postgresql@15/bin:$PATH"

# API Configuration
export API_DNS="localhost"
export API_TLS="False"
export API_TITLE="OpenEO API"
export API_DESCRIPTION="OpenEO FastAPI Implementation"
export OPENEO_VERSION="1.1.0"
export OPENEO_PREFIX="/openeo/1.1.0"

# OIDC Authentication
export OIDC_URL="https://aai.egi.eu/auth/realms/egi"
export OIDC_ORGANISATION="egi"

# STAC Catalog
export STAC_API_URL="https://earth-search.aws.element84.com/v1/"

# PostgreSQL Database
export POSTGRES_USER="macbookpro"
export POSTGRES_PASSWORD=""
export POSTGRESQL_HOST="localhost"
export POSTGRESQL_PORT="5432"
export POSTGRES_DB="openeo"

# Alembic Migrations
export ALEMBIC_DIR="/Users/macbookpro/openeo-deployment/openeo_app/psql"

# Execution Engine (custom)
export RESULT_STORAGE_PATH="/tmp/openeo_results"
```

### 6.2 Environment Variable Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `API_DNS` | Server hostname | localhost |
| `API_TLS` | Enable HTTPS | False |
| `STAC_API_URL` | STAC catalog URL | AWS Earth Search |
| `POSTGRES_*` | Database connection | Local PostgreSQL |
| `OIDC_URL` | Authentication provider | EGI Check-in |
| `RESULT_STORAGE_PATH` | Where to save job results | /tmp/openeo_results |

### 6.3 Alembic Configuration

**File:** `openeo_app/psql/alembic/env.py`

Key modification for database connection:

```python
from os import environ
from openeo_fastapi.client.psql.settings import BASE

config.set_main_option(
    "sqlalchemy.url",
    f"postgresql://{environ.get('POSTGRES_USER')}:{environ.get('POSTGRES_PASSWORD')}"
    f"@{environ.get('POSTGRESQL_HOST')}:{environ.get('POSTGRESQL_PORT')}"
    f"/{environ.get('POSTGRES_DB')}",
)

target_metadata = BASE.metadata
```

---

## 7. Database Setup

### 7.1 Create Database

```bash
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
createdb openeo
```

### 7.2 Run Migrations

```bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate
cd openeo_app/psql

# Generate initial migration
alembic revision --autogenerate -m "initial"

# Apply migrations
alembic upgrade head
```

### 7.3 Database Schema

Tables created by openeo-fastapi:

| Table | Purpose |
|-------|---------|
| `users` | User accounts (OIDC-linked) |
| `jobs` | Batch job metadata and status |
| `udps` | User-defined processes |

### 7.4 Verify Database

```bash
psql -d openeo -c "\dt"
```

Expected output:
```
         List of relations
 Schema | Name  | Type  |   Owner
--------+-------+-------+-----------
 public | jobs  | table | macbookpro
 public | udps  | table | macbookpro
 public | users | table | macbookpro
```

---

## 8. Dask Execution Engine

### 8.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLIENT REQUEST                                 │
│  POST /openeo/1.1.0/result (sync) OR POST /jobs/{id}/results (batch)   │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI LAYER                                       │
│  OpenEOApi routes requests to appropriate register methods              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   EXECUTABLE JOBS REGISTER                               │
│  ExecutableJobsRegister.process_sync_job() / start_job()                │
│  - Extracts process graph from request                                  │
│  - Delegates to ProcessGraphExecutor                                    │
│  - Returns results in requested format                                  │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROCESS GRAPH EXECUTOR                                │
│  1. Parse: OpenEOProcessGraph(process_graph) → NetworkX DAG            │
│  2. Build: pg.to_callable(process_registry) → nested callable          │
│  3. Execute: callable() → lazy xarray.DataArray                        │
│  4. Compute: result.compute() → triggers Dask execution                │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      PROCESS IMPLEMENTATIONS                             │
│  load_collection:                                                       │
│    → Maps collection ID to STAC URL                                     │
│    → pystac_client searches catalog                                     │
│    → odc.stac.load() returns xarray.DataArray with Dask chunks         │
│                                                                         │
│  filter_bbox, filter_temporal, etc:                                     │
│    → xarray slicing operations (lazy)                                   │
│                                                                         │
│  reduce_dimension, apply, etc:                                          │
│    → Dask array operations (lazy until .compute())                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       RESULT STORAGE                                     │
│  ResultStorage.save_result(job_id, data, format)                        │
│  - GeoTIFF: rioxarray.rio.to_raster()                                  │
│  - NetCDF: xarray.to_netcdf()                                          │
│  - JSON: dict serialization                                            │
│  - PNG: PIL Image from normalized array                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Key Libraries Used

| Library | Purpose | How We Use It |
|---------|---------|---------------|
| `openeo-pg-parser-networkx` | Parse process graphs | `OpenEOProcessGraph` class converts JSON to NetworkX DAG |
| `openeo-processes-dask` | Process implementations | Provides `filter_bbox`, `reduce_dimension`, etc. |
| `pystac-client` | STAC API client | Searches STAC catalogs for items |
| `odc-stac` | Load STAC data | `odc.stac.load()` creates xarray from STAC items |
| `xarray` | N-dimensional arrays | Core data structure for datacubes |
| `dask` | Parallel/lazy computing | Enables chunked, out-of-core processing |
| `rioxarray` | Geospatial xarray | Adds CRS handling and GeoTIFF export |

### 8.3 Available Processes (136 Total)

The executor dynamically loads all processes from `openeo-processes-dask`. Here's the complete list organized by category:

| Category | Count | Processes |
|----------|-------|-----------|
| **Data Loading** | 5 | `load_collection`, `load_stac`, `load_geojson`, `load_url`, `create_data_cube` |
| **Filtering** | 5 | `filter_bands`, `filter_bbox`, `filter_labels`, `filter_spatial`, `filter_temporal` |
| **Cube Manipulation** | 9 | `add_dimension`, `drop_dimension`, `dimension_labels`, `rename_dimension`, `rename_labels`, `reduce_dimension`, `reduce_spatial`, `trim_cube`, `rearrange` |
| **Apply/Transform** | 5 | `apply`, `apply_dimension`, `apply_kernel`, `apply_neighborhood_intertwin`, `apply_polygon` |
| **Aggregation** | 3 | `aggregate_spatial`, `aggregate_temporal`, `aggregate_temporal_period` |
| **Resampling** | 3 | `resample_cube_spatial`, `resample_cube_temporal`, `resample_spatial` |
| **Merge/Mask** | 3 | `merge_cubes`, `mask`, `mask_polygon` |
| **Indices** | 2 | `ndvi`, `normalized_difference` |
| **Math** | 21 | `add`, `subtract`, `multiply`, `divide`, `mod`, `power`, `sqrt`, `absolute`, `sgn`, `clip`, `ceil`, `floor`, `ln`, `log`, `exp`, `e`, `pi`, `nan`, `int`, `round`, `linear_scale_range` |
| **Trigonometry** | 13 | `sin`, `cos`, `tan`, `sinh`, `cosh`, `tanh`, `arcsin`, `arccos`, `arctan`, `arctan2`, `arsinh`, `arcosh`, `artanh` |
| **Statistics** | 15 | `min`, `max`, `sum`, `mean`, `median`, `sd`, `variance`, `count`, `product`, `extrema`, `quantiles`, `cumsum`, `cumproduct`, `cummin`, `cummax` |
| **Comparison** | 7 | `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `between` |
| **Logic** | 7 | `and`, `or`, `not`, `xor`, `if`, `all`, `any` |
| **Arrays** | 17 | `array_append`, `array_apply`, `array_concat`, `array_contains`, `array_create`, `array_create_labeled`, `array_element`, `array_filter`, `array_find`, `array_find_label`, `array_interpolate_linear`, `array_labels`, `array_modify`, `first`, `last`, `order`, `sort` |
| **Text** | 4 | `text_begins`, `text_concat`, `text_contains`, `text_ends` |
| **Date/Time** | 4 | `date_between`, `date_difference`, `date_shift`, `datetime_from_str` |
| **Type Checking** | 7 | `is_infinite`, `is_nan`, `is_nodata`, `is_valid`, `isnull`, `notnull`, `constant` |
| **Vector** | 2 | `vector_buffer`, `vector_reproject` |
| **Output** | 2 | `save_result`, `inspect` |
| **UDF** | 1 | `run_udf` |

**Not Loaded (optional dependencies):**
- **ML processes** (~4): `fit_curve`, `fit_regr_random_forest`, `predict_curve`, `predict_random_forest` - requires `pip install openeo-processes-dask[ml]`
- **Experimental** (~8): Deforestation detection - requires Linux-only `rqadeforestation` library

### 8.4 Lazy vs Eager Execution

The execution engine uses **lazy evaluation** by default:

```python
# Lazy execution (returns Dask-backed DataArray)
result = executor.execute_lazy(process_graph)
# result.shape shows dimensions but data isn't loaded yet

# Eager execution (calls .compute())
result = executor.execute(process_graph)
# Data is fully loaded into memory
```

**Why this matters:**
- Lazy evaluation builds a computation graph without executing
- Only `.compute()` triggers actual data loading and processing
- Enables processing datasets larger than RAM

---

## 9. Key Components Deep Dive

### 9.1 ProcessGraphExecutor (`execution/executor.py`)

**Purpose:** Parse and execute OpenEO process graphs using Dask.

**Key Methods:**

```python
class ProcessGraphExecutor:
    def __init__(self, stac_api_url: str):
        """Initialize with STAC API URL."""
        self._process_registry = self._build_process_registry()

    def execute(self, process_graph: dict, parameters: dict = None) -> Any:
        """Execute process graph and return computed result."""
        pg = OpenEOProcessGraph(pg_data=process_graph)
        callable_graph = pg.to_callable(process_registry=self._process_registry)
        result = callable_graph()
        if hasattr(result, 'compute'):
            result = result.compute()  # Trigger Dask computation
        return result

    def execute_lazy(self, process_graph: dict, parameters: dict = None) -> Any:
        """Execute process graph and return lazy (uncomputed) result."""
        # Same as execute() but without .compute()
```

**How Process Registry Works (Dynamic Loading):**

The executor dynamically discovers and loads all 136+ processes from `openeo-processes-dask`:

```python
def _discover_processes_from_package():
    """Dynamically discover all process implementations."""
    from openeo_processes_dask import process_implementations
    import pkgutil, importlib, inspect

    process_map = {}
    for importer, modname, ispkg in pkgutil.walk_packages(
        process_implementations.__path__,
        prefix='openeo_processes_dask.process_implementations.'
    ):
        module = importlib.import_module(modname)
        for name in dir(module):
            obj = getattr(module, name)
            if callable(obj) and not inspect.isclass(obj):
                process_map[name] = _wrap_process(obj)  # Wrap to handle extra kwargs
    return process_map

def _wrap_process(func):
    """Wrap process to accept named_parameters from pg-parser-networkx."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        kwargs.pop('named_parameters', None)
        return func(*args, **kwargs)
    return wrapper
```

**Custom overrides applied:**
- `load_collection`: Our custom implementation with STAC collection ID mapping
- Reserved words (`min`, `max`, `sum`, `and`, `or`, `not`, `if`, etc.): Mapped from `_min`, `_max`, etc.

### 9.2 load_collection (`processes/load_collection.py`)

**Purpose:** Map OpenEO collection IDs to STAC URLs and load data.

**Key Code:**

```python
# Collection ID to STAC URL mapping
COLLECTION_STAC_MAP = {
    "sentinel-2-l2a": f"{STAC_API_URL}collections/sentinel-2-l2a",
    "cop-dem-glo-30": f"{STAC_API_URL}collections/cop-dem-glo-30",
    # ... more collections
}

def load_collection(
    id: str,
    spatial_extent: Optional[dict] = None,
    temporal_extent: Optional[list] = None,
    bands: Optional[list] = None,
    properties: Optional[dict] = None,
    named_parameters: Optional[dict] = None,  # Required by graph executor!
    **kwargs,
) -> xr.DataArray:
    """Load collection by ID."""

    # Get STAC URL
    stac_url = COLLECTION_STAC_MAP.get(id)

    # Convert extents to proper types
    bbox = BoundingBox(...) if spatial_extent else None
    temporal = [pd.to_datetime(t) for t in temporal_extent] if temporal_extent else None

    # Load via openeo-processes-dask
    data = load_stac(
        url=stac_url,
        spatial_extent=bbox,
        temporal_extent=temporal,
        bands=bands,
    )
    return data
```

**Important:** The `named_parameters` argument is required because `openeo-pg-parser-networkx` passes it to all process implementations.

### 9.3 ExecutableJobsRegister (`registers/jobs.py`)

**Purpose:** Override stub methods with real execution.

**Key Methods:**

```python
class ExecutableJobsRegister(JobsRegister):
    def __init__(self, settings, links, executor, storage):
        super().__init__(settings, links)
        self.executor = executor
        self.storage = storage

    def process_sync_job(self, body: JobsRequest, user: User) -> Response:
        """Execute synchronous job."""
        process_graph = body.process.process_graph
        result = self.executor.execute(process_graph)
        output_format = self._get_output_format(process_graph)
        return self._create_response(result, output_format)

    def start_job(self, job_id: uuid.UUID, user: User) -> Response:
        """Start batch job in background."""
        job = get(get_model=Job, primary_key=job_id)
        job.status = Status.queued
        modify(job)
        asyncio.create_task(self._execute_job_async(job))
        return Response(status_code=202)
```

### 9.4 ResultStorage (`storage/results.py`)

**Purpose:** Save job results and logs to disk.

**Key Methods:**

```python
class ResultStorage:
    def __init__(self, base_path: str = "/tmp/openeo_results"):
        self.base_path = Path(base_path)
        self.results_dir = self.base_path / "results"
        self.logs_dir = self.base_path / "logs"

    def save_result(self, job_id, data, format="GTiff") -> Path:
        """Save computation result."""
        job_dir = self.results_dir / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)

        if format in ["GTiff", "GeoTiff"]:
            data.rio.to_raster(result_path, driver="GTiff")
        elif format == "netCDF":
            data.to_netcdf(result_path)
        # ... more formats

        return result_path

    def get_result(self, job_id) -> Optional[Path]:
        """Get path to result file."""
        # ... lookup logic

    def save_log(self, job_id, level, message):
        """Append log entry to JSONL file."""
        # ... logging logic
```

---

## 10. STAC Catalog Integration

### 10.1 AWS Earth Search

**URL:** https://earth-search.aws.element84.com/v1/

**Available Collections:**

| Collection ID | Description | Spatial Coverage |
|---------------|-------------|------------------|
| `sentinel-2-l2a` | Sentinel-2 L2A (atmospherically corrected) | Global |
| `sentinel-2-l1c` | Sentinel-2 L1C (top of atmosphere) | Global |
| `sentinel-1-grd` | Sentinel-1 GRD | Global |
| `landsat-c2-l2` | Landsat Collection 2 Level 2 | Global |
| `cop-dem-glo-30` | Copernicus DEM 30m | Global |
| `cop-dem-glo-90` | Copernicus DEM 90m | Global |
| `naip` | NAIP aerial imagery | USA only |

### 10.2 Band Name Mapping

**CRITICAL:** AWS Earth Search uses different band names than standard OpenEO!

| Standard OpenEO | AWS Earth Search | Wavelength |
|-----------------|------------------|------------|
| `B02` | `blue` | Blue (490nm) |
| `B03` | `green` | Green (560nm) |
| `B04` | `red` | Red (665nm) |
| `B05` | `rededge1` | Red Edge 1 |
| `B06` | `rededge2` | Red Edge 2 |
| `B07` | `rededge3` | Red Edge 3 |
| `B08` | `nir` | NIR (842nm) |
| `B8A` | `nir08` | NIR narrow (865nm) |
| `B09` | `nir09` | Water vapor |
| `B11` | `swir16` | SWIR (1610nm) |
| `B12` | `swir22` | SWIR (2190nm) |
| `SCL` | `scl` | Scene classification |

**Example - Correct Usage:**
```python
# WRONG (will fail)
load_collection(..., bands=["B04", "B08"])

# CORRECT
load_collection(..., bands=["red", "nir"])
```

### 10.3 How Data Loading Works

```
1. Client requests load_collection(id="sentinel-2-l2a", ...)
                    │
                    ▼
2. load_collection() maps ID → STAC URL
   "sentinel-2-l2a" → "https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a"
                    │
                    ▼
3. load_stac() uses pystac_client to search
   - Searches by bbox, datetime, collection
   - Returns STAC ItemCollection
                    │
                    ▼
4. odc.stac.load() creates xarray.DataArray
   - Reads COG (Cloud Optimized GeoTIFF) URLs
   - Creates Dask chunks (lazy loading)
   - Returns DataArray with dims: (bands, time, y, x)
```

### 10.4 Adding Custom Collections

```python
from openeo_app.processes.load_collection import register_collection

# Register a custom collection
register_collection(
    "my-collection",
    "https://my-stac-catalog.com/collections/my-collection"
)
```

---

## 11. Running the Server

### 11.1 Quick Start

```bash
cd /Users/macbookpro/openeo-deployment
./start.sh
```

### 11.2 Manual Start

```bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate
cd openeo_app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 11.3 Background Start

```bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate
cd openeo_app
nohup uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/openeo_server.log 2>&1 &
```

### 11.4 Stop Server

```bash
pkill -f "uvicorn"
# or
lsof -i :8000
kill -9 <PID>
```

### 11.5 Server Startup Logs

When the server starts, you should see:

```
2026-02-04 - openeo_app.app - INFO - STAC API URL: https://earth-search.aws.element84.com/v1/
2026-02-04 - openeo_app.app - INFO - Result storage path: /tmp/openeo_results
2026-02-04 - openeo_app.app - INFO - Initializing ProcessGraphExecutor...
2026-02-04 - openeo_app.execution.executor - INFO - Built process registry with 136 processes
2026-02-04 - openeo_app.execution.executor - INFO - ProcessGraphExecutor initialized with 136 processes
2026-02-04 - openeo_app.app - INFO - Creating ExecutableJobsRegister...
2026-02-04 - openeo_app.registers.jobs - INFO - ExecutableJobsRegister initialized
2026-02-04 - openeo_app.app - INFO - OpenEO FastAPI application initialized successfully
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

## 12. API Endpoints

### 12.1 Core Endpoints

| Path | Method | Description |
|------|--------|-------------|
| `/openeo/1.1.0/` | GET | API capabilities |
| `/openeo/1.1.0/collections` | GET | List all collections |
| `/openeo/1.1.0/collections/{id}` | GET | Get collection details |
| `/openeo/1.1.0/processes` | GET | List all processes |
| `/openeo/1.1.0/result` | POST | Synchronous job execution |
| `/openeo/1.1.0/jobs` | GET, POST | List/create batch jobs |
| `/openeo/1.1.0/jobs/{id}` | GET, PATCH, DELETE | Job operations |
| `/openeo/1.1.0/jobs/{id}/results` | GET, POST, DELETE | Start/get/cancel job |
| `/openeo/1.1.0/jobs/{id}/logs` | GET | Get job logs |

### 12.2 Testing Endpoints

```bash
# Capabilities
curl http://localhost:8000/openeo/1.1.0/

# Collections
curl http://localhost:8000/openeo/1.1.0/collections

# Processes
curl http://localhost:8000/openeo/1.1.0/processes

# Count processes
curl -s http://localhost:8000/openeo/1.1.0/processes | python3 -c "
import sys, json
print(f'Processes: {len(json.load(sys.stdin)[\"processes\"])}')"
```

---

## 13. Testing

### 13.1 Run Test Script

```bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate
python test_execution.py
```

### 13.2 Expected Output

```
============================================================
OpenEO FastAPI Dask Execution Engine Tests
============================================================

Test 1: Executor Initialization - PASSED (136 processes)
Test 2: Simple Math (add) - PASSED
Test 3: Chained Operations - PASSED
Test 4: Load Collection (DEM) - PASSED
Test 5: Result Storage - PASSED
Test 6: NDVI Calculation - PASSED

============================================================
ALL TESTS PASSED!
============================================================
```

### 13.3 Manual Testing

**Test 1: Simple Math**
```python
from openeo_app.execution.executor import ProcessGraphExecutor

executor = ProcessGraphExecutor(stac_api_url='https://earth-search.aws.element84.com/v1/')
result = executor.execute({
    "add1": {"process_id": "add", "arguments": {"x": 1, "y": 2}, "result": True}
})
print(result)  # 3.0
```

**Test 2: Load Collection**
```python
from openeo_app.processes.load_collection import load_collection

data = load_collection(
    id="cop-dem-glo-30",
    spatial_extent={"west": 11.0, "south": 46.0, "east": 11.01, "north": 46.01}
)
print(data.shape)  # (1, 1, ~37, ~36)
print(data.dims)   # ('bands', 'time', 'latitude', 'longitude')
```

**Test 3: NDVI Calculation**
```python
data = load_collection(
    id="sentinel-2-l2a",
    spatial_extent={"west": 11.0, "south": 46.0, "east": 11.01, "north": 46.01},
    temporal_extent=["2024-06-01", "2024-06-10"],
    bands=["red", "nir"]  # Use AWS Earth Search band names!
)
red = data.sel(bands="red")
nir = data.sel(bands="nir")
ndvi = (nir - red) / (nir + red)
```

---

## 14. Key Learnings and Gotchas

### 14.1 Dependency Version Conflicts

**Problem:** `xvec` and `xproj` packages have version conflicts with `xarray`

**Symptom:**
```
ImportError: cannot import name 'AlignmentError' from 'xarray'
```

**Solution:**
```bash
pip install 'xvec==0.3.0'  # Use specific older version
```

### 14.2 macOS Binary Incompatibility

**Problem:** `rqadeforestation` package contains Linux-only binaries

**Symptom:**
```
OSError: dlopen(...rqatrend.so...): slice is not valid mach-o file
```

**Solution:**
```bash
pip uninstall rqadeforestation -y
```

### 14.3 Process Graph Executor Named Parameters

**Problem:** `openeo-pg-parser-networkx` passes `named_parameters` to all process implementations

**Symptom:**
```
TypeError: load_stac() got an unexpected keyword argument 'named_parameters'
```

**Solution:** Add `named_parameters: Optional[dict] = None` to function signatures:
```python
def load_collection(
    id: str,
    ...
    named_parameters: Optional[dict] = None,  # Accept but ignore
    **kwargs,
) -> xr.DataArray:
```

### 14.4 AWS Earth Search Band Names

**Problem:** Band names differ from standard OpenEO conventions

**Symptom:**
```
OpenEOException: The provided bands: ['B04', 'B08'] can't be found in the STAC assets
```

**Solution:** Use AWS Earth Search band names:
- `B04` → `red`
- `B08` → `nir`
- See Section 10.2 for full mapping

### 14.5 PostgreSQL PATH on macOS

**Problem:** Homebrew doesn't add PostgreSQL to PATH

**Symptom:**
```
zsh: command not found: createdb
```

**Solution:**
```bash
export PATH="/opt/homebrew/opt/postgresql@15/bin:$PATH"
```

### 14.6 Time Dimension Handling

**Problem:** GeoTIFF format doesn't support time dimension

**Symptom:**
```
RasterioIOError: Can't write 4D array
```

**Solution:** Select first time slice before saving:
```python
if "time" in data.dims:
    data = data.isel(time=0)
data.rio.to_raster("output.tif")
```

### 14.7 Missing CRS

**Problem:** Some data doesn't have CRS metadata

**Symptom:**
```
RasterioIOError: CRS is required for GeoTIFF
```

**Solution:** Set CRS before saving:
```python
if data.rio.crs is None:
    data = data.rio.write_crs("EPSG:4326")
```

---

## 15. Troubleshooting

### 15.1 Server Won't Start

**Check 1: Port in use**
```bash
lsof -i :8000
pkill -f uvicorn
```

**Check 2: Environment variables**
```bash
source .env
echo $STAC_API_URL  # Should show URL
```

**Check 3: Virtual environment**
```bash
which python  # Should be in venv/bin/
pip list | grep openeo
```

### 15.2 Database Errors

**Check 1: PostgreSQL running**
```bash
brew services list | grep postgresql
brew services start postgresql@15
```

**Check 2: Database exists**
```bash
psql -l | grep openeo
createdb openeo  # If missing
```

**Check 3: Run migrations**
```bash
cd openeo_app/psql
alembic upgrade head
```

### 15.3 Import Errors

**ModuleNotFoundError:**
```bash
source venv/bin/activate
pip install <missing-package>
```

**OSError with .so files:**
```bash
pip uninstall <problematic-package> -y
```

### 15.4 Data Loading Fails

**Check 1: STAC URL accessible**
```bash
curl -s https://earth-search.aws.element84.com/v1/ | head
```

**Check 2: Collection exists**
```bash
curl -s https://earth-search.aws.element84.com/v1/collections | python3 -c "
import sys,json
for c in json.load(sys.stdin)['collections']:
    print(c['id'])"
```

**Check 3: Band names correct**
```bash
curl -s https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a | python3 -c "
import sys,json
print(list(json.load(sys.stdin).get('item_assets',{}).keys()))"
```

### 15.5 Memory Issues

**Symptom:** Process killed or system slowdown

**Solution:** Use smaller spatial/temporal extents:
```python
# Instead of 1 degree, use 0.01 degrees
spatial_extent={
    "west": 11.0, "south": 46.0,
    "east": 11.01, "north": 46.01  # 0.01 degree = ~1km
}
```

---

## 16. Quick Reference

### Start Server
```bash
cd /Users/macbookpro/openeo-deployment && ./start.sh
```

### Stop Server
```bash
pkill -f "uvicorn"
```

### Activate Environment
```bash
source /Users/macbookpro/openeo-deployment/.env
source /Users/macbookpro/openeo-deployment/venv/bin/activate
```

### Check API Status
```bash
curl http://localhost:8000/openeo/1.1.0/
```

### Run Tests
```bash
cd /Users/macbookpro/openeo-deployment
source .env && source venv/bin/activate
python test_execution.py
```

### Key Files

| File | Purpose |
|------|---------|
| `.env` | Environment variables - **source first!** |
| `start.sh` | Server startup script |
| `test_execution.py` | Test script |
| `openeo_app/app.py` | Main FastAPI application |
| `openeo_app/execution/executor.py` | Process graph executor |
| `openeo_app/processes/load_collection.py` | STAC data loading |
| `openeo_app/registers/jobs.py` | Job execution |
| `openeo_app/storage/results.py` | Result storage |

### Version Information

| Component | Version |
|-----------|---------|
| OpenEO FastAPI | 2025.5.1 |
| OpenEO API Spec | 1.1.0 |
| Python | 3.11.14 |
| PostgreSQL | 15.15 |
| GDAL | 3.12.1 |
| Dask | 2026.1.1 |
| xarray | 2025.1.1 |

---

## Additional Resources

- **OpenEO FastAPI Repository:** https://github.com/eodcgmbh/openeo-fastapi
- **OpenEO API Specification:** https://openeo.org/documentation/1.0/
- **OpenEO Processes:** https://processes.openeo.org/
- **STAC Specification:** https://stacspec.org/
- **AWS Earth Search:** https://earth-search.aws.element84.com/v1/
- **Dask Documentation:** https://docs.dask.org/
- **xarray Documentation:** https://docs.xarray.dev/

---

*Documentation created: February 4, 2026*
*Last updated: February 4, 2026 - Complete Dask execution engine implementation*
