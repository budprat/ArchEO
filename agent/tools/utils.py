import numpy as np
from osgeo import gdal


def safe_read_band(ds, band_idx: int, band_name: str = "") -> np.ndarray:
    """Safely read a raster band with validation.

    Returns the band array or raises RuntimeError with a clear message
    explaining which band is missing and how many bands exist.
    """
    n_bands = ds.RasterCount
    if band_idx < 1 or band_idx > n_bands:
        label = f" ({band_name})" if band_name else ""
        raise RuntimeError(
            f"Band {band_idx}{label} requested but image only has {n_bands} band(s). "
            f"This image appears to be a {'grayscale' if n_bands == 1 else 'RGB' if n_bands <= 4 else 'multi-band'} image. "
            f"For RGB images (PNG/JPG), use band indices 1-{n_bands}. "
            f"For multi-band GeoTIFF (e.g. Sentinel-2), higher band indices are available."
        )
    band = ds.GetRasterBand(band_idx)
    if band is None:
        raise RuntimeError(f"GetRasterBand({band_idx}) returned None for image with {n_bands} bands.")
    return band.ReadAsArray()


def validate_band_count(ds, required_bands: dict, tool_name: str = "") -> str | None:
    """Check that all required bands exist in the dataset.

    Args:
        ds: GDAL dataset
        required_bands: dict mapping band_name -> band_index (1-based)
        tool_name: name of the tool for error messages

    Returns:
        None if OK, or an error message string if bands are missing.
    """
    n_bands = ds.RasterCount
    missing = {name: idx for name, idx in required_bands.items() if idx > n_bands}
    if not missing:
        return None
    missing_str = ", ".join(f"{name}=band {idx}" for name, idx in missing.items())
    tool_label = f" ({tool_name})" if tool_name else ""
    return (
        f"Image has {n_bands} band(s) but{tool_label} requires: {missing_str}. "
        f"This tool needs multi-band satellite data (e.g. Sentinel-2 GeoTIFF). "
        f"For RGB images (PNG/JPG), try tools that work with 3 bands: "
        f"iron_oxide_index, brightness_index, redness_index, edge_detection_canny, "
        f"texture_analysis_glcm, or geometric_pattern_analysis."
    )


def read_image(file_path: str) -> np.ndarray:
    ds = gdal.Open(file_path)
    if ds is None:
        raise RuntimeError(f"Failed to open {file_path}")
    
    bands = ds.RasterCount
    if bands == 1:
        img = ds.GetRasterBand(1).ReadAsArray()
    else:
        img = np.stack([ds.GetRasterBand(i + 1).ReadAsArray() for i in range(bands)], axis=0)
        img = np.transpose(img, (1, 2, 0))

    ds = None
    return img


def read_image_uint8(file_path: str) -> np.ndarray:
    ds = gdal.Open(file_path)
    if ds is None:
        raise RuntimeError(f"Failed to open {file_path}")
    
    bands = ds.RasterCount
    if bands == 1:
        img = ds.GetRasterBand(1).ReadAsArray()
    else:
        img = np.stack([ds.GetRasterBand(i + 1).ReadAsArray() for i in range(bands)], axis=0)
        img = np.transpose(img, (1, 2, 0))

    ds = None

    img = img.astype(np.float32)
    min_val = np.min(img)
    max_val = np.max(img)

    if max_val > min_val:
        img = (img - min_val) / (max_val - min_val) * 255
    else:
        img = np.zeros_like(img)

    return img.astype(np.uint8)


def get_geotransform(file_path) -> tuple:
    ds = gdal.Open(file_path)
    if ds is None:
        raise RuntimeError(f"Failed to open {file_path}")
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None
    if geo == (0, 1.0, 0, 0, 0, 1.0):
        return None, None
    else:
        return geo, proj
