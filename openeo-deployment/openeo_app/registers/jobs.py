"""Extended JobsRegister with execution capabilities.

Includes:
- Thread-safe job management with locks
- Automatic cleanup of completed job threads
- Timeout protection for long-running jobs
"""

import io
import json
import logging
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, Response
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from openeo_fastapi.api.models import JobsRequest
from openeo_fastapi.api.types import Error, Status
from openeo_fastapi.client.auth import Authenticator, User
from openeo_fastapi.client.jobs import Job, JobsRegister
from openeo_fastapi.client.psql.engine import get, modify

from openeo_app.execution.executor import ProcessGraphExecutor
from openeo_app.storage.results import ResultStorage

logger = logging.getLogger(__name__)


class _JobCancelledError(Exception):
    """Internal exception raised when a job is cancelled via its cancellation event."""
    pass


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
        """
        Initialize the ExecutableJobsRegister.

        Args:
            settings: Application settings
            links: API links
            executor: ProcessGraphExecutor instance for running process graphs
            storage: ResultStorage instance for saving outputs
        """
        super().__init__(settings, links)
        self.executor = executor
        self.storage = storage or ResultStorage()

        # Thread-safe job tracking
        self._running_jobs = {}  # Track running async jobs
        self._cancel_events = {}  # Cancellation tokens per job
        self._jobs_lock = threading.Lock()  # Lock for _running_jobs and _cancel_events access

        # Job execution settings
        self._job_timeout_seconds = int(
            os.environ.get("JOB_TIMEOUT_SECONDS", "3600")  # 1 hour default
        )

        # Start background cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_completed_jobs_loop,
            daemon=True,
        )
        self._cleanup_thread.start()

        logger.info(f"ExecutableJobsRegister initialized (timeout={self._job_timeout_seconds}s)")

    def process_sync_job(
        self,
        body: JobsRequest = JobsRequest(),
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Execute a synchronous job and return results immediately.

        POST /openeo/1.1.0/result

        Args:
            body: The job request containing the process graph
            user: The authenticated user

        Returns:
            Response with computation results
        """
        logger.info(f"Processing sync job for user {user.user_id}")

        try:
            # Extract process graph
            if body.process is None or body.process.process_graph is None:
                raise HTTPException(
                    status_code=400,
                    detail=Error(
                        code="ProcessGraphMissing",
                        message="No process graph provided.",
                    ),
                )

            process_graph = body.process.process_graph

            logger.debug(f"Executing process graph: {list(process_graph.keys())}")

            # Execute the process graph
            result = self.executor.execute(
                process_graph=process_graph,
                parameters={},
            )

            # Determine output format from save_result node
            output_format = self._get_output_format(process_graph)
            logger.info(f"Output format: {output_format}")

            # Return appropriate response
            return self._create_response(result, output_format)

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Sync job execution failed: {e}", exc_info=True)
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

        Args:
            job_id: The job identifier
            user: The authenticated user

        Returns:
            Response with status 202 (Accepted)
        """
        logger.info(f"Starting batch job {job_id} for user {user.user_id}")

        # Get job from database
        job = get(get_model=Job, primary_key=job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="JobNotFound",
                    message=f"Job {job_id} not found.",
                ),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(
                    code="Forbidden",
                    message="Not authorized to access this job.",
                ),
            )

        # Check if already running or queued
        if job.status in [Status.running, Status.queued]:
            raise HTTPException(
                status_code=400,
                detail=Error(
                    code="JobAlreadyStarted",
                    message=f"Job is already {job.status}.",
                ),
            )

        # Update status to queued
        job.status = Status.queued
        modify(modify_object=job)

        # Log job start
        self.storage.save_log(
            job_id=job_id,
            level="info",
            message="Job queued for execution",
        )

        # Create cancellation token for this job
        cancel_event = threading.Event()

        # Start background execution in a thread (with lock)
        # IMPORTANT: Pass job_id, not job object - SQLAlchemy session issues
        thread = threading.Thread(
            target=self._execute_job_background,
            args=(job.job_id, cancel_event),
            daemon=True,
            name=f"job-{job.job_id}",
        )
        thread.start()

        with self._jobs_lock:
            self._running_jobs[str(job.job_id)] = {
                "thread": thread,
                "started_at": datetime.now(),
            }
            self._cancel_events[str(job.job_id)] = cancel_event

        return Response(
            status_code=202,
            headers={
                "OpenEO-Identifier": str(job_id),
            },
        )

    def _execute_job_background(self, job_id: uuid.UUID, cancel_event: threading.Event = None):
        """
        Execute job in background with enhanced status tracking and timeout.

        Tracks:
        - started_at: When job execution began
        - finished_at: When job completed (success or error)
        - error_message: User-friendly error description on failure

        Features:
        - Timeout enforcement via ThreadPoolExecutor
        - Cancellation support via threading.Event
        - Dask garbage collection after execution

        Args:
            job_id: The job ID to execute (fetched fresh from DB)
            cancel_event: Threading event that signals cancellation when set
        """
        import sys
        import traceback
        from ..core.exceptions import classify_error
        import time
        import gc

        if cancel_event is None:
            cancel_event = threading.Event()

        start_time = time.time()
        logger.info(f"[THREAD] Starting async execution of job {job_id}")
        print(f"[THREAD] Starting job {job_id}", file=sys.stderr, flush=True)

        # Fetch job fresh from database (avoid SQLAlchemy detached session issues)
        job = get(get_model=Job, primary_key=job_id)
        if job is None:
            logger.error(f"Job {job_id} not found in database")
            return

        try:
            # Check cancellation before starting
            if cancel_event.is_set():
                raise _JobCancelledError("Job cancelled before execution started")

            # Update status to running with start timestamp
            job.status = Status.running
            modify(modify_object=job)

            self.storage.save_log(
                job_id=job_id,
                level="info",
                message="Job execution started",
                data={
                    "started_at": datetime.now().isoformat(),
                    "timeout_seconds": self._job_timeout_seconds,
                },
            )

            # Execute process graph with timeout enforcement
            process_graph = job.process.process_graph

            # Use ThreadPoolExecutor to enforce timeout
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    self.executor.execute,
                    process_graph=process_graph,
                    parameters={},
                )
                # Poll for completion, checking cancellation periodically
                poll_interval = 1.0  # Check cancellation every second
                elapsed = 0.0
                while True:
                    if cancel_event.is_set():
                        future.cancel()
                        raise _JobCancelledError("Job cancelled by user")
                    try:
                        result = future.result(timeout=poll_interval)
                        break  # Got result
                    except FuturesTimeoutError:
                        elapsed += poll_interval
                        if elapsed >= self._job_timeout_seconds:
                            future.cancel()
                            raise TimeoutError(
                                f"Job execution exceeded timeout of {self._job_timeout_seconds} seconds"
                            )

            # Check cancellation after execution
            if cancel_event.is_set():
                raise _JobCancelledError("Job cancelled after execution")

            # Determine output format
            output_format = self._get_output_format(process_graph)

            # Save results
            result_path = self.storage.save_result(
                job_id=job_id,
                data=result,
                format=output_format,
            )

            # Calculate duration
            duration_seconds = time.time() - start_time

            self.storage.save_log(
                job_id=job_id,
                level="info",
                message=f"Results saved to {result_path}",
                data={"result_path": str(result_path)},
            )

            # Update job status to finished with completion timestamp
            job.status = Status.finished
            modify(modify_object=job)

            self.storage.save_log(
                job_id=job_id,
                level="info",
                message="Job completed successfully",
                data={
                    "finished_at": datetime.now().isoformat(),
                    "duration_seconds": round(duration_seconds, 2),
                },
            )

            logger.info(f"Job {job_id} completed successfully in {duration_seconds:.1f}s")

            # Clean up result from memory
            del result
            gc.collect()

        except _JobCancelledError as e:
            duration_seconds = time.time() - start_time
            logger.info(f"Job {job_id} cancelled after {duration_seconds:.1f}s")

            job.status = Status.canceled
            modify(modify_object=job)

            self.storage.save_log(
                job_id=job_id,
                level="info",
                message=str(e),
                data={
                    "finished_at": datetime.now().isoformat(),
                    "duration_seconds": round(duration_seconds, 2),
                    "error_type": "cancelled",
                },
            )

            self.storage.delete_result(job_id)
            gc.collect()

        except TimeoutError as e:
            duration_seconds = time.time() - start_time
            logger.error(f"Job {job_id} timed out after {duration_seconds:.1f}s")

            job.status = Status.error
            modify(modify_object=job)

            self.storage.save_log(
                job_id=job_id,
                level="error",
                message=f"Job timed out after {self._job_timeout_seconds} seconds",
                data={
                    "finished_at": datetime.now().isoformat(),
                    "duration_seconds": round(duration_seconds, 2),
                    "error_type": "timeout",
                },
            )

            gc.collect()

        except Exception as e:
            duration_seconds = time.time() - start_time
            logger.error(f"Job {job_id} failed after {duration_seconds:.1f}s: {e}", exc_info=True)

            # Classify error for user-friendly message
            error_info = classify_error(e)

            # Update status to error with completion timestamp
            job.status = Status.error
            modify(modify_object=job)

            # Log error with classification
            self.storage.save_log(
                job_id=job_id,
                level="error",
                message=f"Job failed: {error_info['user_message']}",
                data={
                    "finished_at": datetime.now().isoformat(),
                    "duration_seconds": round(duration_seconds, 2),
                    "error_type": error_info["error_type"],
                    "technical_message": error_info["technical_message"],
                    "details": error_info["details"],
                },
            )

            gc.collect()

        finally:
            # Clean up cancellation event
            with self._jobs_lock:
                self._cancel_events.pop(str(job_id), None)

    def _cleanup_completed_jobs_loop(self):
        """
        Background loop to clean up completed job threads.

        Runs every 60 seconds to remove finished threads from _running_jobs,
        preventing memory leaks from accumulated thread references.
        """
        cleanup_interval = 60  # seconds
        while True:
            time.sleep(cleanup_interval)
            self._cleanup_completed_jobs()

    def _cleanup_completed_jobs(self):
        """Remove completed threads from _running_jobs and stale cancel events."""
        with self._jobs_lock:
            completed = []
            for job_id, job_info in self._running_jobs.items():
                thread = job_info["thread"]
                if not thread.is_alive():
                    completed.append(job_id)

            for job_id in completed:
                del self._running_jobs[job_id]
                self._cancel_events.pop(job_id, None)

            if completed:
                logger.debug(f"Cleaned up {len(completed)} completed job threads")

    def get_running_jobs_count(self) -> int:
        """Get count of currently running jobs (for monitoring)."""
        with self._jobs_lock:
            return sum(
                1 for job_info in self._running_jobs.values()
                if job_info["thread"].is_alive()
            )

    def get_results(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Get results of a completed job.

        GET /openeo/1.1.0/jobs/{job_id}/results

        Args:
            job_id: The job identifier
            user: The authenticated user

        Returns:
            Response with job results
        """
        logger.info(f"Getting results for job {job_id}")

        # Get job
        job = get(get_model=Job, primary_key=job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="JobNotFound",
                    message=f"Job {job_id} not found.",
                ),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(
                    code="Forbidden",
                    message="Not authorized to access this job.",
                ),
            )

        # Check status
        if job.status != Status.finished:
            if job.status == Status.error:
                raise HTTPException(
                    status_code=424,
                    detail=Error(
                        code="JobFailed",
                        message="Job execution failed. Check logs for details.",
                    ),
                )
            elif job.status in [Status.running, Status.queued]:
                raise HTTPException(
                    status_code=400,
                    detail=Error(
                        code="JobNotFinished",
                        message=f"Job is still {job.status}.",
                    ),
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=Error(
                        code="JobNotStarted",
                        message="Job has not been started.",
                    ),
                )

        # Get result file
        result_path = self.storage.get_result(job_id)

        if result_path is None or not result_path.exists():
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="ResultNotFound",
                    message="Result file not found.",
                ),
            )

        return FileResponse(
            path=str(result_path),
            filename=result_path.name,
            media_type=self._get_media_type(result_path),
        )

    def logs(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ):
        """
        Get job execution logs.

        GET /openeo/1.1.0/jobs/{job_id}/logs

        Args:
            job_id: The job identifier
            user: The authenticated user

        Returns:
            Dict with logs and links
        """
        logger.info(f"Getting logs for job {job_id}")

        # Get job
        job = get(get_model=Job, primary_key=job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="JobNotFound",
                    message=f"Job {job_id} not found.",
                ),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(
                    code="Forbidden",
                    message="Not authorized to access this job.",
                ),
            )

        # Get logs from storage
        log_entries = self.storage.get_logs(job_id)

        # Format logs for OpenEO response
        logs = []
        for entry in log_entries:
            logs.append({
                "id": str(uuid.uuid4()),
                "code": entry.get("level", "info").upper(),
                "level": entry.get("level", "info"),
                "message": entry.get("message", ""),
                "time": entry.get("timestamp"),
                "data": entry.get("data"),
            })

        return {"logs": logs, "links": []}

    def cancel_job(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Cancel a running job.

        DELETE /openeo/1.1.0/jobs/{job_id}/results

        Args:
            job_id: The job identifier
            user: The authenticated user

        Returns:
            Response with status 204 (No Content)
        """
        logger.info(f"Cancelling job {job_id}")

        # Get job
        job = get(get_model=Job, primary_key=job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="JobNotFound",
                    message=f"Job {job_id} not found.",
                ),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(
                    code="Forbidden",
                    message="Not authorized to access this job.",
                ),
            )

        # Check if running
        if job.status not in [Status.running, Status.queued]:
            raise HTTPException(
                status_code=400,
                detail=Error(
                    code="JobNotRunning",
                    message=f"Job is not running (status: {job.status}).",
                ),
            )

        # Signal cancellation to the running thread
        with self._jobs_lock:
            cancel_event = self._cancel_events.get(str(job_id))

        if cancel_event is not None:
            cancel_event.set()
            logger.info(f"Cancellation signal sent to job {job_id}")
        else:
            # No cancel event means thread already finished or never started;
            # just update status directly
            job.status = Status.canceled
            modify(modify_object=job)

            # Clean up any partial results
            self.storage.delete_result(job_id)

        self.storage.save_log(
            job_id=job_id,
            level="info",
            message="Job cancelled by user",
        )

        logger.info(f"Cancel requested for job {job_id}")

        return Response(status_code=204)

    def delete_job(
        self,
        job_id: uuid.UUID,
        user: User = Depends(Authenticator.validate),
    ) -> Response:
        """
        Delete a job and its results.

        DELETE /openeo/1.1.0/jobs/{job_id}

        Args:
            job_id: The job identifier
            user: The authenticated user

        Returns:
            Response with status 204 (No Content)
        """
        logger.info(f"Deleting job {job_id}")

        # Get job
        job = get(get_model=Job, primary_key=job_id)

        if job is None:
            raise HTTPException(
                status_code=404,
                detail=Error(
                    code="JobNotFound",
                    message=f"Job {job_id} not found.",
                ),
            )

        # Verify ownership
        if str(job.user_id) != str(user.user_id):
            raise HTTPException(
                status_code=403,
                detail=Error(
                    code="Forbidden",
                    message="Not authorized to access this job.",
                ),
            )

        # Cannot delete running jobs
        if job.status in [Status.running, Status.queued]:
            raise HTTPException(
                status_code=400,
                detail=Error(
                    code="JobLocked",
                    message="Cannot delete a running job. Cancel it first.",
                ),
            )

        # Delete results and logs
        self.storage.delete_result(job_id)
        self.storage.clear_logs(job_id)

        # Note: Actual job deletion from DB would require implementing delete in engine
        # For now, mark as canceled/deleted
        job.status = Status.canceled
        modify(modify_object=job)

        return Response(status_code=204)

    # Helper methods

    def _get_output_format(self, process_graph: dict) -> str:
        """
        Extract output format from save_result node.

        Args:
            process_graph: The process graph dict

        Returns:
            Output format string (default: GTiff)
        """
        for node_id, node in process_graph.items():
            if isinstance(node, dict):
                if node.get("process_id") == "save_result":
                    args = node.get("arguments", {})
                    return args.get("format", "GTiff")

        return "GTiff"

    def _create_response(self, data, output_format: str) -> Response:
        """
        Create appropriate HTTP response for data.

        Args:
            data: The computation result
            output_format: The output format

        Returns:
            FastAPI Response object
        """
        if output_format in ["GTiff", "GeoTiff"]:
            return self._return_geotiff(data)
        elif output_format == "netCDF":
            return self._return_netcdf(data)
        elif output_format == "JSON":
            return self._return_json(data)
        elif output_format == "PNG":
            return self._return_png(data)
        else:
            # Default to GeoTIFF
            return self._return_geotiff(data)

    def _return_geotiff(self, data) -> Response:
        """Return data as GeoTIFF.

        Handles multi-dimensional arrays by:
        1. Selecting first time slice if time dimension exists
        2. Squeezing singleton dimensions
        3. Ensuring proper 2D or 3D (bands, y, x) shape for rasterio
        """
        import rioxarray  # noqa: F401
        import numpy as np

        if hasattr(data, "rio"):
            buffer = io.BytesIO()

            # Handle time dimension
            if "time" in data.dims or "t" in data.dims:
                time_dim = "time" if "time" in data.dims else "t"
                if data[time_dim].size > 1:
                    logger.warning("Multiple time steps found, returning first time slice")
                data = data.isel({time_dim: 0})

            # Handle 4D+ arrays by squeezing singleton dimensions
            if data.ndim > 3:
                data = data.squeeze()

            # If still >3D, select first element of extra dimensions
            while data.ndim > 3:
                for dim in data.dims:
                    if dim not in ("x", "y", "latitude", "longitude", "bands"):
                        logger.warning(f"Reducing dimension '{dim}' to first element")
                        data = data.isel({dim: 0})
                        break
                else:
                    first_dim = data.dims[0]
                    data = data.isel({first_dim: 0})

            # Ensure CRS
            if data.rio.crs is None:
                data = data.rio.write_crs("EPSG:4326")

            # Validate data
            if data.size == 0:
                raise HTTPException(
                    status_code=500,
                    detail=Error(
                        code="EmptyResult",
                        message="Result data is empty.",
                    ),
                )

            data.rio.to_raster(buffer, driver="GTiff")
            buffer.seek(0)

            return StreamingResponse(
                buffer,
                media_type="image/tiff",
                headers={
                    "Content-Disposition": "attachment; filename=result.tif"
                },
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=Error(
                    code="FormatError",
                    message="Cannot convert result to GeoTIFF.",
                ),
            )

    def _return_netcdf(self, data) -> Response:
        """Return data as NetCDF."""
        import xarray as xr

        buffer = io.BytesIO()

        if isinstance(data, xr.DataArray):
            data = data.to_dataset(name="data")

        data.to_netcdf(buffer)
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="application/x-netcdf",
            headers={
                "Content-Disposition": "attachment; filename=result.nc"
            },
        )

    def _return_json(self, data) -> Response:
        """Return data as JSON."""
        import xarray as xr

        if isinstance(data, (xr.DataArray, xr.Dataset)):
            result = data.to_dict()
        elif hasattr(data, "tolist"):
            result = data.tolist()
        elif isinstance(data, (dict, list)):
            result = data
        else:
            result = str(data)

        return Response(
            content=json.dumps(result, default=str),
            media_type="application/json",
        )

    def _return_png(self, data) -> Response:
        """Return data as PNG image."""
        import numpy as np
        from PIL import Image

        buffer = io.BytesIO()

        # Get numpy array
        if hasattr(data, "values"):
            arr = data.values
        else:
            arr = np.array(data)

        # Handle time dimension
        if arr.ndim > 3:
            arr = arr[0]  # Take first time slice

        # Normalize to 0-255
        arr_min, arr_max = np.nanmin(arr), np.nanmax(arr)
        if arr_max > arr_min:
            arr = ((arr - arr_min) / (arr_max - arr_min) * 255).astype(np.uint8)
        else:
            arr = np.zeros_like(arr, dtype=np.uint8)

        # Create image
        if arr.ndim == 2:
            img = Image.fromarray(arr, mode="L")
        elif arr.ndim == 3:
            if arr.shape[0] in [1, 3, 4]:
                arr = np.moveaxis(arr, 0, -1)
            if arr.shape[-1] == 1:
                img = Image.fromarray(arr[:, :, 0], mode="L")
            elif arr.shape[-1] == 3:
                img = Image.fromarray(arr, mode="RGB")
            else:
                img = Image.fromarray(arr[:, :, 0], mode="L")
        else:
            raise HTTPException(
                status_code=500,
                detail=Error(
                    code="FormatError",
                    message=f"Cannot convert {arr.ndim}D array to PNG.",
                ),
            )

        img.save(buffer, format="PNG")
        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type="image/png",
            headers={
                "Content-Disposition": "attachment; filename=result.png"
            },
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
