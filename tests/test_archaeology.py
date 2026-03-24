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


# ---------------------------------------------------------------------------
# Helpers for new tests
# ---------------------------------------------------------------------------

def _write_multiband_geotiff(array: np.ndarray, path: str) -> str:
    """Write (rows, cols, bands) array as a multi-band float32 GeoTIFF."""
    from osgeo import gdal

    path = str(path)
    rows, cols, bands = array.shape
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(path, cols, rows, bands, gdal.GDT_Float32)
    for b in range(bands):
        ds.GetRasterBand(b + 1).WriteArray(array[:, :, b].astype(np.float32))
    ds.FlushCache()
    ds = None
    return path


def _synthetic_multiband(shape=(64, 64), n_bands=4) -> np.ndarray:
    """Create synthetic multi-band data (spectral variation across bands)."""
    rng = np.random.default_rng(42)
    bands = []
    for b in range(n_bands):
        band = (rng.random(shape) * 255 + b * 30).astype(np.float32)
        bands.append(band)
    return np.stack(bands, axis=-1)  # (rows, cols, bands)


# ---------------------------------------------------------------------------
# Test: principal_component_analysis
# ---------------------------------------------------------------------------

class TestPrincipalComponentAnalysis:
    @pytest.fixture(scope="class")
    def multiband_tif(self, tmp_dir):
        data = _synthetic_multiband((64, 64), n_bands=4)
        path = tmp_dir / "pca_input.tif"
        _write_multiband_geotiff(data, str(path))
        return str(path)

    def test_returns_dict_with_required_keys(self, multiband_tif):
        result = arch.principal_component_analysis(multiband_tif, "pca/out")
        assert isinstance(result, dict)
        for key in ("pc_paths", "explained_variance", "cumulative_variance"):
            assert key in result

    def test_pc_paths_exist(self, multiband_tif):
        result = arch.principal_component_analysis(multiband_tif, "pca/paths", n_components=3)
        assert len(result["pc_paths"]) == 3
        for p in result["pc_paths"]:
            assert Path(p).exists()

    def test_explained_variance_sums_to_one(self, multiband_tif):
        result = arch.principal_component_analysis(multiband_tif, "pca/var", n_components=4)
        total = sum(result["explained_variance"])
        assert abs(total - 1.0) < 1e-3, f"Explained variance should sum to ~1, got {total}"

    def test_cumulative_variance_is_monotonic(self, multiband_tif):
        result = arch.principal_component_analysis(multiband_tif, "pca/cum", n_components=3)
        cum = result["cumulative_variance"]
        for i in range(1, len(cum)):
            assert cum[i] >= cum[i - 1]

    def test_output_pc_shape(self, multiband_tif, tmp_dir):
        from osgeo import gdal
        result = arch.principal_component_analysis(multiband_tif, "pca/shape", n_components=2)
        ds = gdal.Open(result["pc_paths"][0])
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)


# ---------------------------------------------------------------------------
# Test: multi_directional_hillshade
# ---------------------------------------------------------------------------

class TestMultiDirectionalHillshade:
    def test_returns_path_string(self, dem_tif):
        result = arch.multi_directional_hillshade(dem_tif, "multihillshade/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, dem_tif):
        result = arch.multi_directional_hillshade(dem_tif, "multihillshade/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_dem(self, dem_tif):
        from osgeo import gdal
        result = arch.multi_directional_hillshade(dem_tif, "multihillshade/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)

    def test_values_in_uint8_range(self, dem_tif):
        from osgeo import gdal
        result = arch.multi_directional_hillshade(dem_tif, "multihillshade/range.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.min() >= 0
        assert arr.max() <= 255

    def test_16_directions(self, dem_tif):
        result = arch.multi_directional_hillshade(dem_tif, "multihillshade/16dir.tif", n_directions=16)
        assert Path(result).exists()


# ---------------------------------------------------------------------------
# Test: local_relief_model
# ---------------------------------------------------------------------------

class TestLocalReliefModel:
    def test_returns_path_string(self, dem_tif):
        result = arch.local_relief_model(dem_tif, "lrm/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, dem_tif):
        result = arch.local_relief_model(dem_tif, "lrm/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_dem(self, dem_tif):
        from osgeo import gdal
        result = arch.local_relief_model(dem_tif, "lrm/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)

    def test_lrm_is_float32(self, dem_tif):
        from osgeo import gdal
        result = arch.local_relief_model(dem_tif, "lrm/dtype.tif")
        ds = gdal.Open(result)
        band = ds.GetRasterBand(1)
        dt = band.DataType
        ds = None
        assert dt == gdal.GDT_Float32

    def test_lrm_has_positive_and_negative_values(self, dem_tif):
        """LRM should have both positive (raised) and negative (depressed) values."""
        from osgeo import gdal
        result = arch.local_relief_model(dem_tif, "lrm/posneg.tif", kernel_size=15)
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        # A cone-shaped DEM should produce both positive and near-zero/negative values
        assert arr.max() > 0


# ---------------------------------------------------------------------------
# Test: adaptive_contrast_enhancement
# ---------------------------------------------------------------------------

class TestAdaptiveContrastEnhancement:
    def test_returns_path_string(self, gray_tif):
        result = arch.adaptive_contrast_enhancement(gray_tif, "clahe/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, gray_tif):
        result = arch.adaptive_contrast_enhancement(gray_tif, "clahe/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_input(self, gray_tif):
        from osgeo import gdal
        result = arch.adaptive_contrast_enhancement(gray_tif, "clahe/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (128, 128)

    def test_custom_clip_and_grid(self, gray_tif):
        result = arch.adaptive_contrast_enhancement(
            gray_tif, "clahe/custom.tif", clip_limit=4.0, grid_size=16
        )
        assert Path(result).exists()

    def test_output_is_uint8(self, gray_tif):
        from osgeo import gdal
        result = arch.adaptive_contrast_enhancement(gray_tif, "clahe/dtype.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.dtype == np.uint8


# ---------------------------------------------------------------------------
# Test: band_ratio_calculator
# ---------------------------------------------------------------------------

class TestBandRatioCalculator:
    @pytest.fixture(scope="class")
    def multiband_tif(self, tmp_dir):
        data = _synthetic_multiband((64, 64), n_bands=4)
        path = tmp_dir / "ratio_input.tif"
        _write_multiband_geotiff(data, str(path))
        return str(path)

    def test_returns_dict_with_required_keys(self, multiband_tif):
        result = arch.band_ratio_calculator(multiband_tif, 1, 2, "ratio/out.tif")
        assert isinstance(result, dict)
        for key in ("image_path", "min", "max", "mean"):
            assert key in result

    def test_output_file_exists(self, multiband_tif):
        result = arch.band_ratio_calculator(multiband_tif, 1, 3, "ratio/exists.tif")
        assert Path(result["image_path"]).exists()

    def test_ratio_values_are_finite(self, multiband_tif):
        result = arch.band_ratio_calculator(multiband_tif, 2, 4, "ratio/finite.tif")
        assert np.isfinite(result["min"])
        assert np.isfinite(result["max"])
        assert np.isfinite(result["mean"])

    def test_ratio_output_shape(self, multiband_tif):
        from osgeo import gdal
        result = arch.band_ratio_calculator(multiband_tif, 1, 2, "ratio/shape.tif")
        ds = gdal.Open(result["image_path"])
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)

    def test_same_band_ratio_is_near_one(self, multiband_tif):
        """Ratio of a band with itself should be near 1.0 everywhere."""
        result = arch.band_ratio_calculator(multiband_tif, 1, 1, "ratio/same.tif")
        assert abs(result["mean"] - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Test: spectral_anomaly_detection
# ---------------------------------------------------------------------------

class TestSpectralAnomalyDetection:
    @pytest.fixture(scope="class")
    def anomaly_tif(self, tmp_dir):
        """Multi-band image with one obvious anomalous pixel."""
        data = np.ones((32, 32, 4), dtype=np.float32) * 100.0
        # Inject obvious anomaly
        data[16, 16, :] = [500.0, 0.0, 500.0, 0.0]
        path = tmp_dir / "anomaly_input.tif"
        _write_multiband_geotiff(data, str(path))
        return str(path)

    def test_returns_dict_with_required_keys(self, anomaly_tif):
        result = arch.spectral_anomaly_detection(anomaly_tif, "anomaly/out.tif")
        assert isinstance(result, dict)
        for key in ("image_path", "anomaly_count", "anomaly_percentage"):
            assert key in result

    def test_output_file_exists(self, anomaly_tif):
        result = arch.spectral_anomaly_detection(anomaly_tif, "anomaly/exists.tif")
        assert Path(result["image_path"]).exists()

    def test_detects_known_anomaly(self, anomaly_tif):
        result = arch.spectral_anomaly_detection(anomaly_tif, "anomaly/detect.tif", threshold_sigma=2.0)
        assert result["anomaly_count"] > 0, "Should detect the injected anomalous pixel"

    def test_anomaly_percentage_in_range(self, anomaly_tif):
        result = arch.spectral_anomaly_detection(anomaly_tif, "anomaly/pct.tif")
        assert 0.0 <= result["anomaly_percentage"] <= 100.0

    def test_output_shape(self, anomaly_tif):
        from osgeo import gdal
        result = arch.spectral_anomaly_detection(anomaly_tif, "anomaly/shape.tif")
        ds = gdal.Open(result["image_path"])
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (32, 32)


# ---------------------------------------------------------------------------
# Test: sky_view_factor
# ---------------------------------------------------------------------------

class TestSkyViewFactor:
    def test_returns_path_string(self, dem_tif):
        result = arch.sky_view_factor(dem_tif, "svf/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, dem_tif):
        result = arch.sky_view_factor(dem_tif, "svf/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_dem(self, dem_tif):
        from osgeo import gdal
        result = arch.sky_view_factor(dem_tif, "svf/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (64, 64)

    def test_values_in_0_1_range(self, dem_tif):
        from osgeo import gdal
        result = arch.sky_view_factor(dem_tif, "svf/range.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.min() >= 0.0
        assert arr.max() <= 1.0

    def test_flat_dem_has_high_svf(self, tmp_dir):
        """A flat DEM should have SVF close to 1 everywhere."""
        from osgeo import gdal
        flat_dem = np.full((32, 32), 100.0, dtype=np.float32)
        path = tmp_dir / "flat_dem.tif"
        _write_dem(flat_dem, str(path))
        result = arch.sky_view_factor(str(path), "svf/flat.tif", radius=5, n_directions=8)
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.mean() > 0.9, f"Flat DEM SVF mean {arr.mean()} should be > 0.9"


# ---------------------------------------------------------------------------
# Test: morphological_cleanup
# ---------------------------------------------------------------------------

class TestMorphologicalCleanup:
    def test_returns_path_string(self, gray_tif):
        result = arch.morphological_cleanup(gray_tif, "morph/out.tif")
        assert isinstance(result, str)

    def test_output_file_exists(self, gray_tif):
        result = arch.morphological_cleanup(gray_tif, "morph/out.tif")
        assert Path(result).exists()

    def test_output_shape_matches_input(self, gray_tif):
        from osgeo import gdal
        result = arch.morphological_cleanup(gray_tif, "morph/shape.tif")
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        assert arr.shape == (128, 128)

    def test_all_operations(self, gray_tif):
        for op in ("dilate", "erode", "open", "close"):
            result = arch.morphological_cleanup(gray_tif, f"morph/{op}.tif", operation=op)
            assert Path(result).exists(), f"Operation '{op}' failed"

    def test_invalid_operation_raises(self, gray_tif):
        with pytest.raises(ValueError):
            arch.morphological_cleanup(gray_tif, "morph/bad.tif", operation="invalid")

    def test_dilate_increases_bright_area(self, tmp_dir):
        """Dilation should increase the area of bright pixels."""
        from osgeo import gdal
        # Small white circle on black background
        import cv2
        img = np.zeros((64, 64), dtype=np.uint8)
        cv2.circle(img, (32, 32), 5, 255, -1)
        path = tmp_dir / "morph_circle.tif"
        _write_geotiff(img, str(path))
        original_bright = int((img > 128).sum())
        result = arch.morphological_cleanup(str(path), "morph/dilated.tif", operation="dilate", kernel_size=5)
        ds = gdal.Open(result)
        arr = ds.GetRasterBand(1).ReadAsArray()
        ds = None
        dilated_bright = int((arr > 128).sum())
        assert dilated_bright >= original_bright, "Dilation should not shrink bright regions"
