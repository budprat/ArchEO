"""
Phase 2: Custom Tools Tests

Test-Driven Development: These tests define the expected behavior
of the OpenEO tools before implementation.

Tests cover:
- OpenEO data discovery tools
- Job management tools
- Process graph generation
- Tool input/output formats
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json


class TestOpenEOListCollections:
    """Test openeo_list_collections tool."""

    @pytest.mark.asyncio
    async def test_list_collections_returns_array(self, available_collections):
        """Tool should return array of collections."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_fetch_collections', return_value=available_collections):
            result = await tools.list_collections()

            assert isinstance(result, list)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_list_collections_includes_required_fields(self, available_collections):
        """Each collection should have required fields."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_fetch_collections', return_value=available_collections):
            result = await tools.list_collections()

            for collection in result:
                assert "id" in collection
                assert "title" in collection or "description" in collection

    @pytest.mark.asyncio
    async def test_list_collections_tool_format(self, available_collections):
        """Tool output should match Claude SDK format."""
        from openeo_ai.tools.openeo_tools import list_collections_tool

        with patch('openeo_ai.tools.openeo_tools.OpenEOTools') as MockTools:
            mock_instance = MockTools.return_value
            mock_instance.list_collections = AsyncMock(return_value=available_collections)

            result = await list_collections_tool({})

            assert "content" in result
            assert isinstance(result["content"], list)
            assert result["content"][0]["type"] == "text"


class TestOpenEOGetCollectionInfo:
    """Test openeo_get_collection_info tool."""

    @pytest.mark.asyncio
    async def test_get_collection_info_returns_details(self, sentinel2_bands):
        """Tool should return collection details including bands."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        mock_info = {
            "id": "sentinel-2-l2a",
            "title": "Sentinel-2 L2A",
            "description": "Atmospherically corrected",
            "bands": sentinel2_bands,
            "extent": {
                "spatial": {"bbox": [[-180, -90, 180, 90]]},
                "temporal": {"interval": [["2015-06-27", None]]}
            }
        }

        with patch.object(tools, '_fetch_collection_info', return_value=mock_info):
            result = await tools.get_collection_info("sentinel-2-l2a")

            assert result["id"] == "sentinel-2-l2a"
            assert "bands" in result

    @pytest.mark.asyncio
    async def test_get_collection_info_invalid_id(self):
        """Tool should handle invalid collection ID."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_fetch_collection_info', return_value=None):
            result = await tools.get_collection_info("nonexistent-collection")

            assert result is None or "error" in result


class TestOpenEOValidateGraph:
    """Test openeo_validate_graph tool."""

    @pytest.mark.asyncio
    async def test_validate_valid_graph(self, ndvi_process_graph):
        """Tool should validate a correct process graph."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(ndvi_process_graph)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_missing_result_node(self, invalid_process_graph_missing_result):
        """Tool should detect missing result node."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(invalid_process_graph_missing_result)

        assert result["valid"] is False
        assert any("result" in err.lower() for err in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_bad_node_reference(self, invalid_process_graph_bad_reference):
        """Tool should detect bad node references."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(invalid_process_graph_bad_reference)

        assert result["valid"] is False
        assert any("reference" in err.lower() or "unknown" in err.lower()
                   for err in result["errors"])

    @pytest.mark.asyncio
    async def test_validate_returns_warnings(self, process_graph_large_extent):
        """Tool should return warnings for large extents."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()
        result = await tools.validate(process_graph_large_extent)

        assert len(result["warnings"]) > 0
        assert any("large" in warn.lower() or "extent" in warn.lower()
                   for warn in result["warnings"])

    @pytest.mark.asyncio
    async def test_validate_returns_suggestions(self, ndvi_process_graph):
        """Tool should return helpful suggestions."""
        from openeo_ai.tools.validation_tools import ValidationTools

        tools = ValidationTools()

        # Remove cloud masking to trigger suggestion
        result = await tools.validate(ndvi_process_graph)

        # May have suggestions even for valid graphs
        assert "suggestions" in result


class TestJobTools:
    """Test job management tools."""

    @pytest.mark.asyncio
    async def test_create_job_returns_job_id(self, ndvi_process_graph):
        """Create job should return job ID."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_create_job_request') as mock_create:
            mock_create.return_value = {"id": "job-123", "status": "created"}

            result = await tools.create(
                title="Test NDVI",
                description="Calculate NDVI",
                process_graph=ndvi_process_graph
            )

            assert "id" in result
            assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_start_job_changes_status(self, sample_job_id):
        """Start job should change status to queued/running."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_start_job_request') as mock_start:
            mock_start.return_value = {"id": str(sample_job_id), "status": "running"}

            result = await tools.start(str(sample_job_id))

            assert result["status"] in ["queued", "running"]

    @pytest.mark.asyncio
    async def test_get_job_status(self, sample_job_id):
        """Get job status should return current status."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_get_status_request') as mock_status:
            mock_status.return_value = {
                "id": str(sample_job_id),
                "status": "finished",
                "progress": 100
            }

            result = await tools.get_status(str(sample_job_id))

            assert "status" in result
            assert result["status"] in ["created", "queued", "running", "finished", "error"]

    @pytest.mark.asyncio
    async def test_get_results_returns_path(self, sample_job_id, temp_storage_path):
        """Get results should return result file path."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_get_results_request') as mock_results:
            mock_results.return_value = {
                "path": str(temp_storage_path / "result.tif"),
                "format": "GTiff",
                "size_bytes": 1024
            }

            result = await tools.get_results(
                str(sample_job_id),
                output_path=str(temp_storage_path)
            )

            assert "path" in result


class TestProcessGraphGeneration:
    """Test process graph generation tool."""

    @pytest.mark.asyncio
    async def test_generate_ndvi_graph(self):
        """Tool should generate NDVI process graph."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        result = await tools.generate_process_graph(
            description="Calculate NDVI",
            collection="sentinel-2-l2a",
            spatial_extent={
                "west": 11.0, "south": 46.0,
                "east": 11.01, "north": 46.01
            },
            temporal_extent=["2024-06-01", "2024-06-10"],
            output_format="GTiff"
        )

        assert isinstance(result, dict)
        # Should have load_collection node
        assert any(
            node.get("process_id") == "load_collection"
            for node in result.values()
        )
        # Should have result node
        assert any(
            node.get("result", False)
            for node in result.values()
        )

    @pytest.mark.asyncio
    async def test_generate_graph_with_cloud_mask(self):
        """Tool should add cloud masking when requested."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        result = await tools.generate_process_graph(
            description="Calculate NDVI with cloud masking",
            collection="sentinel-2-l2a",
            spatial_extent={
                "west": 11.0, "south": 46.0,
                "east": 11.01, "north": 46.01
            },
            temporal_extent=["2024-06-01", "2024-06-10"],
            output_format="GTiff"
        )

        # Should detect "cloud" in description and add masking
        # Check for mask process or SCL band
        graph_str = json.dumps(result)
        # Either has mask process or SCL band referenced
        assert "mask" in graph_str.lower() or "scl" in graph_str.lower()


class TestToolInputValidation:
    """Test input validation for tools."""

    @pytest.mark.asyncio
    async def test_create_job_validates_process_graph(self):
        """Create job should validate process graph before submission."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        # Empty process graph should be rejected
        with pytest.raises(ValueError):
            await tools.create(
                title="Invalid Job",
                description="",
                process_graph={}
            )

    @pytest.mark.asyncio
    async def test_get_collection_info_validates_id(self):
        """Get collection info should validate collection ID."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        # Empty ID should be rejected
        with pytest.raises(ValueError):
            await tools.get_collection_info("")


class TestToolOutputFormat:
    """Test that tools return properly formatted output."""

    @pytest.mark.asyncio
    async def test_tool_returns_claude_sdk_format(self, available_collections):
        """Tools should return Claude SDK compatible format."""
        from openeo_ai.tools.openeo_tools import list_collections_tool

        with patch('openeo_ai.tools.openeo_tools.OpenEOTools') as MockTools:
            mock_instance = MockTools.return_value
            mock_instance.list_collections = AsyncMock(return_value=available_collections)

            result = await list_collections_tool({})

            # Should have content array
            assert "content" in result
            assert isinstance(result["content"], list)

            # Content should have type and text/data
            for item in result["content"]:
                assert "type" in item
                assert item["type"] in ["text", "image", "visualization"]

    @pytest.mark.asyncio
    async def test_validation_tool_returns_structured_result(self, ndvi_process_graph):
        """Validation tool should return structured result."""
        from openeo_ai.tools.validation_tools import validate_graph_tool

        result = await validate_graph_tool({"process_graph": ndvi_process_graph})

        assert "content" in result

        # Parse the content
        content_text = result["content"][0]["text"]
        parsed = json.loads(content_text)

        assert "valid" in parsed
        assert "errors" in parsed
        assert "warnings" in parsed
        assert "suggestions" in parsed


class TestToolErrorHandling:
    """Test error handling in tools."""

    @pytest.mark.asyncio
    async def test_list_collections_handles_network_error(self):
        """List collections should handle network errors."""
        from openeo_ai.tools.openeo_tools import OpenEOTools

        tools = OpenEOTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_fetch_collections', side_effect=ConnectionError("Network error")):
            with pytest.raises(ConnectionError):
                await tools.list_collections()

    @pytest.mark.asyncio
    async def test_create_job_handles_api_error(self, ndvi_process_graph):
        """Create job should handle API errors."""
        from openeo_ai.tools.job_tools import JobTools

        tools = JobTools(openeo_url="http://localhost:8000/openeo/1.1.0")

        with patch.object(tools, '_create_job_request', side_effect=Exception("API error")):
            with pytest.raises(Exception):
                await tools.create(
                    title="Test Job",
                    description="",
                    process_graph=ndvi_process_graph
                )
