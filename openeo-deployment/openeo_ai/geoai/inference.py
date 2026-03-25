# ABOUTME: GeoAI inference engine with tiled processing support.
# Runs segmentation, change detection, and canopy height estimation on satellite imagery.

"""
GeoAI inference engine for OpenEO AI Assistant.

Provides high-level API for running AI inference on Earth Observation data
with support for tiled processing and multi-format output.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

import numpy as np

from .model_registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Result from GeoAI inference."""
    output_path: Optional[str]
    statistics: Dict[str, Any]
    metadata: Dict[str, Any]


class GeoAIInference:
    """
    High-level inference engine for GeoAI tasks.

    Supports:
    - Semantic segmentation
    - Change detection
    - Canopy height estimation

    Features:
    - Tiled processing for large images
    - Automatic preprocessing
    - Multiple output formats
    """

    def __init__(
        self,
        models_path: Optional[str] = None,
        tile_size: int = 256,
        overlap: int = 32
    ):
        """
        Initialize inference engine.

        Args:
            models_path: Path to directory containing model files
            tile_size: Size of tiles for processing large images
            overlap: Overlap between adjacent tiles
        """
        self.registry = ModelRegistry(models_path)
        self.tile_size = tile_size
        self.overlap = overlap

        logger.info(
            f"GeoAIInference initialized with tile_size={tile_size}, "
            f"overlap={overlap}"
        )

    async def segment(
        self,
        input_path: str,
        model: str = "segmentation_default",
        output_path: Optional[str] = None,
        output_format: str = "GeoTiff"
    ) -> Dict[str, Any]:
        """
        Run semantic segmentation on input image.

        Args:
            input_path: Path to input GeoTIFF
            model: Model name
            output_path: Optional output path
            output_format: Output format (GeoTiff, PNG)

        Returns:
            Result dictionary with output path and statistics
        """
        logger.info(f"Running segmentation on {input_path} with model {model}")

        # Load model
        ml_model = self.registry.load_model(model)
        model_info = self.registry.get_model_info(model)

        # Load and preprocess input
        data, metadata = self._load_geotiff(input_path)

        # Run tiled inference
        predictions = await self._tiled_inference(data, ml_model, model_info)

        # Compute statistics
        class_labels = model_info.output_classes or [f"class_{i}" for i in range(int(predictions.max()) + 1)]
        stats = self._compute_segmentation_stats(predictions, class_labels)

        # Save output
        if output_path is None:
            p = Path(input_path)
            output_path = str(p.parent / f"{p.stem}_segmented.tif")

        self._save_result(predictions, output_path, metadata, output_format)

        return {
            "output_path": output_path,
            "classes": class_labels,
            "statistics": stats,
            "metadata": {
                "model": model,
                "input_path": input_path,
                "tile_size": self.tile_size
            }
        }

    async def detect_change(
        self,
        before_path: str,
        after_path: str,
        model: str = "change_default",
        output_path: Optional[str] = None,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Detect changes between two images.

        Args:
            before_path: Path to before image
            after_path: Path to after image
            model: Model name
            output_path: Optional output path
            threshold: Change detection threshold

        Returns:
            Result dictionary with change statistics
        """
        logger.info(f"Running change detection: {before_path} -> {after_path}")

        # Load model
        ml_model = self.registry.load_model(model)
        model_info = self.registry.get_model_info(model)

        # Load both images
        before_data, before_meta = self._load_geotiff(before_path)
        after_data, after_meta = self._load_geotiff(after_path)

        # Validate dimensions match
        if before_data.shape != after_data.shape:
            raise ValueError(
                f"Image dimensions must match: {before_data.shape} vs {after_data.shape}"
            )

        # Stack images for bi-temporal model
        stacked = np.concatenate([before_data, after_data], axis=0)

        # Run tiled inference
        change_probs = await self._tiled_inference(stacked, ml_model, model_info)

        # Apply threshold
        change_mask = change_probs > threshold

        # Compute statistics
        total_pixels = change_mask.size
        changed_pixels = change_mask.sum()
        change_percent = (changed_pixels / total_pixels) * 100

        # Save output
        if output_path is None:
            p = Path(before_path)
            output_path = str(p.parent / f"{p.stem}_change.tif")

        self._save_result(change_mask.astype(np.uint8), output_path, before_meta, "GeoTiff")

        return {
            "output_path": output_path,
            "statistics": {
                "total_pixels": int(total_pixels),
                "changed_pixels": int(changed_pixels),
                "change_percent": round(change_percent, 2),
                "threshold": threshold
            },
            "metadata": {
                "model": model,
                "before_path": before_path,
                "after_path": after_path
            }
        }

    async def estimate_canopy_height(
        self,
        input_path: str,
        model: str = "canopy_height_default",
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Estimate canopy height from RGB imagery.

        Args:
            input_path: Path to input GeoTIFF
            model: Model name
            output_path: Optional output path

        Returns:
            Result dictionary with height statistics
        """
        logger.info(f"Estimating canopy height from {input_path}")

        # Load model
        ml_model = self.registry.load_model(model)
        model_info = self.registry.get_model_info(model)

        # Load and preprocess input
        data, metadata = self._load_geotiff(input_path)

        # Ensure we have RGB bands
        if data.shape[0] < 3:
            raise ValueError("Canopy height estimation requires at least RGB bands")

        # Use only RGB
        rgb_data = data[:3]

        # Run tiled inference
        heights = await self._tiled_inference(rgb_data, ml_model, model_info)

        # Compute statistics
        valid_heights = heights[heights > 0]
        stats = {
            "min_height": float(valid_heights.min()) if len(valid_heights) > 0 else 0,
            "max_height": float(valid_heights.max()) if len(valid_heights) > 0 else 0,
            "mean_height": float(valid_heights.mean()) if len(valid_heights) > 0 else 0,
            "std_height": float(valid_heights.std()) if len(valid_heights) > 0 else 0,
            "coverage_percent": round(len(valid_heights) / heights.size * 100, 2)
        }

        # Save output
        if output_path is None:
            p = Path(input_path)
            output_path = str(p.parent / f"{p.stem}_height.tif")

        self._save_result(heights, output_path, metadata, "GeoTiff")

        return {
            "output_path": output_path,
            "statistics": stats,
            "metadata": {
                "model": model,
                "input_path": input_path,
                "unit": "meters"
            }
        }

    async def _tiled_inference(
        self,
        data: np.ndarray,
        model: Any,
        model_info: Any
    ) -> np.ndarray:
        """
        Run inference on tiles with overlap handling.

        Args:
            data: Input data array (C, H, W)
            model: Loaded model
            model_info: Model metadata

        Returns:
            Output predictions
        """
        _, height, width = data.shape
        tile_size = self.tile_size
        overlap = self.overlap
        step = tile_size - overlap

        # Initialize output
        output_shape = (height, width)
        output = np.zeros(output_shape, dtype=np.float32)
        counts = np.zeros(output_shape, dtype=np.float32)

        # Process tiles
        for y in range(0, height, step):
            for x in range(0, width, step):
                # Extract tile
                y_end = min(y + tile_size, height)
                x_end = min(x + tile_size, width)
                tile = data[:, y:y_end, x:x_end]

                # Pad if necessary
                if tile.shape[1] < tile_size or tile.shape[2] < tile_size:
                    padded = np.zeros(
                        (data.shape[0], tile_size, tile_size),
                        dtype=tile.dtype
                    )
                    padded[:, :tile.shape[1], :tile.shape[2]] = tile
                    tile = padded

                # Preprocess
                tile_normalized = self._preprocess_tile(tile)

                # Run inference
                pred = model.predict(tile_normalized)

                # Handle output shape
                if pred.ndim > 2:
                    pred = pred.squeeze()
                if pred.ndim > 2:
                    pred = np.argmax(pred, axis=0)

                # Accumulate predictions
                pred_h, pred_w = y_end - y, x_end - x
                output[y:y_end, x:x_end] += pred[:pred_h, :pred_w]
                counts[y:y_end, x:x_end] += 1

        # Average overlapping regions
        counts[counts == 0] = 1
        output = output / counts

        return output

    def _preprocess_tile(self, tile: np.ndarray) -> np.ndarray:
        """Preprocess tile for model input."""
        # Normalize to 0-1
        if tile.max() > 1:
            tile = tile.astype(np.float32) / 255.0

        return tile

    def _load_geotiff(self, path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Load GeoTIFF file.

        Args:
            path: Path to GeoTIFF

        Returns:
            Tuple of (data array, metadata dict)
        """
        try:
            import rasterio

            with rasterio.open(path) as src:
                data = src.read()
                metadata = {
                    "crs": str(src.crs),
                    "transform": list(src.transform),
                    "bounds": list(src.bounds),
                    "width": src.width,
                    "height": src.height,
                    "count": src.count,
                    "dtype": str(src.dtypes[0])
                }

            return data, metadata

        except ImportError:
            logger.warning("rasterio not available, using fallback loader")
            return self._load_geotiff_fallback(path)

    def _load_geotiff_fallback(self, path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Fallback GeoTIFF loader using PIL/numpy."""
        from PIL import Image

        img = Image.open(path)
        data = np.array(img)

        # Ensure (C, H, W) format
        if data.ndim == 2:
            data = np.expand_dims(data, 0)
        elif data.ndim == 3 and data.shape[-1] in [3, 4]:
            data = np.transpose(data, (2, 0, 1))

        metadata = {
            "width": data.shape[-1],
            "height": data.shape[-2],
            "count": data.shape[0],
            "dtype": str(data.dtype)
        }

        return data, metadata

    def _save_result(
        self,
        data: np.ndarray,
        path: str,
        metadata: Dict[str, Any],
        format: str
    ) -> None:
        """
        Save inference result.

        Args:
            data: Result data array
            path: Output path
            metadata: Geospatial metadata
            format: Output format
        """
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if format.lower() in ["geotiff", "gtiff", "tiff", "tif"]:
            self._save_geotiff(data, path, metadata)
        elif format.lower() == "png":
            self._save_png(data, path)
        else:
            raise ValueError(f"Unsupported output format: {format}")

    def _save_geotiff(
        self,
        data: np.ndarray,
        path: str,
        metadata: Dict[str, Any]
    ) -> None:
        """Save as GeoTIFF with metadata."""
        try:
            import rasterio
            from rasterio.transform import Affine

            # Ensure 3D
            if data.ndim == 2:
                data = np.expand_dims(data, 0)

            # Get transform
            transform = None
            if "transform" in metadata:
                transform = Affine(*metadata["transform"][:6])

            # Get CRS
            crs = metadata.get("crs", "EPSG:4326")

            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=data.shape[-2],
                width=data.shape[-1],
                count=data.shape[0],
                dtype=data.dtype,
                crs=crs,
                transform=transform
            ) as dst:
                dst.write(data)

            logger.info(f"Saved GeoTIFF: {path}")

        except ImportError:
            logger.warning("rasterio not available, saving without geospatial metadata")
            self._save_geotiff_fallback(data, path)

    def _save_geotiff_fallback(self, data: np.ndarray, path: str) -> None:
        """Fallback GeoTIFF saver using PIL."""
        from PIL import Image

        # Convert to 2D if single band
        if data.ndim == 3 and data.shape[0] == 1:
            data = data.squeeze()

        # Convert to uint8 for PIL
        if data.dtype != np.uint8:
            data = (data * 255).astype(np.uint8)

        img = Image.fromarray(data)
        img.save(path)
        logger.info(f"Saved TIFF (no georef): {path}")

    def _save_png(self, data: np.ndarray, path: str) -> None:
        """Save as PNG."""
        from PIL import Image

        # Convert to 2D if single band
        if data.ndim == 3 and data.shape[0] == 1:
            data = data.squeeze()

        # Normalize to 0-255
        if data.max() <= 1:
            data = (data * 255)

        data = data.astype(np.uint8)

        img = Image.fromarray(data)
        img.save(path)
        logger.info(f"Saved PNG: {path}")

    def _compute_segmentation_stats(
        self,
        predictions: np.ndarray,
        class_labels: List[str]
    ) -> Dict[str, Any]:
        """Compute class-wise statistics for segmentation output."""
        total_pixels = predictions.size
        stats = {"total_pixels": int(total_pixels)}

        class_stats = {}
        for i, label in enumerate(class_labels):
            count = int((predictions == i).sum())
            percent = round(count / total_pixels * 100, 2)
            class_stats[label] = {
                "pixels": count,
                "percent": percent
            }

        stats["classes"] = class_stats
        return stats

    def list_available_models(self, task: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available models.

        Args:
            task: Filter by task type

        Returns:
            List of model info dictionaries
        """
        models = self.registry.list_models(task)
        return [
            {
                "name": m.name,
                "task": m.task,
                "version": m.version,
                "description": m.description,
                "loaded": m.loaded
            }
            for m in models
        ]
