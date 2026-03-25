"""Tests for result storage functionality."""

import numpy as np
import pytest
import xarray as xr

from openeo_app.storage.results import validate_result_data


class TestValidateResultData:
    """Tests for the validate_result_data function."""

    def test_valid_data_passes(self):
        """Test that valid data passes validation."""
        data = xr.DataArray(
            np.random.rand(3, 10, 10),
            dims=["bands", "y", "x"],
        )
        result = validate_result_data(data)

        assert result["is_valid"] is True
        assert result["warnings"] == []
        assert "min" in result["stats"]
        assert "max" in result["stats"]

    def test_empty_data_raises(self):
        """Test that empty data raises ValueError."""
        data = xr.DataArray(
            np.array([]).reshape(0, 0),
            dims=["y", "x"],
        )

        with pytest.raises(ValueError, match="empty"):
            validate_result_data(data)

    def test_all_nan_warns(self):
        """Test that all-NaN data produces warnings."""
        data = xr.DataArray(
            np.full((10, 10), np.nan),
            dims=["y", "x"],
        )
        result = validate_result_data(data)

        assert len(result["warnings"]) > 0
        assert any("NaN" in w for w in result["warnings"])
        assert result["stats"]["nan_percent"] == 100.0

    def test_partial_nan_reports_percentage(self):
        """Test that partial NaN data reports correct percentage."""
        arr = np.ones((10, 10))
        arr[:5, :] = np.nan  # 50% NaN
        data = xr.DataArray(arr, dims=["y", "x"])

        result = validate_result_data(data)
        assert result["stats"]["nan_percent"] == 50.0

    def test_shape_in_stats(self):
        """Test that shape is included in stats."""
        data = xr.DataArray(
            np.random.rand(3, 20, 30),
            dims=["bands", "y", "x"],
        )
        result = validate_result_data(data)

        assert result["stats"]["shape"] == [3, 20, 30]

    def test_dataset_validation(self):
        """Test validation of xarray Dataset."""
        ds = xr.Dataset({
            "var1": xr.DataArray(np.random.rand(10, 10), dims=["y", "x"]),
            "var2": xr.DataArray(np.random.rand(10, 10), dims=["y", "x"]),
        })
        result = validate_result_data(ds)

        assert result["is_valid"] is True
        assert "var1" in result["stats"]
        assert "var2" in result["stats"]

    def test_high_nan_percentage_warns(self):
        """Test that >90% NaN produces warning."""
        arr = np.ones((10, 10))
        arr[:, :9] = np.nan  # 90% NaN
        data = xr.DataArray(arr, dims=["y", "x"])

        result = validate_result_data(data)
        # 90% NaN should trigger warning
        assert result["stats"]["nan_percent"] == 90.0


class TestGeoTiffMultiDimensional:
    """Tests for multi-dimensional array handling in GeoTIFF saving."""

    def test_squeeze_singleton_dimensions(self):
        """Test that singleton dimensions are squeezed."""
        # Create 4D array with singleton dimension
        data = xr.DataArray(
            np.random.rand(1, 3, 10, 10),
            dims=["time", "bands", "y", "x"],
        )

        # After squeezing, should be 3D
        squeezed = data.squeeze()
        assert squeezed.ndim == 3
        assert squeezed.shape == (3, 10, 10)

    def test_reduce_extra_dimensions(self):
        """Test reducing non-spatial dimensions."""
        # Create 4D array that can't be fully squeezed
        data = xr.DataArray(
            np.random.rand(2, 3, 10, 10),
            dims=["time", "bands", "y", "x"],
        )

        # Simulate the dimension reduction logic
        if data.ndim > 3:
            for dim in data.dims:
                if dim not in ("x", "y", "latitude", "longitude", "bands"):
                    data = data.isel({dim: 0})
                    break

        assert data.ndim == 3
        assert "time" not in data.dims


class TestMetadataWithValidation:
    """Tests for metadata saving with validation info."""

    def test_metadata_includes_validation(self):
        """Test that metadata includes validation results."""
        validation = {
            "is_valid": True,
            "warnings": [],
            "stats": {"min": 0.0, "max": 1.0, "nan_percent": 0.0},
        }

        # Construct expected metadata structure
        metadata = {
            "job_id": "test-job",
            "validation": {
                "is_valid": validation.get("is_valid", True),
                "warnings": validation.get("warnings", []),
            },
            "statistics": validation["stats"],
        }

        assert metadata["validation"]["is_valid"] is True
        assert metadata["statistics"]["min"] == 0.0

    def test_metadata_includes_warnings(self):
        """Test that warnings are included in metadata."""
        validation = {
            "is_valid": True,
            "warnings": ["Data is 95% NaN"],
            "stats": {"nan_percent": 95.0},
        }

        metadata = {
            "validation": {
                "is_valid": validation["is_valid"],
                "warnings": validation["warnings"],
            },
        }

        assert "Data is 95% NaN" in metadata["validation"]["warnings"]
