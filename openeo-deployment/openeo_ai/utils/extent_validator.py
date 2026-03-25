# ABOUTME: Extent validation and size estimation for OpenEO queries.
# Warns users about large data requests and suggests optimizations.

"""
Extent validation utilities for OpenEO AI Assistant.

Provides size estimation, cost warnings, and optimization suggestions
for spatial and temporal extents in EO data queries.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger(__name__)


# Collection resolution metadata (meters)
COLLECTION_RESOLUTIONS = {
    "sentinel-2-l2a": 10,
    "sentinel-2-l1c": 10,
    "landsat-c2-l2": 30,
    "sentinel-1-grd": 10,
    "cop-dem-glo-30": 30,
    "cop-dem-glo-90": 90,
}

# Collection band counts
COLLECTION_BANDS = {
    "sentinel-2-l2a": 13,
    "sentinel-2-l1c": 13,
    "landsat-c2-l2": 7,
    "sentinel-1-grd": 2,
    "cop-dem-glo-30": 1,
    "cop-dem-glo-90": 1,
}

# Typical revisit times (days)
COLLECTION_REVISIT = {
    "sentinel-2-l2a": 5,
    "sentinel-2-l1c": 5,
    "landsat-c2-l2": 16,
    "sentinel-1-grd": 6,
    "cop-dem-glo-30": None,  # Static
    "cop-dem-glo-90": None,  # Static
}

# Size thresholds (bytes)
SIZE_THRESHOLDS = {
    "info": 100 * 1024 * 1024,       # 100 MB
    "warning": 1024 * 1024 * 1024,    # 1 GB
    "error": 10 * 1024 * 1024 * 1024, # 10 GB
}


@dataclass
class ExtentEstimate:
    """Estimated size and characteristics of a data request."""

    # Spatial
    width_km: float
    height_km: float
    area_km2: float
    pixel_width: int
    pixel_height: int
    total_pixels: int

    # Temporal
    days_span: int
    estimated_scenes: int

    # Data size
    bytes_per_scene: int
    total_bytes: int
    total_mb: float
    total_gb: float

    # Warnings
    severity: str  # "ok", "info", "warning", "error"
    warnings: List[str]
    suggestions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "spatial": {
                "width_km": round(self.width_km, 2),
                "height_km": round(self.height_km, 2),
                "area_km2": round(self.area_km2, 2),
                "pixels": f"{self.pixel_width} x {self.pixel_height}",
                "total_pixels": f"{self.total_pixels:,}",
            },
            "temporal": {
                "days_span": self.days_span,
                "estimated_scenes": self.estimated_scenes,
            },
            "size": {
                "mb": round(self.total_mb, 2),
                "gb": round(self.total_gb, 3),
                "human": self._human_readable_size(self.total_bytes),
            },
            "severity": self.severity,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }

    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"


class ExtentValidator:
    """Validates and estimates data size for EO queries."""

    def __init__(self):
        """Initialize extent validator."""
        self.resolutions = COLLECTION_RESOLUTIONS
        self.band_counts = COLLECTION_BANDS
        self.revisit_times = COLLECTION_REVISIT
        self.thresholds = SIZE_THRESHOLDS

    def estimate_size(
        self,
        spatial_extent: Dict[str, float],
        temporal_extent: Optional[List[str]] = None,
        collection: str = "sentinel-2-l2a",
        bands: Optional[List[str]] = None,
        output_format: str = "GTiff"
    ) -> ExtentEstimate:
        """
        Estimate the size of a data request.

        Args:
            spatial_extent: Bounding box {west, south, east, north}
            temporal_extent: [start_date, end_date] ISO strings
            collection: Collection ID
            bands: List of bands (None = all)
            output_format: Output format

        Returns:
            ExtentEstimate with size info and warnings
        """
        warnings = []
        suggestions = []

        # Get collection metadata
        resolution = self.resolutions.get(collection, 10)
        total_bands = self.band_counts.get(collection, 1)
        revisit = self.revisit_times.get(collection)

        # Calculate spatial dimensions
        west = spatial_extent.get("west", 0)
        east = spatial_extent.get("east", 0)
        south = spatial_extent.get("south", 0)
        north = spatial_extent.get("north", 0)

        # Width and height in degrees
        width_deg = abs(east - west)
        height_deg = abs(north - south)

        # Convert to kilometers (approximate at mid-latitude)
        mid_lat = (south + north) / 2
        import math
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * math.cos(math.radians(mid_lat))

        width_km = width_deg * km_per_deg_lon
        height_km = height_deg * km_per_deg_lat
        area_km2 = width_km * height_km

        # Calculate pixels
        width_m = width_km * 1000
        height_m = height_km * 1000
        pixel_width = int(width_m / resolution)
        pixel_height = int(height_m / resolution)
        total_pixels = pixel_width * pixel_height

        # Calculate temporal span
        days_span = 1
        estimated_scenes = 1

        if temporal_extent and len(temporal_extent) >= 2:
            try:
                start = datetime.fromisoformat(temporal_extent[0].replace("Z", ""))
                end = datetime.fromisoformat(temporal_extent[1].replace("Z", ""))
                days_span = max(1, (end - start).days)

                if revisit:
                    estimated_scenes = max(1, days_span // revisit)
                else:
                    estimated_scenes = 1
            except (ValueError, TypeError):
                pass

        # Calculate data size
        num_bands = len(bands) if bands else total_bands
        bytes_per_pixel = 4  # float32

        bytes_per_scene = total_pixels * num_bands * bytes_per_pixel
        total_bytes = bytes_per_scene * estimated_scenes

        total_mb = total_bytes / (1024 * 1024)
        total_gb = total_bytes / (1024 * 1024 * 1024)

        # Determine severity and generate warnings
        severity = "ok"

        if total_bytes >= self.thresholds["error"]:
            severity = "error"
            warnings.append(
                f"Estimated data size ({total_gb:.1f} GB) exceeds safe limit"
            )
            suggestions.append("Reduce spatial extent to a smaller area")
            suggestions.append("Limit temporal range or use monthly composites")
            suggestions.append("Select fewer bands")

        elif total_bytes >= self.thresholds["warning"]:
            severity = "warning"
            warnings.append(
                f"Large data request ({total_gb:.2f} GB) may take significant time"
            )
            suggestions.append("Consider using a batch job for better reliability")
            suggestions.append("Processing may take several minutes")

        elif total_bytes >= self.thresholds["info"]:
            severity = "info"
            warnings.append(
                f"Moderate data size ({total_mb:.0f} MB)"
            )

        # Additional checks
        if area_km2 > 10000:
            warnings.append(f"Large spatial extent: {area_km2:.0f} km²")
            suggestions.append("Consider splitting into multiple smaller queries")

        if days_span > 365:
            warnings.append(f"Long temporal range: {days_span} days")
            suggestions.append("Consider temporal aggregation (monthly means)")

        if pixel_width > 10000 or pixel_height > 10000:
            warnings.append(f"High pixel count: {pixel_width}x{pixel_height}")
            suggestions.append("Consider using lower resolution or smaller extent")

        # Check for antimeridian crossing
        if west > east:
            warnings.append("Extent crosses the antimeridian (180° longitude)")
            suggestions.append("Split query into two separate extents")
            severity = max(severity, "warning", key=lambda x: ["ok", "info", "warning", "error"].index(x))

        # Check for valid coordinates
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            warnings.append("Longitude values should be between -180 and 180")
            severity = "error"

        if not (-90 <= south <= 90 and -90 <= north <= 90):
            warnings.append("Latitude values should be between -90 and 90")
            severity = "error"

        if south >= north:
            warnings.append("South coordinate must be less than north")
            severity = "error"

        return ExtentEstimate(
            width_km=width_km,
            height_km=height_km,
            area_km2=area_km2,
            pixel_width=pixel_width,
            pixel_height=pixel_height,
            total_pixels=total_pixels,
            days_span=days_span,
            estimated_scenes=estimated_scenes,
            bytes_per_scene=bytes_per_scene,
            total_bytes=total_bytes,
            total_mb=total_mb,
            total_gb=total_gb,
            severity=severity,
            warnings=warnings,
            suggestions=suggestions,
        )

    def validate_extent(
        self,
        spatial_extent: Dict[str, float],
        temporal_extent: Optional[List[str]] = None,
        collection: str = "sentinel-2-l2a",
        bands: Optional[List[str]] = None,
        max_size_gb: float = 10.0
    ) -> Dict[str, Any]:
        """
        Validate an extent and return validation result.

        Args:
            spatial_extent: Bounding box
            temporal_extent: Date range
            collection: Collection ID
            bands: Band list
            max_size_gb: Maximum allowed size in GB

        Returns:
            Validation result with pass/fail and details
        """
        estimate = self.estimate_size(
            spatial_extent=spatial_extent,
            temporal_extent=temporal_extent,
            collection=collection,
            bands=bands,
        )

        is_valid = estimate.severity != "error"

        return {
            "valid": is_valid,
            "estimate": estimate.to_dict(),
            "requires_confirmation": estimate.severity == "warning",
            "error": not is_valid,
        }


# Module-level validator instance
_validator: Optional[ExtentValidator] = None


def get_validator() -> ExtentValidator:
    """Get or create extent validator."""
    global _validator
    if _validator is None:
        _validator = ExtentValidator()
    return _validator


def estimate_extent_size(
    spatial_extent: Dict[str, float],
    temporal_extent: Optional[List[str]] = None,
    collection: str = "sentinel-2-l2a",
    bands: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Estimate size of a data request (convenience function).

    Returns dict suitable for JSON response.
    """
    validator = get_validator()
    estimate = validator.estimate_size(
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        collection=collection,
        bands=bands,
    )
    return estimate.to_dict()


def validate_extent(
    spatial_extent: Dict[str, float],
    temporal_extent: Optional[List[str]] = None,
    collection: str = "sentinel-2-l2a",
    bands: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Validate an extent (convenience function).

    Returns validation result dict.
    """
    validator = get_validator()
    return validator.validate_extent(
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        collection=collection,
        bands=bands,
    )
