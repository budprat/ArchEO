# ABOUTME: Visualization tools wrapping map and chart components for Claude SDK.
# Creates MCP-UI compatible interactive maps, time series, and comparison views.

"""
Visualization tools for Claude SDK.

Provides tools for creating interactive maps, charts, and comparison views
following the MCP-UI component format.
"""

import json
from typing import Any, Dict


def create_viz_tools(config) -> Dict[str, Any]:
    """
    Create visualization tools dict for Claude SDK.

    Tools return MCP-UI compatible component specifications
    wrapped in Claude SDK format.
    """
    from ..visualization.maps import MapComponent
    from ..visualization.charts import ChartComponent

    # Lazy initialization
    _map_component = None
    _chart_component = None

    def get_map_component():
        nonlocal _map_component
        if _map_component is None:
            _map_component = MapComponent()
        return _map_component

    def get_chart_component():
        nonlocal _chart_component
        if _chart_component is None:
            _chart_component = ChartComponent()
        return _chart_component

    async def _show_map(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Display a GeoTIFF on an interactive map.

        Args:
            geotiff_path: Path to GeoTIFF file
            title: Map title
            colormap: Colormap name (default: "viridis")
            vmin: Minimum value for colormap
            vmax: Maximum value for colormap

        Returns:
            Claude SDK format response with visualization component
        """
        component = get_map_component()

        result = await component.create_raster_map(
            geotiff_path=args["geotiff_path"],
            title=args.get("title", "Result"),
            colormap=args.get("colormap", "viridis"),
            vmin=args.get("vmin"),
            vmax=args.get("vmax")
        )

        return {
            "content": [{
                "type": "visualization",
                "component": result
            }]
        }

    async def _show_ndvi_map(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Display NDVI results with vegetation color scale.

        Args:
            geotiff_path: Path to NDVI GeoTIFF
            title: Map title (default: "NDVI")

        Returns:
            Claude SDK format response with NDVI visualization
        """
        component = get_map_component()

        result = await component.create_ndvi_map(
            geotiff_path=args["geotiff_path"],
            title=args.get("title", "NDVI")
        )

        return {
            "content": [{
                "type": "visualization",
                "component": result
            }]
        }

    async def _show_time_series(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Display a time series chart.

        Args:
            values: List of values
            dates: List of date strings
            title: Chart title
            ylabel: Y-axis label

        Returns:
            Claude SDK format response with chart component
        """
        component = get_chart_component()

        result = await component.create_time_series(
            values=args["values"],
            dates=args["dates"],
            title=args.get("title", "Time Series"),
            ylabel=args.get("ylabel", "Value"),
            series_name=args.get("series_name", "Data")
        )

        return {
            "content": [{
                "type": "visualization",
                "component": result
            }]
        }

    async def _compare_images(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a before/after comparison slider.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            title: Comparison title

        Returns:
            Claude SDK format response with comparison component
        """
        component = get_map_component()

        result = await component.create_comparison_slider(
            before_path=args["before_path"],
            after_path=args["after_path"],
            title=args.get("title", "Before / After")
        )

        return {
            "content": [{
                "type": "visualization",
                "component": result
            }]
        }

    return {
        "viz_show_map": _show_map,
        "viz_show_ndvi_map": _show_ndvi_map,
        "viz_show_time_series": _show_time_series,
        "viz_compare_images": _compare_images,
    }


# Standalone tool functions for testing
async def show_map_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone show map tool."""
    from ..visualization.maps import MapComponent

    component = MapComponent()
    result = await component.create_raster_map(
        geotiff_path=args["geotiff_path"],
        title=args.get("title", "Result"),
        colormap=args.get("colormap", "viridis"),
        vmin=args.get("vmin"),
        vmax=args.get("vmax")
    )

    return {
        "content": [{
            "type": "visualization",
            "component": result
        }]
    }


async def show_ndvi_map_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone NDVI map tool."""
    from ..visualization.maps import MapComponent

    component = MapComponent()
    result = await component.create_ndvi_map(
        geotiff_path=args["geotiff_path"],
        title=args.get("title", "NDVI")
    )

    return {
        "content": [{
            "type": "visualization",
            "component": result
        }]
    }


async def show_time_series_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone time series tool."""
    from ..visualization.charts import ChartComponent

    component = ChartComponent()
    result = await component.create_time_series(
        values=args["values"],
        dates=args["dates"],
        title=args.get("title", "Time Series"),
        ylabel=args.get("ylabel", "Value")
    )

    return {
        "content": [{
            "type": "visualization",
            "component": result
        }]
    }


async def compare_images_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """Standalone comparison tool."""
    from ..visualization.maps import MapComponent

    component = MapComponent()
    result = await component.create_comparison_slider(
        before_path=args["before_path"],
        after_path=args["after_path"],
        title=args.get("title", "Before / After")
    )

    return {
        "content": [{
            "type": "visualization",
            "component": result
        }]
    }
