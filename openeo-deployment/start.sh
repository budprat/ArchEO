#!/bin/bash
# OpenEO FastAPI Server Startup Script with Dask Execution Engine

cd /Users/macbookpro/openeo-deployment
source .env
source venv/bin/activate

# CRITICAL: Add deployment directory to Python path for imports to work
export PYTHONPATH="/Users/macbookpro/openeo-deployment:$PYTHONPATH"

echo "=========================================="
echo "Starting OpenEO FastAPI Server with Dask"
echo "=========================================="
echo ""
echo "API Endpoints:"
echo "  - Root:         http://localhost:8000/"
echo "  - Capabilities: http://localhost:8000/openeo/1.1.0/"
echo "  - Collections:  http://localhost:8000/openeo/1.1.0/collections"
echo "  - Processes:    http://localhost:8000/openeo/1.1.0/processes"
echo ""
echo "Execution Engine:"
echo "  - STAC URL:     $STAC_API_URL"
echo "  - Storage:      $RESULT_STORAGE_PATH"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=========================================="
echo ""

cd openeo_app
uvicorn app:app --reload --host 0.0.0.0 --port 8000
