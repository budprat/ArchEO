"""Tests for extent validation."""

import pytest
from datetime import datetime, timedelta

from openeo_app.validation.extent_validator import (
    STACExtentValidator,
    ValidatedExtent,
    validate_extent,
)
from openeo_app.core.exceptions import ExtentValidationError


class TestSpatialExtentValidation:
    """Tests for spatial extent validation."""

    def test_valid_extent_passes(self):
        """Test that valid extent passes without modification."""
        extent = {
            "west": 11.0,
            "south": 46.0,
            "east": 12.0,
            "north": 47.0,
        }

        result = STACExtentValidator.validate_spatial_extent(extent)

        assert not result.was_modified
        assert result.west == 11.0
        assert result.east == 12.0

    def test_oversized_extent_reduction(self):
        """Verify large extents are reduced to max."""
        extent = {
            "west": 0.0,
            "south": 0.0,
            "east": 20.0,  # 20° width > 10° max
            "north": 15.0,  # 15° height > 10° max
        }

        result = STACExtentValidator.validate_spatial_extent(extent, max_degrees=10.0)

        assert result.was_modified
        # Width should be reduced to 10°
        assert (result.east - result.west) == pytest.approx(10.0, rel=0.01)
        # Height should be reduced to 10°
        assert (result.north - result.south) == pytest.approx(10.0, rel=0.01)

    def test_center_preserved_on_reduction(self):
        """Verify center point is preserved when extent is reduced."""
        extent = {
            "west": 0.0,
            "south": 40.0,
            "east": 20.0,
            "north": 60.0,
        }
        original_center_lon = 10.0  # (0 + 20) / 2
        original_center_lat = 50.0  # (40 + 60) / 2

        result = STACExtentValidator.validate_spatial_extent(extent, max_degrees=10.0)

        new_center_lon = (result.west + result.east) / 2
        new_center_lat = (result.south + result.north) / 2

        assert new_center_lon == pytest.approx(original_center_lon, rel=0.01)
        assert new_center_lat == pytest.approx(original_center_lat, rel=0.01)

    def test_global_extent_rejection(self):
        """Verify 360° extent is limited or rejected."""
        extent = {
            "west": -180.0,
            "south": -90.0,
            "east": 180.0,
            "north": 90.0,
        }

        # With auto_limit=True, should be reduced
        result = STACExtentValidator.validate_spatial_extent(
            extent, max_degrees=10.0, auto_limit=True
        )
        assert result.was_modified

        # With auto_limit=False, should raise error
        with pytest.raises(ExtentValidationError):
            STACExtentValidator.validate_spatial_extent(
                extent, max_degrees=10.0, auto_limit=False
            )

    def test_invalid_coordinates_rejected(self):
        """Test that invalid coordinates raise error."""
        # Longitude out of range
        extent = {
            "west": -200.0,  # Invalid
            "south": 0.0,
            "east": 10.0,
            "north": 10.0,
        }

        with pytest.raises(ExtentValidationError):
            STACExtentValidator.validate_spatial_extent(extent)

    def test_swapped_coordinates_fixed(self):
        """Test that swapped coordinates are corrected."""
        extent = {
            "west": 12.0,  # west > east
            "south": 47.0,  # south > north
            "east": 11.0,
            "north": 46.0,
        }

        result = STACExtentValidator.validate_spatial_extent(extent)

        assert result.west < result.east
        assert result.south < result.north

    def test_minimum_extent_enforced(self):
        """Test that minimum extent size is enforced."""
        extent = {
            "west": 11.0,
            "south": 46.0,
            "east": 11.0,  # Point query (0 width)
            "north": 46.0,  # Point query (0 height)
        }

        result = STACExtentValidator.validate_spatial_extent(extent)

        # Should have minimum extent (use approx for floating point)
        width = result.east - result.west
        height = result.north - result.south
        assert width >= STACExtentValidator.MIN_EXTENT_SIZE * 0.99, f"Width {width} too small"
        assert height >= STACExtentValidator.MIN_EXTENT_SIZE * 0.99, f"Height {height} too small"


class TestTemporalExtentValidation:
    """Tests for temporal extent validation."""

    def test_valid_temporal_passes(self):
        """Test that valid temporal extent passes."""
        extent = ["2024-01-01", "2024-02-01"]

        start, end, modified = STACExtentValidator.validate_temporal_extent(extent)

        assert not modified
        assert start is not None
        assert end is not None

    def test_long_temporal_reduced(self):
        """Test that long temporal ranges are reduced."""
        extent = ["2020-01-01", "2024-01-01"]  # 4 years

        start, end, modified = STACExtentValidator.validate_temporal_extent(
            extent, max_days=365
        )

        assert modified
        # Should be reduced to max_days
        assert (end - start).days <= 365

    def test_swapped_dates_fixed(self):
        """Test that swapped dates are corrected."""
        extent = ["2024-06-01", "2024-01-01"]  # End before start

        start, end, modified = STACExtentValidator.validate_temporal_extent(extent)

        assert start < end

    def test_invalid_date_format_rejected(self):
        """Test that invalid date format raises error."""
        extent = ["not-a-date", "2024-01-01"]

        with pytest.raises(ExtentValidationError):
            STACExtentValidator.validate_temporal_extent(extent)


class TestDataVolumeEstimation:
    """Tests for data volume estimation."""

    def test_estimate_small_area(self):
        """Test volume estimation for small area."""
        spatial = {"west": 11.0, "south": 46.0, "east": 11.1, "north": 46.1}

        result = STACExtentValidator.estimate_data_volume(
            spatial, temporal_days=30, resolution_m=10
        )

        assert "total_bytes" in result
        assert "size_human" in result
        assert result["total_bytes"] > 0

    def test_estimate_larger_area(self):
        """Test that larger areas produce larger estimates."""
        small = {"west": 11.0, "south": 46.0, "east": 11.1, "north": 46.1}
        large = {"west": 11.0, "south": 46.0, "east": 12.0, "north": 47.0}

        small_est = STACExtentValidator.estimate_data_volume(small, temporal_days=30)
        large_est = STACExtentValidator.estimate_data_volume(large, temporal_days=30)

        assert large_est["total_bytes"] > small_est["total_bytes"]


class TestValidateExtentConvenience:
    """Tests for validate_extent convenience function."""

    def test_validates_both_extents(self):
        """Test that both spatial and temporal are validated."""
        spatial = {"west": 0, "south": 0, "east": 20, "north": 20}  # Too large
        temporal = ["2020-01-01", "2024-01-01"]  # Too long

        result = validate_extent(
            spatial_extent=spatial,
            temporal_extent=temporal,
            max_spatial_degrees=10.0,
            max_temporal_days=365,
        )

        assert result["spatial_modified"]
        assert result["temporal_modified"]
        assert len(result["warnings"]) == 2

    def test_no_modification_when_valid(self):
        """Test no warnings when extents are valid."""
        spatial = {"west": 11.0, "south": 46.0, "east": 11.5, "north": 46.5}
        temporal = ["2024-01-01", "2024-02-01"]

        result = validate_extent(
            spatial_extent=spatial,
            temporal_extent=temporal,
        )

        assert not result["spatial_modified"]
        assert not result["temporal_modified"]
        assert len(result["warnings"]) == 0


class TestValidatedExtent:
    """Tests for ValidatedExtent dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        extent = ValidatedExtent(
            west=11.0, south=46.0, east=12.0, north=47.0, crs="EPSG:4326"
        )

        result = extent.to_dict()

        assert result["west"] == 11.0
        assert result["crs"] == "EPSG:4326"

    def test_stores_original_on_modification(self):
        """Test that original extent is stored when modified."""
        extent = {
            "west": 0.0,
            "south": 0.0,
            "east": 20.0,
            "north": 20.0,
        }

        result = STACExtentValidator.validate_spatial_extent(extent, max_degrees=10.0)

        assert result.was_modified
        assert result.original_extent is not None
        assert result.original_extent["east"] == 20.0
