# ABOUTME: MCP-UI compatible map visualization components.
# Renders rasters on interactive maps with colormaps, legends, and comparison sliders.

"""
Map visualization components for OpenEO AI Assistant.

Provides MCP-UI compatible map components for displaying:
- Raster data on interactive maps
- NDVI and other index visualizations
- Before/after comparison sliders
"""

import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# Colormap definitions
COLORMAPS = {
    "viridis": [
        (68, 1, 84), (72, 35, 116), (64, 67, 135), (52, 94, 141),
        (41, 120, 142), (32, 144, 140), (34, 167, 132), (68, 190, 112),
        (121, 209, 81), (189, 222, 38), (253, 231, 37)
    ],
    "plasma": [
        (13, 8, 135), (75, 3, 161), (125, 3, 168), (168, 34, 150),
        (203, 70, 121), (229, 107, 93), (248, 148, 65), (253, 195, 40),
        (240, 249, 33)
    ],
    "inferno": [
        (0, 0, 4), (22, 11, 57), (66, 10, 104), (106, 23, 110),
        (147, 38, 103), (188, 55, 84), (221, 81, 58), (243, 118, 27),
        (252, 165, 10), (246, 215, 70), (252, 255, 164)
    ],
    "ndvi": [
        (165, 0, 38), (215, 48, 39), (244, 109, 67), (253, 174, 97),
        (254, 224, 139), (255, 255, 191), (217, 239, 139), (166, 217, 106),
        (102, 189, 99), (26, 152, 80), (0, 104, 55)
    ],
    "terrain": [
        (0, 97, 71), (16, 122, 47), (232, 215, 125), (161, 67, 0),
        (130, 30, 30), (161, 161, 161), (206, 206, 206), (255, 255, 255)
    ],
    "coolwarm": [
        (59, 76, 192), (103, 136, 238), (154, 187, 255), (201, 215, 240),
        (237, 209, 194), (247, 168, 137), (226, 105, 82), (180, 4, 38)
    ],
    "grayscale": [
        (0, 0, 0), (51, 51, 51), (102, 102, 102), (153, 153, 153),
        (204, 204, 204), (255, 255, 255)
    ],
}


class MapComponent:
    """
    Create MCP-UI compatible map visualizations.

    Generates interactive map components with raster overlays,
    legends, and comparison tools.
    """

    def __init__(self, default_colormap: str = "viridis"):
        """
        Initialize map component.

        Args:
            default_colormap: Default colormap for raster display
        """
        self.default_colormap = default_colormap

    async def create_raster_map(
        self,
        geotiff_path: str,
        title: str = "Result",
        colormap: str = "viridis",
        vmin: Optional[float] = None,
        vmax: Optional[float] = None,
        opacity: float = 0.8
    ) -> Dict[str, Any]:
        """
        Create a map component with raster overlay.

        Args:
            geotiff_path: Path to GeoTIFF file
            title: Map title
            colormap: Colormap name
            vmin: Minimum value for colormap
            vmax: Maximum value for colormap
            opacity: Raster opacity (0-1)

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating raster map for {geotiff_path}")

        # Load raster data
        data, metadata = self._load_raster(geotiff_path)

        # Calculate bounds
        bounds = self._get_bounds(metadata)
        center = self._get_center(bounds)

        # Generate colored image
        vmin = vmin if vmin is not None else float(np.nanmin(data))
        vmax = vmax if vmax is not None else float(np.nanmax(data))
        colored_image = self._apply_colormap(data, colormap, vmin, vmax)

        # Encode as base64
        image_data = self._encode_image(colored_image)

        # Generate legend
        legend = self._create_legend(colormap, vmin, vmax)

        return {
            "type": "map",
            "spec": {
                "title": title,
                "center": center,
                "zoom": 12,
                "layers": [
                    {
                        "type": "raster",
                        "bounds": bounds,
                        "url": f"data:image/png;base64,{image_data}",
                        "source": geotiff_path,
                        "opacity": opacity,
                        "colormap": colormap,
                        "vmin": vmin,
                        "vmax": vmax
                    }
                ],
                "colorbar": {
                    "min": vmin,
                    "max": vmax,
                    "colormap": colormap
                },
                "controls": ["zoom", "scale", "fullscreen"]
            }
        }

    async def create_ndvi_map(
        self,
        geotiff_path: str,
        title: str = "NDVI"
    ) -> Dict[str, Any]:
        """
        Create an NDVI visualization map.

        Args:
            geotiff_path: Path to NDVI GeoTIFF
            title: Map title

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating NDVI map for {geotiff_path}")

        # Load raster data
        data, metadata = self._load_raster(geotiff_path)

        # Calculate bounds
        bounds = self._get_bounds(metadata)
        center = self._get_center(bounds)

        # NDVI specific settings
        vmin = -1.0
        vmax = 1.0
        colormap = "RdYlGn"

        # Generate colored image
        colored_image = self._apply_colormap(data, "ndvi", vmin, vmax)
        image_data = self._encode_image(colored_image)

        return {
            "type": "map",
            "spec": {
                "title": title,
                "center": center,
                "zoom": 12,
                "layers": [
                    {
                        "type": "raster",
                        "bounds": bounds,
                        "url": f"data:image/png;base64,{image_data}",
                        "source": geotiff_path,
                        "opacity": 0.8,
                        "colormap": colormap,
                        "vmin": vmin,
                        "vmax": vmax
                    }
                ],
                "colorbar": {
                    "min": vmin,
                    "max": vmax,
                    "colormap": colormap
                }
            }
        }

    async def create_comparison_slider(
        self,
        before_path: str,
        after_path: str,
        title: str = "Before / After",
        colormap: str = "viridis"
    ) -> Dict[str, Any]:
        """
        Create a before/after comparison slider.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            title: Comparison title
            colormap: Colormap for both images

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating comparison: {before_path} vs {after_path}")

        # Load both images
        before_data, before_meta = self._load_raster(before_path)
        after_data, after_meta = self._load_raster(after_path)

        # Calculate common bounds
        bounds = self._get_bounds(before_meta)
        center = self._get_center(bounds)

        # Calculate common value range
        vmin = float(min(np.nanmin(before_data), np.nanmin(after_data)))
        vmax = float(max(np.nanmax(before_data), np.nanmax(after_data)))

        # Generate colored images
        before_colored = self._apply_colormap(before_data, colormap, vmin, vmax)
        after_colored = self._apply_colormap(after_data, colormap, vmin, vmax)

        # Encode as base64
        before_b64 = self._encode_image(before_colored)
        after_b64 = self._encode_image(after_colored)

        return {
            "type": "comparison_slider",
            "spec": {
                "title": title,
                "center": center,
                "zoom": 12,
                "before": {
                    "label": "Before",
                    "bounds": bounds,
                    "source": before_path,
                    "url": f"data:image/png;base64,{before_b64}"
                },
                "after": {
                    "label": "After",
                    "bounds": bounds,
                    "source": after_path,
                    "url": f"data:image/png;base64,{after_b64}"
                },
                "colorbar": {
                    "min": vmin,
                    "max": vmax,
                    "colormap": colormap
                },
                "initial_position": 50
            }
        }

    async def create_multi_layer_map(
        self,
        layers: List[Dict[str, Any]],
        title: str = "Multi-Layer View",
        center: Optional[List[float]] = None,
        zoom: int = 10
    ) -> Dict[str, Any]:
        """
        Create a map with multiple toggleable layers.

        Args:
            layers: List of layer specifications
            title: Map title
            center: Map center [lat, lon]
            zoom: Initial zoom level

        Returns:
            MCP-UI component specification
        """
        processed_layers = []
        all_bounds = []

        for layer_spec in layers:
            if layer_spec.get("type") == "raster" and "path" in layer_spec:
                data, metadata = self._load_raster(layer_spec["path"])
                bounds = self._get_bounds(metadata)
                all_bounds.append(bounds)

                colormap = layer_spec.get("colormap", self.default_colormap)
                vmin = layer_spec.get("vmin", float(np.nanmin(data)))
                vmax = layer_spec.get("vmax", float(np.nanmax(data)))

                colored = self._apply_colormap(data, colormap, vmin, vmax)
                image_data = self._encode_image(colored)

                processed_layers.append({
                    "type": "image",
                    "name": layer_spec.get("name", "Layer"),
                    "bounds": bounds,
                    "url": f"data:image/png;base64,{image_data}",
                    "opacity": layer_spec.get("opacity", 0.8),
                    "visible": layer_spec.get("visible", True)
                })
            else:
                processed_layers.append(layer_spec)

        # Calculate center from bounds if not provided
        if center is None and all_bounds:
            center = self._get_center(all_bounds[0])

        return {
            "type": "map",
            "spec": {
                "title": title,
                "center": center or [0, 0],
                "zoom": zoom,
                "layers": processed_layers,
                "layerControl": True,
                "controls": ["zoom", "scale", "fullscreen", "layers"]
            }
        }

    def _load_raster(self, path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Load raster data from GeoTIFF."""
        try:
            import rasterio

            with rasterio.open(path) as src:
                data = src.read(1)  # Read first band
                metadata = {
                    "crs": str(src.crs),
                    "transform": list(src.transform),
                    "bounds": list(src.bounds),
                    "width": src.width,
                    "height": src.height
                }

            return data, metadata

        except ImportError:
            logger.warning("rasterio not available, using fallback")
            return self._load_raster_fallback(path)

    def _load_raster_fallback(self, path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Fallback raster loader using PIL."""
        from PIL import Image

        img = Image.open(path)
        data = np.array(img)

        if data.ndim == 3:
            data = data[:, :, 0]  # Use first channel

        # Assume WGS84 and small region if no georef
        metadata = {
            "bounds": [0, 0, 1, 1],  # Default bounds
            "width": data.shape[1],
            "height": data.shape[0]
        }

        return data, metadata

    def _get_bounds(self, metadata: Dict[str, Any]) -> List[List[float]]:
        """Extract bounds as [[south, west], [north, east]]."""
        if "bounds" in metadata:
            b = metadata["bounds"]
            return [[b[1], b[0]], [b[3], b[2]]]  # [minlat, minlon], [maxlat, maxlon]
        return [[0, 0], [1, 1]]

    def _get_center(self, bounds: List[List[float]]) -> List[float]:
        """Calculate center from bounds."""
        lat = (bounds[0][0] + bounds[1][0]) / 2
        lon = (bounds[0][1] + bounds[1][1]) / 2
        return [lat, lon]

    def _apply_colormap(
        self,
        data: np.ndarray,
        colormap: str,
        vmin: float,
        vmax: float
    ) -> np.ndarray:
        """Apply colormap to data array."""
        colors = COLORMAPS.get(colormap, COLORMAPS["viridis"])

        # Normalize data to 0-1
        normalized = np.clip((data - vmin) / (vmax - vmin + 1e-10), 0, 1)

        # Handle NaN values
        mask = np.isnan(data)
        normalized[mask] = 0

        # Interpolate colors
        n_colors = len(colors)
        indices = normalized * (n_colors - 1)
        lower_idx = np.floor(indices).astype(int)
        upper_idx = np.ceil(indices).astype(int)
        frac = indices - lower_idx

        # Clamp indices
        lower_idx = np.clip(lower_idx, 0, n_colors - 1)
        upper_idx = np.clip(upper_idx, 0, n_colors - 1)

        # Interpolate RGB
        result = np.zeros((*data.shape, 4), dtype=np.uint8)

        for c in range(3):
            lower_colors = np.array([colors[i][c] for i in range(n_colors)])
            upper_colors = np.array([colors[i][c] for i in range(n_colors)])

            lower_vals = lower_colors[lower_idx]
            upper_vals = upper_colors[upper_idx]

            result[:, :, c] = (lower_vals * (1 - frac) + upper_vals * frac).astype(np.uint8)

        # Alpha channel (transparent for NaN)
        result[:, :, 3] = 255
        result[mask, 3] = 0

        return result

    def _encode_image(self, rgba_array: np.ndarray) -> str:
        """Encode RGBA array as base64 PNG."""
        from PIL import Image
        import io

        img = Image.fromarray(rgba_array, mode="RGBA")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return base64.b64encode(buffer.read()).decode("utf-8")

    def _create_legend(
        self,
        colormap: str,
        vmin: float,
        vmax: float
    ) -> Dict[str, Any]:
        """Create legend specification."""
        colors = COLORMAPS.get(colormap, COLORMAPS["viridis"])

        return {
            "type": "gradient",
            "title": "Value",
            "colors": [f"rgb({c[0]},{c[1]},{c[2]})" for c in colors],
            "labels": [
                f"{vmin:.2f}",
                f"{(vmin + vmax) / 2:.2f}",
                f"{vmax:.2f}"
            ]
        }
