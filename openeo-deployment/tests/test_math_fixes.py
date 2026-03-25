"""Tests for numerically stable math operations."""

import numpy as np
import pytest
import xarray as xr

from openeo_app.processes.math_fixes import (
    normalized_difference_stable,
    divide_safe,
    apply_scale_factor,
    EPSILON,
)


class TestNormalizedDifferenceStable:
    """Tests for normalized_difference_stable function."""

    def test_basic_ndvi_calculation(self):
        """Test basic NDVI calculation with typical values."""
        # NIR = 0.8, RED = 0.2 -> NDVI = (0.8 - 0.2) / (0.8 + 0.2) = 0.6
        nir = np.array([0.8])
        red = np.array([0.2])

        result = normalized_difference_stable(nir, red)

        np.testing.assert_almost_equal(result[0], 0.6, decimal=5)

    def test_zero_denominator_protection(self):
        """Test epsilon protection with dark pixels (nir=0, red=0)."""
        # Both bands zero - should return ~0 instead of NaN
        nir = np.array([0.0, 0.0, 0.0])
        red = np.array([0.0, 0.0, 0.0])

        result = normalized_difference_stable(nir, red)

        # Should not contain NaN or Inf
        assert not np.any(np.isnan(result)), "Result contains NaN"
        assert not np.any(np.isinf(result)), "Result contains Inf"

        # With epsilon, (0-0)/(0+0+eps) = 0
        np.testing.assert_almost_equal(result, [0.0, 0.0, 0.0], decimal=5)

    def test_clipping_high_values(self):
        """Verify output is clipped to max 1.0."""
        # Edge case that could produce values > 1
        nir = np.array([1.0])
        red = np.array([-0.5])  # Negative reflectance (invalid but test clipping)

        result = normalized_difference_stable(nir, red)

        assert result[0] <= 1.0, f"Result {result[0]} exceeds 1.0"

    def test_clipping_low_values(self):
        """Verify output is clipped to min -1.0."""
        # Edge case that could produce values < -1
        nir = np.array([-0.5])  # Negative reflectance (invalid but test clipping)
        red = np.array([1.0])

        result = normalized_difference_stable(nir, red)

        assert result[0] >= -1.0, f"Result {result[0]} below -1.0"

    def test_typical_vegetation_range(self):
        """Test typical NDVI values for vegetation."""
        # Dense vegetation: high NIR, low RED
        nir = np.array([0.9])
        red = np.array([0.1])
        result = normalized_difference_stable(nir, red)
        assert 0.7 < result[0] < 0.9, f"Expected high NDVI for vegetation, got {result[0]}"

        # Bare soil: similar NIR and RED
        nir = np.array([0.3])
        red = np.array([0.25])
        result = normalized_difference_stable(nir, red)
        assert 0.0 < result[0] < 0.2, f"Expected low NDVI for bare soil, got {result[0]}"

        # Water: low NIR, higher RED
        nir = np.array([0.05])
        red = np.array([0.1])
        result = normalized_difference_stable(nir, red)
        assert result[0] < 0, f"Expected negative NDVI for water, got {result[0]}"

    def test_xarray_dataarray_input(self):
        """Test with xarray DataArray input."""
        nir = xr.DataArray([0.8, 0.6, 0.4], dims=["x"])
        red = xr.DataArray([0.2, 0.3, 0.35], dims=["x"])

        result = normalized_difference_stable(nir, red)

        assert isinstance(result, xr.DataArray)
        assert result.shape == (3,)
        assert not np.any(np.isnan(result.values))

    def test_array_shapes_preserved(self):
        """Test that input shapes are preserved."""
        shape = (3, 10, 10)
        nir = np.random.uniform(0.3, 0.9, shape)
        red = np.random.uniform(0.1, 0.5, shape)

        result = normalized_difference_stable(nir, red)

        assert result.shape == shape


class TestDivideSafe:
    """Tests for divide_safe function."""

    def test_normal_division(self):
        """Test normal division works correctly."""
        x = np.array([10.0, 20.0, 30.0])
        y = np.array([2.0, 4.0, 5.0])

        result = divide_safe(x, y)

        np.testing.assert_array_equal(result, [5.0, 5.0, 6.0])

    def test_zero_division_protection(self):
        """Test division by zero protection."""
        x = np.array([10.0, 20.0, 30.0])
        y = np.array([0.0, 0.0, 0.0])

        result = divide_safe(x, y)

        # Should not contain Inf
        assert not np.any(np.isinf(result)), "Result contains Inf"
        # Should produce very large numbers (x / epsilon)
        assert np.all(result > 1e9), "Expected large values from division by epsilon"

    def test_mixed_zeros(self):
        """Test with mix of zeros and non-zeros."""
        x = np.array([10.0, 20.0, 30.0])
        y = np.array([2.0, 0.0, 5.0])

        result = divide_safe(x, y)

        assert result[0] == 5.0
        assert not np.isinf(result[1])  # Zero divisor handled
        assert result[2] == 6.0

    def test_xarray_dataarray_input(self):
        """Test with xarray DataArray input."""
        x = xr.DataArray([10.0, 20.0, 30.0], dims=["x"])
        y = xr.DataArray([2.0, 0.0, 5.0], dims=["x"])

        result = divide_safe(x, y)

        assert isinstance(result, xr.DataArray)
        assert not np.any(np.isinf(result.values))


class TestApplyScaleFactor:
    """Tests for apply_scale_factor function."""

    def test_sentinel2_scale(self):
        """Test Sentinel-2 scale factor (0.0001)."""
        # DN value 5000 -> reflectance 0.5
        dn = np.array([5000, 10000, 2500])

        result = apply_scale_factor(dn, scale=0.0001)

        np.testing.assert_almost_equal(result, [0.5, 1.0, 0.25], decimal=5)

    def test_with_offset(self):
        """Test scale factor with offset."""
        dn = np.array([1000, 2000, 3000])

        result = apply_scale_factor(dn, scale=0.1, offset=-100)

        np.testing.assert_almost_equal(result, [0.0, 100.0, 200.0], decimal=5)

    def test_xarray_input(self):
        """Test with xarray DataArray input."""
        dn = xr.DataArray([5000, 10000], dims=["x"])

        result = apply_scale_factor(dn, scale=0.0001)

        assert isinstance(result, xr.DataArray)
        np.testing.assert_almost_equal(result.values, [0.5, 1.0], decimal=5)


class TestStableProcesses:
    """Tests for STABLE_PROCESSES dictionary."""

    def test_all_processes_callable(self):
        """Test that all stable processes are callable."""
        from openeo_app.processes.math_fixes import STABLE_PROCESSES

        for name, func in STABLE_PROCESSES.items():
            assert callable(func), f"{name} is not callable"

    def test_expected_processes_present(self):
        """Test that expected processes are in the dictionary."""
        from openeo_app.processes.math_fixes import STABLE_PROCESSES

        expected = ["normalized_difference", "divide", "add", "subtract", "multiply"]
        for name in expected:
            assert name in STABLE_PROCESSES, f"{name} not in STABLE_PROCESSES"
