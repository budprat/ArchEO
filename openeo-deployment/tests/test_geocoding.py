"""Tests for openeo_ai/utils/geocoding.py.

Verifies location resolution from place names, coordinates, and predefined
regions -- all without network access (Nominatim is mocked).
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from openeo_ai.utils.geocoding import (
    GeocodingService,
    LocationResult,
    KNOWN_REGIONS,
    DEFAULT_BUFFER_DEG,
    resolve_location,
)


# ---------------------------------------------------------------------------
# GeocodingService -- predefined (known) regions
# ---------------------------------------------------------------------------


class TestKnownRegions:
    """Tests for resolving well-known / predefined regions."""

    def test_known_region_kerala(self):
        """Verify that 'Kerala' resolves to the predefined bounding box."""
        svc = GeocodingService()
        result = svc.resolve("Kerala")

        assert result.success is True
        assert result.source == "known"
        assert result.confidence == 1.0
        assert result.bbox == KNOWN_REGIONS["kerala"]

    def test_known_region_case_insensitive(self):
        """Verify that region lookup is case-insensitive."""
        svc = GeocodingService()
        result = svc.resolve("MUMBAI")

        assert result.success is True
        assert result.source == "known"
        assert result.bbox == KNOWN_REGIONS["mumbai"]

    def test_known_region_with_whitespace(self):
        """Verify that leading/trailing whitespace is stripped."""
        svc = GeocodingService()
        result = svc.resolve("  delhi  ")

        assert result.success is True
        assert result.bbox == KNOWN_REGIONS["delhi"]

    def test_known_region_amazon(self):
        """Verify the Amazon rainforest predefined region."""
        svc = GeocodingService()
        result = svc.resolve("Amazon Rainforest")

        assert result.success is True
        assert result.bbox["west"] == -73.0

    def test_known_region_display_name(self):
        """Verify display_name contains '(predefined region)'."""
        svc = GeocodingService()
        result = svc.resolve("Netherlands")

        assert "predefined region" in result.display_name

    def test_all_known_regions_resolve(self):
        """Every entry in KNOWN_REGIONS should resolve successfully."""
        svc = GeocodingService()
        for region_name in KNOWN_REGIONS:
            result = svc.resolve(region_name)
            assert result.success is True, f"Failed to resolve: {region_name}"
            assert result.source == "known"


# ---------------------------------------------------------------------------
# GeocodingService -- coordinate parsing
# ---------------------------------------------------------------------------


class TestCoordinateParsing:
    """Tests for parsing raw coordinate strings."""

    def test_simple_lat_lon(self):
        """Parse 'lat, lon' format."""
        svc = GeocodingService()
        result = svc.resolve("28.6139, 77.2090")

        assert result.success is True
        assert result.source == "coordinates"
        assert result.confidence == 1.0
        assert abs(result.bbox["south"] - (28.6139 - DEFAULT_BUFFER_DEG)) < 0.001

    def test_lat_lon_with_degree_symbols(self):
        """Parse coordinates containing degree symbols."""
        svc = GeocodingService()
        result = svc.resolve("28.6139°N, 77.2090°E")

        assert result.success is True
        assert result.source == "coordinates"

    def test_lat_lon_with_labels(self):
        """Parse 'lat: 28.6, lon: 77.2' format."""
        svc = GeocodingService()
        result = svc.resolve("lat: 28.6139, lon: 77.2090")

        assert result.success is True
        assert result.source == "coordinates"

    def test_custom_buffer_degrees(self):
        """Verify that buffer_deg parameter is honoured for coordinates."""
        svc = GeocodingService()
        buffer = 0.5
        result = svc.resolve("10.0, 20.0", buffer_deg=buffer)

        assert result.success is True
        assert abs(result.bbox["west"] - (20.0 - buffer)) < 0.001
        assert abs(result.bbox["east"] - (20.0 + buffer)) < 0.001

    def test_negative_coordinates(self):
        """Parse negative (southern/western hemisphere) coordinates."""
        svc = GeocodingService()
        result = svc.resolve("-33.8688, 151.2093")  # Sydney

        assert result.success is True
        assert result.bbox["south"] < 0

    def test_out_of_range_coordinates_fail(self):
        """Coordinates outside valid ranges should not match."""
        svc = GeocodingService()
        # Both numbers > 180, so neither qualifies as valid lat/lon
        coords = svc._parse_coordinates("999.0, 999.0")
        assert coords is None


# ---------------------------------------------------------------------------
# GeocodingService -- Nominatim geocoding (mocked)
# ---------------------------------------------------------------------------


class TestNominatimGeocoding:
    """Tests for Nominatim-based geocoding with mocked responses."""

    @patch.object(GeocodingService, "__init__", lambda self, **kw: None)
    def _make_service(self, geocoder_return=None, geocoder_side_effect=None):
        """Helper: create a GeocodingService with a mocked geocoder."""
        svc = GeocodingService.__new__(GeocodingService)
        svc.known_regions = KNOWN_REGIONS
        svc.geocoder = MagicMock()
        if geocoder_side_effect:
            svc.geocoder.geocode.side_effect = geocoder_side_effect
        else:
            svc.geocoder.geocode.return_value = geocoder_return
        return svc

    def test_nominatim_success_with_boundingbox(self, mock_nominatim_result):
        """Verify successful Nominatim resolution when bounding box is available."""
        svc = self._make_service(geocoder_return=mock_nominatim_result)
        result = svc.resolve("Paris")

        assert result.success is True
        assert result.source == "nominatim"
        assert result.bbox is not None
        # bounding box comes from raw['boundingbox']
        assert result.bbox["south"] == pytest.approx(48.815573, rel=1e-4)

    def test_nominatim_success_without_boundingbox(self):
        """Verify fallback to point+buffer when no bounding box in raw data."""
        mock_result = MagicMock()
        mock_result.latitude = 40.7128
        mock_result.longitude = -74.0060
        mock_result.address = "New York, NY, USA"
        mock_result.raw = {"name": "New York", "importance": 0.8}

        svc = self._make_service(geocoder_return=mock_result)
        result = svc.resolve("New York")

        assert result.success is True
        assert result.source == "nominatim"
        assert result.bbox["west"] == pytest.approx(-74.0060 - DEFAULT_BUFFER_DEG)

    def test_nominatim_no_result(self):
        """Verify failure when Nominatim returns None."""
        svc = self._make_service(geocoder_return=None)
        # Also mock _find_alternatives to avoid secondary geocode call
        svc._find_alternatives = MagicMock(return_value=None)

        result = svc.resolve("xyznonexistent")

        assert result.success is False
        assert "Could not find" in result.error

    def test_nominatim_timeout(self):
        """Verify graceful handling of Nominatim timeout."""
        svc = self._make_service(
            geocoder_side_effect=GeocoderTimedOut("timeout")
        )
        result = svc.resolve("SomePlace")

        assert result.success is False
        assert "timed out" in result.error

    def test_nominatim_service_error(self):
        """Verify graceful handling of Nominatim service error."""
        svc = self._make_service(
            geocoder_side_effect=GeocoderServiceError("service down")
        )
        result = svc.resolve("SomePlace")

        assert result.success is False
        assert "service error" in result.error.lower()

    def test_nominatim_unexpected_error(self):
        """Verify graceful handling of unexpected exceptions."""
        svc = self._make_service(
            geocoder_side_effect=RuntimeError("unexpected")
        )
        result = svc.resolve("SomePlace")

        assert result.success is False
        assert "Unexpected" in result.error

    def test_confidence_from_importance(self, mock_nominatim_result):
        """Verify confidence is derived from OSM importance field."""
        mock_nominatim_result.raw["importance"] = 0.75
        svc = self._make_service(geocoder_return=mock_nominatim_result)
        result = svc.resolve("Paris")

        assert result.confidence == pytest.approx(0.75 * 1.2)


# ---------------------------------------------------------------------------
# LocationResult dataclass
# ---------------------------------------------------------------------------


class TestLocationResult:
    """Tests for the LocationResult dataclass and its serialization."""

    def test_to_dict_success(self):
        """Verify to_dict for a successful result."""
        lr = LocationResult(
            success=True,
            bbox={"west": 1, "south": 2, "east": 3, "north": 4},
            name="Test",
            display_name="Test Place",
            confidence=0.9,
            source="known",
        )
        d = lr.to_dict()

        assert d["success"] is True
        assert d["bbox"] == {"west": 1, "south": 2, "east": 3, "north": 4}
        assert d["spatial_extent"] == d["bbox"]
        assert "error" not in d

    def test_to_dict_failure(self):
        """Verify to_dict for a failed result."""
        lr = LocationResult(
            success=False,
            error="not found",
            alternatives=["Place A", "Place B"],
        )
        d = lr.to_dict()

        assert d["success"] is False
        assert d["error"] == "not found"
        assert "alternatives" in d


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


class TestResolveLocationFunction:
    """Tests for the module-level resolve_location() convenience function."""

    def test_resolve_known_region(self):
        """resolve_location should work for known regions."""
        result = resolve_location("Singapore")

        assert result.success is True
        assert result.bbox == KNOWN_REGIONS["singapore"]

    def test_resolve_coordinates(self):
        """resolve_location should work for coordinate strings."""
        result = resolve_location("48.8566, 2.3522")

        assert result.success is True
        assert result.source == "coordinates"
