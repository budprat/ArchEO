# ABOUTME: Geospatial validation utilities for coordinate systems, projections, and extent handling.
# Validates CRS, handles antimeridian crossing, and provides coordinate transformations.

"""
Geospatial validation utilities for OpenEO AI Assistant.

Provides comprehensive validation for:
- Coordinate Reference Systems (CRS)
- Antimeridian crossing detection and handling
- Bounding box validation and normalization
- Coordinate transformations
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


# Common CRS definitions
SUPPORTED_CRS = {
    "EPSG:4326": {
        "name": "WGS 84",
        "description": "World Geodetic System 1984 (lat/lon)",
        "units": "degrees",
        "bounds": {"west": -180, "south": -90, "east": 180, "north": 90},
        "is_geographic": True,
    },
    "EPSG:3857": {
        "name": "Web Mercator",
        "description": "Pseudo-Mercator (used by web maps)",
        "units": "meters",
        "bounds": {"west": -20037508.34, "south": -20037508.34,
                   "east": 20037508.34, "north": 20037508.34},
        "is_geographic": False,
    },
    "EPSG:32632": {
        "name": "UTM Zone 32N",
        "description": "Universal Transverse Mercator Zone 32 North",
        "units": "meters",
        "bounds": {"west": 166021.44, "south": 0, "east": 833978.56, "north": 9329005.18},
        "is_geographic": False,
    },
    "EPSG:32633": {
        "name": "UTM Zone 33N",
        "description": "Universal Transverse Mercator Zone 33 North",
        "units": "meters",
        "bounds": {"west": 166021.44, "south": 0, "east": 833978.56, "north": 9329005.18},
        "is_geographic": False,
    },
}

# Default CRS for OpenEO
DEFAULT_CRS = "EPSG:4326"


@dataclass
class ValidationResult:
    """Result of geospatial validation."""

    valid: bool
    warnings: List[str]
    errors: List[str]
    suggestions: List[str]
    normalized_extent: Optional[Dict[str, float]] = None
    crs: str = DEFAULT_CRS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "valid": self.valid,
            "warnings": self.warnings,
            "errors": self.errors,
            "suggestions": self.suggestions,
            "normalized_extent": self.normalized_extent,
            "crs": self.crs,
        }


class GeospatialValidator:
    """Validates geospatial parameters for EO queries."""

    def __init__(self):
        """Initialize geospatial validator."""
        self.supported_crs = SUPPORTED_CRS

    def validate_crs(self, crs: str) -> Tuple[bool, List[str]]:
        """
        Validate a CRS string.

        Args:
            crs: CRS identifier (e.g., "EPSG:4326")

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Normalize CRS string
        crs_normalized = crs.upper().strip()

        # Check if supported
        if crs_normalized not in self.supported_crs:
            # Try to parse EPSG code
            if crs_normalized.startswith("EPSG:"):
                try:
                    code = int(crs_normalized.split(":")[1])
                    if 1024 <= code <= 32767:
                        issues.append(f"CRS {crs_normalized} not in common list but may be valid")
                        return True, issues
                except ValueError:
                    pass

            issues.append(f"Unsupported CRS: {crs}. Supported: {list(self.supported_crs.keys())}")
            return False, issues

        return True, issues

    def validate_extent(
        self,
        spatial_extent: Dict[str, float],
        crs: str = DEFAULT_CRS
    ) -> ValidationResult:
        """
        Validate a spatial extent.

        Args:
            spatial_extent: Bounding box {west, south, east, north}
            crs: Coordinate reference system

        Returns:
            ValidationResult with details
        """
        warnings = []
        errors = []
        suggestions = []

        # Extract coordinates
        west = spatial_extent.get("west")
        south = spatial_extent.get("south")
        east = spatial_extent.get("east")
        north = spatial_extent.get("north")

        # Check for missing coordinates
        missing = []
        if west is None:
            missing.append("west")
        if south is None:
            missing.append("south")
        if east is None:
            missing.append("east")
        if north is None:
            missing.append("north")

        if missing:
            errors.append(f"Missing coordinates: {', '.join(missing)}")
            return ValidationResult(
                valid=False,
                warnings=warnings,
                errors=errors,
                suggestions=["Provide all four coordinates: west, south, east, north"],
                crs=crs
            )

        # Validate CRS
        crs_valid, crs_issues = self.validate_crs(crs)
        if not crs_valid:
            errors.extend(crs_issues)
        else:
            warnings.extend(crs_issues)

        # Get CRS bounds if known
        crs_info = self.supported_crs.get(crs.upper())

        # Check coordinate validity based on CRS
        if crs_info:
            crs_bounds = crs_info["bounds"]

            if crs_info["is_geographic"]:
                # Geographic CRS validation
                if not (-180 <= west <= 180):
                    errors.append(f"West longitude {west} out of range [-180, 180]")
                if not (-180 <= east <= 180):
                    errors.append(f"East longitude {east} out of range [-180, 180]")
                if not (-90 <= south <= 90):
                    errors.append(f"South latitude {south} out of range [-90, 90]")
                if not (-90 <= north <= 90):
                    errors.append(f"North latitude {north} out of range [-90, 90]")
            else:
                # Projected CRS validation
                if not (crs_bounds["west"] <= west <= crs_bounds["east"]):
                    warnings.append(f"West coordinate {west} may be outside CRS bounds")
                if not (crs_bounds["west"] <= east <= crs_bounds["east"]):
                    warnings.append(f"East coordinate {east} may be outside CRS bounds")

        # Check south < north
        if south >= north:
            errors.append(f"South ({south}) must be less than north ({north})")
            suggestions.append("Swap south and north coordinates")

        # Check for antimeridian crossing
        antimeridian_crossing = False
        normalized_extent = {"west": west, "south": south, "east": east, "north": north}

        if crs_info and crs_info["is_geographic"]:
            if west > east:
                antimeridian_crossing = True
                warnings.append(f"Extent crosses the antimeridian (180° longitude)")
                suggestions.append("Consider splitting into two separate queries")
                suggestions.append("Or use the normalized extent with east > 180")

                # Normalize for processing (east can exceed 180)
                normalized_extent["east"] = east + 360

        # Check for very small extents
        if crs_info and crs_info["is_geographic"]:
            width_deg = abs(east - west) if not antimeridian_crossing else (360 - west + east)
            height_deg = abs(north - south)

            if width_deg < 0.0001 or height_deg < 0.0001:
                warnings.append("Very small extent (< 0.0001 degrees)")
                suggestions.append("Extent may be too small for meaningful analysis")

        # Check for pole coverage
        if crs_info and crs_info["is_geographic"]:
            if north > 85 or south < -85:
                warnings.append("Extent includes polar regions (lat > 85° or < -85°)")
                suggestions.append("Polar regions may have limited satellite coverage")
                suggestions.append("Consider using a polar-specific projection")

        # Check for very large extents
        if crs_info and crs_info["is_geographic"]:
            width_deg = abs(east - west) if not antimeridian_crossing else (360 - west + east)
            height_deg = abs(north - south)

            if width_deg > 10 or height_deg > 10:
                warnings.append(f"Large extent: {width_deg:.1f}° x {height_deg:.1f}°")
                suggestions.append("Consider reducing extent for faster processing")

        valid = len(errors) == 0

        return ValidationResult(
            valid=valid,
            warnings=warnings,
            errors=errors,
            suggestions=suggestions,
            normalized_extent=normalized_extent,
            crs=crs
        )

    def split_antimeridian_extent(
        self,
        spatial_extent: Dict[str, float]
    ) -> List[Dict[str, float]]:
        """
        Split an extent that crosses the antimeridian into two extents.

        Args:
            spatial_extent: Bounding box that crosses antimeridian

        Returns:
            List of two bounding boxes
        """
        west = spatial_extent["west"]
        south = spatial_extent["south"]
        east = spatial_extent["east"]
        north = spatial_extent["north"]

        # Only split if actually crossing
        if west <= east:
            return [spatial_extent]

        # Western part: west to 180
        extent_west = {
            "west": west,
            "south": south,
            "east": 180,
            "north": north
        }

        # Eastern part: -180 to east
        extent_east = {
            "west": -180,
            "south": south,
            "east": east,
            "north": north
        }

        return [extent_west, extent_east]

    def transform_extent(
        self,
        spatial_extent: Dict[str, float],
        source_crs: str,
        target_crs: str
    ) -> Dict[str, float]:
        """
        Transform extent between coordinate systems.

        Note: This is a simplified implementation. For production,
        use pyproj or similar library.

        Args:
            spatial_extent: Source bounding box
            source_crs: Source CRS
            target_crs: Target CRS

        Returns:
            Transformed bounding box
        """
        west = spatial_extent["west"]
        south = spatial_extent["south"]
        east = spatial_extent["east"]
        north = spatial_extent["north"]

        source_crs = source_crs.upper()
        target_crs = target_crs.upper()

        # Same CRS - no transformation needed
        if source_crs == target_crs:
            return spatial_extent.copy()

        # EPSG:4326 to EPSG:3857 (Web Mercator)
        if source_crs == "EPSG:4326" and target_crs == "EPSG:3857":
            def to_mercator(lon, lat):
                x = lon * 20037508.34 / 180
                y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
                y = y * 20037508.34 / 180
                return x, y

            west_m, south_m = to_mercator(west, max(south, -85.051129))
            east_m, north_m = to_mercator(east, min(north, 85.051129))

            return {
                "west": west_m,
                "south": south_m,
                "east": east_m,
                "north": north_m
            }

        # EPSG:3857 to EPSG:4326
        if source_crs == "EPSG:3857" and target_crs == "EPSG:4326":
            def from_mercator(x, y):
                lon = x * 180 / 20037508.34
                lat = math.atan(math.exp(y * math.pi / 20037508.34)) * 360 / math.pi - 90
                return lon, lat

            west_ll, south_ll = from_mercator(west, south)
            east_ll, north_ll = from_mercator(east, north)

            return {
                "west": west_ll,
                "south": south_ll,
                "east": east_ll,
                "north": north_ll
            }

        # Unsupported transformation
        logger.warning(f"Transformation from {source_crs} to {target_crs} not implemented")
        return spatial_extent.copy()

    def get_utm_zone(self, longitude: float, latitude: float) -> str:
        """
        Determine the appropriate UTM zone for a location.

        Args:
            longitude: Longitude in degrees
            latitude: Latitude in degrees

        Returns:
            EPSG code for the UTM zone
        """
        # Calculate UTM zone number
        zone = int((longitude + 180) / 6) + 1

        # Determine hemisphere
        if latitude >= 0:
            # Northern hemisphere: EPSG:326XX
            return f"EPSG:326{zone:02d}"
        else:
            # Southern hemisphere: EPSG:327XX
            return f"EPSG:327{zone:02d}"

    def calculate_area_km2(
        self,
        spatial_extent: Dict[str, float],
        crs: str = DEFAULT_CRS
    ) -> float:
        """
        Calculate approximate area of extent in square kilometers.

        Args:
            spatial_extent: Bounding box
            crs: Coordinate reference system

        Returns:
            Area in km²
        """
        west = spatial_extent["west"]
        south = spatial_extent["south"]
        east = spatial_extent["east"]
        north = spatial_extent["north"]

        crs_info = self.supported_crs.get(crs.upper())

        if crs_info and crs_info["is_geographic"]:
            # Geographic coordinates - use spherical approximation
            mid_lat = (south + north) / 2

            # Handle antimeridian crossing
            if west > east:
                width_deg = 360 - west + east
            else:
                width_deg = east - west

            height_deg = north - south

            # Approximate conversion at mid-latitude
            km_per_deg_lat = 111.0
            km_per_deg_lon = 111.0 * math.cos(math.radians(mid_lat))

            width_km = width_deg * km_per_deg_lon
            height_km = height_deg * km_per_deg_lat

            return width_km * height_km
        else:
            # Projected coordinates - assume meters
            width_m = abs(east - west)
            height_m = abs(north - south)

            return (width_m * height_m) / 1_000_000


# Module-level validator instance
_validator: Optional[GeospatialValidator] = None


def get_validator() -> GeospatialValidator:
    """Get or create geospatial validator."""
    global _validator
    if _validator is None:
        _validator = GeospatialValidator()
    return _validator


def validate_extent(
    spatial_extent: Dict[str, float],
    crs: str = DEFAULT_CRS
) -> Dict[str, Any]:
    """
    Validate a spatial extent (convenience function).

    Args:
        spatial_extent: Bounding box {west, south, east, north}
        crs: Coordinate reference system

    Returns:
        Validation result dict
    """
    validator = get_validator()
    result = validator.validate_extent(spatial_extent, crs)
    return result.to_dict()


def validate_crs(crs: str) -> Dict[str, Any]:
    """
    Validate a CRS string (convenience function).

    Args:
        crs: CRS identifier

    Returns:
        Validation result dict
    """
    validator = get_validator()
    is_valid, issues = validator.validate_crs(crs)
    return {
        "valid": is_valid,
        "crs": crs,
        "issues": issues,
        "info": SUPPORTED_CRS.get(crs.upper())
    }


def split_antimeridian(spatial_extent: Dict[str, float]) -> List[Dict[str, float]]:
    """
    Split extent at antimeridian (convenience function).

    Args:
        spatial_extent: Bounding box

    Returns:
        List of extents (1 or 2)
    """
    validator = get_validator()
    return validator.split_antimeridian_extent(spatial_extent)


def get_utm_zone_for_extent(spatial_extent: Dict[str, float]) -> str:
    """
    Get recommended UTM zone for an extent (convenience function).

    Args:
        spatial_extent: Bounding box in EPSG:4326

    Returns:
        EPSG code for UTM zone
    """
    validator = get_validator()
    center_lon = (spatial_extent["west"] + spatial_extent["east"]) / 2
    center_lat = (spatial_extent["south"] + spatial_extent["north"]) / 2
    return validator.get_utm_zone(center_lon, center_lat)
