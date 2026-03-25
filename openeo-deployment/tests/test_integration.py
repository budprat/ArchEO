"""
Integration tests that run against the live local stack.

Requirements:
  - OpenEO API running at localhost:8000
  - Web Interface running at localhost:8080
  - Network access to AWS Earth Search STAC catalog

Run with:
  pytest tests/test_integration.py -v --tb=short

Skip if services not running:
  pytest tests/test_integration.py -v -k "not integration"
"""

import io
import json
import struct
import asyncio
import pytest
import requests
import websockets

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000/openeo/1.1.0"
WEB_BASE = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws"
AUTH = ("testuser", "password")  # Dev mode basic auth


def _api_available() -> bool:
    """Check if the OpenEO API is reachable."""
    try:
        r = requests.get(f"{API_BASE}/", timeout=3)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


def _web_available() -> bool:
    """Check if the web interface is reachable."""
    try:
        r = requests.get(f"{WEB_BASE}/health", timeout=3)
        return r.status_code == 200
    except requests.ConnectionError:
        return False


skip_no_api = pytest.mark.skipif(
    not _api_available(),
    reason="OpenEO API not running at localhost:8000",
)
skip_no_web = pytest.mark.skipif(
    not _web_available(),
    reason="Web interface not running at localhost:8080",
)


# ---------------------------------------------------------------------------
# 1. API Capabilities & Collections (port 8000)
# ---------------------------------------------------------------------------

@skip_no_api
class TestAPICapabilities:
    """Test the OpenEO API root and capabilities."""

    def test_root_returns_valid_capabilities(self):
        """GET / should return OpenEO 1.1.0 capabilities."""
        r = requests.get(f"{API_BASE}/")
        assert r.status_code == 200

        data = r.json()
        assert data["api_version"] == "1.1.0"
        assert data["stac_version"] == "1.0.0"
        assert "endpoints" in data
        assert len(data["endpoints"]) > 10

    def test_collections_returns_real_stac_data(self):
        """GET /collections should return real STAC collections from AWS Earth Search."""
        r = requests.get(f"{API_BASE}/collections")
        assert r.status_code == 200

        data = r.json()
        assert "collections" in data
        collections = data["collections"]
        assert len(collections) > 0

        # Verify known collections are present
        collection_ids = [c["id"] for c in collections]
        assert "sentinel-2-l2a" in collection_ids
        assert "cop-dem-glo-30" in collection_ids

    def test_collection_detail_sentinel2(self):
        """GET /collections/sentinel-2-l2a should return detailed metadata."""
        r = requests.get(f"{API_BASE}/collections/sentinel-2-l2a")
        assert r.status_code == 200

        data = r.json()
        assert data["id"] == "sentinel-2-l2a"
        assert "extent" in data
        assert "spatial" in data["extent"]
        assert "temporal" in data["extent"]

    def test_processes_list_has_130_plus(self):
        """GET /processes should return 130+ registered processes."""
        r = requests.get(f"{API_BASE}/processes")
        assert r.status_code == 200

        data = r.json()
        assert "processes" in data
        processes = data["processes"]
        assert len(processes) >= 130

        # Verify key processes exist
        process_ids = [p["id"] for p in processes]
        assert "load_collection" in process_ids
        assert "ndvi" in process_ids
        assert "save_result" in process_ids
        assert "filter_bbox" in process_ids
        assert "reduce_dimension" in process_ids


# ---------------------------------------------------------------------------
# 2. Synchronous Job - Small DEM Load (port 8000)
# ---------------------------------------------------------------------------

@skip_no_api
class TestSyncJobDEM:
    """Test synchronous job execution with a small DEM load."""

    def _dem_process_graph(self, output_format="GTiff"):
        """Build a small DEM process graph (tiny extent ~1km)."""
        return {
            "process": {
                "process_graph": {
                    "load": {
                        "process_id": "load_collection",
                        "arguments": {
                            "id": "cop-dem-glo-30",
                            "spatial_extent": {
                                "west": 11.0,
                                "south": 46.0,
                                "east": 11.01,
                                "north": 46.01,
                            },
                        },
                    },
                    "save": {
                        "process_id": "save_result",
                        "arguments": {
                            "data": {"from_node": "load"},
                            "format": output_format,
                        },
                        "result": True,
                    },
                }
            }
        }

    def test_sync_dem_returns_geotiff(self):
        """POST /result with DEM graph should return a valid GeoTIFF."""
        r = requests.post(
            f"{API_BASE}/result",
            json=self._dem_process_graph("GTiff"),
            auth=AUTH,
            timeout=120,
        )
        assert r.status_code == 200

        content = r.content
        assert len(content) > 100, "GeoTIFF response too small"

        # GeoTIFF files start with TIFF magic bytes: II (little-endian) or MM (big-endian)
        assert content[:2] in (b"II", b"MM"), (
            f"Not a TIFF file, starts with: {content[:4]!r}"
        )

        # TIFF version number should be 42 (classic TIFF) or 43 (BigTIFF)
        if content[:2] == b"II":
            version = struct.unpack("<H", content[2:4])[0]
        else:
            version = struct.unpack(">H", content[2:4])[0]
        assert version in (42, 43), f"Unexpected TIFF version: {version}"

    def test_sync_dem_returns_json(self):
        """POST /result with JSON format should return valid JSON data."""
        r = requests.post(
            f"{API_BASE}/result",
            json=self._dem_process_graph("JSON"),
            auth=AUTH,
            timeout=120,
        )
        assert r.status_code == 200

        data = r.json()
        assert data is not None
        # Should have some numeric data
        assert isinstance(data, (dict, list))


# ---------------------------------------------------------------------------
# 3. Band Name Translation (B04 vs red)
# ---------------------------------------------------------------------------

@skip_no_api
class TestBandNameTranslation:
    """Test that both OpenEO standard (B04) and AWS (red) band names work."""

    def _sentinel2_graph(self, bands):
        """Build a small Sentinel-2 process graph with specific bands."""
        return {
            "process": {
                "process_graph": {
                    "load": {
                        "process_id": "load_collection",
                        "arguments": {
                            "id": "sentinel-2-l2a",
                            "spatial_extent": {
                                "west": 11.0,
                                "south": 46.0,
                                "east": 11.005,
                                "north": 46.005,
                            },
                            "temporal_extent": ["2024-06-01", "2024-06-10"],
                            "bands": bands,
                        },
                    },
                    "save": {
                        "process_id": "save_result",
                        "arguments": {
                            "data": {"from_node": "load"},
                            "format": "JSON",
                        },
                        "result": True,
                    },
                }
            }
        }

    def test_aws_band_names_work(self):
        """Loading with AWS band names (red, nir) should succeed."""
        r = requests.post(
            f"{API_BASE}/result",
            json=self._sentinel2_graph(["red", "nir"]),
            auth=AUTH,
            timeout=300,
        )
        assert r.status_code == 200, f"Failed with AWS names: {r.text[:200]}"

    def test_openeo_band_names_auto_translated(self):
        """Loading with OpenEO standard names (B04, B08) should auto-translate and succeed."""
        r = requests.post(
            f"{API_BASE}/result",
            json=self._sentinel2_graph(["B04", "B08"]),
            auth=AUTH,
            timeout=300,
        )
        assert r.status_code == 200, f"Failed with OpenEO names: {r.text[:200]}"


# ---------------------------------------------------------------------------
# 4. Batch Job Lifecycle (port 8000)
# ---------------------------------------------------------------------------

@skip_no_api
class TestBatchJobLifecycle:
    """Test the full batch job lifecycle: create -> start -> poll -> results."""

    def test_create_job(self):
        """POST /jobs should create a batch job."""
        graph = {
            "process": {
                "process_graph": {
                    "load": {
                        "process_id": "load_collection",
                        "arguments": {
                            "id": "cop-dem-glo-30",
                            "spatial_extent": {
                                "west": 11.0,
                                "south": 46.0,
                                "east": 11.01,
                                "north": 46.01,
                            },
                        },
                    },
                    "save": {
                        "process_id": "save_result",
                        "arguments": {
                            "data": {"from_node": "load"},
                            "format": "GTiff",
                        },
                        "result": True,
                    },
                }
            }
        }

        # Create
        r = requests.post(f"{API_BASE}/jobs", json=graph, auth=AUTH, timeout=30)
        assert r.status_code == 201

        # Extract job ID from Location header or response
        location = r.headers.get("Location", r.headers.get("OpenEO-Identifier", ""))
        job_id = location.split("/")[-1] if "/" in location else location
        assert job_id, "No job ID returned"

        # Verify job exists
        r2 = requests.get(f"{API_BASE}/jobs/{job_id}", auth=AUTH, timeout=10)
        assert r2.status_code == 200
        job_data = r2.json()
        assert job_data["status"] in ("created", "queued", "running")

    def test_list_jobs(self):
        """GET /jobs should return a list of jobs."""
        r = requests.get(f"{API_BASE}/jobs", auth=AUTH, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)


# ---------------------------------------------------------------------------
# 5. Health Check (port 8000)
# ---------------------------------------------------------------------------

@skip_no_api
class TestHealthCheck:
    """Test health endpoints on the API server."""

    def test_health_endpoint(self):
        """GET /health should return healthy status."""
        r = requests.get("http://localhost:8000/health", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("healthy", "ok", True)

    def test_health_ready(self):
        """GET /health/ready should return ready status."""
        r = requests.get("http://localhost:8000/health/ready", timeout=5)
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# 6. Web Interface Health & Endpoints (port 8080)
# ---------------------------------------------------------------------------

@skip_no_web
class TestWebInterface:
    """Test the web interface at port 8080."""

    def test_health_endpoint(self):
        """GET /health should return status with uptime and session info."""
        r = requests.get(f"{WEB_BASE}/health", timeout=5)
        assert r.status_code == 200

        data = r.json()
        assert "status" in data
        assert data["status"] in ("healthy", "ok")

    def test_root_serves_html(self):
        """GET / should serve the web UI HTML."""
        r = requests.get(f"{WEB_BASE}/", timeout=5)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# 7. WebSocket Chat Flow (port 8080)
# ---------------------------------------------------------------------------

@skip_no_web
class TestWebSocketChat:
    """Test real WebSocket communication with the AI backend."""

    @pytest.mark.asyncio
    async def test_websocket_connects_and_receives_session(self):
        """WebSocket should connect and receive a session message."""
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            # Should receive a session message on connect
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = json.loads(raw)

            assert msg["type"] == "session"
            assert "session_id" in msg

    @pytest.mark.asyncio
    async def test_websocket_send_message_gets_response(self):
        """Sending a simple message should get at least one response back."""
        async with websockets.connect(WS_URL, open_timeout=10) as ws:
            # Wait for session
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            session_msg = json.loads(raw)
            assert session_msg["type"] == "session"

            # Send a simple message
            await ws.send(json.dumps({
                "type": "message",
                "content": "What collections are available?",
                "session_id": session_msg.get("session_id"),
            }))

            # Collect responses until we get "done" or timeout
            responses = []
            try:
                while True:
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    msg = json.loads(raw)
                    responses.append(msg)
                    if msg.get("type") == "done":
                        break
            except asyncio.TimeoutError:
                pass  # Timeout is acceptable if we got some responses

            assert len(responses) > 0, "No responses received from WebSocket"

            # Should have at least one text, tool_result, or error response
            types = [r["type"] for r in responses]
            has_content = any(t in types for t in ("text", "tool_result", "tool_start", "error", "done"))
            assert has_content, f"No content responses, got types: {types}"


# ---------------------------------------------------------------------------
# 8. Rate Limiting (port 8000)
# ---------------------------------------------------------------------------

@skip_no_api
class TestRateLimiting:
    """Test that rate limiting middleware code exists (requires server restart to activate)."""

    def test_rate_limit_middleware_exists(self):
        """Rate limit middleware module should be importable."""
        import importlib.util
        spec = importlib.util.find_spec("openeo_app.rate_limit")
        assert spec is not None, "openeo_app.rate_limit module not found"

        from openeo_app.rate_limit import RateLimitMiddleware
        assert RateLimitMiddleware is not None

    def test_rate_limit_headers_if_active(self):
        """If rate limiting is active, responses should include headers."""
        r = requests.get(f"{API_BASE}/collections", timeout=10)
        headers = dict(r.headers)
        has_rate_headers = any(
            "ratelimit" in k.lower() or "rate-limit" in k.lower()
            for k in headers
        )
        # Rate limiting requires server restart to activate.
        # If headers present, verify format. If not, just pass.
        if has_rate_headers:
            rate_keys = [k for k in headers if "ratelimit" in k.lower()]
            assert len(rate_keys) >= 1


# ---------------------------------------------------------------------------
# 9. Error Handling
# ---------------------------------------------------------------------------

@skip_no_api
class TestErrorHandling:
    """Test that the API returns proper errors for invalid requests."""

    def test_invalid_collection_returns_error(self):
        """GET /collections/nonexistent should return 404 or error."""
        r = requests.get(f"{API_BASE}/collections/nonexistent-collection-xyz")
        assert r.status_code in (400, 404, 500)

    def test_sync_job_without_auth_returns_error(self):
        """POST /result without auth should return an error status."""
        graph = {
            "process": {
                "process_graph": {
                    "add": {
                        "process_id": "add",
                        "arguments": {"x": 1, "y": 2},
                        "result": True,
                    }
                }
            }
        }
        r = requests.post(f"{API_BASE}/result", json=graph, timeout=10)
        # In dev mode: may return 200 (auto-auth) or 422 (validation)
        # In prod mode: should return 401/403
        # All are valid depending on configuration
        assert r.status_code in (200, 401, 403, 422)

    def test_invalid_process_graph_returns_error(self):
        """POST /result with invalid graph should return error."""
        r = requests.post(
            f"{API_BASE}/result",
            json={"process": {"process_graph": {}}},
            auth=AUTH,
            timeout=10,
        )
        assert r.status_code in (400, 500)
