# ABOUTME: Job management tools for batch processing operations.
# Create, start, monitor status, and retrieve results from OpenEO jobs.

"""
Job management tools for OpenEO AI Assistant.

Provides tools for creating, starting, monitoring, and
retrieving results from batch jobs.
"""

import json
import base64
import os
import httpx
from typing import Any, Dict, Optional


class JobTools:
    """Job management tools."""

    def __init__(self, openeo_url: str, auth_token: Optional[str] = None):
        """
        Initialize job tools.

        Args:
            openeo_url: Base URL of OpenEO API
            auth_token: Optional auth token (Basic or Bearer)
        """
        self.openeo_url = openeo_url.rstrip("/")
        self._client = None

        # Get auth from env or use dev mode basic auth
        if auth_token:
            self.auth_header = auth_token
        elif os.environ.get("OPENEO_AUTH_TOKEN"):
            self.auth_header = f"Bearer {os.environ['OPENEO_AUTH_TOKEN']}"
        else:
            # Default to dev mode basic auth
            dev_creds = base64.b64encode(b"dev:dev").decode("utf-8")
            self.auth_header = f"Basic {dev_creds}"

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialize HTTP client with auth."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                headers={"Authorization": self.auth_header}
            )
        return self._client

    async def _create_job_request(
        self,
        title: str,
        description: str,
        process_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send job creation request to API."""
        response = await self.client.post(
            f"{self.openeo_url}/jobs",
            json={
                "title": title,
                "description": description,
                "process": {"process_graph": process_graph}
            }
        )
        response.raise_for_status()

        # Get job ID from Location header or response
        location = response.headers.get("Location", "")
        job_id = location.split("/")[-1] if location else response.json().get("id")

        return {"id": job_id, "status": "created"}

    async def create(
        self,
        title: str,
        description: str,
        process_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new batch job.

        Args:
            title: Job title
            description: Job description
            process_graph: OpenEO process graph

        Returns:
            Job info dict with id and status

        Raises:
            ValueError: If process_graph is empty
        """
        if not process_graph:
            raise ValueError("process_graph cannot be empty")

        return await self._create_job_request(title, description, process_graph)

    async def _start_job_request(self, job_id: str) -> Dict[str, Any]:
        """Send job start request to API with retry logic."""
        import asyncio

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                # Small delay to ensure job is persisted
                if attempt > 0:
                    await asyncio.sleep(1)

                response = await self.client.post(
                    f"{self.openeo_url}/jobs/{job_id}/results"
                )

                if response.status_code == 404:
                    # Job might not be persisted yet, retry
                    last_error = f"Job {job_id} not found (attempt {attempt + 1}/{max_retries})"
                    continue

                response.raise_for_status()
                return {"id": job_id, "status": "running"}

            except httpx.HTTPStatusError as e:
                last_error = str(e)
                if e.response.status_code != 404:
                    raise

        return {"id": job_id, "status": "error", "error": last_error}

    async def start(self, job_id: str) -> Dict[str, Any]:
        """
        Start a queued batch job.

        Args:
            job_id: Job identifier

        Returns:
            Job info dict with updated status
        """
        return await self._start_job_request(job_id)

    async def _list_jobs_request(self, limit: int = 50) -> Dict[str, Any]:
        """List all batch jobs from the API."""
        response = await self.client.get(f"{self.openeo_url}/jobs")
        response.raise_for_status()
        data = response.json()
        jobs = data.get("jobs", [])
        # Return compact summary
        summary = []
        for j in jobs[:limit]:
            summary.append({
                "id": j.get("id"),
                "title": j.get("title", "Untitled"),
                "status": j.get("status", "unknown"),
                "created": j.get("created", ""),
            })
        return {"count": len(jobs), "jobs": summary}

    async def list_jobs(self, limit: int = 50, status: Optional[str] = None) -> Dict[str, Any]:
        """List batch jobs, optionally filtered by status."""
        result = await self._list_jobs_request(limit=limit)
        if status:
            result["jobs"] = [j for j in result["jobs"] if j["status"] == status]
            result["count"] = len(result["jobs"])
        return result

    async def _get_status_request(self, job_id: str) -> Dict[str, Any]:
        """Get job status from API."""
        response = await self.client.get(f"{self.openeo_url}/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get job status.

        Args:
            job_id: Job identifier

        Returns:
            Job status dict
        """
        return await self._get_status_request(job_id)

    async def _get_results_request(
        self,
        job_id: str,
        output_path: str
    ) -> Dict[str, Any]:
        """Get job results path."""
        import os
        from pathlib import Path

        # Results are stored at /tmp/openeo_results/results/{job_id}/
        results_base = os.environ.get("RESULT_STORAGE_PATH", "/tmp/openeo_results")
        job_dir = Path(results_base) / "results" / job_id

        # Check for result file
        result_path = None
        for ext in [".tif", ".nc", ".json", ".png"]:
            candidate = job_dir / f"result{ext}"
            if candidate.exists():
                result_path = candidate
                break

        # Check metadata for custom filename
        metadata_path = job_dir / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            import json
            with open(metadata_path) as f:
                metadata = json.load(f)
                if not result_path:
                    result_file = metadata.get("result_file")
                    if result_file:
                        candidate = job_dir / result_file
                        if candidate.exists():
                            result_path = candidate

        if result_path and result_path.exists():
            # Get bounds from the GeoTIFF if available
            bounds = None
            if result_path.suffix in [".tif", ".tiff"]:
                try:
                    import rasterio
                    with rasterio.open(result_path) as src:
                        bounds = list(src.bounds)  # [west, south, east, north]
                except Exception:
                    pass

            return {
                "output_path": str(result_path),
                "path": str(result_path),
                "format": metadata.get("format", "GTiff"),
                "size_bytes": result_path.stat().st_size,
                "bounds": bounds,
                "statistics": metadata.get("statistics"),
                "validation": metadata.get("validation")
            }
        else:
            # Result not ready yet - check job status
            try:
                status_response = await self.client.get(f"{self.openeo_url}/jobs/{job_id}")
                status_response.raise_for_status()
                job_status = status_response.json()
                return {
                    "error": f"Job results not ready. Status: {job_status.get('status', 'unknown')}",
                    "status": job_status.get("status"),
                    "job_id": job_id
                }
            except Exception as e:
                return {
                    "error": f"Results not found for job {job_id}",
                    "job_id": job_id
                }

    async def get_results(
        self,
        job_id: str,
        output_path: str = "/tmp"
    ) -> Dict[str, Any]:
        """
        Get job results.

        Args:
            job_id: Job identifier
            output_path: Directory to save results

        Returns:
            Result info dict with path
        """
        return await self._get_results_request(job_id, output_path)


def create_job_tools(config) -> Dict[str, Any]:
    """Create job tools dict for Claude SDK."""
    tools = JobTools(openeo_url=config.openeo_url)

    async def _create_job(args: Dict[str, Any]) -> Dict[str, Any]:
        import asyncio

        # Step 1: Create
        result = await tools.create(
            title=args["title"],
            description=args.get("description", ""),
            process_graph=args["process_graph"]
        )
        job_id = result.get("id")
        if not job_id:
            return {"content": [{"type": "text", "text": json.dumps(result)}]}

        # Step 2: Auto-start
        start_result = await tools.start(job_id)
        if start_result.get("status") == "error":
            return {"content": [{"type": "text", "text": json.dumps(start_result)}]}

        # Step 3: Poll status for up to 120s
        for _ in range(12):
            await asyncio.sleep(10)
            try:
                status = await tools.get_status(job_id)
                job_status = status.get("status", "unknown")
                if job_status in ("finished", "completed", "error", "canceled"):
                    return {"content": [{"type": "text", "text": json.dumps(status)}]}
            except Exception:
                pass

        # Timed out — return last known status
        try:
            status = await tools.get_status(job_id)
        except Exception:
            status = {"id": job_id, "status": "running"}
        return {"content": [{"type": "text", "text": json.dumps(status)}]}

    async def _start_job(args: Dict[str, Any]) -> Dict[str, Any]:
        result = await tools.start(args["job_id"])
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _get_job_status(args: Dict[str, Any]) -> Dict[str, Any]:
        result = await tools.get_status(args["job_id"])
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _get_results(args: Dict[str, Any]) -> Dict[str, Any]:
        result = await tools.get_results(
            args["job_id"],
            args.get("output_path", "/tmp")
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _list_jobs(args: Dict[str, Any]) -> Dict[str, Any]:
        result = await tools.list_jobs(
            limit=args.get("limit", 50),
            status=args.get("status"),
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    return {
        "openeo_list_jobs": _list_jobs,
        "openeo_create_job": _create_job,
        "openeo_start_job": _start_job,
        "openeo_get_job_status": _get_job_status,
        "openeo_get_results": _get_results,
    }
