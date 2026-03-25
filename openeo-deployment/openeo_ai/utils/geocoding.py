# ABOUTME: Geocoding utility for resolving place names to bounding boxes.
# Uses Nominatim (OpenStreetMap) for free geocoding without API keys.

"""
Geocoding utilities for OpenEO AI Assistant.

Resolves natural language location references to geographic bounding boxes
suitable for Earth Observation data queries.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

logger = logging.getLogger(__name__)

# Default buffer in degrees for point locations
DEFAULT_BUFFER_DEG = 0.1  # ~11km at equator

# Well-known regions with predefined bounding boxes
KNOWN_REGIONS = {
    # Indian States
    "kerala": {"west": 74.85, "south": 8.28, "east": 77.42, "north": 12.79},
    "maharashtra": {"west": 72.60, "south": 15.60, "east": 80.90, "north": 22.10},
    "rajasthan": {"west": 69.30, "south": 23.30, "east": 78.27, "north": 30.19},
    "punjab": {"west": 73.87, "south": 29.53, "east": 76.94, "north": 32.51},
    "tamil nadu": {"west": 76.23, "south": 8.07, "east": 80.35, "north": 13.57},
    "karnataka": {"west": 74.05, "south": 11.59, "east": 78.59, "north": 18.45},

    # Major Cities (with reasonable analysis extent)
    "delhi": {"west": 76.84, "south": 28.40, "east": 77.35, "north": 28.88},
    "mumbai": {"west": 72.77, "south": 18.89, "east": 72.98, "north": 19.27},
    "bangalore": {"west": 77.46, "south": 12.83, "east": 77.78, "north": 13.14},
    "chennai": {"west": 80.17, "south": 12.90, "east": 80.32, "north": 13.23},
    "kolkata": {"west": 88.25, "south": 22.45, "east": 88.50, "north": 22.65},
    "hyderabad": {"west": 78.27, "south": 17.28, "east": 78.60, "north": 17.55},

    # Global Regions
    "amazon rainforest": {"west": -73.0, "south": -10.0, "east": -50.0, "north": 5.0},
    "amazon": {"west": -73.0, "south": -10.0, "east": -50.0, "north": 5.0},
    "sahara": {"west": -17.0, "south": 15.0, "east": 35.0, "north": 35.0},
    "alps": {"west": 5.5, "south": 44.0, "east": 16.5, "north": 48.5},
    "himalayas": {"west": 73.0, "south": 26.0, "east": 95.0, "north": 36.0},

    # Countries (small/medium sized for practical analysis)
    "netherlands": {"west": 3.31, "south": 50.75, "east": 7.21, "north": 53.47},
    "belgium": {"west": 2.54, "south": 49.50, "east": 6.41, "north": 51.50},
    "switzerland": {"west": 5.96, "south": 45.82, "east": 10.49, "north": 47.81},
    "austria": {"west": 9.53, "south": 46.37, "east": 17.16, "north": 49.02},
    "singapore": {"west": 103.60, "south": 1.17, "east": 104.09, "north": 1.47},
}


@dataclass
class LocationResult:
    """Result of location resolution."""

    success: bool
    bbox: Optional[Dict[str, float]] = None  # west, south, east, north
    name: str = ""
    display_name: str = ""
    confidence: float = 0.0
    source: str = ""  # "known", "nominatim", "coordinates"
    error: Optional[str] = None
    alternatives: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "name": self.name,
            "display_name": self.display_name,
            "confidence": self.confidence,
            "source": self.source,
        }
        if self.bbox:
            result["bbox"] = self.bbox
            result["spatial_extent"] = self.bbox  # OpenEO format alias
        if self.error:
            result["error"] = self.error
        if self.alternatives:
            result["alternatives"] = self.alternatives
        return result


class GeocodingService:
    """Service for resolving location names to bounding boxes."""

    def __init__(self, user_agent: str = "openeo-ai-assistant"):
        """
        Initialize geocoding service.

        Args:
            user_agent: User agent string for Nominatim (required)
        """
        self.geocoder = Nominatim(user_agent=user_agent, timeout=10)
        self.known_regions = KNOWN_REGIONS

    def resolve(
        self,
        location: str,
        buffer_deg: float = DEFAULT_BUFFER_DEG
    ) -> LocationResult:
        """
        Resolve a location string to a bounding box.

        Args:
            location: Location name, coordinates, or description
            buffer_deg: Buffer to add around point locations (degrees)

        Returns:
            LocationResult with bounding box or error
        """
        location = location.strip()

        # Try parsing as coordinates first
        coords = self._parse_coordinates(location)
        if coords:
            lat, lon = coords
            return LocationResult(
                success=True,
                bbox={
                    "west": lon - buffer_deg,
                    "south": lat - buffer_deg,
                    "east": lon + buffer_deg,
                    "north": lat + buffer_deg,
                },
                name=f"Point ({lat:.4f}, {lon:.4f})",
                display_name=f"Coordinates: {lat:.4f}°N, {lon:.4f}°E",
                confidence=1.0,
                source="coordinates",
            )

        # Check known regions
        location_lower = location.lower().strip()
        if location_lower in self.known_regions:
            bbox = self.known_regions[location_lower]
            return LocationResult(
                success=True,
                bbox=bbox,
                name=location.title(),
                display_name=f"{location.title()} (predefined region)",
                confidence=1.0,
                source="known",
            )

        # Try Nominatim geocoding
        return self._geocode_nominatim(location, buffer_deg)

    def _parse_coordinates(self, text: str) -> Optional[Tuple[float, float]]:
        """
        Parse coordinate string to (lat, lon) tuple.

        Supports formats:
        - "28.6139, 77.2090"
        - "28.6139°N, 77.2090°E"
        - "lat: 28.6139, lon: 77.2090"
        """
        import re

        # Remove common prefixes
        text = re.sub(r'(lat|latitude|lon|longitude|lng)[\s:=]*', '', text, flags=re.I)

        # Try to find two numbers
        numbers = re.findall(r'[-+]?\d+\.?\d*', text)
        if len(numbers) >= 2:
            try:
                lat = float(numbers[0])
                lon = float(numbers[1])

                # Validate ranges
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
                # Try swapping if first looks like longitude
                if -180 <= lat <= 180 and -90 <= lon <= 90:
                    return (lon, lat)
            except ValueError:
                pass

        return None

    def _geocode_nominatim(
        self,
        location: str,
        buffer_deg: float
    ) -> LocationResult:
        """Geocode using Nominatim service."""
        try:
            # Search with bounding box preference
            result = self.geocoder.geocode(
                location,
                exactly_one=True,
                addressdetails=True,
                language="en",
            )

            if not result:
                # Try to find alternatives
                alternatives = self._find_alternatives(location)
                return LocationResult(
                    success=False,
                    error=f"Could not find location: '{location}'",
                    alternatives=alternatives,
                )

            # Extract bounding box if available
            raw = result.raw
            if 'boundingbox' in raw:
                bb = raw['boundingbox']
                bbox = {
                    "south": float(bb[0]),
                    "north": float(bb[1]),
                    "west": float(bb[2]),
                    "east": float(bb[3]),
                }
            else:
                # Create bbox from point + buffer
                bbox = {
                    "west": result.longitude - buffer_deg,
                    "south": result.latitude - buffer_deg,
                    "east": result.longitude + buffer_deg,
                    "north": result.latitude + buffer_deg,
                }

            # Calculate confidence based on importance
            importance = raw.get('importance', 0.5)
            confidence = min(importance * 1.2, 1.0)

            return LocationResult(
                success=True,
                bbox=bbox,
                name=raw.get('name', location),
                display_name=result.address,
                confidence=confidence,
                source="nominatim",
            )

        except GeocoderTimedOut:
            return LocationResult(
                success=False,
                error="Geocoding service timed out. Please try again.",
            )
        except GeocoderServiceError as e:
            return LocationResult(
                success=False,
                error=f"Geocoding service error: {str(e)}",
            )
        except Exception as e:
            logger.exception(f"Unexpected geocoding error for '{location}'")
            return LocationResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    def _find_alternatives(self, location: str) -> List[str]:
        """Find alternative location suggestions."""
        location_lower = location.lower()
        alternatives = []

        # Check for partial matches in known regions
        for name in self.known_regions:
            if location_lower in name or name in location_lower:
                alternatives.append(name.title())

        # Try geocoding with different queries
        try:
            results = self.geocoder.geocode(
                location,
                exactly_one=False,
                limit=5,
                language="en",
            )
            if results:
                for r in results[:3]:
                    if r.address not in alternatives:
                        alternatives.append(r.address)
        except Exception:
            pass

        return alternatives[:5] if alternatives else None


# Module-level instance for convenience
_service: Optional[GeocodingService] = None


def get_service() -> GeocodingService:
    """Get or create the geocoding service singleton."""
    global _service
    if _service is None:
        _service = GeocodingService()
    return _service


def resolve_location(
    location: str,
    buffer_deg: float = DEFAULT_BUFFER_DEG
) -> LocationResult:
    """
    Resolve a location string to a bounding box.

    This is the main entry point for location resolution.

    Args:
        location: Location name, coordinates, or description
        buffer_deg: Buffer to add around point locations (degrees)

    Returns:
        LocationResult with bounding box or error

    Examples:
        >>> result = resolve_location("Mumbai")
        >>> result.bbox
        {'west': 72.77, 'south': 18.89, 'east': 72.98, 'north': 19.27}

        >>> result = resolve_location("28.6139, 77.2090")
        >>> result.source
        'coordinates'
    """
    return get_service().resolve(location, buffer_deg)


# Convenience function for tools
async def resolve_location_async(
    location: str,
    buffer_deg: float = DEFAULT_BUFFER_DEG
) -> Dict[str, Any]:
    """
    Async wrapper for location resolution (for tool use).

    Returns dict suitable for JSON response.
    """
    result = resolve_location(location, buffer_deg)
    return result.to_dict()
