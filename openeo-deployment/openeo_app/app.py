"""OpenEO FastAPI Application with Dask Execution Engine.

This module configures and creates the OpenEO FastAPI application with:
- Custom ExecutableJobsRegister for actual job processing
- ProcessGraphExecutor for running process graphs using Dask
- ResultStorage for managing job outputs
- Development mode with Basic Auth bypass
- Production logging with rotating file handlers
"""

import logging
import logging.handlers
import os
from pathlib import Path

from fastapi import FastAPI

from openeo_fastapi.api.app import OpenEOApi
from openeo_fastapi.api.types import Billing, FileFormat, GisDataType, Link, Plan
from openeo_fastapi.client.core import OpenEOCore
from openeo_fastapi.client.settings import AppSettings
from openeo_fastapi.client.auth import Authenticator

# Import custom components
from openeo_app.auth import DevAuthenticator, DEV_MODE
from openeo_app.execution.executor import ProcessGraphExecutor
from openeo_app.rate_limit import RateLimitMiddleware
from openeo_app.registers.jobs import ExecutableJobsRegister
from openeo_app.storage.results import ResultStorage


def configure_logging():
    """Configure production logging with rotating file handlers.

    Creates three log files:
    - openeo.log: All logs
    - openeo_execution.log: Process execution logs only
    - openeo_error.log: Error logs only
    """
    log_dir = Path(os.environ.get("LOG_DIR", "/tmp/openeo_logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    # Log format
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Main log file with rotation (10MB, keep 10 backups)
    main_handler = logging.handlers.RotatingFileHandler(
        log_dir / "openeo.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
    )
    main_handler.setFormatter(log_format)
    main_handler.setLevel(logging.INFO)
    root_logger.addHandler(main_handler)

    # Execution log file (for process execution details)
    execution_handler = logging.handlers.RotatingFileHandler(
        log_dir / "openeo_execution.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    execution_handler.setFormatter(log_format)
    execution_handler.setLevel(logging.DEBUG)

    # Add to execution-related loggers
    for logger_name in ["openeo_app.execution", "openeo_app.processes", "openeo_app.registers"]:
        exec_logger = logging.getLogger(logger_name)
        exec_logger.addHandler(execution_handler)

    # Error log file (errors only)
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "openeo_error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
    )
    error_handler.setFormatter(log_format)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)

    return log_dir


# Configure logging
log_dir = configure_logging()
logger = logging.getLogger(__name__)
logger.info(f"Logging configured, log directory: {log_dir}")

# Load settings
settings = AppSettings()

# Get configuration from environment
STAC_API_URL = os.environ.get(
    "STAC_API_URL",
    "https://earth-search.aws.element84.com/v1/"
)
RESULT_STORAGE_PATH = os.environ.get(
    "RESULT_STORAGE_PATH",
    "/tmp/openeo_results"
)

logger.info(f"STAC API URL: {STAC_API_URL}")
logger.info(f"Result storage path: {RESULT_STORAGE_PATH}")

# Log dev mode status
if DEV_MODE:
    logger.warning("=" * 50)
    logger.warning("DEVELOPMENT MODE ENABLED - Basic Auth allowed!")
    logger.warning("Use: Authorization: Basic <base64(user:pass)>")
    logger.warning("=" * 50)

# Initialize executor
logger.info("Initializing ProcessGraphExecutor...")
executor = ProcessGraphExecutor(
    stac_api_url=STAC_API_URL,
)
logger.info(f"Executor initialized with {len(executor.get_available_processes())} processes")

# Initialize storage
logger.info("Initializing ResultStorage...")
storage = ResultStorage(base_path=RESULT_STORAGE_PATH)

# Define supported file formats
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
    FileFormat(
        title="PNG",
        gis_data_types=[GisDataType("raster")],
        parameters={},
    ),
]

# Define API links
links = [
    Link(
        href="https://github.com/eodcgmbh/openeo-fastapi",
        rel="about",
        type="text/html",
        title="OpenEO FastAPI GitHub Repository",
    ),
    Link(
        href="https://openeo.org/documentation/1.0/",
        rel="documentation",
        type="text/html",
        title="OpenEO API Documentation",
    ),
]

# Create custom jobs register with executor
logger.info("Creating ExecutableJobsRegister...")
jobs_register = ExecutableJobsRegister(
    settings=settings,
    links=links,
    executor=executor,
    storage=storage,
)

# Create OpenEO client with custom jobs register
logger.info("Creating OpenEOCore client...")
client = OpenEOCore(
    input_formats=formats,
    output_formats=formats,
    links=links,
    billing=Billing(
        currency="credits",
        default_plan="free",
        plans=[
            Plan(name="free", description="Free tier for testing", paid=False),
            Plan(name="user", description="Standard user plan", paid=True),
        ],
    ),
    jobs=jobs_register,  # Use our custom executable jobs register
)

# Create FastAPI application
logger.info("Creating OpenEO API...")
api = OpenEOApi(client=client, app=FastAPI(
    title="OpenEO FastAPI with Dask",
    description="OpenEO API implementation with Dask-based datacube processing",
    version="1.1.0",
))

# Export app for uvicorn
app = api.app

# Add rate limiting middleware: 30 requests/minute per IP
app.add_middleware(RateLimitMiddleware, max_requests=30, window_seconds=60)
logger.info("Rate limiting enabled: 30 requests/minute per IP")

# Override authentication dependency with our custom dev authenticator
app.dependency_overrides[Authenticator.validate] = DevAuthenticator.validate
logger.info(f"Authentication override applied: DevAuthenticator (DEV_MODE={DEV_MODE})")

logger.info("OpenEO FastAPI application initialized successfully")
logger.info(f"Available processes: {len(executor.get_available_processes())}")


# Health check endpoint for production monitoring
@app.get("/health", tags=["monitoring"])
async def health_check():
    """Health check endpoint for load balancers and monitoring.

    Returns system status and basic metrics.
    """
    from openeo_app.execution.process_registry_singleton import ProcessRegistrySingleton

    return {
        "status": "healthy",
        "version": "1.1.0",
        "processes_count": ProcessRegistrySingleton.get_process_count(),
        "registry_initialized": ProcessRegistrySingleton.is_initialized(),
        "registry_init_time_ms": ProcessRegistrySingleton.get_initialization_time_ms(),
        "running_jobs": jobs_register.get_running_jobs_count(),
        "dev_mode": DEV_MODE,
    }


@app.get("/health/ready", tags=["monitoring"])
async def readiness_check():
    """Readiness check for Kubernetes probes.

    Returns 200 only when the service is ready to accept traffic.
    """
    from openeo_app.execution.process_registry_singleton import ProcessRegistrySingleton

    if not ProcessRegistrySingleton.is_initialized():
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Process registry not initialized")

    return {"status": "ready"}


@app.get("/health/live", tags=["monitoring"])
async def liveness_check():
    """Liveness check for Kubernetes probes.

    Simple check that the service is running.
    """
    return {"status": "alive"}


# OpenEO API compliance endpoints

@app.get("/openeo/1.1.0/credentials/basic", tags=["authentication"])
async def credentials_basic():
    """Get Basic Auth credentials endpoint.

    OpenEO 1.1.0 API requirement for Basic Auth support.
    In dev mode, returns guidance for Basic Auth.
    In prod mode, indicates Basic Auth is not available.
    """
    if DEV_MODE:
        return {
            "access_token": "basic_auth_enabled",
            "message": "Use Basic Auth with any username:password in dev mode",
        }
    else:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=501,
            detail="Basic Auth not available in production. Use OIDC Bearer tokens.",
        )


@app.get("/openeo/1.1.0/udf_runtimes", tags=["udf"])
async def udf_runtimes():
    """List available UDF runtimes.

    Returns an empty dict as UDFs are not currently supported.
    OpenEO spec requires this endpoint to exist.
    """
    return {}


@app.get("/openeo/1.1.0/service_types", tags=["services"])
async def service_types():
    """List available secondary service types.

    Returns an empty dict as secondary services are not currently supported.
    OpenEO spec requires this endpoint to exist.
    """
    return {}
