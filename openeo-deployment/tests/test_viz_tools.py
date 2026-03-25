"""Tests for openeo_ai/tools/viz_tools.py and visualization components.

Verifies map visualization generation, chart data formatting, and
component creation -- all without requiring rasterio or actual GeoTIFF files.
"""

import asyncio
import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np

from openeo_ai.visualization.charts import ChartComponent
from openeo_ai.visualization.maps import MapComponent, COLORMAPS


# ---------------------------------------------------------------------------
# MapComponent -- raster map creation
# ---------------------------------------------------------------------------


class TestMapComponent:
    """Tests for the MapComponent class."""

    @pytest.fixture
    def map_component(self):
        """Create a MapComponent instance."""
        return MapComponent()

    @pytest.mark.asyncio
    async def test_create_raster_map_structure(self, map_component):
        """Verify raster map result has correct MCP-UI component structure."""
        fake_data = np.random.rand(100, 100).astype(np.float32)
        fake_metadata = {
            "crs": "EPSG:4326",
            "transform": [0.001, 0, 11.0, 0, -0.001, 46.1],
            "bounds": [11.0, 46.0, 11.1, 46.1],
            "width": 100,
            "height": 100,
        }

        with patch.object(
            map_component, "_load_raster", return_value=(fake_data, fake_metadata)
        ):
            result = await map_component.create_raster_map(
                geotiff_path="/fake/path.tif",
                title="Test Map",
                colormap="viridis",
            )

        assert result["type"] == "map"
        assert "spec" in result
        assert result["spec"]["title"] == "Test Map"
        assert "layers" in result["spec"]
        assert len(result["spec"]["layers"]) == 1
        assert result["spec"]["layers"][0]["type"] == "raster"
        assert "colorbar" in result["spec"]

    @pytest.mark.asyncio
    async def test_create_raster_map_base64_image(self, map_component):
        """Verify raster map contains a valid base64-encoded PNG."""
        fake_data = np.random.rand(50, 50).astype(np.float32)
        fake_metadata = {
            "bounds": [11.0, 46.0, 11.1, 46.1],
            "width": 50,
            "height": 50,
        }

        with patch.object(
            map_component, "_load_raster", return_value=(fake_data, fake_metadata)
        ):
            result = await map_component.create_raster_map(
                geotiff_path="/fake/path.tif",
            )

        url = result["spec"]["layers"][0]["url"]
        assert url.startswith("data:image/png;base64,")
        # Verify it is valid base64
        b64_part = url.split(",")[1]
        decoded = base64.b64decode(b64_part)
        # PNG magic bytes
        assert decoded[:4] == b"\x89PNG"

    @pytest.mark.asyncio
    async def test_create_raster_map_custom_vmin_vmax(self, map_component):
        """Verify custom vmin/vmax are reflected in the component."""
        fake_data = np.random.rand(20, 20).astype(np.float32)
        fake_metadata = {"bounds": [0, 0, 1, 1], "width": 20, "height": 20}

        with patch.object(
            map_component, "_load_raster", return_value=(fake_data, fake_metadata)
        ):
            result = await map_component.create_raster_map(
                geotiff_path="/fake/path.tif",
                vmin=-1.0,
                vmax=1.0,
            )

        assert result["spec"]["colorbar"]["min"] == -1.0
        assert result["spec"]["colorbar"]["max"] == 1.0

    @pytest.mark.asyncio
    async def test_create_ndvi_map(self, map_component):
        """Verify NDVI map uses appropriate settings."""
        fake_data = np.random.uniform(-1, 1, (50, 50)).astype(np.float32)
        fake_metadata = {"bounds": [11.0, 46.0, 11.1, 46.1], "width": 50, "height": 50}

        with patch.object(
            map_component, "_load_raster", return_value=(fake_data, fake_metadata)
        ):
            result = await map_component.create_ndvi_map(
                geotiff_path="/fake/ndvi.tif",
                title="NDVI Result",
            )

        assert result["type"] == "map"
        assert result["spec"]["title"] == "NDVI Result"
        assert result["spec"]["colorbar"]["min"] == -1.0
        assert result["spec"]["colorbar"]["max"] == 1.0

    @pytest.mark.asyncio
    async def test_create_comparison_slider(self, map_component):
        """Verify comparison slider has before/after layers."""
        before_data = np.random.rand(30, 30).astype(np.float32)
        after_data = np.random.rand(30, 30).astype(np.float32) + 0.5
        metadata = {"bounds": [0, 0, 1, 1], "width": 30, "height": 30}

        with patch.object(
            map_component,
            "_load_raster",
            side_effect=[(before_data, metadata), (after_data, metadata)],
        ):
            result = await map_component.create_comparison_slider(
                before_path="/fake/before.tif",
                after_path="/fake/after.tif",
                title="Change Detection",
            )

        assert result["type"] == "comparison_slider"
        assert result["spec"]["title"] == "Change Detection"
        assert "before" in result["spec"]
        assert "after" in result["spec"]
        assert result["spec"]["before"]["label"] == "Before"
        assert result["spec"]["after"]["label"] == "After"
        assert result["spec"]["initial_position"] == 50

    def test_get_bounds(self, map_component):
        """Verify bounds extraction from metadata."""
        metadata = {"bounds": [11.0, 46.0, 11.1, 46.1]}
        bounds = map_component._get_bounds(metadata)

        # Expected: [[south, west], [north, east]]
        assert bounds == [[46.0, 11.0], [46.1, 11.1]]

    def test_get_center(self, map_component):
        """Verify center calculation from bounds."""
        bounds = [[46.0, 11.0], [46.1, 11.1]]
        center = map_component._get_center(bounds)

        assert center[0] == pytest.approx(46.05, rel=1e-3)
        assert center[1] == pytest.approx(11.05, rel=1e-3)

    def test_apply_colormap(self, map_component):
        """Verify colormap application produces RGBA array."""
        data = np.random.rand(10, 10).astype(np.float32)
        result = map_component._apply_colormap(data, "viridis", 0.0, 1.0)

        assert result.shape == (10, 10, 4)
        assert result.dtype == np.uint8
        # Alpha should be 255 for non-NaN values
        assert np.all(result[:, :, 3] == 255)

    def test_apply_colormap_nan_transparency(self, map_component):
        """Verify NaN pixels get alpha=0 (transparent)."""
        data = np.ones((10, 10), dtype=np.float32)
        data[5, 5] = np.nan
        result = map_component._apply_colormap(data, "viridis", 0.0, 1.0)

        assert result[5, 5, 3] == 0  # Transparent
        assert result[0, 0, 3] == 255  # Opaque

    def test_colormaps_available(self):
        """Verify all expected colormaps are defined."""
        expected = ["viridis", "plasma", "inferno", "ndvi", "terrain", "coolwarm", "grayscale"]
        for name in expected:
            assert name in COLORMAPS


# ---------------------------------------------------------------------------
# ChartComponent -- time series
# ---------------------------------------------------------------------------


class TestChartComponent:
    """Tests for the ChartComponent class."""

    @pytest.fixture
    def chart_component(self):
        """Create a ChartComponent instance."""
        return ChartComponent()

    @pytest.mark.asyncio
    async def test_create_time_series(self, chart_component):
        """Verify time series chart structure."""
        values = [0.3, 0.5, 0.7, 0.6, 0.8]
        dates = [
            "2024-01-01",
            "2024-02-01",
            "2024-03-01",
            "2024-04-01",
            "2024-05-01",
        ]

        result = await chart_component.create_time_series(
            values=values,
            dates=dates,
            title="NDVI Time Series",
            ylabel="NDVI",
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "line"
        assert result["spec"]["title"] == "NDVI Time Series"
        assert len(result["spec"]["data"]["y"]) == 5
        assert "statistics" in result["spec"]

    @pytest.mark.asyncio
    async def test_time_series_mismatched_lengths_raises(self, chart_component):
        """Mismatched values and dates should raise ValueError."""
        with pytest.raises(ValueError, match="same length"):
            await chart_component.create_time_series(
                values=[1, 2, 3],
                dates=["2024-01-01", "2024-02-01"],
            )

    @pytest.mark.asyncio
    async def test_time_series_statistics(self, chart_component):
        """Verify statistics are calculated correctly."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        dates = [f"2024-0{i}-01" for i in range(1, 6)]

        result = await chart_component.create_time_series(values=values, dates=dates)

        stats = result["spec"]["statistics"]
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["count"] == 5

    @pytest.mark.asyncio
    async def test_create_bar_chart(self, chart_component):
        """Verify bar chart structure."""
        result = await chart_component.create_bar_chart(
            categories=["Urban", "Forest", "Water"],
            values=[45.0, 30.0, 25.0],
            title="Land Cover",
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "bar"
        assert len(result["spec"]["data"]["x"]) == 3

    @pytest.mark.asyncio
    async def test_create_histogram(self, chart_component):
        """Verify histogram generation."""
        values = list(np.random.normal(0.5, 0.15, 100))

        result = await chart_component.create_histogram(
            values=values,
            bins=10,
            title="NDVI Distribution",
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "histogram"
        assert result["spec"]["bins"] == 10
        assert len(result["spec"]["data"]["y"]) == 10

    @pytest.mark.asyncio
    async def test_create_pie_chart(self, chart_component):
        """Verify pie chart structure."""
        result = await chart_component.create_pie_chart(
            labels=["Cloud", "Clear", "Shadow"],
            values=[30, 60, 10],
            title="Cloud Coverage",
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "pie"
        assert len(result["spec"]["data"]["labels"]) == 3

    @pytest.mark.asyncio
    async def test_create_scatter_plot(self, chart_component):
        """Verify scatter plot structure."""
        result = await chart_component.create_scatter_plot(
            x_values=[1.0, 2.0, 3.0, 4.0],
            y_values=[2.0, 4.0, 6.0, 8.0],
            title="Correlation",
        )

        assert result["type"] == "chart"
        assert result["spec"]["chart_type"] == "scatter"
        assert len(result["spec"]["data"]["x"]) == 4

    @pytest.mark.asyncio
    async def test_create_stats_summary(self, chart_component):
        """Verify statistics summary card."""
        result = await chart_component.create_stats_summary(
            data={"Mean NDVI": 0.65, "Max": 0.92, "Pixels": 10000},
            title="Analysis Summary",
        )

        assert result["type"] == "stats"
        assert result["spec"]["title"] == "Analysis Summary"
        assert len(result["spec"]["items"]) == 3

    def test_calculate_stats(self, chart_component):
        """Verify basic statistics calculation."""
        stats = chart_component._calculate_stats([1.0, 2.0, 3.0, 4.0, 5.0])

        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["count"] == 5

    def test_alpha_helper(self, chart_component):
        """Verify hex-to-rgba conversion."""
        result = chart_component._alpha("#4CAF50", 0.5)
        assert result == "rgba(76,175,80,0.5)"

    def test_darken_helper(self, chart_component):
        """Verify color darkening."""
        result = chart_component._darken("#FFFFFF", 0.5)
        # 255 * 0.5 = 127
        assert result == "#7f7f7f"

    def test_format_value_integer(self, chart_component):
        """Verify integer formatting with commas."""
        assert chart_component._format_value(10000) == "10,000"

    def test_format_value_float(self, chart_component):
        """Verify float formatting."""
        assert chart_component._format_value(0.0012) == "0.0012"
        assert chart_component._format_value(12345.6789) == "12,345.68"
