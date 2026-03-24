"""
Functional tests for agent/tools/Archaeology.py

Each test creates a synthetic image or DEM using cv2/numpy, writes it as a
GeoTIFF to a temp directory, calls the tool function directly, and asserts
the expected return type and values.
"""

import sys
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Bootstrap: Archaeology.py calls argparse at import time so we must inject
# --temp_dir before the module is imported.
# ---------------------------------------------------------------------------

_tmp = tempfile.mkdtemp(prefix="archeo_test_")
sys.argv = ["test", "--temp_dir", _tmp]

# Ensure the tools directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "agent" / "tools"))

import Archaeology as arch  # noqa: E402 (must come after argv injection)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_geotiff(array: np.ndarray, path: str, bands: int = 1) -> str:
    """Write a numpy array to a single-band or multi-band GeoTIFF."""
    from osgeo import gdal

    path = str(path)
    rows, cols = array.shape[:2]
    driver = gdal.GetDriverByName("GTiff")

    if bands == 1:
        ds = driver.Create(path, cols, rows, 1, gdal.GDT_Byte)
        ds.GetRasterBand(1).WriteArray(array.astype(np.uint8))
    else:
        ds = driver.Create(path, cols, rows, bands, gdal.GDT_Byte)
        for b in range(bands):
            ds.GetRasterBand(b + 1).WriteArray(array[:, :, b].astype(np.uint8))

    ds.FlushCache()
    ds = None
    return path


def _write_dem(array: np.ndarray, path: str) -> str:
    """Write a float32 DEM GeoTIFF with a minimal geotransform."""
    from osgeo import gdal

    path = str(path)
    rows, cols = array.shape
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0, 30, 0, 0, 0, -30))   # 30 m cell size
    ds.GetRasterBand(1).WriteArray(array.astype(np.float32))
    ds.FlushCache()
    ds = None
    return path


def _synthetic_grayscale(shape=(128, 128)) -> np.ndarray:
    """Create a grayscale image with strong edges (circle on gradient bg)."""
    img = np.zeros(shape, dtype=np.uint8)
    # gradient background
    img[:, :] = np.linspace(30, 200, shape[1], dtype=np.uint8)
    # white circle
    cy, cx = shape[0] // 2, shape[1] // 2
    r = min(shape) // 4
    for y in range(shape[0]):
        for x in range(shape[1]):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2:
                img[y, x] = 255
    return img


def _synthetic_dem(shape=(64, 64)) -> np.ndarray:
    """Create a simple synthetic DEM (cone-shaped hill)."""
    cy, cx = shape[0] // 2, shape[1] // 2
    y_idx, x_idx = np.mgrid[0:shape[0], 0:shape[1]]
    dem = 200 - 3 * np.sqrt((x_idx - cx) ** 2 + (y_idx - cy) ** 2)
    return np.clip(dem, 0, 200).astype(np.float32)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tmp_dir():
    return Path(_tmp)


@pytest.fixture(scope="module")
def gray_tif(tmp_dir):
    img = _synthetic_grayscale()
    path = tmp_dir / "gray_input.tif"
    _write_geotiff(img, str(path))
    return str(path)


@pytest.fixture(scope="module")
def dem_tif(tmp_dir):
    dem = _synthetic_dem()
    path = tmp_dir / "dem_input.tif"
    _write_dem(dem, str(path))
    return str(path)


# ---------------------------------------------------------------------------
# Test: edge_detection_canny
# ---------------------------------------------------------------------------

class TestEdgeDetectionCanny:
    def test_returns_path_string(self, gray_tif, tmp_dir):
        result = arch.edge_detection_canny(gray_tif, "canny/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, gray_tif, tmp_dir):
        result = arch.edge_detection_canny(gray_tif, "canny/out.tif")
        assert Path(result).exists()

    def test_output_is_readable_geotiff(self, gray_tif, tmp_dir):
        from osgeo import gdal
        result = arch.edge_detection_canny(gray_tif, "canny/out2.tif")
        ds = gdal.Open(result)
        assert ds is not None
        arr = ds.GetRasterBand(1).ReadAsArray()
        assert arr.shape == (128, 128)
        ds = None

    def test_custom_thresholds(self, gray_tif):
        result = arch.edge_detection_canny(gray_tif, "canny/out_thresh.tif", low_threshold=10, high_threshold=80)
        assert Path(result).exists()

    def test_has_nonzero_edges(self, gray_tif):
        from osgeo import gdal
        result = arch.edge_detection_canny(gray_tif, "canny/out_nz.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.max() > 0, "Canny should detect some edges in the synthetic image"


# ---------------------------------------------------------------------------
# Test: edge_detection_sobel
# ---------------------------------------------------------------------------

class TestEdgeDetectionSobel:
    def test_returns_path_string(self, gray_tif):
        result = arch.edge_detection_sobel(gray_tif, "sobel/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, gray_tif):
        result = arch.edge_detection_sobel(gray_tif, "sobel/out.tif")
        assert Path(result).exists()

    def test_output_shape(self, gray_tif):
        from osgeo import gdal
        result = arch.edge_detection_sobel(gray_tif, "sobel/out_shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (128, 128)

    def test_custom_ksize(self, gray_tif):
        result = arch.edge_detection_sobel(gray_tif, "sobel/out_k5.tif", ksize=5)
        assert Path(result).exists()

    def test_has_nonzero_gradient(self, gray_tif):
        from osgeo import gdal
        result = arch.edge_detection_sobel(gray_tif, "sobel/out_nz.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.max() > 0, "Sobel should produce non-zero gradients"


# ---------------------------------------------------------------------------
# Test: linear_feature_detection
# ---------------------------------------------------------------------------

class TestLinearFeatureDetection:
    def _line_image(self, tmp_dir):
        """Create an image with obvious straight lines."""
        img = np.zeros((128, 128), dtype=np.uint8)
        img[30, :] = 255   # horizontal line
        img[:, 60] = 255   # vertical line
        path = tmp_dir / "lines_input.tif"
        _write_geotiff(img, str(path))
        return str(path)

    def test_returns_dict_with_required_keys(self, tmp_dir, gray_tif):
        result = arch.linear_feature_detection(gray_tif, "lines/out.tif")
        assert isinstance(result, dict)
        for key in ("image_path", "lines", "orientations", "count"):
            assert key in result

    def test_count_matches_lines_length(self, gray_tif):
        result = arch.linear_feature_detection(gray_tif, "lines/count.tif")
        assert result["count"] == len(result["lines"])
        assert result["count"] == len(result["orientations"])

    def test_output_image_exists(self, gray_tif):
        result = arch.linear_feature_detection(gray_tif, "lines/img.tif")
        assert Path(result["image_path"]).exists()

    def test_detects_lines_in_line_image(self, tmp_dir):
        img_path = self._line_image(tmp_dir)
        result = arch.linear_feature_detection(img_path, "lines/line_detect.tif", min_line_length=20)
        assert result["count"] > 0, "Should detect at least one line"

    def test_orientation_range(self, tmp_dir):
        img_path = self._line_image(tmp_dir)
        result = arch.linear_feature_detection(img_path, "lines/orient.tif", min_line_length=20)
        for angle in result["orientations"]:
            assert 0 <= angle <= 90, f"Orientation {angle} out of range"


# ---------------------------------------------------------------------------
# Test: geometric_pattern_analysis
# ---------------------------------------------------------------------------

class TestGeometricPatternAnalysis:
    def test_returns_dict_with_required_keys(self, gray_tif):
        result = arch.geometric_pattern_analysis(gray_tif, "shapes/out.tif")
        assert isinstance(result, dict)
        for key in ("image_path", "shapes", "count"):
            assert key in result

    def test_count_matches_shapes_length(self, gray_tif):
        result = arch.geometric_pattern_analysis(gray_tif, "shapes/count.tif")
        assert result["count"] == len(result["shapes"])

    def test_output_image_exists(self, gray_tif):
        result = arch.geometric_pattern_analysis(gray_tif, "shapes/img.tif")
        assert Path(result["image_path"]).exists()

    def test_shape_descriptor_keys(self, gray_tif):
        result = arch.geometric_pattern_analysis(gray_tif, "shapes/keys.tif")
        if result["count"] > 0:
            shape = result["shapes"][0]
            for key in ("area", "perimeter", "circularity", "aspect_ratio", "bounding_box"):
                assert key in shape

    def test_min_area_filter(self, gray_tif):
        result_low = arch.geometric_pattern_analysis(gray_tif, "shapes/low_area.tif", min_area=1)
        result_high = arch.geometric_pattern_analysis(gray_tif, "shapes/high_area.tif", min_area=10000)
        assert result_low["count"] >= result_high["count"], "Lower min_area should yield >= shapes"

    def test_circularity_circle_image(self, tmp_dir):
        """A near-perfect circle should yield high circularity."""
        import cv2
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (100, 100), 60, 255, -1)
        path = tmp_dir / "circle_input.tif"
        _write_geotiff(img, str(path))
        result = arch.geometric_pattern_analysis(str(path), "shapes/circ.tif", min_area=100)
        assert result["count"] > 0
        circ = result["shapes"][0]["circularity"]
        assert circ > 0.7, f"Circle circularity {circ} should be > 0.7"


# ---------------------------------------------------------------------------
# Test: dem_hillshade
# ---------------------------------------------------------------------------

class TestDemHillshade:
    def test_returns_path_string(self, dem_tif):
        result = arch.dem_hillshade(dem_tif, "hillshade/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, dem_tif):
        result = arch.dem_hillshade(dem_tif, "hillshade/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_dem(self, dem_tif):
        from osgeo import gdal
        result = arch.dem_hillshade(dem_tif, "hillshade/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)

    def test_values_in_uint8_range(self, dem_tif):
        from osgeo import gdal
        result = arch.dem_hillshade(dem_tif, "hillshade/range.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.min() >= 0
        assert arr.max() <= 255

    def test_custom_azimuth_altitude(self, dem_tif):
        result = arch.dem_hillshade(dem_tif, "hillshade/custom.tif", azimuth=90, altitude=30)
        assert Path(result).exists()

    def test_geotransform_preserved(self, dem_tif):
        from osgeo import gdal
        result = arch.dem_hillshade(dem_tif, "hillshade/geo.tif")
        ds = gdal.Open(result)
        gt = ds.GetGeoTransform()
        ds = None
        assert gt is not None
        # Cell size should be 30 m as set in _write_dem
        assert abs(gt[1] - 30) < 1e-3


# ---------------------------------------------------------------------------
# Test: texture_analysis_glcm
# ---------------------------------------------------------------------------

class TestTextureAnalysisGlcm:
    def test_returns_dict_with_required_keys(self, gray_tif):
        result = arch.texture_analysis_glcm(gray_tif)
        assert isinstance(result, dict)
        for key in ("contrast", "homogeneity", "entropy", "correlation", "energy"):
            assert key in result

    def test_all_values_are_floats(self, gray_tif):
        result = arch.texture_analysis_glcm(gray_tif)
        for key, val in result.items():
            assert isinstance(val, float), f"{key} should be float, got {type(val)}"

    def test_homogeneity_in_range(self, gray_tif):
        result = arch.texture_analysis_glcm(gray_tif)
        assert 0.0 <= result["homogeneity"] <= 1.0

    def test_energy_in_range(self, gray_tif):
        result = arch.texture_analysis_glcm(gray_tif)
        assert 0.0 <= result["energy"] <= 1.0

    def test_entropy_is_positive(self, gray_tif):
        result = arch.texture_analysis_glcm(gray_tif)
        assert result["entropy"] >= 0.0

    def test_custom_distances_and_angles(self, gray_tif):
        import math
        result = arch.texture_analysis_glcm(
            gray_tif,
            distances=[1, 2],
            angles=[0, math.pi / 4, math.pi / 2],
        )
        assert isinstance(result, dict)
        assert result["contrast"] >= 0

    def test_uniform_image_high_homogeneity(self, tmp_dir):
        """A uniform image should give maximum homogeneity and minimum contrast."""
        img = np.full((64, 64), 128, dtype=np.uint8)
        path = tmp_dir / "uniform_input.tif"
        _write_geotiff(img, str(path))
        result = arch.texture_analysis_glcm(str(path))
        assert result["homogeneity"] > 0.9, "Uniform image should have high homogeneity"
        assert result["contrast"] < 0.1, "Uniform image should have near-zero contrast"
