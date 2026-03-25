# ABOUTME: Algorithm package for OpenEO AI Assistant.
# Provides modular, reusable algorithm implementations for EO analysis.

"""
Algorithm package for OpenEO AI.

Provides:
- BaseAlgorithm class for creating new algorithms
- AlgorithmRegistry for discovering and loading algorithms
- Pre-built indices (NDVI, EVI, NDWI, etc.)
"""

from .base.loader import BaseAlgorithm, AlgorithmParameter, AlgorithmMetadata
from .base.registry import AlgorithmRegistry, get_algorithm_registry

__all__ = [
    "BaseAlgorithm",
    "AlgorithmParameter",
    "AlgorithmMetadata",
    "AlgorithmRegistry",
    "get_algorithm_registry",
]
