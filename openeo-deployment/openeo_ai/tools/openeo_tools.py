# ABOUTME: OpenEO data discovery and process graph generation tools.
# List collections, get metadata, and generate graphs from natural language.

"""
OpenEO data discovery and process graph tools.

Provides tools for listing collections, getting collection info,
and generating process graphs.
"""

import json
import time
import threading
import httpx
from typing import Any, Dict, List, Optional

# TTL cache for STAC queries (5 minutes)
_CACHE_TTL_SECONDS = 300


class _TTLCache:
    """Simple thread-safe TTL cache using a dict with timestamps."""

    def __init__(self, ttl: float = _CACHE_TTL_SECONDS):
        self._store: Dict[str, Any] = {}  # key -> (value, expiry_time)
        self._lock = threading.Lock()
        self._ttl = ttl

    def get(self, key: str) -> Any:
        """Get a cached value. Returns None if not found or expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expiry = entry
            if time.monotonic() > expiry:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        """Store a value with TTL."""
        with self._lock:
            self._store[key] = (value, time.monotonic() + self._ttl)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()


class OpenEOTools:
    """OpenEO data discovery tools."""

    def __init__(self, openeo_url: str):
        """
        Initialize OpenEO tools.

        Args:
            openeo_url: Base URL of OpenEO API
        """
        self.openeo_url = openeo_url.rstrip("/")
        self._client = None
        self._cache = _TTLCache(ttl=_CACHE_TTL_SECONDS)

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _fetch_collections(self) -> List[Dict[str, Any]]:
        """Fetch collections from OpenEO API, with TTL caching."""
        cache_key = "collections_list"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self.client.get(f"{self.openeo_url}/collections")
        response.raise_for_status()
        data = response.json()
        result = data.get("collections", [])
        self._cache.set(cache_key, result)
        return result

    async def list_collections(self) -> List[Dict[str, Any]]:
        """
        List available Earth Observation collections.

        Returns:
            List of collection summaries
        """
        collections = await self._fetch_collections()
        return [
            {
                "id": c.get("id"),
                "title": c.get("title", c.get("id")),
                "description": c.get("description", ""),
            }
            for c in collections
        ]

    async def _fetch_collection_info(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Fetch detailed collection info, with TTL caching."""
        cache_key = f"collection_info:{collection_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        response = await self.client.get(
            f"{self.openeo_url}/collections/{collection_id}"
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        result = response.json()
        self._cache.set(cache_key, result)
        return result

    async def get_collection_info(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Collection details including bands, or None if not found
        """
        if not collection_id:
            raise ValueError("collection_id is required")

        info = await self._fetch_collection_info(collection_id)
        if info is None:
            return None

        # Extract band information
        bands = {}
        for asset_name, asset in info.get("item_assets", {}).items():
            if "eo:bands" in asset:
                for band in asset["eo:bands"]:
                    bands[band.get("name", asset_name)] = {
                        "common_name": band.get("common_name"),
                        "description": band.get("description"),
                    }
            else:
                bands[asset_name] = {
                    "description": asset.get("description", "")
                }

        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "description": info.get("description"),
            "bands": bands,
            "extent": info.get("extent"),
        }

    async def generate_process_graph(
        self,
        description: str,
        collection: str,
        spatial_extent: Dict[str, float],
        temporal_extent: List[str],
        output_format: str = "GTiff"
    ) -> Dict[str, Any]:
        """
        Generate a process graph from a description.

        Args:
            description: Natural language description of desired analysis
            collection: Collection ID to use
            spatial_extent: Bounding box dict
            temporal_extent: [start_date, end_date]
            output_format: Output format (GTiff, netCDF, etc.)

        Returns:
            OpenEO process graph dict
        """
        # Base process graph with load_collection
        process_graph = {
            "load": {
                "process_id": "load_collection",
                "arguments": {
                    "id": collection,
                    "spatial_extent": spatial_extent,
                    "temporal_extent": temporal_extent,
                }
            }
        }

        # Check if NDVI is requested
        desc_lower = description.lower()
        if "ndvi" in desc_lower:
            process_graph["load"]["arguments"]["bands"] = ["red", "nir"]

            # Select NIR band (index 1 in [red, nir])
            process_graph["nir"] = {
                "process_id": "array_element",
                "arguments": {
                    "data": {"from_node": "load"},
                    "index": 1,
                    "dimension": "bands"
                }
            }

            # Select RED band (index 0 in [red, nir])
            process_graph["red"] = {
                "process_id": "array_element",
                "arguments": {
                    "data": {"from_node": "load"},
                    "index": 0,
                    "dimension": "bands"
                }
            }

            # Compute NDVI: (NIR - RED) / (NIR + RED)
            process_graph["ndvi"] = {
                "process_id": "normalized_difference",
                "arguments": {
                    "x": {"from_node": "nir"},
                    "y": {"from_node": "red"}
                }
            }

            # Add cloud masking if requested
            if "cloud" in desc_lower and "sentinel" in collection.lower():
                process_graph["load"]["arguments"]["bands"].append("scl")
                # Would add mask process here

            process_graph["save"] = {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "ndvi"},
                    "format": output_format
                },
                "result": True
            }
        else:
            # Generic save
            process_graph["save"] = {
                "process_id": "save_result",
                "arguments": {
                    "data": {"from_node": "load"},
                    "format": output_format
                },
                "result": True
            }

        return process_graph


def create_openeo_tools(config) -> Dict[str, Any]:
    """Create OpenEO tools dict for Claude SDK."""
    from .validation_tools import ValidationTools

    tools = OpenEOTools(openeo_url=config.openeo_url)
    validation_tools = ValidationTools()

    async def _list_collections(args: Dict[str, Any]) -> Dict[str, Any]:
        """List available Earth Observation data collections."""
        collections = await tools.list_collections()
        return {
            "content": [{"type": "text", "text": json.dumps(collections)}]
        }

    async def _get_collection_info(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed information about a specific collection."""
        info = await tools.get_collection_info(args["collection_id"])
        return {
            "content": [{"type": "text", "text": json.dumps(info)}]
        }

    async def _generate_graph(args: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a process graph from natural language description."""
        graph = await tools.generate_process_graph(
            description=args["description"],
            collection=args["collection"],
            spatial_extent=args["spatial_extent"],
            temporal_extent=args["temporal_extent"],
            output_format=args.get("output_format", "GTiff")
        )
        return {
            "content": [{"type": "text", "text": json.dumps(graph)}]
        }

    async def _validate_graph(args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a process graph for errors and provide suggestions."""
        result = await validation_tools.validate(args.get("process_graph", {}))
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _resolve_location(args: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve a location name to a bounding box for spatial queries."""
        from ..utils.geocoding import resolve_location

        location = args.get("location", "")
        buffer_deg = args.get("buffer_degrees", 0.1)

        result = resolve_location(location, buffer_deg)
        return {
            "content": [{"type": "text", "text": json.dumps(result.to_dict())}]
        }

    async def _parse_temporal(args: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a natural language temporal expression to date range."""
        from ..utils.temporal import parse_temporal_expression

        expression = args.get("expression", "")
        result = parse_temporal_expression(expression)
        return {
            "content": [{"type": "text", "text": json.dumps(result.to_dict())}]
        }

    async def _estimate_extent(args: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate data size and validate extent for a query."""
        from ..utils.extent_validator import validate_extent

        spatial_extent = args.get("spatial_extent", {})
        temporal_extent = args.get("temporal_extent")
        collection = args.get("collection", "sentinel-2-l2a")
        bands = args.get("bands")

        result = validate_extent(
            spatial_extent=spatial_extent,
            temporal_extent=temporal_extent,
            collection=collection,
            bands=bands,
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _get_quality_metrics(args: Dict[str, Any]) -> Dict[str, Any]:
        """Get comprehensive data quality metrics including cloud coverage and temporal coverage."""
        from ..utils.quality_metrics import get_quality_metrics

        spatial_extent = args.get("spatial_extent", {})
        temporal_extent = args.get("temporal_extent")
        collection = args.get("collection", "sentinel-2-l2a")
        bands = args.get("bands")

        result = get_quality_metrics(
            collection=collection,
            spatial_extent=spatial_extent,
            temporal_extent=temporal_extent,
            bands=bands,
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    async def _validate_geospatial(args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate geospatial extent including CRS, antimeridian handling, and coordinate bounds."""
        from ..utils.geospatial import validate_extent as validate_geo

        spatial_extent = args.get("spatial_extent", {})
        crs = args.get("crs", "EPSG:4326")

        result = validate_geo(
            spatial_extent=spatial_extent,
            crs=crs,
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}]
        }

    return {
        "openeo_list_collections": _list_collections,
        "openeo_get_collection_info": _get_collection_info,
        "openeo_validate_graph": _validate_graph,
        "openeo_generate_graph": _generate_graph,
        "openeo_resolve_location": _resolve_location,
        "openeo_parse_temporal": _parse_temporal,
        "openeo_estimate_extent": _estimate_extent,
        "openeo_quality_metrics": _get_quality_metrics,
        "openeo_validate_geospatial": _validate_geospatial,
    }


async def list_collections_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone tool function for listing collections."""
    tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")
    collections = await tools.list_collections()
    return {
        "content": [{"type": "text", "text": json.dumps(collections)}]
    }
