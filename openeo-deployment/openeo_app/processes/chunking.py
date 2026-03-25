"""Collection-specific chunking strategies for optimized data loading.

Different satellite collections have different optimal chunk sizes based on:
- Native resolution (10m for Sentinel-2, 30m for Landsat)
- Typical file sizes and cloud-optimized GeoTIFF tile sizes
- Memory constraints for Dask workers
- Network efficiency (fewer, larger chunks = fewer HTTP requests)

Using optimized chunks can reduce network requests by 16x or more compared
to default small chunks.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChunkConfiguration:
    """Configuration for Dask chunking.

    Attributes:
        time: Number of time slices per chunk
        x: Number of pixels in x dimension per chunk
        y: Number of pixels in y dimension per chunk
        estimated_mb_per_chunk: Estimated memory per chunk (for 4-band float32)
    """
    time: int
    x: int
    y: int
    estimated_mb_per_chunk: float = 200.0

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for odc.stac.load()."""
        return {
            "time": self.time,
            "x": self.x,
            "y": self.y,
        }


# Pre-configured chunk sizes for different collections
# These are tuned for typical use cases and memory constraints

SENTINEL2_CONFIG = ChunkConfiguration(
    time=3,
    x=2048,
    y=2048,
    estimated_mb_per_chunk=400.0,  # ~400MB for 4 bands
)
"""Sentinel-2 chunks: 2048x2048 spatial (~20km at 10m), 3 time slices.
This is 16x fewer requests than 512x512 chunks."""

LANDSAT_CONFIG = ChunkConfiguration(
    time=2,
    x=1024,
    y=1024,
    estimated_mb_per_chunk=200.0,
)
"""Landsat chunks: 1024x1024 spatial (~30km at 30m), 2 time slices.
Optimized for 30m resolution data."""

MODIS_CONFIG = ChunkConfiguration(
    time=5,
    x=4096,
    y=4096,
    estimated_mb_per_chunk=300.0,
)
"""MODIS chunks: 4096x4096 spatial, 5 time slices.
Larger coverage appropriate for lower-resolution data."""

DEM_CONFIG = ChunkConfiguration(
    time=1,
    x=2048,
    y=2048,
    estimated_mb_per_chunk=32.0,
)
"""DEM chunks: 2048x2048 spatial, no time dimension.
Single-band elevation data."""

DEFAULT_CONFIG = ChunkConfiguration(
    time=1,
    x=1024,
    y=1024,
    estimated_mb_per_chunk=200.0,
)
"""Default chunks for unknown collections."""


class ChunkingStrategy:
    """Factory for collection-specific chunk configurations.

    Example usage:
        chunks = ChunkingStrategy.for_collection("sentinel-2-l2a", num_items=5)
        load_params["chunks"] = chunks.to_dict()
    """

    # Collection patterns to configurations
    COLLECTION_CONFIGS = {
        "sentinel-2": SENTINEL2_CONFIG,
        "sentinel2": SENTINEL2_CONFIG,
        "landsat": LANDSAT_CONFIG,
        "modis": MODIS_CONFIG,
        "cop-dem": DEM_CONFIG,
        "dem": DEM_CONFIG,
    }

    @classmethod
    def for_collection(
        cls,
        collection_id: str,
        num_items: int = 1,
        max_memory_mb: Optional[float] = None,
    ) -> ChunkConfiguration:
        """Get optimized chunk configuration for a collection.

        Args:
            collection_id: Collection identifier (e.g., "sentinel-2-l2a")
            num_items: Number of STAC items being loaded (for time capping)
            max_memory_mb: Optional maximum memory per chunk in MB

        Returns:
            ChunkConfiguration optimized for the collection
        """
        collection_lower = collection_id.lower()

        # Find matching configuration
        config = None
        for pattern, cfg in cls.COLLECTION_CONFIGS.items():
            if pattern in collection_lower:
                config = cfg
                break

        if config is None:
            config = DEFAULT_CONFIG
            logger.info(
                f"No specific chunking for '{collection_id}', using default"
            )

        # Cap time chunks to not exceed number of items
        # (Dask doesn't like chunks larger than the dimension)
        time_chunks = min(config.time, num_items) if num_items > 0 else config.time

        # Create adjusted configuration
        result = ChunkConfiguration(
            time=time_chunks,
            x=config.x,
            y=config.y,
            estimated_mb_per_chunk=config.estimated_mb_per_chunk,
        )

        logger.info(
            f"Chunking for {collection_id}: "
            f"time={result.time}, x={result.x}, y={result.y}"
        )

        return result

    @classmethod
    def estimate_memory_usage(
        cls,
        config: ChunkConfiguration,
        num_bands: int = 4,
        dtype_size: int = 4,  # float32 = 4 bytes
    ) -> float:
        """Estimate memory usage per chunk in MB.

        Args:
            config: Chunk configuration
            num_bands: Number of bands being loaded
            dtype_size: Size of data type in bytes (4 for float32)

        Returns:
            Estimated memory per chunk in MB
        """
        pixels_per_chunk = config.time * config.x * config.y * num_bands
        bytes_per_chunk = pixels_per_chunk * dtype_size
        mb_per_chunk = bytes_per_chunk / (1024 * 1024)
        return mb_per_chunk

    @classmethod
    def get_optimal_workers(
        cls,
        config: ChunkConfiguration,
        total_memory_mb: float = 4096,  # 4GB default
        num_bands: int = 4,
    ) -> int:
        """Calculate optimal number of Dask workers based on memory.

        Args:
            config: Chunk configuration
            total_memory_mb: Total available memory in MB
            num_bands: Number of bands

        Returns:
            Recommended number of workers
        """
        mb_per_chunk = cls.estimate_memory_usage(config, num_bands)
        # Leave 20% headroom
        usable_memory = total_memory_mb * 0.8
        workers = max(1, int(usable_memory / mb_per_chunk))
        return workers


def get_chunks_for_collection(
    collection_id: str,
    num_items: int = 1,
) -> Dict[str, int]:
    """Convenience function to get chunk dict for a collection.

    Args:
        collection_id: Collection identifier
        num_items: Number of STAC items

    Returns:
        Dictionary suitable for odc.stac.load(chunks=...)
    """
    config = ChunkingStrategy.for_collection(collection_id, num_items)
    return config.to_dict()
