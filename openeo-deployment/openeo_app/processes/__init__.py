"""Custom process implementations for OpenEO.

This module provides:
- load_collection: STAC-based data loading with band mapping and optimized chunking
- Math fixes: Numerically stable operations (NDVI, division, etc.)
- Band mapping: Collection-specific band name translation
- Chunking strategies: Optimized chunk sizes per collection
"""

from openeo_app.processes.load_collection import (
    load_collection,
    register_collection,
    get_available_collections,
    get_collection_stac_url,
)

from openeo_app.processes.math_fixes import (
    normalized_difference_stable,
    divide_safe,
    apply_scale_factor,
    STABLE_PROCESSES,
)

from openeo_app.processes.band_mapper import (
    BandMapper,
    get_mapper_for_collection,
    get_scale_factor,
    get_offset,
)

from openeo_app.processes.chunking import (
    ChunkingStrategy,
    ChunkConfiguration,
    get_chunks_for_collection,
)

__all__ = [
    # Data loading
    "load_collection",
    "register_collection",
    "get_available_collections",
    "get_collection_stac_url",
    # Math fixes
    "normalized_difference_stable",
    "divide_safe",
    "apply_scale_factor",
    "STABLE_PROCESSES",
    # Band mapping
    "BandMapper",
    "get_mapper_for_collection",
    "get_scale_factor",
    "get_offset",
    # Chunking
    "ChunkingStrategy",
    "ChunkConfiguration",
    "get_chunks_for_collection",
]
