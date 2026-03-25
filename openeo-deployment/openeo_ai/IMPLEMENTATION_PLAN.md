# OpenEO AI Assistant - Detailed Implementation Plan

## Executive Summary

This implementation plan builds the OpenEO AI Assistant on top of the **existing OpenEO FastAPI deployment** at `/Users/macbookpro/openeo-deployment/`. The existing infrastructure provides:

- **PostgreSQL Database** with Alembic migrations
- **ProcessGraphExecutor** with 136+ processes
- **ResultStorage** for multi-format outputs
- **STAC Integration** with 9 collections
- **Validation Framework** (extent validation)
- **Test Infrastructure** with pytest

We follow **Test-Driven Development (TDD)**: write tests first, then implement.

---

## Leveraged Existing Components

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| ProcessGraphExecutor | `execution/executor.py` | Direct import - executes process graphs |
| ResultStorage | `storage/results.py` | Direct import - save results |
| load_collection | `processes/load_collection.py` | Direct import - STAC data loading |
| PostgreSQL | `psql/models.py` | Extend with new tables via Alembic |
| ExtentValidator | `validation/extent_validator.py` | Direct import - prevent resource exhaustion |
| BandMapper | `processes/band_mapper.py` | Direct import - band name translation |

---

## Project Structure

```
/Users/macbookpro/openeo-deployment/
├── openeo_app/                    # Existing OpenEO API
│   ├── execution/executor.py      # REUSE: ProcessGraphExecutor
│   ├── storage/results.py         # REUSE: ResultStorage
│   ├── processes/                 # REUSE: load_collection, band_mapper
│   └── validation/                # REUSE: extent_validator
│
├── openeo_ai/                     # NEW: AI Assistant
│   ├── __init__.py
│   ├── IMPLEMENTATION_PLAN.md     # This file
│   │
│   ├── sdk/                       # Phase 1: Claude SDK Integration
│   │   ├── __init__.py
│   │   ├── client.py              # Claude SDK client wrapper
│   │   ├── tools.py               # Custom tool definitions
│   │   ├── permissions.py         # Permission callbacks
│   │   └── sessions.py            # Session management
│   │
│   ├── tools/                     # Phase 2: Tool Implementations
│   │   ├── __init__.py
│   │   ├── openeo_tools.py        # OpenEO data tools
│   │   ├── job_tools.py           # Batch job tools
│   │   ├── validation_tools.py    # Process graph validation
│   │   └── viz_tools.py           # Visualization tools
│   │
│   ├── storage/                   # Phase 3: Extended Storage
│   │   ├── __init__.py
│   │   ├── models.py              # SQLAlchemy models (new tables)
│   │   ├── migrations/            # Alembic migrations
│   │   └── repositories.py        # Data access layer
│   │
│   ├── geoai/                     # Phase 4: GeoAI Models
│   │   ├── __init__.py
│   │   ├── model_registry.py      # Model management
│   │   ├── inference.py           # Inference engine
│   │   └── models/                # Pre-trained models
│   │
│   └── visualization/             # Phase 5: MCP-UI Components
│       ├── __init__.py
│       ├── maps.py                # Interactive maps
│       └── charts.py              # Time series charts
│
└── tests/
    ├── test_openeo_ai/            # NEW: AI Assistant tests
    │   ├── __init__.py
    │   ├── test_sdk_client.py     # Phase 1 tests
    │   ├── test_tools.py          # Phase 2 tests
    │   ├── test_storage.py        # Phase 3 tests
    │   ├── test_validation.py     # Phase 2 tests
    │   ├── test_geoai.py          # Phase 4 tests
    │   └── test_visualization.py  # Phase 5 tests
    └── conftest.py                # Shared fixtures
```

---

## Phase 1: Claude SDK Integration (Week 1-2)

### 1.1 Goals
- Integrate Claude SDK for conversational AI
- Create session management with PostgreSQL
- Define permission callbacks for tool execution

### 1.2 Test Cases (Write First)

```python
# tests/test_openeo_ai/test_sdk_client.py
```

### 1.3 Implementation Files
- `openeo_ai/sdk/client.py` - Main Claude SDK wrapper
- `openeo_ai/sdk/sessions.py` - Session persistence
- `openeo_ai/sdk/permissions.py` - Permission callbacks

---

## Phase 2: Custom Tools & Validation (Week 2-3)

### 2.1 Goals
- Implement OpenEO tools for Claude SDK
- Create process graph validator with educational feedback
- Wrap existing ProcessGraphExecutor

### 2.2 Test Cases (Write First)

```python
# tests/test_openeo_ai/test_tools.py
# tests/test_openeo_ai/test_validation.py
```

### 2.3 Implementation Files
- `openeo_ai/tools/openeo_tools.py` - Data discovery tools
- `openeo_ai/tools/job_tools.py` - Job management tools
- `openeo_ai/tools/validation_tools.py` - Graph validation

---

## Phase 3: Storage & Process Graph Library (Week 3-4)

### 3.1 Goals
- Extend PostgreSQL schema for AI sessions & saved graphs
- Create repositories for data access
- Implement process graph library

### 3.2 Test Cases (Write First)

```python
# tests/test_openeo_ai/test_storage.py
```

### 3.3 Implementation Files
- `openeo_ai/storage/models.py` - SQLAlchemy models
- `openeo_ai/storage/repositories.py` - Data access layer
- `openeo_ai/storage/migrations/` - Alembic migrations

---

## Phase 4: GeoAI Model Integration (Week 4-6)

### 4.1 Goals
- Create model registry for GeoAI models
- Implement inference engine with tiling
- Add segmentation, change detection, canopy height

### 4.2 Test Cases (Write First)

```python
# tests/test_openeo_ai/test_geoai.py
```

### 4.3 Implementation Files
- `openeo_ai/geoai/model_registry.py`
- `openeo_ai/geoai/inference.py`
- `openeo_ai/geoai/models/`

---

## Phase 5: Visualization (Week 6-7)

### 5.1 Goals
- Create MCP-UI map components
- Implement chart components
- Add comparison slider

### 5.2 Test Cases (Write First)

```python
# tests/test_openeo_ai/test_visualization.py
```

### 5.3 Implementation Files
- `openeo_ai/visualization/maps.py`
- `openeo_ai/visualization/charts.py`

---

## Detailed Test Specifications

See individual test files created below for complete test specifications.

---

## Database Schema Extensions

### New Tables (via Alembic Migration)

```sql
-- AI Chat Sessions
CREATE TABLE ai_sessions (
    id UUID PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP DEFAULT NOW(),
    context JSONB,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Saved Process Graphs
CREATE TABLE saved_process_graphs (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    process_graph JSONB NOT NULL,
    user_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- Process Graph Tags
CREATE TABLE process_graph_tags (
    id UUID PRIMARY KEY,
    name VARCHAR UNIQUE NOT NULL
);

-- Many-to-many relation
CREATE TABLE graph_tag_associations (
    graph_id UUID REFERENCES saved_process_graphs(id),
    tag_id UUID REFERENCES process_graph_tags(id),
    PRIMARY KEY (graph_id, tag_id)
);

-- Execution History
CREATE TABLE execution_history (
    id UUID PRIMARY KEY,
    graph_id UUID REFERENCES saved_process_graphs(id),
    job_id UUID REFERENCES jobs(id),
    session_id UUID REFERENCES ai_sessions(id),
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR,
    result_path VARCHAR,
    error_message TEXT
);
```

---

## Dependencies to Install

```bash
# Core dependencies
pip install anthropic  # Claude SDK (when available) or use HTTP API

# Already installed (verify)
pip show openeo-fastapi openeo-processes-dask xarray dask rioxarray

# For GeoAI (Phase 4)
pip install torch torchvision  # If running local models

# For visualization (Phase 5)
pip install folium  # Interactive maps
```

---

## Running Tests

```bash
cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate

# Run all AI tests
pytest tests/test_openeo_ai/ -v

# Run specific phase tests
pytest tests/test_openeo_ai/test_sdk_client.py -v  # Phase 1
pytest tests/test_openeo_ai/test_tools.py -v       # Phase 2
pytest tests/test_openeo_ai/test_validation.py -v  # Phase 2
pytest tests/test_openeo_ai/test_storage.py -v     # Phase 3
pytest tests/test_openeo_ai/test_geoai.py -v       # Phase 4
pytest tests/test_openeo_ai/test_visualization.py -v  # Phase 5

# With coverage
pytest tests/test_openeo_ai/ -v --cov=openeo_ai --cov-report=html
```
