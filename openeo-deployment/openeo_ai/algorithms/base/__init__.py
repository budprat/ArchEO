# ABOUTME: Base classes for algorithm implementations.
# Provides BaseAlgorithm and AlgorithmRegistry for modular algorithm design.

"""Base algorithm classes."""

from .loader import BaseAlgorithm, AlgorithmParameter, AlgorithmMetadata
from .registry import AlgorithmRegistry, get_algorithm_registry

__all__ = [
    "BaseAlgorithm",
    "AlgorithmParameter",
    "AlgorithmMetadata",
    "AlgorithmRegistry",
    "get_algorithm_registry",
]
