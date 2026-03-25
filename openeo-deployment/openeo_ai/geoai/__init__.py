# ABOUTME: GeoAI module providing AI analysis for Earth Observation data.
# Includes inference engine and model registry for segmentation, change detection, canopy height.

"""
GeoAI module for OpenEO AI Assistant.

Provides AI-powered analysis tools for Earth Observation data:
- Semantic segmentation
- Change detection
- Canopy height estimation
"""

from .inference import GeoAIInference
from .model_registry import ModelRegistry

__all__ = [
    "GeoAIInference",
    "ModelRegistry",
]
