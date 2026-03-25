"""
Unified visualization components for OpenEO AI Assistant.

ABOUTME: Provides a single unified interface to all visualization components.
Combines map and chart capabilities for easy access from tools and endpoints.
"""

import logging
from typing import Dict, Any, Optional, List

from .maps import MapComponent
from .charts import ChartComponent

logger = logging.getLogger(__name__)


class VisualizationEngine:
    """
    Unified visualization engine combining maps and charts.

    Provides a single interface for creating all visualization types:
    - Interactive maps with raster overlays
    - Time series and statistical charts
    - Before/after comparison views
    - Multi-layer map displays
    """

    def __init__(self, default_colormap: str = "viridis"):
        """
        Initialize visualization engine.

        Args:
            default_colormap: Default colormap for raster visualization
        """
        self.maps = MapComponent(default_colormap=default_colormap)
        self.charts = ChartComponent()
        logger.info("VisualizationEngine initialized")

    # === Map Methods ===

    async def show_raster(
        self,
        geotiff_path: str,
        title: str = "Result",
        colormap: str = "viridis",
        vmin: Optional[float] = None,
        vmax: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Display a raster file on an interactive map.

        Args:
            geotiff_path: Path to GeoTIFF file
            title: Map title
            colormap: Colormap name (viridis, plasma, ndvi, terrain)
            vmin: Minimum value for color scale
            vmax: Maximum value for color scale

        Returns:
            MCP-UI component specification
        """
        return await self.maps.create_raster_map(
            geotiff_path=geotiff_path,
            title=title,
            colormap=colormap,
            vmin=vmin,
            vmax=vmax
        )

    async def show_ndvi(
        self,
        geotiff_path: str,
        title: str = "NDVI"
    ) -> Dict[str, Any]:
        """
        Display NDVI data with appropriate color scale.

        Args:
            geotiff_path: Path to NDVI GeoTIFF
            title: Map title

        Returns:
            MCP-UI component specification
        """
        return await self.maps.create_ndvi_map(
            geotiff_path=geotiff_path,
            title=title
        )

    async def show_comparison(
        self,
        before_path: str,
        after_path: str,
        title: str = "Before / After"
    ) -> Dict[str, Any]:
        """
        Create a before/after comparison slider.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            title: Comparison title

        Returns:
            MCP-UI component specification
        """
        return await self.maps.create_comparison_slider(
            before_path=before_path,
            after_path=after_path,
            title=title
        )

    async def show_layers(
        self,
        layers: List[Dict[str, Any]],
        title: str = "Multi-Layer View"
    ) -> Dict[str, Any]:
        """
        Display multiple layers with toggle controls.

        Args:
            layers: List of layer specifications with path, name, colormap
            title: Map title

        Returns:
            MCP-UI component specification
        """
        return await self.maps.create_multi_layer_map(
            layers=layers,
            title=title
        )

    # === Chart Methods ===

    async def show_time_series(
        self,
        values: List[float],
        dates: List[str],
        title: str = "Time Series",
        ylabel: str = "Value"
    ) -> Dict[str, Any]:
        """
        Display a time series chart.

        Args:
            values: Data values
            dates: Date strings (ISO format)
            title: Chart title
            ylabel: Y-axis label

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_time_series(
            values=values,
            dates=dates,
            title=title,
            ylabel=ylabel
        )

    async def show_bar_chart(
        self,
        categories: List[str],
        values: List[float],
        title: str = "Statistics",
        ylabel: str = "Value"
    ) -> Dict[str, Any]:
        """
        Display a bar chart.

        Args:
            categories: Category labels
            values: Values per category
            title: Chart title
            ylabel: Y-axis label

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_bar_chart(
            categories=categories,
            values=values,
            title=title,
            ylabel=ylabel
        )

    async def show_histogram(
        self,
        values: List[float],
        bins: int = 20,
        title: str = "Distribution"
    ) -> Dict[str, Any]:
        """
        Display a histogram of value distribution.

        Args:
            values: Data values
            bins: Number of histogram bins
            title: Chart title

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_histogram(
            values=values,
            bins=bins,
            title=title
        )

    async def show_pie_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = "Distribution"
    ) -> Dict[str, Any]:
        """
        Display a pie chart.

        Args:
            labels: Category labels
            values: Values per category
            title: Chart title

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_pie_chart(
            labels=labels,
            values=values,
            title=title
        )

    async def show_scatter(
        self,
        x_values: List[float],
        y_values: List[float],
        title: str = "Scatter Plot",
        xlabel: str = "X",
        ylabel: str = "Y",
        show_regression: bool = False
    ) -> Dict[str, Any]:
        """
        Display a scatter plot.

        Args:
            x_values: X-axis values
            y_values: Y-axis values
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            show_regression: Whether to show regression line

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_scatter_plot(
            x_values=x_values,
            y_values=y_values,
            title=title,
            xlabel=xlabel,
            ylabel=ylabel,
            show_regression=show_regression
        )

    async def show_stats(
        self,
        data: Dict[str, float],
        title: str = "Statistics"
    ) -> Dict[str, Any]:
        """
        Display a statistics summary card.

        Args:
            data: Dictionary of stat name -> value
            title: Summary title

        Returns:
            MCP-UI component specification
        """
        return await self.charts.create_stats_summary(
            data=data,
            title=title
        )

    # === Convenience Methods ===

    async def show_segmentation_results(
        self,
        segmentation_path: str,
        class_stats: Dict[str, Dict[str, Any]],
        title: str = "Segmentation Results"
    ) -> List[Dict[str, Any]]:
        """
        Display segmentation results with map and class distribution.

        Args:
            segmentation_path: Path to segmentation result GeoTIFF
            class_stats: Dictionary of class -> {pixels, percent}
            title: Title for visualizations

        Returns:
            List of MCP-UI component specifications
        """
        components = []

        # Create map
        map_component = await self.show_raster(
            geotiff_path=segmentation_path,
            title=title,
            colormap="viridis"
        )
        components.append(map_component)

        # Create class distribution pie chart
        labels = list(class_stats.keys())
        values = [s.get("percent", 0) for s in class_stats.values()]

        pie_component = await self.show_pie_chart(
            labels=labels,
            values=values,
            title="Class Distribution"
        )
        components.append(pie_component)

        return components

    async def show_change_detection_results(
        self,
        before_path: str,
        after_path: str,
        change_path: str,
        change_stats: Dict[str, Any],
        title: str = "Change Detection"
    ) -> List[Dict[str, Any]]:
        """
        Display change detection results with comparison and statistics.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            change_path: Path to change detection result
            change_stats: Change statistics
            title: Title for visualizations

        Returns:
            List of MCP-UI component specifications
        """
        components = []

        # Create before/after comparison
        comparison = await self.show_comparison(
            before_path=before_path,
            after_path=after_path,
            title=f"{title} - Before/After"
        )
        components.append(comparison)

        # Create change map
        change_map = await self.show_raster(
            geotiff_path=change_path,
            title=f"{title} - Change Mask",
            colormap="plasma"
        )
        components.append(change_map)

        # Create stats summary
        stats = await self.show_stats(
            data={
                "Changed Pixels": change_stats.get("changed_pixels", 0),
                "Total Pixels": change_stats.get("total_pixels", 0),
                "Change %": change_stats.get("change_percent", 0),
            },
            title="Change Statistics"
        )
        components.append(stats)

        return components


# Create default engine instance
_default_engine: Optional[VisualizationEngine] = None


def get_visualization_engine() -> VisualizationEngine:
    """Get the default visualization engine instance."""
    global _default_engine
    if _default_engine is None:
        _default_engine = VisualizationEngine()
    return _default_engine
