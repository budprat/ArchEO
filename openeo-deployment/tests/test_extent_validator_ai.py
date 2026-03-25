"""Tests for openeo_ai/utils/extent_validator.py.

Verifies size estimation, warning severity thresholds, and validation
for the AI assistant's extent validator (distinct from openeo_app's
STAC extent validator tested in test_extent_validator.py).
"""

import math
import pytest

from openeo_ai.utils.extent_validator import (
    ExtentValidator,
    ExtentEstimate,
    COLLECTION_RESOLUTIONS,
    COLLECTION_BANDS,
    COLLECTION_REVISIT,
    SIZE_THRESHOLDS,
    estimate_extent_size,
    validate_extent,
    get_validator,
)


@pytest.fixture
def validator():
    """Create a fresh ExtentValidator."""
    return ExtentValidator()


# ---------------------------------------------------------------------------
# Size estimation -- basic spatial calculations
# ---------------------------------------------------------------------------


class TestSizeEstimation:
    """Tests for estimate_size spatial calculations."""

    def test_small_extent_ok_severity(self, validator, small_spatial_extent):
        """A small extent should have 'ok' severity."""
        est = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            collection="sentinel-2-l2a",
        )

        assert est.severity == "ok"
        assert est.area_km2 > 0
        assert est.total_pixels > 0
        assert est.total_bytes > 0

    def test_area_calculation(self, validator):
        """Verify width/height in km are approximately correct at equator."""
        extent = {"west": 0.0, "south": 0.0, "east": 1.0, "north": 1.0}
        est = validator.estimate_size(spatial_extent=extent)

        # At equator, 1 degree latitude ~ 111 km
        assert est.height_km == pytest.approx(111.0, rel=0.05)
        # At equator, 1 degree longitude ~ 111 km
        assert est.width_km == pytest.approx(111.0, rel=0.05)
        assert est.area_km2 == pytest.approx(111.0 * 111.0, rel=0.1)

    def test_pixel_count_sentinel2(self, validator):
        """Verify pixel count for Sentinel-2 (10m resolution)."""
        # 1km x 1km area
        extent = {"west": 0.0, "south": 0.0, "east": 0.009, "north": 0.009}
        est = validator.estimate_size(
            spatial_extent=extent,
            collection="sentinel-2-l2a",
        )

        # ~1km / 10m = ~100 pixels per side
        assert est.pixel_width > 50
        assert est.pixel_height > 50

    def test_landsat_lower_resolution(self, validator):
        """Landsat (30m) should produce fewer pixels than Sentinel-2 (10m)."""
        extent = {"west": 0.0, "south": 0.0, "east": 1.0, "north": 1.0}

        est_s2 = validator.estimate_size(
            spatial_extent=extent, collection="sentinel-2-l2a"
        )
        est_ls = validator.estimate_size(
            spatial_extent=extent, collection="landsat-c2-l2"
        )

        assert est_ls.total_pixels < est_s2.total_pixels

    def test_known_collections_have_metadata(self):
        """All known collections should have resolution and band count."""
        for coll in COLLECTION_RESOLUTIONS:
            assert coll in COLLECTION_BANDS


# ---------------------------------------------------------------------------
# Temporal estimation
# ---------------------------------------------------------------------------


class TestTemporalEstimation:
    """Tests for temporal scene count estimation."""

    def test_no_temporal_returns_one_scene(self, validator, small_spatial_extent):
        """Without temporal extent, estimated_scenes should be 1."""
        est = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=None,
        )

        assert est.estimated_scenes == 1
        assert est.days_span == 1

    def test_30_days_sentinel2(self, validator, small_spatial_extent):
        """30 days of Sentinel-2 (5-day revisit) should give ~6 scenes."""
        est = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-07-01"],
            collection="sentinel-2-l2a",
        )

        assert est.days_span == 30
        # 30 days / 5 day revisit = 6 scenes
        assert est.estimated_scenes == 6

    def test_static_collection_one_scene(self, validator, small_spatial_extent):
        """Static collections (DEM) should always return 1 scene."""
        est = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-01-01", "2024-12-31"],
            collection="cop-dem-glo-30",
        )

        assert est.estimated_scenes == 1

    def test_longer_temporal_range_more_data(self, validator, small_spatial_extent):
        """A longer temporal range should produce more estimated bytes."""
        est_short = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
            collection="sentinel-2-l2a",
        )
        est_long = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=["2024-01-01", "2024-12-31"],
            collection="sentinel-2-l2a",
        )

        assert est_long.total_bytes > est_short.total_bytes


# ---------------------------------------------------------------------------
# Warning severity thresholds
# ---------------------------------------------------------------------------


class TestSeverityThresholds:
    """Tests for info/warning/error severity levels."""

    def test_info_threshold(self, validator):
        """Moderate-size request should get 'info' severity."""
        # Use a smaller area that produces ~100MB (info threshold)
        extent = {"west": 0.0, "south": 0.0, "east": 0.1, "north": 0.1}
        est = validator.estimate_size(
            spatial_extent=extent,
            temporal_extent=["2024-06-01", "2024-06-30"],
            collection="sentinel-2-l2a",
        )

        # This should be around info level or ok
        assert est.severity in ("ok", "info")

    def test_large_extent_warning_or_error(self, validator, large_spatial_extent):
        """A very large extent should trigger warning or error."""
        est = validator.estimate_size(
            spatial_extent=large_spatial_extent,
            temporal_extent=["2024-01-01", "2024-12-31"],
            collection="sentinel-2-l2a",
        )

        assert est.severity in ("warning", "error")
        assert len(est.warnings) > 0

    def test_suggestions_provided_for_warnings(self, validator, large_spatial_extent):
        """When warnings are generated, suggestions should be provided."""
        est = validator.estimate_size(
            spatial_extent=large_spatial_extent,
            temporal_extent=["2024-01-01", "2024-12-31"],
        )

        assert len(est.suggestions) > 0


# ---------------------------------------------------------------------------
# Invalid / edge-case extents
# ---------------------------------------------------------------------------


class TestInvalidExtents:
    """Tests for invalid or edge-case extents."""

    def test_south_greater_than_north(self, validator):
        """South > North should produce an error severity."""
        extent = {"west": 0.0, "south": 50.0, "east": 1.0, "north": 40.0}
        est = validator.estimate_size(spatial_extent=extent)

        assert est.severity == "error"
        assert any("South" in w or "south" in w.lower() for w in est.warnings)

    def test_longitude_out_of_range(self, validator):
        """Longitude outside [-180, 180] should produce error."""
        extent = {"west": -200.0, "south": 0.0, "east": 10.0, "north": 10.0}
        est = validator.estimate_size(spatial_extent=extent)

        assert est.severity == "error"
        assert any("Longitude" in w or "longitude" in w.lower() for w in est.warnings)

    def test_latitude_out_of_range(self, validator):
        """Latitude outside [-90, 90] should produce error."""
        extent = {"west": 0.0, "south": -100.0, "east": 10.0, "north": 10.0}
        est = validator.estimate_size(spatial_extent=extent)

        assert est.severity == "error"
        assert any("Latitude" in w or "latitude" in w.lower() for w in est.warnings)

    def test_antimeridian_crossing(self, validator):
        """West > East indicates antimeridian crossing -- should warn."""
        extent = {"west": 170.0, "south": 0.0, "east": -170.0, "north": 10.0}
        est = validator.estimate_size(spatial_extent=extent)

        assert any("antimeridian" in w.lower() for w in est.warnings)

    def test_long_temporal_range_warning(self, validator, small_spatial_extent):
        """Temporal range > 365 days should produce a warning."""
        est = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            temporal_extent=["2020-01-01", "2024-01-01"],
            collection="sentinel-2-l2a",
        )

        assert any("temporal" in w.lower() for w in est.warnings)

    def test_large_area_warning(self, validator):
        """Area > 10,000 km^2 should produce a warning."""
        extent = {"west": 0.0, "south": 0.0, "east": 2.0, "north": 2.0}
        est = validator.estimate_size(spatial_extent=extent)

        # 2 degrees ~ 222 km per side at equator = ~49,000 km^2
        assert est.area_km2 > 10000
        assert any("spatial extent" in w.lower() or "km" in w.lower() for w in est.warnings)


# ---------------------------------------------------------------------------
# Band selection
# ---------------------------------------------------------------------------


class TestBandSelection:
    """Tests for custom band selection impact on size."""

    def test_fewer_bands_less_data(self, validator, small_spatial_extent):
        """Selecting fewer bands should produce less estimated data."""
        est_all = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            collection="sentinel-2-l2a",
        )
        est_few = validator.estimate_size(
            spatial_extent=small_spatial_extent,
            collection="sentinel-2-l2a",
            bands=["red", "nir"],
        )

        assert est_few.total_bytes < est_all.total_bytes


# ---------------------------------------------------------------------------
# ExtentEstimate serialization
# ---------------------------------------------------------------------------


class TestExtentEstimateSerialization:
    """Tests for ExtentEstimate.to_dict()."""

    def test_to_dict_structure(self, validator, small_spatial_extent):
        """Verify the structure of the serialized estimate."""
        est = validator.estimate_size(spatial_extent=small_spatial_extent)
        d = est.to_dict()

        assert "spatial" in d
        assert "temporal" in d
        assert "size" in d
        assert "severity" in d
        assert "warnings" in d
        assert "suggestions" in d

    def test_to_dict_human_readable_size(self, validator, small_spatial_extent):
        """The human-readable size should contain a unit."""
        est = validator.estimate_size(spatial_extent=small_spatial_extent)
        d = est.to_dict()

        human_size = d["size"]["human"]
        assert any(unit in human_size for unit in ["B", "KB", "MB", "GB", "TB"])


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_estimate_extent_size(self, small_spatial_extent):
        """estimate_extent_size should return a dict."""
        result = estimate_extent_size(spatial_extent=small_spatial_extent)

        assert isinstance(result, dict)
        assert "spatial" in result

    def test_validate_extent_valid(self, small_spatial_extent):
        """validate_extent should return valid=True for a small extent."""
        result = validate_extent(spatial_extent=small_spatial_extent)

        assert result["valid"] is True
        assert result["error"] is False

    def test_validate_extent_invalid(self):
        """validate_extent should return valid=False for an invalid extent."""
        bad_extent = {"west": 0.0, "south": 50.0, "east": 1.0, "north": 40.0}
        result = validate_extent(spatial_extent=bad_extent)

        assert result["valid"] is False
        assert result["error"] is True

    def test_validate_extent_requires_confirmation(self, large_spatial_extent):
        """Large valid extents should require user confirmation."""
        result = validate_extent(
            spatial_extent=large_spatial_extent,
            temporal_extent=["2024-01-01", "2024-12-31"],
        )

        # Large extent triggers warning or error
        assert result["requires_confirmation"] or result["error"]

    def test_get_validator_singleton(self):
        """get_validator should return the same instance."""
        v1 = get_validator()
        v2 = get_validator()
        assert v1 is v2
