"""STAC extent validation to prevent resource exhaustion.

Validates spatial and temporal extents to prevent:
- Global extent queries (full planet downloads)
- Very long temporal ranges (years of data)
- Invalid coordinate values
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class ValidatedExtent:
    """Result of extent validation with potentially modified values."""

    west: float
    south: float
    east: float
    north: float
    crs: str = "EPSG:4326"
    was_modified: bool = False
    original_extent: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "west": self.west,
            "south": self.south,
            "east": self.east,
            "north": self.north,
            "crs": self.crs,
        }


class STACExtentValidator:
    """Validates and optionally limits spatial and temporal extents.

    Prevents resource exhaustion from overly large queries while
    maintaining center position for user intent.
    """

    # Maximum spatial extent in degrees (default: 10°)
    MAX_SPATIAL_EXTENT: float = 10.0

    # Maximum temporal range in days (default: 365)
    MAX_TEMPORAL_DAYS: int = 365

    # Minimum extent size (prevents point queries)
    MIN_EXTENT_SIZE: float = 0.0001  # ~10m at equator

    @classmethod
    def validate_spatial_extent(
        cls,
        extent: Dict,
        max_degrees: Optional[float] = None,
        auto_limit: bool = True,
    ) -> ValidatedExtent:
        """Validate and optionally limit spatial extent.

        Args:
            extent: Dict with west, south, east, north, optionally crs
            max_degrees: Maximum extent size in degrees (overrides class default)
            auto_limit: If True, automatically reduce oversized extents

        Returns:
            ValidatedExtent with potentially modified coordinates

        Raises:
            ExtentValidationError: If extent is invalid and can't be fixed
        """
        from ..core.exceptions import ExtentValidationError

        max_size = max_degrees or cls.MAX_SPATIAL_EXTENT

        # Extract coordinates
        try:
            west = float(extent.get("west", 0))
            south = float(extent.get("south", 0))
            east = float(extent.get("east", 0))
            north = float(extent.get("north", 0))
            crs = extent.get("crs", "EPSG:4326")
        except (TypeError, ValueError) as e:
            raise ExtentValidationError(
                f"Invalid coordinate values: {e}",
                extent_type="spatial",
                provided_extent=extent,
            )

        # Validate coordinate ranges for EPSG:4326
        if crs == "EPSG:4326":
            if not (-180 <= west <= 180 and -180 <= east <= 180):
                raise ExtentValidationError(
                    f"Longitude must be between -180 and 180, got west={west}, east={east}",
                    extent_type="spatial",
                    provided_extent=extent,
                )
            if not (-90 <= south <= 90 and -90 <= north <= 90):
                raise ExtentValidationError(
                    f"Latitude must be between -90 and 90, got south={south}, north={north}",
                    extent_type="spatial",
                    provided_extent=extent,
                )

        # Validate extent ordering
        if west > east:
            logger.warning(f"West ({west}) > East ({east}), swapping")
            west, east = east, west

        if south > north:
            logger.warning(f"South ({south}) > North ({north}), swapping")
            south, north = north, south

        # Calculate extent size
        width = east - west
        height = north - south

        # Check for global extent
        if width >= 360 or height >= 180:
            logger.warning(
                f"GLOBAL EXTENT DETECTED! Width={width}°, Height={height}°"
            )
            if not auto_limit:
                raise ExtentValidationError(
                    "Global extent queries are not allowed. Please specify a smaller area.",
                    extent_type="spatial",
                    provided_extent=extent,
                )

        # Check if extent exceeds maximum
        was_modified = False
        original_extent = None

        if width > max_size or height > max_size:
            if auto_limit:
                original_extent = {
                    "west": west,
                    "south": south,
                    "east": east,
                    "north": north,
                }

                # Center-preserving reduction
                center_lon = (west + east) / 2
                center_lat = (south + north) / 2

                new_width = min(width, max_size)
                new_height = min(height, max_size)

                west = center_lon - new_width / 2
                east = center_lon + new_width / 2
                south = center_lat - new_height / 2
                north = center_lat + new_height / 2

                was_modified = True
                logger.warning(
                    f"Extent reduced from {width:.2f}°x{height:.2f}° "
                    f"to {new_width:.2f}°x{new_height:.2f}° (center preserved)"
                )
            else:
                raise ExtentValidationError(
                    f"Spatial extent ({width:.1f}°x{height:.1f}°) exceeds maximum "
                    f"({max_size}°x{max_size}°). Please specify a smaller area.",
                    extent_type="spatial",
                    provided_extent=extent,
                )

        # Ensure minimum extent size
        if width < cls.MIN_EXTENT_SIZE:
            east = west + cls.MIN_EXTENT_SIZE
            was_modified = True
        if height < cls.MIN_EXTENT_SIZE:
            north = south + cls.MIN_EXTENT_SIZE
            was_modified = True

        return ValidatedExtent(
            west=west,
            south=south,
            east=east,
            north=north,
            crs=crs,
            was_modified=was_modified,
            original_extent=original_extent,
        )

    @classmethod
    def validate_temporal_extent(
        cls,
        extent: list,
        max_days: Optional[int] = None,
        auto_limit: bool = True,
    ) -> Tuple[Optional[datetime], Optional[datetime], bool]:
        """Validate and optionally limit temporal extent.

        Args:
            extent: List of [start, end] datetime strings or objects
            max_days: Maximum temporal range in days (overrides class default)
            auto_limit: If True, automatically reduce oversized ranges

        Returns:
            Tuple of (start_datetime, end_datetime, was_modified)

        Raises:
            ExtentValidationError: If extent is invalid and can't be fixed
        """
        from ..core.exceptions import ExtentValidationError
        import pandas as pd

        max_days_limit = max_days or cls.MAX_TEMPORAL_DAYS

        if not extent or len(extent) < 2:
            raise ExtentValidationError(
                "Temporal extent must have start and end dates",
                extent_type="temporal",
                provided_extent={"extent": extent},
            )

        try:
            start = pd.to_datetime(extent[0]) if extent[0] else None
            end = pd.to_datetime(extent[1]) if extent[1] else None
        except Exception as e:
            raise ExtentValidationError(
                f"Invalid date format: {e}",
                extent_type="temporal",
                provided_extent={"extent": extent},
            )

        # Both dates must be provided for range check
        if start is None or end is None:
            return (start, end, False)

        # Validate ordering
        if start > end:
            logger.warning(f"Start ({start}) > End ({end}), swapping")
            start, end = end, start

        # Calculate range
        range_days = (end - start).days

        was_modified = False
        if range_days > max_days_limit:
            if auto_limit:
                # Keep end date, adjust start
                new_start = end - timedelta(days=max_days_limit)
                logger.warning(
                    f"Temporal range reduced from {range_days} days to {max_days_limit} days"
                )
                start = new_start
                was_modified = True
            else:
                raise ExtentValidationError(
                    f"Temporal range ({range_days} days) exceeds maximum "
                    f"({max_days_limit} days). Please specify a shorter time range.",
                    extent_type="temporal",
                    provided_extent={"extent": extent},
                )

        return (start, end, was_modified)

    @classmethod
    def estimate_data_volume(
        cls,
        spatial_extent: Dict,
        temporal_days: int,
        resolution_m: float = 10.0,
        num_bands: int = 4,
        bytes_per_pixel: int = 4,
    ) -> Dict:
        """Estimate data volume for a query.

        Args:
            spatial_extent: Dict with west, south, east, north
            temporal_days: Number of days in temporal range
            resolution_m: Spatial resolution in meters
            num_bands: Number of bands to load
            bytes_per_pixel: Bytes per pixel (4 for float32)

        Returns:
            Dict with estimated pixels, bytes, and human-readable size
        """
        # Calculate extent in degrees
        width_deg = spatial_extent["east"] - spatial_extent["west"]
        height_deg = spatial_extent["north"] - spatial_extent["south"]

        # Convert to meters (approximate at equator)
        width_m = width_deg * 111_000  # ~111km per degree
        height_m = height_deg * 111_000

        # Calculate pixels
        pixels_x = int(width_m / resolution_m)
        pixels_y = int(height_m / resolution_m)

        # Estimate number of scenes (assume daily for Sentinel-2)
        num_scenes = max(1, temporal_days // 5)  # ~5 day revisit

        # Total pixels
        total_pixels = pixels_x * pixels_y * num_scenes * num_bands

        # Total bytes
        total_bytes = total_pixels * bytes_per_pixel

        # Human-readable size
        if total_bytes > 1e9:
            size_str = f"{total_bytes / 1e9:.1f} GB"
        elif total_bytes > 1e6:
            size_str = f"{total_bytes / 1e6:.1f} MB"
        else:
            size_str = f"{total_bytes / 1e3:.1f} KB"

        return {
            "pixels_x": pixels_x,
            "pixels_y": pixels_y,
            "num_scenes": num_scenes,
            "num_bands": num_bands,
            "total_pixels": total_pixels,
            "total_bytes": total_bytes,
            "size_human": size_str,
        }


def validate_extent(
    spatial_extent: Optional[Dict] = None,
    temporal_extent: Optional[list] = None,
    max_spatial_degrees: float = 10.0,
    max_temporal_days: int = 365,
    auto_limit: bool = True,
) -> Dict:
    """Convenience function to validate both extents.

    Args:
        spatial_extent: Dict with west, south, east, north
        temporal_extent: List of [start, end] datetime strings
        max_spatial_degrees: Maximum spatial extent in degrees
        max_temporal_days: Maximum temporal range in days
        auto_limit: If True, automatically reduce oversized extents

    Returns:
        Dict with validated extents and modification flags
    """
    result = {
        "spatial_modified": False,
        "temporal_modified": False,
        "warnings": [],
    }

    if spatial_extent:
        validated = STACExtentValidator.validate_spatial_extent(
            spatial_extent,
            max_degrees=max_spatial_degrees,
            auto_limit=auto_limit,
        )
        result["spatial_extent"] = validated.to_dict()
        result["spatial_modified"] = validated.was_modified
        if validated.was_modified:
            result["warnings"].append(
                f"Spatial extent was reduced to {max_spatial_degrees}° maximum"
            )

    if temporal_extent:
        start, end, modified = STACExtentValidator.validate_temporal_extent(
            temporal_extent,
            max_days=max_temporal_days,
            auto_limit=auto_limit,
        )
        result["temporal_extent"] = [start, end]
        result["temporal_modified"] = modified
        if modified:
            result["warnings"].append(
                f"Temporal extent was reduced to {max_temporal_days} days maximum"
            )

    return result
