# ABOUTME: Vegetation and water indices algorithms.
# Provides NDVI, EVI, NDWI, and other spectral indices.

"""
Spectral indices for remote sensing analysis.

Available indices:
- NDVI: Normalized Difference Vegetation Index
- EVI: Enhanced Vegetation Index
- NDWI: Normalized Difference Water Index
- NDMI: Normalized Difference Moisture Index
- SAVI: Soil Adjusted Vegetation Index
"""

from .ndvi import NDVIAlgorithm
from .evi import EVIAlgorithm
from .ndwi import NDWIAlgorithm

__all__ = [
    "NDVIAlgorithm",
    "EVIAlgorithm",
    "NDWIAlgorithm",
]
