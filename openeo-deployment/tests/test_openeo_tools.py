"""Tests for openeo_ai/tools/openeo_tools.py.

Verifies collection listing, collection info retrieval, and process graph
generation -- all without network access (HTTP calls are mocked).
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import httpx

from openeo_ai.tools.openeo_tools import OpenEOTools


@pytest.fixture
def tools():
    """Create an OpenEOTools instance with a mock HTTP client."""
    t = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")
    return t


# ---------------------------------------------------------------------------
# list_collections
# ---------------------------------------------------------------------------


class TestListCollections:
    """Tests for the list_collections method."""

    @pytest.mark.asyncio
    async def test_list_collections_success(
        self, tools, mock_stac_collections_response
    ):
        """Verify list_collections returns formatted collection summaries."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_stac_collections_response
        mock_response.raise_for_status = MagicMock()

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        result = await tools.list_collections()

        assert len(result) == 3
        assert result[0]["id"] == "sentinel-2-l2a"
        assert result[0]["title"] == "Sentinel-2 Level-2A"
        assert "description" in result[0]

    @pytest.mark.asyncio
    async def test_list_collections_empty(self, tools):
        """Verify empty list when API returns no collections."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"collections": []}
        mock_response.raise_for_status = MagicMock()

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        result = await tools.list_collections()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_collections_http_error(self, tools):
        """Verify exception propagation on HTTP error."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        with pytest.raises(httpx.HTTPStatusError):
            await tools.list_collections()


# ---------------------------------------------------------------------------
# get_collection_info
# ---------------------------------------------------------------------------


class TestGetCollectionInfo:
    """Tests for the get_collection_info method."""

    @pytest.mark.asyncio
    async def test_get_collection_info_success(
        self, tools, mock_stac_collection_detail
    ):
        """Verify detailed collection info is correctly parsed."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_stac_collection_detail
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        result = await tools.get_collection_info("sentinel-2-l2a")

        assert result is not None
        assert result["id"] == "sentinel-2-l2a"
        assert "bands" in result
        assert "red" in result["bands"]
        assert result["bands"]["red"]["common_name"] == "red"

    @pytest.mark.asyncio
    async def test_get_collection_info_not_found(self, tools):
        """Verify None is returned for non-existent collection."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        result = await tools.get_collection_info("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_collection_info_empty_id_raises(self, tools):
        """Empty collection_id should raise ValueError."""
        with pytest.raises(ValueError, match="collection_id is required"):
            await tools.get_collection_info("")

    @pytest.mark.asyncio
    async def test_get_collection_info_extracts_extent(
        self, tools, mock_stac_collection_detail
    ):
        """Verify that extent metadata is included."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_stac_collection_detail
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        tools._client = AsyncMock()
        tools._client.get = AsyncMock(return_value=mock_response)

        result = await tools.get_collection_info("sentinel-2-l2a")

        assert "extent" in result
        assert "spatial" in result["extent"]


# ---------------------------------------------------------------------------
# generate_process_graph
# ---------------------------------------------------------------------------


class TestGenerateProcessGraph:
    """Tests for the generate_process_graph method."""

    @pytest.mark.asyncio
    async def test_basic_graph_structure(self, tools, small_spatial_extent):
        """Verify basic process graph has load and save nodes."""
        graph = await tools.generate_process_graph(
            description="Get satellite imagery",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        assert "load" in graph
        assert graph["load"]["process_id"] == "load_collection"
        assert "save" in graph
        assert graph["save"]["process_id"] == "save_result"
        assert graph["save"]["result"] is True

    @pytest.mark.asyncio
    async def test_ndvi_graph_generation(self, tools, small_spatial_extent):
        """Verify NDVI keyword triggers NDVI computation nodes."""
        graph = await tools.generate_process_graph(
            description="Calculate NDVI for this area",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        assert "ndvi" in graph
        assert graph["ndvi"]["process_id"] == "normalized_difference"
        assert "nir" in graph
        assert "red" in graph
        # Load should request red and nir bands
        assert "red" in graph["load"]["arguments"]["bands"]
        assert "nir" in graph["load"]["arguments"]["bands"]

    @pytest.mark.asyncio
    async def test_ndvi_graph_save_references_ndvi(self, tools, small_spatial_extent):
        """NDVI graph's save node should reference the ndvi node."""
        graph = await tools.generate_process_graph(
            description="compute ndvi",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        assert graph["save"]["arguments"]["data"]["from_node"] == "ndvi"

    @pytest.mark.asyncio
    async def test_non_ndvi_graph_save_references_load(
        self, tools, small_spatial_extent
    ):
        """Non-NDVI graph's save node should reference the load node."""
        graph = await tools.generate_process_graph(
            description="get raw imagery",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        assert graph["save"]["arguments"]["data"]["from_node"] == "load"

    @pytest.mark.asyncio
    async def test_custom_output_format(self, tools, small_spatial_extent):
        """Verify output_format is passed to save_result."""
        graph = await tools.generate_process_graph(
            description="get data",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
            output_format="netCDF",
        )

        assert graph["save"]["arguments"]["format"] == "netCDF"

    @pytest.mark.asyncio
    async def test_cloud_masking_with_sentinel_ndvi(self, tools, small_spatial_extent):
        """NDVI with 'cloud' keyword on Sentinel should add SCL band."""
        graph = await tools.generate_process_graph(
            description="compute cloud-free ndvi",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        bands = graph["load"]["arguments"]["bands"]
        assert "scl" in bands

    @pytest.mark.asyncio
    async def test_spatial_extent_in_load(self, tools, small_spatial_extent):
        """Verify spatial_extent is passed to load_collection."""
        graph = await tools.generate_process_graph(
            description="get data",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
        )

        assert graph["load"]["arguments"]["spatial_extent"] == small_spatial_extent

    @pytest.mark.asyncio
    async def test_temporal_extent_in_load(self, tools, small_spatial_extent):
        """Verify temporal_extent is passed to load_collection."""
        temporal = ["2024-01-01", "2024-12-31"]
        graph = await tools.generate_process_graph(
            description="get data",
            collection="sentinel-2-l2a",
            spatial_extent=small_spatial_extent,
            temporal_extent=temporal,
        )

        assert graph["load"]["arguments"]["temporal_extent"] == temporal


# ---------------------------------------------------------------------------
# URL handling
# ---------------------------------------------------------------------------


class TestURLHandling:
    """Tests for URL normalization."""

    def test_trailing_slash_removed(self):
        """Trailing slash should be stripped from openeo_url."""
        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0/")
        assert tools.openeo_url == "http://localhost:8000/openeo/1.1.0"

    def test_no_trailing_slash(self):
        """URL without trailing slash should remain unchanged."""
        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")
        assert tools.openeo_url == "http://localhost:8000/openeo/1.1.0"

    def test_lazy_client_initialization(self):
        """HTTP client should not be created until first use."""
        tools = OpenEOTools(openeo_url="http://localhost:8000")
        assert tools._client is None
