"""Tests for chunking strategies."""

import pytest

from openeo_app.processes.chunking import (
    ChunkingStrategy,
    ChunkConfiguration,
    get_chunks_for_collection,
    SENTINEL2_CONFIG,
    LANDSAT_CONFIG,
    MODIS_CONFIG,
    DEM_CONFIG,
    DEFAULT_CONFIG,
)


class TestChunkConfiguration:
    """Tests for ChunkConfiguration dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = ChunkConfiguration(time=3, x=2048, y=2048)

        result = config.to_dict()

        assert result == {"time": 3, "x": 2048, "y": 2048}

    def test_default_memory_estimate(self):
        """Test default memory estimate is set."""
        config = ChunkConfiguration(time=1, x=1024, y=1024)

        assert config.estimated_mb_per_chunk == 200.0


class TestChunkingStrategy:
    """Tests for ChunkingStrategy class."""

    def test_sentinel2_chunking(self):
        """Verify Sentinel-2 gets 2048x2048 spatial, 3 time chunks."""
        config = ChunkingStrategy.for_collection("sentinel-2-l2a", num_items=10)

        assert config.x == 2048
        assert config.y == 2048
        assert config.time == 3  # min(3, 10) = 3

    def test_landsat_chunking(self):
        """Verify Landsat gets 1024x1024 spatial, 2 time chunks."""
        config = ChunkingStrategy.for_collection("landsat-c2-l2", num_items=10)

        assert config.x == 1024
        assert config.y == 1024
        assert config.time == 2  # min(2, 10) = 2

    def test_modis_chunking(self):
        """Verify MODIS gets large spatial chunks."""
        config = ChunkingStrategy.for_collection("modis-something", num_items=10)

        assert config.x == 4096
        assert config.y == 4096
        assert config.time == 5

    def test_dem_chunking(self):
        """Verify DEM gets single time chunk (no temporal dimension)."""
        config = ChunkingStrategy.for_collection("cop-dem-glo-30", num_items=1)

        assert config.time == 1

    def test_time_capping(self):
        """Verify time chunks don't exceed item count."""
        # Sentinel-2 config has time=3, but we only have 2 items
        config = ChunkingStrategy.for_collection("sentinel-2-l2a", num_items=2)

        assert config.time == 2  # Capped to num_items

    def test_time_capping_single_item(self):
        """Verify time=1 for single item."""
        config = ChunkingStrategy.for_collection("sentinel-2-l2a", num_items=1)

        assert config.time == 1

    def test_unknown_collection_uses_default(self):
        """Verify unknown collection gets default config."""
        config = ChunkingStrategy.for_collection("unknown-collection", num_items=5)

        assert config.x == DEFAULT_CONFIG.x
        assert config.y == DEFAULT_CONFIG.y

    def test_case_insensitive_matching(self):
        """Verify collection matching is case-insensitive."""
        config1 = ChunkingStrategy.for_collection("SENTINEL-2-L2A", num_items=5)
        config2 = ChunkingStrategy.for_collection("sentinel-2-l2a", num_items=5)

        assert config1.x == config2.x
        assert config1.y == config2.y


class TestMemoryEstimation:
    """Tests for memory estimation."""

    def test_estimate_memory_usage(self):
        """Test memory estimation calculation."""
        config = ChunkConfiguration(time=1, x=1024, y=1024)

        # 1 time * 1024 * 1024 * 4 bands * 4 bytes = 16MB
        mb = ChunkingStrategy.estimate_memory_usage(config, num_bands=4)

        assert 15 < mb < 17  # ~16MB

    def test_estimate_sentinel2_memory(self):
        """Test Sentinel-2 chunk memory estimate."""
        # 3 time * 2048 * 2048 * 4 bands * 4 bytes
        mb = ChunkingStrategy.estimate_memory_usage(SENTINEL2_CONFIG, num_bands=4)

        # Should be around 192MB (3 * 2048 * 2048 * 4 * 4 / 1024 / 1024)
        assert 180 < mb < 210

    def test_get_optimal_workers(self):
        """Test optimal worker calculation."""
        config = ChunkConfiguration(time=1, x=1024, y=1024, estimated_mb_per_chunk=100)

        # Calculation depends on actual memory per chunk
        workers = ChunkingStrategy.get_optimal_workers(
            config, total_memory_mb=4096, num_bands=4
        )

        # Should return at least 1 worker
        assert workers >= 1
        # Should be a reasonable integer
        assert isinstance(workers, int)


class TestPreConfiguredConfigs:
    """Tests for pre-configured chunk configurations."""

    def test_sentinel2_config_values(self):
        """Test Sentinel-2 config values."""
        assert SENTINEL2_CONFIG.time == 3
        assert SENTINEL2_CONFIG.x == 2048
        assert SENTINEL2_CONFIG.y == 2048

    def test_landsat_config_values(self):
        """Test Landsat config values."""
        assert LANDSAT_CONFIG.time == 2
        assert LANDSAT_CONFIG.x == 1024
        assert LANDSAT_CONFIG.y == 1024

    def test_dem_config_single_time(self):
        """Test DEM config has single time slice."""
        assert DEM_CONFIG.time == 1


class TestConvenienceFunction:
    """Tests for get_chunks_for_collection convenience function."""

    def test_returns_dict(self):
        """Test function returns dictionary."""
        chunks = get_chunks_for_collection("sentinel-2-l2a", num_items=5)

        assert isinstance(chunks, dict)
        assert "time" in chunks
        assert "x" in chunks
        assert "y" in chunks

    def test_correct_values(self):
        """Test function returns correct values."""
        chunks = get_chunks_for_collection("sentinel-2-l2a", num_items=5)

        assert chunks["x"] == 2048
        assert chunks["y"] == 2048
        assert chunks["time"] == 3
