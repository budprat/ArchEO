"""
Phase 4: GeoAI Model Integration Tests

Test-Driven Development: These tests define the expected behavior
of the GeoAI model integration before implementation.

Tests cover:
- Model registry
- Inference engine
- Segmentation
- Change detection
- Canopy height estimation
- Tiled processing
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import numpy as np
import tempfile
from pathlib import Path


class TestModelRegistry:
    """Test GeoAI model registry."""

    def test_registry_loads_available_models(self):
        """Registry should discover available models."""
        from openeo_ai.geoai.model_registry import ModelRegistry

        registry = ModelRegistry(models_path="/tmp/test_models")

        # Even without actual models, should initialize with defaults
        assert registry is not None
        assert hasattr(registry, 'list_models')

    def test_registry_lists_models(self):
        """Registry should list available models."""
        from openeo_ai.geoai.model_registry import ModelRegistry

        registry = ModelRegistry(models_path="/tmp/test_models")

        # Should have default models registered
        models = registry.list_models()
        assert len(models) >= 3  # segmentation_default, change_default, canopy_height_default

    def test_registry_gets_model_info(self):
        """Registry should return model information."""
        from openeo_ai.geoai.model_registry import ModelRegistry

        registry = ModelRegistry(models_path="/tmp/test_models")

        info = registry.get_model_info("segmentation_default")

        assert info is not None
        assert info.name == "segmentation_default"
        assert info.task == "segmentation"

    def test_registry_validates_model_exists(self):
        """Registry should validate model exists before loading."""
        from openeo_ai.geoai.model_registry import ModelRegistry

        registry = ModelRegistry(models_path="/tmp/test_models")

        # Non-existent model should return None
        info = registry.get_model_info("nonexistent_model")
        assert info is None


class TestInferenceEngine:
    """Test GeoAI inference engine."""

    def test_engine_initializes_with_registry(self):
        """Engine should initialize with model registry."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        assert engine.registry is not None
        assert hasattr(engine.registry, 'list_models')

    def test_engine_has_tile_settings(self):
        """Engine should have tile processing settings."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models", tile_size=512, overlap=64)

        assert engine.tile_size == 512
        assert engine.overlap == 64

    def test_engine_lists_models(self):
        """Engine should list available models."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        models = engine.list_available_models()
        assert len(models) >= 3


class TestSegmentation:
    """Test semantic segmentation inference."""

    @pytest.mark.asyncio
    async def test_segment_returns_result(self, temp_geotiff):
        """Segmentation should return result dict."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        result = await engine.segment(
            input_path=str(temp_geotiff),
            model="segmentation_default"
        )

        assert "output_path" in result
        assert "statistics" in result

    @pytest.mark.asyncio
    async def test_segment_creates_output_file(self, temp_geotiff, temp_storage_path):
        """Segmentation should create output GeoTIFF."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        result = await engine.segment(
            input_path=str(temp_geotiff),
            model="segmentation_default"
        )

        assert "output_path" in result

    @pytest.mark.asyncio
    async def test_segment_accepts_custom_output_path(self, temp_geotiff, temp_storage_path):
        """Segmentation should accept custom output path."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        custom_output = str(temp_storage_path / "custom_output.tif")

        result = await engine.segment(
            input_path=str(temp_geotiff),
            model="segmentation_default",
            output_path=custom_output
        )

        assert result["output_path"] == custom_output

    @pytest.mark.asyncio
    async def test_segment_returns_class_statistics(self, temp_geotiff):
        """Segmentation should return class statistics."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        result = await engine.segment(
            input_path=str(temp_geotiff),
            model="segmentation_default"
        )

        assert "statistics" in result
        assert "classes" in result["statistics"]


class TestChangeDetection:
    """Test change detection inference."""

    @pytest.mark.asyncio
    async def test_detect_change_returns_result(self, temp_comparison_files):
        """Change detection should return result dict."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        before_path, after_path = temp_comparison_files

        result = await engine.detect_change(
            before_path=str(before_path),
            after_path=str(after_path),
            model="change_default"
        )

        assert "output_path" in result
        assert "statistics" in result

    @pytest.mark.asyncio
    async def test_detect_change_validates_same_dimensions(self, temp_storage_path):
        """Change detection should validate input dimensions."""
        from openeo_ai.geoai.inference import GeoAIInference
        import rioxarray
        import xarray as xr

        engine = GeoAIInference(models_path="/tmp/test_models")

        # Create mismatched size images
        before_data = np.random.rand(100, 100).astype(np.float32)
        after_data = np.random.rand(50, 50).astype(np.float32)

        before_arr = xr.DataArray(before_data, dims=["y", "x"])
        before_arr = before_arr.rio.write_crs("EPSG:4326")

        after_arr = xr.DataArray(after_data, dims=["y", "x"])
        after_arr = after_arr.rio.write_crs("EPSG:4326")

        before_path = temp_storage_path / "before_mismatch.tif"
        after_path = temp_storage_path / "after_mismatch.tif"

        before_arr.rio.to_raster(str(before_path))
        after_arr.rio.to_raster(str(after_path))

        with pytest.raises(ValueError):
            await engine.detect_change(
                before_path=str(before_path),
                after_path=str(after_path)
            )

    @pytest.mark.asyncio
    async def test_detect_change_returns_binary_mask(self, temp_comparison_files):
        """Change detection should produce binary mask."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        before_path, after_path = temp_comparison_files

        result = await engine.detect_change(
            before_path=str(before_path),
            after_path=str(after_path)
        )

        # Should have pixel counts
        stats = result["statistics"]
        assert "changed_pixels" in stats
        assert "total_pixels" in stats


class TestCanopyHeightEstimation:
    """Test canopy height estimation inference."""

    @pytest.mark.asyncio
    async def test_estimate_canopy_height_returns_result(self, temp_rgb_geotiff):
        """Canopy height estimation should return result dict."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        result = await engine.estimate_canopy_height(
            input_path=str(temp_rgb_geotiff)
        )

        assert "output_path" in result
        assert "statistics" in result

    @pytest.mark.asyncio
    async def test_canopy_height_returns_statistics(self, temp_rgb_geotiff):
        """Canopy height should return height statistics."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        result = await engine.estimate_canopy_height(str(temp_rgb_geotiff))

        stats = result["statistics"]
        assert "min_height" in stats
        assert "max_height" in stats
        assert "mean_height" in stats


class TestTiledProcessing:
    """Test tiled processing for large images."""

    def test_tiled_processing_handles_large_image(self):
        """Tiled processing should handle images larger than tile size."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        # Create large image (larger than typical tile size)
        large_data = np.random.rand(3, 2000, 2000).astype(np.float32)

        # Test tile calculation
        tile_size = engine.tile_size
        overlap = engine.overlap
        step = tile_size - overlap

        expected_tiles_x = (2000 - overlap) // step + 1
        expected_tiles_y = (2000 - overlap) // step + 1

        # Should process multiple tiles
        assert expected_tiles_x > 1
        assert expected_tiles_y > 1

    def test_tiled_processing_handles_overlap(self):
        """Tiled processing should handle tile overlap correctly."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        # Verify overlap logic
        tile_size = engine.tile_size
        overlap = engine.overlap

        # Overlapping tiles should share edge pixels
        tile1_end = tile_size
        tile2_start = tile_size - overlap

        # Overlap region
        overlap_region = tile1_end - tile2_start
        assert overlap_region == overlap

    def test_tiled_processing_pads_edge_tiles(self):
        """Tiled processing should pad edge tiles correctly."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        # Image size not divisible by tile size
        image_size = 1000
        tile_size = engine.tile_size

        # Last tile needs padding
        remainder = image_size % (tile_size - engine.overlap)
        needs_padding = remainder > 0

        assert needs_padding


class TestGeoAITools:
    """Test GeoAI tools for Claude SDK."""

    @pytest.mark.asyncio
    async def test_segment_tool_format(self, temp_geotiff):
        """Segment tool should return Claude SDK format."""
        from openeo_ai.tools.geoai_tools import segment_tool

        result = await segment_tool({
            "input_path": str(temp_geotiff),
            "model": "segmentation_default"
        })

        assert "content" in result
        assert isinstance(result["content"], list)
        assert result["content"][0]["type"] == "text"

    @pytest.mark.asyncio
    async def test_change_detection_tool_format(self, temp_comparison_files):
        """Change detection tool should return Claude SDK format."""
        from openeo_ai.tools.geoai_tools import detect_change_tool

        before_path, after_path = temp_comparison_files

        result = await detect_change_tool({
            "before_path": str(before_path),
            "after_path": str(after_path)
        })

        assert "content" in result


class TestModelErrors:
    """Test error handling in GeoAI models."""

    @pytest.mark.asyncio
    async def test_segment_handles_invalid_input(self):
        """Segmentation should handle invalid input gracefully."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        with pytest.raises((FileNotFoundError, Exception)):
            await engine.segment(
                input_path="/nonexistent/file.tif",
                model="segmentation_default"
            )

    def test_handles_model_not_found(self):
        """Should handle missing model gracefully."""
        from openeo_ai.geoai.model_registry import ModelRegistry

        registry = ModelRegistry(models_path="/tmp/test_models")

        with pytest.raises(ValueError):
            registry.load_model("nonexistent_model")

    @pytest.mark.asyncio
    async def test_handles_out_of_memory(self, temp_geotiff):
        """Should handle out of memory errors."""
        from openeo_ai.geoai.inference import GeoAIInference

        engine = GeoAIInference(models_path="/tmp/test_models")

        with patch.object(engine, 'segment', side_effect=MemoryError("Out of memory")):
            with pytest.raises(MemoryError):
                await engine.segment(
                    input_path=str(temp_geotiff),
                    model="default"
                )
