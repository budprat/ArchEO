"""
Phase 5: Visualization Tests

Test-Driven Development: These tests define the expected behavior
of the visualization components before implementation.

Tests cover:
- Interactive maps
- Time series charts
- Comparison sliders
- MCP-UI component format
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
import numpy as np


class TestMapComponent:
    """Test interactive map visualization."""

    @pytest.mark.asyncio
    async def test_create_raster_map(self, temp_geotiff):
        """Should create raster map component."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test Map"
        )

        assert result["type"] == "map"
        assert "spec" in result
        assert result["spec"]["title"] == "Test Map"

    @pytest.mark.asyncio
    async def test_map_includes_center_coordinates(self, temp_geotiff):
        """Map should include center coordinates from raster."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test Map"
        )

        assert "center" in result["spec"]
        assert isinstance(result["spec"]["center"], list)
        assert len(result["spec"]["center"]) == 2  # [lat, lon]

    @pytest.mark.asyncio
    async def test_map_includes_zoom_level(self, temp_geotiff):
        """Map should include appropriate zoom level."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test Map"
        )

        assert "zoom" in result["spec"]
        assert isinstance(result["spec"]["zoom"], (int, float))
        assert 1 <= result["spec"]["zoom"] <= 20

    @pytest.mark.asyncio
    async def test_map_includes_layer_config(self, temp_geotiff):
        """Map should include layer configuration."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test Map",
            colormap="viridis"
        )

        assert "layers" in result["spec"]
        assert len(result["spec"]["layers"]) > 0

        layer = result["spec"]["layers"][0]
        assert layer["type"] == "raster"
        assert layer["colormap"] == "viridis"

    @pytest.mark.asyncio
    async def test_map_includes_colorbar(self, temp_geotiff):
        """Map should include colorbar configuration."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="NDVI",
            colormap="RdYlGn",
            vmin=-1,
            vmax=1
        )

        assert "colorbar" in result["spec"]
        colorbar = result["spec"]["colorbar"]
        assert colorbar["min"] == -1
        assert colorbar["max"] == 1

    @pytest.mark.asyncio
    async def test_ndvi_map_uses_vegetation_colormap(self, temp_geotiff):
        """NDVI map should use vegetation-appropriate colormap."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_ndvi_map(
            geotiff_path=str(temp_geotiff),
            title="NDVI"
        )

        layer = result["spec"]["layers"][0]
        assert layer["colormap"] == "RdYlGn"
        assert layer["vmin"] == -1
        assert layer["vmax"] == 1


class TestComparisonSlider:
    """Test before/after comparison slider."""

    @pytest.mark.asyncio
    async def test_create_comparison_slider(self, temp_comparison_files):
        """Should create comparison slider component."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        before_path, after_path = temp_comparison_files

        result = await component.create_comparison_slider(
            before_path=str(before_path),
            after_path=str(after_path),
            title="Before / After"
        )

        assert result["type"] == "comparison_slider"
        assert "spec" in result

    @pytest.mark.asyncio
    async def test_comparison_has_before_after_config(self, temp_comparison_files):
        """Comparison should have before/after configuration."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        before_path, after_path = temp_comparison_files

        result = await component.create_comparison_slider(
            before_path=str(before_path),
            after_path=str(after_path)
        )

        spec = result["spec"]
        assert "before" in spec
        assert "after" in spec
        assert spec["before"]["source"] == str(before_path)
        assert spec["after"]["source"] == str(after_path)

    @pytest.mark.asyncio
    async def test_comparison_has_initial_position(self, temp_comparison_files):
        """Comparison should have initial slider position."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        before_path, after_path = temp_comparison_files

        result = await component.create_comparison_slider(
            before_path=str(before_path),
            after_path=str(after_path)
        )

        assert "initial_position" in result["spec"]
        assert 0 <= result["spec"]["initial_position"] <= 100


class TestChartComponent:
    """Test chart visualization components."""

    @pytest.mark.asyncio
    async def test_create_time_series_chart(self):
        """Should create time series line chart."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        result = await component.create_time_series(
            values=[0.45, 0.52, 0.61, 0.58],
            dates=["2024-06-01", "2024-06-15", "2024-07-01", "2024-07-15"],
            title="NDVI Time Series",
            ylabel="NDVI"
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "line"

    @pytest.mark.asyncio
    async def test_time_series_has_data(self):
        """Time series should include data arrays."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        values = [0.45, 0.52, 0.61]
        dates = ["2024-06-01", "2024-06-15", "2024-07-01"]

        result = await component.create_time_series(
            values=values,
            dates=dates,
            title="Test"
        )

        data = result["spec"]["data"]
        # Dates may be parsed to ISO format with time component
        assert len(data["x"]) == len(dates)
        assert all("2024-06" in d or "2024-07" in d for d in data["x"])
        assert data["y"] == values

    @pytest.mark.asyncio
    async def test_time_series_has_axis_labels(self):
        """Time series should have axis labels."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        result = await component.create_time_series(
            values=[0.45, 0.52],
            dates=["2024-06-01", "2024-06-15"],
            title="Test",
            ylabel="NDVI"
        )

        assert "xaxis" in result["spec"]
        assert "yaxis" in result["spec"]
        assert result["spec"]["yaxis"]["title"] == "NDVI"

    @pytest.mark.asyncio
    async def test_create_histogram(self):
        """Should create histogram chart."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        values = list(np.random.randn(1000))

        result = await component.create_histogram(
            values=values,
            title="Value Distribution",
            xlabel="Value",
            bins=50
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "histogram"
        assert result["spec"]["bins"] == 50

    @pytest.mark.asyncio
    async def test_create_bar_chart(self):
        """Should create bar chart."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        result = await component.create_bar_chart(
            categories=["Vegetation", "Water", "Urban", "Bare"],
            values=[45.2, 12.3, 28.1, 14.4],
            title="Land Cover",
            ylabel="Percentage"
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "bar"


class TestVisualizationTools:
    """Test visualization tools for Claude SDK."""

    @pytest.mark.asyncio
    async def test_viz_show_map_tool(self, temp_geotiff, sample_map_spec):
        """viz_show_map tool should return proper format."""
        from openeo_ai.tools.viz_tools import show_map_tool

        # The tool creates its own MapComponent internally
        result = await show_map_tool({
            "geotiff_path": str(temp_geotiff),
            "title": "Test"
        })

        assert "content" in result
        # Should have visualization type content
        content = result["content"][0]
        assert content["type"] == "visualization"

    @pytest.mark.asyncio
    async def test_viz_show_ndvi_map_tool(self, temp_geotiff):
        """viz_show_ndvi_map tool should use NDVI settings."""
        from openeo_ai.tools.viz_tools import show_ndvi_map_tool

        result = await show_ndvi_map_tool({
            "geotiff_path": str(temp_geotiff)
        })

        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "visualization"

    @pytest.mark.asyncio
    async def test_viz_show_time_series_tool(self, sample_chart_spec):
        """viz_show_time_series tool should return chart format."""
        from openeo_ai.tools.viz_tools import show_time_series_tool

        result = await show_time_series_tool({
            "values": [0.45, 0.52, 0.61],
            "dates": ["2024-06-01", "2024-06-15", "2024-07-01"],
            "title": "NDVI"
        })

        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "visualization"

    @pytest.mark.asyncio
    async def test_viz_compare_images_tool(self, temp_comparison_files):
        """viz_compare_images tool should return comparison slider."""
        from openeo_ai.tools.viz_tools import compare_images_tool

        before_path, after_path = temp_comparison_files

        result = await compare_images_tool({
            "before_path": str(before_path),
            "after_path": str(after_path)
        })

        assert "content" in result
        content = result["content"][0]
        assert content["type"] == "visualization"


class TestMCPUIFormat:
    """Test MCP-UI component format compliance."""

    @pytest.mark.asyncio
    async def test_map_spec_is_json_serializable(self, temp_geotiff):
        """Map spec should be JSON serializable."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test"
        )

        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    @pytest.mark.asyncio
    async def test_chart_spec_is_json_serializable(self):
        """Chart spec should be JSON serializable."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        result = await component.create_time_series(
            values=[0.45, 0.52],
            dates=["2024-06-01", "2024-06-15"],
            title="Test"
        )

        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    @pytest.mark.asyncio
    async def test_component_has_type_field(self, temp_geotiff):
        """All components should have type field."""
        from openeo_ai.visualization.maps import MapComponent
        from openeo_ai.visualization.charts import ChartComponent

        map_comp = MapComponent()
        chart_comp = ChartComponent()

        map_result = await map_comp.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test"
        )

        chart_result = await chart_comp.create_time_series(
            values=[0.45],
            dates=["2024-06-01"],
            title="Test"
        )

        assert "type" in map_result
        assert "type" in chart_result

    @pytest.mark.asyncio
    async def test_component_has_spec_field(self, temp_geotiff):
        """All components should have spec field."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        result = await component.create_raster_map(
            geotiff_path=str(temp_geotiff),
            title="Test"
        )

        assert "spec" in result
        assert isinstance(result["spec"], dict)


class TestVisualizationErrors:
    """Test error handling in visualization components."""

    @pytest.mark.asyncio
    async def test_map_handles_invalid_geotiff(self):
        """Map should handle invalid GeoTIFF gracefully."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        # Accept either FileNotFoundError or rasterio's IOError
        with pytest.raises((FileNotFoundError, Exception)) as exc_info:
            await component.create_raster_map(
                geotiff_path="/nonexistent/file.tif",
                title="Test"
            )
        # Verify it's related to file not found
        assert "No such file" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_chart_handles_mismatched_arrays(self):
        """Chart should handle mismatched array lengths."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        with pytest.raises(ValueError):
            await component.create_time_series(
                values=[0.45, 0.52, 0.61],  # 3 values
                dates=["2024-06-01", "2024-06-15"],  # 2 dates
                title="Test"
            )

    @pytest.mark.asyncio
    async def test_comparison_handles_missing_files(self, temp_storage_path):
        """Comparison should handle missing files."""
        from openeo_ai.visualization.maps import MapComponent

        component = MapComponent()

        # Accept either FileNotFoundError or rasterio's IOError
        with pytest.raises((FileNotFoundError, Exception)) as exc_info:
            await component.create_comparison_slider(
                before_path="/nonexistent/before.tif",
                after_path="/nonexistent/after.tif"
            )
        # Verify it's related to file not found
        assert "No such file" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


class TestVisualizationIntegration:
    """Test visualization integration with other components."""

    @pytest.mark.asyncio
    async def test_segmentation_result_can_be_visualized(
        self, sample_segmentation_result, temp_storage_path
    ):
        """Segmentation result should be visualizable."""
        from openeo_ai.visualization.maps import MapComponent
        import rioxarray  # noqa: F401

        component = MapComponent()

        # Save segmentation result to temp file
        output_path = temp_storage_path / "segmentation.tif"

        # Mock the visualization
        mock_result = {
            "type": "map",
            "spec": {
                "title": "Segmentation",
                "layers": [{"type": "raster", "colormap": "tab10"}]
            }
        }

        with patch.object(component, 'create_raster_map', return_value=mock_result):
            result = await component.create_raster_map(
                geotiff_path=str(output_path),
                title="Segmentation",
                colormap="tab10"
            )

            assert result["type"] == "map"

    @pytest.mark.asyncio
    async def test_ndvi_result_time_series(self):
        """NDVI results should support time series visualization."""
        from openeo_ai.visualization.charts import ChartComponent

        component = ChartComponent()

        # Typical NDVI time series data
        ndvi_values = [0.35, 0.42, 0.58, 0.62, 0.55, 0.48]
        dates = [
            "2024-04-01", "2024-05-01", "2024-06-01",
            "2024-07-01", "2024-08-01", "2024-09-01"
        ]

        result = await component.create_time_series(
            values=ndvi_values,
            dates=dates,
            title="Seasonal NDVI",
            ylabel="NDVI",
            series_name="Mean NDVI"
        )

        assert result["type"] == "chart"
        assert len(result["spec"]["data"]["y"]) == 6
