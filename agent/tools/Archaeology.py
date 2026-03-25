import argparse

from pathlib import Path
from fastmcp import FastMCP
from utils import read_image, read_image_uint8


mcp = FastMCP()
parser = argparse.ArgumentParser()
parser.add_argument('--temp_dir', type=str)
args, unknown = parser.parse_known_args()

TEMP_DIR = Path(args.temp_dir)
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_input(image_path: str) -> str:
    """Resolve input path — try as-is first, then under TEMP_DIR."""
    from pathlib import Path as _P
    p = _P(image_path)
    if p.exists():
        return str(p)
    # Try under TEMP_DIR (agent may pass relative output_path from a previous tool)
    under_temp = TEMP_DIR / image_path
    if under_temp.exists():
        return str(under_temp)
    # Try just the filename under TEMP_DIR
    under_temp_name = TEMP_DIR / p.name
    if under_temp_name.exists():
        return str(under_temp_name)
    # Search subdirectories of TEMP_DIR (tools may create per-analysis folders)
    for match in TEMP_DIR.rglob(p.name):
        if match.is_file():
            return str(match)
    # Return original — let the tool raise its own error
    return image_path


def _to_grayscale(img):
    """Convert any image (1-band, 3-band, or N-band) to single-channel grayscale uint8."""
    import cv2
    import numpy as np

    if img.ndim == 2:
        return img  # already grayscale

    channels = img.shape[2]

    if channels == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    elif channels == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    else:
        # Multi-band (e.g. 13-band Sentinel-2): use bands 4,3,2 (indices 3,2,1)
        # for true-color RGB (Red=B4, Green=B3, Blue=B2 in Sentinel-2 convention)
        if channels >= 4:
            rgb = np.stack([img[:, :, 3], img[:, :, 2], img[:, :, 1]], axis=-1)
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        elif channels >= 3:
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            return img[:, :, 0]


@mcp.tool(description='''
Description:
Apply Canny edge detection to an image and save the result as a GeoTIFF.
Defaults are calibrated for 10m resolution satellite imagery (e.g., Sentinel-2).

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the output edge image
                     (e.g., "results/edges_canny.tif").
- low_threshold (float, optional): Lower hysteresis threshold. Default = 20
                                   (tuned for satellite imagery contrast levels).
- high_threshold (float, optional): Upper hysteresis threshold. Default = 60
                                    (tuned for satellite imagery contrast levels).
- gaussian_sigma (float, optional): Sigma for Gaussian blur applied before Canny
                                    to reduce noise. Default = 1.5. Set to 0 to skip.

Returns:
- str: Path to the saved edge detection result image.
''')
def edge_detection_canny(
    image_path: str,
    output_path: str,
    low_threshold: float = 20,
    high_threshold: float = 60,
    gaussian_sigma: float = 1.5,
) -> str:
    """
    Description:
        Apply Canny edge detection to an input image. The image is read via GDAL
        (supporting GeoTIFF and other formats), normalized to uint8, converted to
        grayscale if needed, optionally blurred, then processed with the Canny operator.
        Defaults are tuned for 10m satellite imagery (e.g., Sentinel-2).

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the result GeoTIFF.
        low_threshold (float, default=20):
            Lower bound for the hysteresis thresholding step.
        high_threshold (float, default=60):
            Upper bound for the hysteresis thresholding step.
        gaussian_sigma (float, default=1.5):
            Sigma for Gaussian pre-blur. Set to 0 to disable.

    Returns:
        str:
            Absolute path to the saved edge image.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))

    if img.ndim == 3:
        gray = _to_grayscale(img)
    else:
        gray = img

    if gaussian_sigma > 0:
        gray = cv2.GaussianBlur(gray, (0, 0), gaussian_sigma)

    edges = cv2.Canny(gray, low_threshold, high_threshold)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), edges.shape[1], edges.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(edges)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Apply Sobel gradient magnitude edge detection to an image and save the result.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the output gradient magnitude image
                     (e.g., "results/edges_sobel.tif").
- ksize (int, optional): Sobel kernel size (must be odd, e.g. 1, 3, 5, 7). Default = 3.

Returns:
- str: Path to the saved Sobel gradient magnitude image.
''')
def edge_detection_sobel(
    image_path: str,
    output_path: str,
    ksize: int = 3,
) -> str:
    """
    Description:
        Compute the Sobel gradient magnitude of an input image. The x and y
        gradient images are combined using the L2 norm (sqrt(Gx^2 + Gy^2)) and
        the result is normalized to uint8 range [0, 255].

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the result GeoTIFF.
        ksize (int, default=3):
            Aperture parameter for the Sobel operator. Must be 1, 3, 5, or 7.

    Returns:
        str:
            Absolute path to the saved gradient magnitude image.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))

    if img.ndim == 3:
        gray = _to_grayscale(img)
    else:
        gray = img

    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=ksize)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=ksize)
    magnitude = np.sqrt(sobelx ** 2 + sobely ** 2)

    # Normalize to uint8
    mag_min, mag_max = magnitude.min(), magnitude.max()
    if mag_max > mag_min:
        magnitude = (magnitude - mag_min) / (mag_max - mag_min) * 255
    else:
        magnitude = np.zeros_like(magnitude)
    magnitude = magnitude.astype(np.uint8)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), magnitude.shape[1], magnitude.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(magnitude)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Detect linear features in an image using the Hough line transform and return
orientation statistics. Useful for identifying archaeological linear structures
such as roads, field boundaries, or ditches.
Defaults are calibrated for 10m resolution satellite imagery (e.g., Sentinel-2).

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the annotated output image
                     (e.g., "results/lines.tif").
- min_line_length (int, optional): Minimum line length in pixels. Default = 5
                                   (= ~50m at 10m/px resolution).
- max_line_gap (int, optional): Maximum allowed gap between line segments to treat
                                them as a single line. Default = 3 (= ~30m at 10m/px).
- hough_threshold (int, optional): Hough accumulator threshold — minimum number of
                                   votes for a line to be detected. Default = 50.

Returns:
- dict: {
    "image_path": str,        # Path to the saved annotated image
    "lines": list[list[int]], # List of detected lines [[x1, y1, x2, y2], ...]
    "orientations": list[float], # Angle in degrees for each line (0-180)
    "count": int              # Number of detected lines
  }
''')
def linear_feature_detection(
    image_path: str,
    output_path: str,
    min_line_length: int = 5,
    max_line_gap: int = 3,
    hough_threshold: int = 50,
) -> dict:
    """
    Description:
        Detect linear features using the Probabilistic Hough Line Transform.
        Gaussian blur and Canny edge detection (tuned for satellite imagery) are
        applied first; detected lines are drawn on a copy of the grayscale image
        and the result is saved. Orientation angles (0-180°) are computed for each
        line segment. Defaults calibrated for 10m/px satellite imagery.

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the annotated result GeoTIFF.
        min_line_length (int, default=5):
            Minimum pixel length for a segment to be retained (~50m at 10m/px).
        max_line_gap (int, default=3):
            Maximum gap in pixels between collinear points to bridge (~30m at 10m/px).
        hough_threshold (int, default=50):
            Hough accumulator threshold (minimum votes to accept a line).

    Returns:
        dict with keys:
            image_path (str): Path to annotated output image.
            lines (list[list[int]]): Each entry is [x1, y1, x2, y2].
            orientations (list[float]): Angle in degrees (0-180) per line.
            count (int): Total number of detected lines.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))

    if img.ndim == 3:
        gray = _to_grayscale(img)
    else:
        gray = img

    blurred = cv2.GaussianBlur(gray, (0, 0), 1.5)
    edges = cv2.Canny(blurred, 20, 60)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )

    # Build output image (BGR for drawing)
    out_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    line_list = []
    orientations = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(out_img, (x1, y1), (x2, y2), (0, 0, 255), 1)
            line_list.append([int(x1), int(y1), int(x2), int(y2)])
            angle = float(np.degrees(np.arctan2(abs(y2 - y1), abs(x2 - x1))))
            orientations.append(round(angle, 2))

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), out_img.shape[1], out_img.shape[0], 3, gdal.GDT_Byte)
    for band_idx in range(3):
        out_ds.GetRasterBand(band_idx + 1).WriteArray(out_img[:, :, band_idx])
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "lines": line_list,
        "orientations": orientations,
        "count": len(line_list),
    }


@mcp.tool(description='''
Description:
Analyze geometric patterns in an image by extracting contours and computing
shape descriptors. Best results when run on PRE-PROCESSED input such as edge
detection output, PCA components, or CLAHE-enhanced images rather than raw
satellite imagery. Uses adaptive thresholding and RETR_TREE to capture nested
structures like the Nazca monkey's spiral tail.
Defaults are calibrated for 10m resolution satellite imagery (e.g., Sentinel-2).

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the annotated output image
                     (e.g., "results/shapes.tif").
- min_area (int, optional): Minimum contour area in pixels to include. Default = 10
                            (= ~1000 sq.m at 10m/px resolution).

Returns:
- dict: {
    "image_path": str,   # Path to the saved annotated image
    "shapes": list[dict],# List of shape descriptors per contour
    "count": int         # Number of shapes detected
  }
  Each shape dict contains:
    "area" (float), "perimeter" (float), "circularity" (float),
    "aspect_ratio" (float), "bounding_box" ([x, y, w, h]),
    "hu_moments" (list[float], 7 values), "solidity" (float),
    "convex_defects_count" (int)
''')
def geometric_pattern_analysis(
    image_path: str,
    output_path: str,
    min_area: int = 10,
) -> dict:
    """
    Description:
        Detect contours in the image and compute shape descriptors including
        area, perimeter, circularity (4π·area/perimeter²), aspect ratio
        (bounding box width / height), bounding box [x, y, w, h], Hu moments
        (7 rotation-invariant moments), solidity (area/convex_hull_area), and
        convexity defects count. Contours below min_area are filtered out.
        Default min_area = 10 pixels (~1000 sq.m at 10m/px).

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the annotated result GeoTIFF.
        min_area (int, default=10):
            Minimum contour area in pixels to retain (~1000 sq.m at 10m/px).

    Returns:
        dict with keys:
            image_path (str): Path to annotated output image.
            shapes (list[dict]): Shape descriptors per contour.
            count (int): Number of retained contours.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))

    if img.ndim == 3:
        gray = _to_grayscale(img)
    else:
        gray = img

    # Use adaptive thresholding for better detection of subtle features
    # in satellite imagery (Otsu fails on low-contrast geoglyph lines)
    # If input is already binary/edge (max ~255, mostly 0), use simple threshold
    nonzero_ratio = np.count_nonzero(gray) / gray.size
    if nonzero_ratio < 0.3:
        # Input looks like an edge map — simple threshold
        _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    else:
        # Raw image — use adaptive threshold for local contrast
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, blockSize=51, C=-5
        )
    # Use RETR_TREE to capture nested structures (e.g., monkey's spiral tail)
    contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    out_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    shapes = []

    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < min_area:
            continue

        perimeter = float(cv2.arcLength(cnt, closed=True))
        circularity = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0.0
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / float(h) if h > 0 else 0.0

        # Hu moments (7 rotation-invariant moments)
        moments = cv2.moments(cnt)
        hu = cv2.HuMoments(moments).flatten()
        hu_moments = [float(v) for v in hu]

        # Solidity = contour area / convex hull area
        hull = cv2.convexHull(cnt)
        hull_area = float(cv2.contourArea(hull))
        solidity = area / hull_area if hull_area > 0 else 0.0

        # Convexity defects count
        try:
            hull_idx = cv2.convexHull(cnt, returnPoints=False)
            if hull_idx is not None and len(hull_idx) > 3 and len(cnt) > 3:
                defects = cv2.convexityDefects(cnt, hull_idx)
                convex_defects_count = int(len(defects)) if defects is not None else 0
            else:
                convex_defects_count = 0
        except cv2.error:
            convex_defects_count = 0

        cv2.drawContours(out_img, [cnt], -1, (0, 255, 0), 1)
        shapes.append({
            "area": round(area, 2),
            "perimeter": round(perimeter, 2),
            "circularity": round(float(circularity), 4),
            "aspect_ratio": round(aspect_ratio, 4),
            "bounding_box": [int(x), int(y), int(w), int(h)],
            "hu_moments": [round(v, 8) for v in hu_moments],
            "solidity": round(float(solidity), 4),
            "convex_defects_count": convex_defects_count,
        })

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), out_img.shape[1], out_img.shape[0], 3, gdal.GDT_Byte)
    for band_idx in range(3):
        out_ds.GetRasterBand(band_idx + 1).WriteArray(out_img[:, :, band_idx])
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "shapes": shapes,
        "count": len(shapes),
    }


@mcp.tool(description='''
Description:
Generate a hillshade visualization from a Digital Elevation Model (DEM) raster.
Hillshading enhances topographic relief and can reveal subtle earthworks and
micro-topographic archaeological features.

Parameters:
- dem_path (str): Path to the input DEM raster (single-band GeoTIFF).
- output_path (str): Relative file path to save the hillshade output
                     (e.g., "results/hillshade.tif").
- azimuth (float, optional): Sun azimuth angle in degrees (0=N, 90=E, 180=S, 270=W).
                             Default = 315.
- altitude (float, optional): Sun altitude angle in degrees above horizon (0-90).
                              Default = 45.

Returns:
- str: Path to the saved hillshade GeoTIFF.
''')
def dem_hillshade(
    dem_path: str,
    output_path: str,
    azimuth: float = 315,
    altitude: float = 45,
) -> str:
    """
    Description:
        Compute a hillshade from a DEM using the standard formula:
        hillshade = cos(zenith) * cos(slope) + sin(zenith) * sin(slope) * cos(azimuth - aspect)
        The result is scaled to [0, 255] uint8 and saved as a GeoTIFF preserving
        georeference metadata from the source DEM.

    Parameters:
        dem_path (str):
            Path to the single-band DEM GeoTIFF.
        output_path (str):
            Relative path (within TEMP_DIR) to write the hillshade GeoTIFF.
        azimuth (float, default=315):
            Sun azimuth in degrees (geographic convention, 0=North, clockwise).
        altitude (float, default=45):
            Sun altitude above the horizon in degrees.

    Returns:
        str:
            Absolute path to the saved hillshade image.
    """
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(_resolve_input(dem_path))
    if ds is None:
        raise RuntimeError(f"Failed to open DEM: {dem_path}")

    band = ds.GetRasterBand(1)
    dem = band.ReadAsArray().astype(np.float64)

    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()

    # Cell size (assume square pixels; use absolute x pixel size)
    cell_size = abs(geo[1]) if geo and geo[1] != 0 else 1.0

    # Compute slope and aspect using numpy gradient
    dy, dx = np.gradient(dem, cell_size)

    slope = np.arctan(np.sqrt(dx ** 2 + dy ** 2))

    # Aspect: 0=North, clockwise (geographic)
    aspect = np.arctan2(-dy, dx)  # math convention
    # Convert math aspect to geographic (north-clockwise)
    aspect = np.pi / 2 - aspect
    aspect = np.where(aspect < 0, aspect + 2 * np.pi, aspect)

    # Convert sun angles to radians
    zenith_rad = np.radians(90 - altitude)
    azimuth_rad = np.radians(azimuth)

    hillshade = (
        np.cos(zenith_rad) * np.cos(slope)
        + np.sin(zenith_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
    )

    # Clip and scale to [0, 255]
    hillshade = np.clip(hillshade, 0, 1) * 255
    hillshade = hillshade.astype(np.uint8)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), hillshade.shape[1], hillshade.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(hillshade)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None
    ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Compute Gray-Level Co-occurrence Matrix (GLCM) texture metrics from an image.
GLCM features capture spatial relationships between pixel intensities and are
widely used to characterize soil texture, surface roughness, and archaeological
feature boundaries. Defaults are calibrated for 10m satellite imagery (Sentinel-2).

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- distances (list[int], optional): List of pixel-pair distances for GLCM computation.
                                   Default = [1, 3, 5] (multi-scale: 10m, 30m, 50m at 10m/px).
- angles (list[float], optional): List of angles in radians for GLCM computation.
                                  Default = [0, 0.785, 1.571, 2.356] (0°, 45°, 90°, 135°).
- output_path (str, optional): If provided, compute a local texture roughness map
                                (local std-dev proxy) and save as GeoTIFF alongside metrics.

Returns:
- dict: {
    "contrast"    (float): Measures local intensity variation.
    "homogeneity" (float): Measures closeness of element distribution to GLCM diagonal.
    "entropy"     (float): Measures randomness of texture.
    "correlation" (float): Measures linear dependency of intensity levels.
    "energy"      (float): Sum of squared GLCM elements (angular second moment).
    "texture_map_path" (str, optional): Path to texture roughness GeoTIFF if output_path given.
  }
''')
def texture_analysis_glcm(
    image_path: str,
    distances: list = None,
    angles: list = None,
    output_path: str = None,
) -> dict:
    """
    Description:
        Compute GLCM-based texture features from an input image.
        The image is read via GDAL, normalized to uint8, and reduced to 32 gray
        levels. scikit-image's graycomatrix and graycoprops are used to compute
        the standard features. Defaults use multi-scale distances [1,3,5] and
        four angles (0°,45°,90°,135°), calibrated for 10m satellite imagery.
        Optionally saves a local texture roughness map (local std-dev proxy).

    Parameters:
        image_path (str):
            Path to the input raster image.
        distances (list[int], default=[1, 3, 5]):
            Pixel-pair distances for GLCM computation (multi-scale).
        angles (list[float], default=[0, 0.785, 1.571, 2.356]):
            Angles in radians (0°, 45°, 90°, 135°).
        output_path (str, default=None):
            If provided, saves a local texture roughness (std-dev) map as GeoTIFF
            to this relative path within TEMP_DIR.

    Returns:
        dict with keys:
            contrast (float), homogeneity (float), entropy (float),
            correlation (float), energy (float).
            Each value is the mean over all distance/angle combinations.
            texture_map_path (str): Only present when output_path is given.
    """
    import numpy as np
    from skimage.feature import graycomatrix, graycoprops

    if distances is None:
        distances = [1, 3, 5]
    if angles is None:
        angles = [0, 0.785, 1.571, 2.356]

    img = read_image_uint8(_resolve_input(image_path))

    if img.ndim == 3:
        import cv2
        gray = _to_grayscale(img)
    else:
        gray = img

    # Reduce to 32 levels for efficient GLCM with better discrimination
    levels = 32
    gray_quantized = (gray // (256 // levels)).astype(np.uint8)
    gray_quantized = np.clip(gray_quantized, 0, levels - 1)

    glcm = graycomatrix(
        gray_quantized,
        distances=distances,
        angles=angles,
        levels=levels,
        symmetric=True,
        normed=True,
    )

    contrast = float(np.mean(graycoprops(glcm, "contrast")))
    homogeneity = float(np.mean(graycoprops(glcm, "homogeneity")))
    correlation = float(np.mean(graycoprops(glcm, "correlation")))
    energy = float(np.mean(graycoprops(glcm, "energy")))

    # Entropy: -sum(p * log2(p + eps)) — glcm is already normed=True
    eps = 1e-10
    entropy = float(-np.sum(glcm * np.log2(glcm + eps)))

    result = {
        "contrast": round(contrast, 6),
        "homogeneity": round(homogeneity, 6),
        "entropy": round(entropy, 6),
        "correlation": round(correlation, 6),
        "energy": round(energy, 6),
    }

    # Optional texture roughness map via local std-dev proxy
    if output_path is not None:
        from osgeo import gdal
        from scipy.ndimage import uniform_filter

        gray_f = gray.astype(np.float64)
        # Local std-dev: sqrt(E[x^2] - E[x]^2) using uniform_filter
        window = 7
        mean = uniform_filter(gray_f, size=window)
        mean_sq = uniform_filter(gray_f ** 2, size=window)
        variance = np.maximum(mean_sq - mean ** 2, 0.0)
        texture_map = np.sqrt(variance).astype(np.float32)

        out_path = TEMP_DIR / output_path
        out_path.parent.mkdir(parents=True, exist_ok=True)

        driver = gdal.GetDriverByName("GTiff")
        out_ds = driver.Create(str(out_path), texture_map.shape[1], texture_map.shape[0], 1, gdal.GDT_Float32)
        out_ds.GetRasterBand(1).WriteArray(texture_map)
        out_ds.FlushCache()
        out_ds = None

        result["texture_map_path"] = str(out_path)

    return result


@mcp.tool(description='''
Description:
Perform Principal Component Analysis (PCA) on a multi-band raster image.
PCA is the most important tool for archaeological remote sensing — it decorrelates
spectral bands and concentrates archaeological information into the first few
principal components, often revealing buried features invisible in individual bands.

Parameters:
- image_path (str): Path to the input multi-band raster (any GDAL-supported format).
- output_prefix (str): Relative path prefix for output files (e.g., "results/pca").
                       Each PC is saved as "{output_prefix}_pc{N}.tif".
- n_components (int, optional): Number of principal components to compute. Default = 3.

Returns:
- dict: {
    "pc_paths": list[str],           # Paths to each saved PC GeoTIFF
    "explained_variance": list[float], # Variance explained by each PC (0-1)
    "cumulative_variance": list[float] # Cumulative variance explained (0-1)
  }
''')
def principal_component_analysis(
    image_path: str,
    output_prefix: str,
    n_components: int = 3,
) -> dict:
    """
    Perform PCA on all bands of a multi-band raster.

    Parameters:
        image_path (str): Path to the input raster image.
        output_prefix (str): Relative prefix (within TEMP_DIR) for output PC GeoTIFFs.
        n_components (int, default=3): Number of principal components to save.

    Returns:
        dict with keys:
            pc_paths (list[str]): Absolute paths to saved PC images.
            explained_variance (list[float]): Variance fraction per component.
            cumulative_variance (list[float]): Cumulative variance fractions.
    """
    import numpy as np
    from osgeo import gdal
    from sklearn.decomposition import PCA

    ds = gdal.Open(_resolve_input(image_path))
    if ds is None:
        raise RuntimeError(f"Failed to open image: {image_path}")

    n_bands = ds.RasterCount
    rows = ds.RasterYSize
    cols = ds.RasterXSize
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()

    # Stack all bands into (pixels, bands) float64
    bands_data = []
    for b in range(1, n_bands + 1):
        band_arr = ds.GetRasterBand(b).ReadAsArray().astype(np.float64)
        bands_data.append(band_arr.ravel())
    ds = None

    pixel_matrix = np.column_stack(bands_data)  # shape: (rows*cols, n_bands)

    n_components = min(n_components, n_bands)
    pca = PCA(n_components=n_components)
    transformed = pca.fit_transform(pixel_matrix)  # shape: (rows*cols, n_components)

    explained = [float(v) for v in pca.explained_variance_ratio_]
    cumulative = [float(np.sum(explained[:i + 1])) for i in range(len(explained))]

    driver = gdal.GetDriverByName("GTiff")
    pc_paths = []

    for i in range(n_components):
        pc_map = transformed[:, i].reshape(rows, cols)

        out_path = TEMP_DIR / f"{output_prefix}_pc{i + 1}.tif"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Float32)
        out_ds.GetRasterBand(1).WriteArray(pc_map.astype(np.float32))
        if geo:
            out_ds.SetGeoTransform(geo)
        if proj:
            out_ds.SetProjection(proj)
        out_ds.FlushCache()
        out_ds = None
        pc_paths.append(str(out_path))

    return {
        "pc_paths": pc_paths,
        "explained_variance": [round(v, 6) for v in explained],
        "cumulative_variance": [round(v, 6) for v in cumulative],
    }


@mcp.tool(description='''
Description:
Generate a multi-directional hillshade by combining hillshades from multiple sun
azimuths. This evenly illuminates all terrain orientations, eliminating directional
bias and revealing linear archaeological features regardless of their orientation.

Parameters:
- dem_path (str): Path to the input DEM raster (single-band GeoTIFF).
- output_path (str): Relative file path to save the multi-directional hillshade
                     (e.g., "results/multihillshade.tif").
- n_directions (int, optional): Number of evenly-spaced sun azimuths to combine.
                                Default = 8.
- altitude (float, optional): Sun altitude angle in degrees above horizon. Default = 45.

Returns:
- str: Path to the saved multi-directional hillshade GeoTIFF.
''')
def multi_directional_hillshade(
    dem_path: str,
    output_path: str,
    n_directions: int = 8,
    altitude: float = 45,
) -> str:
    """
    Compute multi-directional hillshade by averaging hillshades from evenly-spaced azimuths.

    Parameters:
        dem_path (str): Path to the single-band DEM GeoTIFF.
        output_path (str): Relative path (within TEMP_DIR) to write the output GeoTIFF.
        n_directions (int, default=8): Number of azimuths (evenly spaced 0-360).
        altitude (float, default=45): Sun altitude above horizon in degrees.

    Returns:
        str: Absolute path to the saved multi-directional hillshade image.
    """
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(_resolve_input(dem_path))
    if ds is None:
        raise RuntimeError(f"Failed to open DEM: {dem_path}")

    band = ds.GetRasterBand(1)
    dem = band.ReadAsArray().astype(np.float64)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None

    cell_size = abs(geo[1]) if geo and geo[1] != 0 else 1.0
    dy, dx = np.gradient(dem, cell_size)
    slope = np.arctan(np.sqrt(dx ** 2 + dy ** 2))
    aspect = np.pi / 2 - np.arctan2(-dy, dx)
    aspect = np.where(aspect < 0, aspect + 2 * np.pi, aspect)

    zenith_rad = np.radians(90 - altitude)
    azimuths = np.linspace(0, 360, n_directions, endpoint=False)

    hillshade_sum = np.zeros_like(dem)
    for az in azimuths:
        azimuth_rad = np.radians(az)
        hs = (
            np.cos(zenith_rad) * np.cos(slope)
            + np.sin(zenith_rad) * np.sin(slope) * np.cos(azimuth_rad - aspect)
        )
        hillshade_sum += np.clip(hs, 0, 1)

    hillshade_mean = hillshade_sum / n_directions
    hillshade_out = (hillshade_mean * 255).astype(np.uint8)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), hillshade_out.shape[1], hillshade_out.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(hillshade_out)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Generate a Local Relief Model (LRM) from a DEM by subtracting a smoothed version
of the terrain. The LRM reveals micro-topographic features such as burial mounds,
field systems, and earthworks that are superimposed on larger-scale topography.

Parameters:
- dem_path (str): Path to the input DEM raster (single-band GeoTIFF).
- output_path (str): Relative file path to save the LRM output
                     (e.g., "results/lrm.tif").
- kernel_size (int, optional): Size of the smoothing filter in pixels. Default = 25.

Returns:
- str: Path to the saved Local Relief Model GeoTIFF.
''')
def local_relief_model(
    dem_path: str,
    output_path: str,
    kernel_size: int = 25,
) -> str:
    """
    Compute Local Relief Model = DEM - smoothed_DEM.

    Parameters:
        dem_path (str): Path to the single-band DEM GeoTIFF.
        output_path (str): Relative path (within TEMP_DIR) to write the LRM GeoTIFF.
        kernel_size (int, default=25): Uniform filter window size in pixels.

    Returns:
        str: Absolute path to the saved LRM image.
    """
    import numpy as np
    from osgeo import gdal
    from scipy.ndimage import uniform_filter

    ds = gdal.Open(_resolve_input(dem_path))
    if ds is None:
        raise RuntimeError(f"Failed to open DEM: {dem_path}")

    band = ds.GetRasterBand(1)
    dem = band.ReadAsArray().astype(np.float64)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None

    smoothed = uniform_filter(dem, size=kernel_size)
    lrm = (dem - smoothed).astype(np.float32)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), lrm.shape[1], lrm.shape[0], 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(lrm)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) to an image for
local contrast enhancement. CLAHE improves visibility of subtle texture and
tonal variations without over-amplifying noise, useful for revealing faint
archaeological soil marks or crop marks.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format).
- output_path (str): Relative file path to save the enhanced output
                     (e.g., "results/clahe.tif").
- clip_limit (float, optional): Contrast limiting threshold. Higher values give
                                more contrast. Default = 2.0.
- grid_size (int, optional): Size of the tile grid for histogram equalization.
                             Default = 8.

Returns:
- str: Path to the saved CLAHE-enhanced GeoTIFF.
''')
def adaptive_contrast_enhancement(
    image_path: str,
    output_path: str,
    clip_limit: float = 2.0,
    grid_size: int = 8,
) -> str:
    """
    Apply CLAHE to an image for local contrast enhancement.

    Parameters:
        image_path (str): Path to the input raster image.
        output_path (str): Relative path (within TEMP_DIR) to write the output GeoTIFF.
        clip_limit (float, default=2.0): CLAHE clip limit parameter.
        grid_size (int, default=8): Tile grid size for histogram equalization.

    Returns:
        str: Absolute path to the saved enhanced image.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))
    gray = _to_grayscale(img)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(grid_size, grid_size))
    enhanced = clahe.apply(gray)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), enhanced.shape[1], enhanced.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(enhanced)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Compute the ratio of two spectral bands from a multi-band raster image.
Band ratios are fundamental remote sensing tools for detecting archaeological
features — they highlight differences in surface composition, moisture, and
vegetation health that may indicate buried structures.

Parameters:
- image_path (str): Path to the input multi-band raster (any GDAL-supported format).
- band_a (int): 1-based index of the numerator band.
- band_b (int): 1-based index of the denominator band.
- output_path (str): Relative file path to save the ratio image
                     (e.g., "results/band_ratio.tif").

Returns:
- dict: {
    "image_path": str,   # Path to the saved ratio GeoTIFF
    "min": float,        # Minimum ratio value
    "max": float,        # Maximum ratio value
    "mean": float        # Mean ratio value
  }
''')
def band_ratio_calculator(
    image_path: str,
    band_a: int,
    band_b: int,
    output_path: str,
) -> dict:
    """
    Compute band_a / (band_b + epsilon) ratio from a multi-band raster.

    Parameters:
        image_path (str): Path to the input raster image.
        band_a (int): 1-based band index for numerator.
        band_b (int): 1-based band index for denominator.
        output_path (str): Relative path (within TEMP_DIR) to write the ratio GeoTIFF.

    Returns:
        dict with keys:
            image_path (str): Path to saved ratio image.
            min (float): Minimum ratio value.
            max (float): Maximum ratio value.
            mean (float): Mean ratio value.
    """
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(_resolve_input(image_path))
    if ds is None:
        raise RuntimeError(f"Failed to open image: {image_path}")

    arr_a = ds.GetRasterBand(band_a).ReadAsArray().astype(np.float64)
    arr_b = ds.GetRasterBand(band_b).ReadAsArray().astype(np.float64)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None

    ratio = (arr_a / (arr_b + 1e-10)).astype(np.float32)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), ratio.shape[1], ratio.shape[0], 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(ratio)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "min": round(float(ratio.min()), 6),
        "max": round(float(ratio.max()), 6),
        "mean": round(float(ratio.mean()), 6),
    }


@mcp.tool(description='''
Description:
Detect spectral anomalies in a multi-band image using Mahalanobis distance.
Pixels that differ significantly from the mean spectral signature of the scene
are flagged as anomalies. This is highly effective for detecting archaeological
features with unusual spectral properties against a homogeneous background.

Parameters:
- image_path (str): Path to the input multi-band raster (any GDAL-supported format).
- output_path (str): Relative file path to save the anomaly distance map
                     (e.g., "results/anomalies.tif").
- threshold_sigma (float, optional): Number of standard deviations above the mean
                                     distance to use as anomaly threshold. Default = 2.5
                                     (calibrated for satellite imagery to reduce false positives).

Returns:
- dict: {
    "image_path": str,         # Path to the saved distance map GeoTIFF
    "anomaly_count": int,      # Number of anomalous pixels
    "anomaly_percentage": float # Percentage of image that is anomalous
  }
''')
def spectral_anomaly_detection(
    image_path: str,
    output_path: str,
    threshold_sigma: float = 2.5,
) -> dict:
    """
    Detect spectral anomalies using Mahalanobis distance on multi-band imagery.

    Parameters:
        image_path (str): Path to the input raster image.
        output_path (str): Relative path (within TEMP_DIR) to write the distance map GeoTIFF.
        threshold_sigma (float, default=2.5): Threshold in standard deviations above mean distance.

    Returns:
        dict with keys:
            image_path (str): Path to saved distance map.
            anomaly_count (int): Number of anomalous pixels.
            anomaly_percentage (float): Fraction of total pixels flagged as anomalies.
    """
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(_resolve_input(image_path))
    if ds is None:
        raise RuntimeError(f"Failed to open image: {image_path}")

    n_bands = ds.RasterCount
    rows = ds.RasterYSize
    cols = ds.RasterXSize
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()

    bands_data = []
    for b in range(1, n_bands + 1):
        arr = ds.GetRasterBand(b).ReadAsArray().astype(np.float64)
        bands_data.append(arr.ravel())
    ds = None

    X = np.column_stack(bands_data)  # (n_pixels, n_bands)

    mean_vec = X.mean(axis=0)
    X_centered = X - mean_vec

    cov = np.cov(X_centered, rowvar=False)
    try:
        cov_inv = np.linalg.inv(cov)
    except np.linalg.LinAlgError:
        cov_inv = np.linalg.pinv(cov)

    # Mahalanobis distance for each pixel: sqrt(x^T * cov_inv * x)
    # Efficient batch computation
    temp = X_centered @ cov_inv  # (n_pixels, n_bands)
    dist_sq = np.sum(temp * X_centered, axis=1)
    dist_sq = np.maximum(dist_sq, 0.0)
    distances = np.sqrt(dist_sq).astype(np.float32)

    dist_mean = distances.mean()
    dist_std = distances.std()
    threshold = dist_mean + threshold_sigma * dist_std
    anomaly_mask = distances > threshold

    dist_map = distances.reshape(rows, cols)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(dist_map)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None

    anomaly_count = int(anomaly_mask.sum())
    anomaly_percentage = round(float(anomaly_count) / float(rows * cols) * 100, 4)

    return {
        "image_path": str(out_path),
        "anomaly_count": anomaly_count,
        "anomaly_percentage": anomaly_percentage,
    }


@mcp.tool(description='''
Description:
Compute the Sky View Factor (SVF) from a Digital Elevation Model. SVF measures
the proportion of the sky hemisphere visible from each ground point, ranging from
0 (fully enclosed) to 1 (fully open sky). SVF is excellent for detecting subtle
earthworks, ditches, and embankments in LiDAR-derived DEMs.

Parameters:
- dem_path (str): Path to the input DEM raster (single-band GeoTIFF).
- output_path (str): Relative file path to save the SVF output
                     (e.g., "results/svf.tif").
- radius (int, optional): Search radius in pixels for horizon detection. Default = 10.
- n_directions (int, optional): Number of azimuth directions to sample. Default = 16.

Returns:
- str: Path to the saved Sky View Factor GeoTIFF (float32, values 0-1).
''')
def sky_view_factor(
    dem_path: str,
    output_path: str,
    radius: int = 10,
    n_directions: int = 16,
) -> str:
    """
    Compute Sky View Factor from a DEM using horizon elevation angle sampling.

    Parameters:
        dem_path (str): Path to the single-band DEM GeoTIFF.
        output_path (str): Relative path (within TEMP_DIR) to write the SVF GeoTIFF.
        radius (int, default=10): Search radius in pixels.
        n_directions (int, default=16): Number of azimuth directions sampled.

    Returns:
        str: Absolute path to the saved SVF image.
    """
    import numpy as np
    from osgeo import gdal

    ds = gdal.Open(_resolve_input(dem_path))
    if ds is None:
        raise RuntimeError(f"Failed to open DEM: {dem_path}")

    band = ds.GetRasterBand(1)
    dem = band.ReadAsArray().astype(np.float64)
    geo = ds.GetGeoTransform()
    proj = ds.GetProjection()
    ds = None

    rows, cols = dem.shape
    cell_size = abs(geo[1]) if geo and geo[1] != 0 else 1.0

    azimuths = np.linspace(0, 2 * np.pi, n_directions, endpoint=False)

    # For each direction, compute the max elevation angle seen within radius
    # and accumulate sin of max elevation angle
    sin_sum = np.zeros((rows, cols), dtype=np.float64)

    for az in azimuths:
        cos_az = np.cos(az)
        sin_az = np.sin(az)
        max_sin_elev = np.zeros((rows, cols), dtype=np.float64)

        for r in range(1, radius + 1):
            # Offset in pixel coords
            dr = -r * cos_az  # row offset (north = -row)
            dc = r * sin_az   # col offset

            # Source and target row/col arrays
            row_src = np.arange(rows)
            col_src = np.arange(cols)
            row_grid, col_grid = np.meshgrid(row_src, col_src, indexing='ij')

            row_tgt = np.clip(np.round(row_grid + dr).astype(int), 0, rows - 1)
            col_tgt = np.clip(np.round(col_grid + dc).astype(int), 0, cols - 1)

            dh = dem[row_tgt, col_tgt] - dem[row_grid, col_grid]
            horiz_dist = r * cell_size
            elev_angle = np.arctan2(dh, horiz_dist)
            sin_elev = np.sin(np.maximum(elev_angle, 0.0))

            max_sin_elev = np.maximum(max_sin_elev, sin_elev)

        sin_sum += max_sin_elev

    svf = (1.0 - sin_sum / n_directions).astype(np.float32)
    svf = np.clip(svf, 0.0, 1.0)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(svf)
    if geo:
        out_ds.SetGeoTransform(geo)
    if proj:
        out_ds.SetProjection(proj)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Description:
Apply morphological operations to a binary or grayscale image using OpenCV.
Morphological processing can clean up edge detection results, connect broken
linear features, fill small gaps in detected structures, or remove noise from
archaeological feature maps.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format).
- output_path (str): Relative file path to save the processed image
                     (e.g., "results/morphology.tif").
- operation (str, optional): Morphological operation to apply.
                             Options: "dilate", "erode", "open", "close".
                             Default = "close".
- kernel_size (int, optional): Size of the structuring element kernel. Default = 3.
- iterations (int, optional): Number of times to apply the operation. Default = 1.

Returns:
- str: Path to the saved morphologically processed GeoTIFF.
''')
def morphological_cleanup(
    image_path: str,
    output_path: str,
    operation: str = "close",
    kernel_size: int = 3,
    iterations: int = 1,
) -> str:
    """
    Apply morphological operations (dilate, erode, open, close) to an image.

    Parameters:
        image_path (str): Path to the input raster image.
        output_path (str): Relative path (within TEMP_DIR) to write the output GeoTIFF.
        operation (str, default="close"): One of "dilate", "erode", "open", "close".
        kernel_size (int, default=3): Structuring element size.
        iterations (int, default=1): Number of iterations.

    Returns:
        str: Absolute path to the saved processed image.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    op_map = {
        "dilate": cv2.MORPH_DILATE,
        "erode": cv2.MORPH_ERODE,
        "open": cv2.MORPH_OPEN,
        "close": cv2.MORPH_CLOSE,
    }

    if operation not in op_map:
        raise ValueError(f"operation must be one of {list(op_map.keys())}, got '{operation}'")

    img = read_image_uint8(_resolve_input(image_path))
    gray = _to_grayscale(img)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (kernel_size, kernel_size),
    )
    result = cv2.morphologyEx(gray, op_map[operation], kernel, iterations=iterations)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), result.shape[1], result.shape[0], 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(result)
    out_ds.FlushCache()
    out_ds = None

    return str(out_path)


@mcp.tool(description='''
Change Vector Analysis on two multi-band images.
Computes per-pixel CVA magnitude across all bands, optionally with histogram matching.
Params: image_path_1, image_path_2, output_path, match_histograms (bool, default=True).
Returns: dict {image_path, mean_change, max_change, changed_pixel_count}.
''')
def temporal_difference_map(
    image_path_1: str,
    image_path_2: str,
    output_path: str,
    match_histograms: bool = True,
) -> dict:
    import numpy as np
    from osgeo import gdal

    ds1 = gdal.Open(_resolve_input(image_path_1))
    ds2 = gdal.Open(_resolve_input(image_path_2))

    if ds1 is None:
        raise FileNotFoundError(f"Cannot open: {image_path_1}")
    if ds2 is None:
        raise FileNotFoundError(f"Cannot open: {image_path_2}")

    rows1, cols1 = ds1.RasterYSize, ds1.RasterXSize
    rows2, cols2 = ds2.RasterYSize, ds2.RasterXSize
    if rows1 != rows2 or cols1 != cols2:
        raise ValueError(f"Image dimensions differ: ({rows1},{cols1}) vs ({rows2},{cols2})")

    n_bands = min(ds1.RasterCount, ds2.RasterCount)

    img1 = np.stack([ds1.GetRasterBand(b + 1).ReadAsArray().astype(np.float32) for b in range(n_bands)], axis=-1)
    img2 = np.stack([ds2.GetRasterBand(b + 1).ReadAsArray().astype(np.float32) for b in range(n_bands)], axis=-1)
    ds1 = ds2 = None

    if match_histograms:
        from skimage.exposure import match_histograms
        img2 = match_histograms(img2, img1, channel_axis=-1).astype(np.float32)

    diff = img1 - img2
    magnitude = np.sqrt(np.sum(diff ** 2, axis=-1))

    mean_change = float(magnitude.mean())
    max_change = float(magnitude.max())
    threshold = mean_change + 2 * magnitude.std()
    changed_pixel_count = int((magnitude > threshold).sum())

    mag_min, mag_max = magnitude.min(), magnitude.max()
    if mag_max > mag_min:
        magnitude_u8 = ((magnitude - mag_min) / (mag_max - mag_min) * 255).astype(np.uint8)
    else:
        magnitude_u8 = np.zeros_like(magnitude, dtype=np.uint8)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols1, rows1, 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(magnitude_u8)
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "mean_change": mean_change,
        "max_change": max_change,
        "changed_pixel_count": changed_pixel_count,
    }


@mcp.tool(description='''
LBP entropy and edge orientation analysis for detecting man-made features.
Low LBP entropy indicates regularity (potentially man-made structures).
Params: image_path, output_path, window_size (int, default=15).
Returns: dict {image_path, mean_regularity, high_regularity_percentage}.
''')
def regularity_index(
    image_path: str,
    output_path: str,
    window_size: int = 15,
) -> dict:
    import numpy as np
    from scipy import ndimage
    from skimage.feature import local_binary_pattern

    img = read_image_uint8(_resolve_input(image_path))
    gray = _to_grayscale(img).astype(np.float64)

    lbp = local_binary_pattern(gray, P=8, R=1, method='uniform')

    def _entropy(values):
        values = values.astype(np.int32)
        counts = np.bincount(values, minlength=10)
        probs = counts / (counts.sum() + 1e-10)
        probs = probs[probs > 0]
        return -np.sum(probs * np.log2(probs + 1e-10))

    lbp_entropy = ndimage.generic_filter(lbp, _entropy, size=window_size)

    ent_min, ent_max = lbp_entropy.min(), lbp_entropy.max()
    if ent_max > ent_min:
        norm_entropy = (lbp_entropy - ent_min) / (ent_max - ent_min)
    else:
        norm_entropy = np.zeros_like(lbp_entropy)

    regularity = (1.0 - norm_entropy).astype(np.float32)

    mean_regularity = float(regularity.mean())
    high_regularity_percentage = float((regularity > 0.7).sum() / regularity.size * 100)

    reg_u8 = (regularity * 255).astype(np.uint8)

    from osgeo import gdal
    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, cols = reg_u8.shape
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(reg_u8)
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "mean_regularity": mean_regularity,
        "high_regularity_percentage": high_regularity_percentage,
    }


@mcp.tool(description='''
NDVI local z-score for detecting buried features via vegetation anomalies.
Positive z-score = wetter (ditches), negative z-score = drier (walls).
Params: image_path, output_path, window_size (int, default=25).
Returns: dict {image_path, positive_anomaly_count, negative_anomaly_count, mean_zscore}.
''')
def crop_mark_detector(
    image_path: str,
    output_path: str,
    window_size: int = 25,
) -> dict:
    import numpy as np
    from osgeo import gdal
    from scipy import ndimage

    ds = gdal.Open(_resolve_input(image_path))
    if ds is None:
        raise FileNotFoundError(f"Cannot open: {image_path}")

    n_bands = ds.RasterCount
    rows, cols = ds.RasterYSize, ds.RasterXSize

    if n_bands >= 8:
        # Sentinel-2: NDVI = (B8 - B4) / (B8 + B4)
        b4 = ds.GetRasterBand(4).ReadAsArray().astype(np.float32)
        b8 = ds.GetRasterBand(8).ReadAsArray().astype(np.float32)
        index_map = (b8 - b4) / (b8 + b4 + 1e-10)
    elif n_bands >= 4:
        # Use band4 as proxy for NIR, band3 as red
        b_red = ds.GetRasterBand(3).ReadAsArray().astype(np.float32)
        b_nir = ds.GetRasterBand(4).ReadAsArray().astype(np.float32)
        index_map = (b_nir - b_red) / (b_nir + b_red + 1e-10)
    else:
        # Fallback: grayscale intensity
        img = read_image_uint8(_resolve_input(image_path))
        gray = _to_grayscale(img)
        index_map = gray.astype(np.float32) / 255.0
    ds = None

    local_mean = ndimage.uniform_filter(index_map, size=window_size).astype(np.float32)
    local_sq_mean = ndimage.uniform_filter(index_map ** 2, size=window_size).astype(np.float32)
    local_var = np.maximum(local_sq_mean - local_mean ** 2, 0)
    local_std = np.sqrt(local_var)

    z_score = (index_map - local_mean) / (local_std + 1e-10)

    positive_anomaly_count = int((z_score > 1.5).sum())
    negative_anomaly_count = int((z_score < -1.5).sum())
    mean_zscore = float(z_score.mean())

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(z_score.astype(np.float32))
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "positive_anomaly_count": positive_anomaly_count,
        "negative_anomaly_count": negative_anomaly_count,
        "mean_zscore": mean_zscore,
    }


@mcp.tool(description='''
Contour shape analysis: aspect ratio, compactness, solidity, and orientation histogram.
Detects dominant orientations in man-made features via orientation histogram peaks.
Params: image_path, output_path, min_area (int, default=10).
Returns: dict {image_path, shape_count, dominant_orientations, mean_compactness, mean_aspect_ratio, orientation_histogram}.
''')
def shape_statistics(
    image_path: str,
    output_path: str,
    min_area: int = 10,
) -> dict:
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))
    gray = _to_grayscale(img)

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    shapes = []
    orientations_all = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue

        compactness = (4 * np.pi * area) / (perimeter ** 2)
        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0.0

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h if h > 0 else 1.0

        if len(cnt) >= 5:
            (_, _), (ma, MA), angle = cv2.fitEllipse(cnt)
            orientation = float(angle)
        else:
            orientation = 0.0

        orientations_all.append(orientation % 180)
        shapes.append({
            "aspect_ratio": round(aspect_ratio, 4),
            "compactness": round(float(compactness), 4),
            "solidity": round(float(solidity), 4),
            "orientation": round(orientation % 180, 2),
        })

    # Orientation histogram: 18 bins (0-180 degrees)
    if orientations_all:
        hist, _ = np.histogram(orientations_all, bins=18, range=(0, 180))
        orientation_histogram = hist.tolist()
        # Find dominant orientations (local peaks in histogram)
        peaks = []
        for i in range(len(hist)):
            left = hist[(i - 1) % 18]
            right = hist[(i + 1) % 18]
            if hist[i] > 0 and hist[i] >= left and hist[i] >= right:
                angle_center = (i + 0.5) * 10  # bin center in degrees
                peaks.append(round(angle_center, 1))
        peaks.sort(key=lambda a: -hist[int(a / 10) % 18])
        dominant_orientations = peaks[:5]
    else:
        orientation_histogram = [0] * 18
        dominant_orientations = []

    mean_compactness = float(np.mean([s["compactness"] for s in shapes])) if shapes else 0.0
    mean_aspect_ratio = float(np.mean([s["aspect_ratio"] for s in shapes])) if shapes else 0.0

    # Save binary/contour image as output
    vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR) if gray.ndim == 2 else img.copy()
    cv2.drawContours(vis, contours, -1, (0, 255, 0), 1)
    vis_gray = cv2.cvtColor(vis, cv2.COLOR_BGR2GRAY)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, cols = vis_gray.shape
    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Byte)
    out_ds.GetRasterBand(1).WriteArray(vis_gray)
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "shape_count": len(shapes),
        "dominant_orientations": dominant_orientations,
        "mean_compactness": round(mean_compactness, 4),
        "mean_aspect_ratio": round(mean_aspect_ratio, 4),
        "orientation_histogram": orientation_histogram,
    }


@mcp.tool(description='''
Divide image into tiles and compute Archaeological Potential Score (APS) per tile.
APS = 0.4*edge_density + 0.3*contrast + 0.3*anomaly_score.
Params: image_path, output_path, grid_size (int, default=10).
Returns: dict {image_path, top_tiles, max_score, mean_score}.
''')
def systematic_grid_analysis(
    image_path: str,
    output_path: str,
    grid_size: int = 10,
) -> dict:
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(_resolve_input(image_path))
    gray = _to_grayscale(img).astype(np.float32)

    rows, cols = gray.shape
    tile_h = rows // grid_size
    tile_w = cols // grid_size

    if tile_h == 0 or tile_w == 0:
        raise ValueError(f"grid_size={grid_size} too large for image of size {rows}x{cols}")

    image_mean = float(gray.mean())
    image_std = float(gray.std()) + 1e-10

    aps_grid = np.zeros((grid_size, grid_size), dtype=np.float32)
    edge_densities = []
    contrasts = []
    anomaly_scores = []

    for row_i in range(grid_size):
        for col_i in range(grid_size):
            r0, r1 = row_i * tile_h, (row_i + 1) * tile_h
            c0, c1 = col_i * tile_w, (col_i + 1) * tile_w
            tile = gray[r0:r1, c0:c1]

            tile_u8 = tile.astype(np.uint8)
            edges = cv2.Canny(tile_u8, 20, 60)
            edge_density = float(edges.sum() / 255) / tile.size
            contrast = float(tile.std()) / 255.0
            tile_mean = float(tile.mean())
            anomaly_score = abs(tile_mean - image_mean) / image_std

            edge_densities.append(edge_density)
            contrasts.append(contrast)
            anomaly_scores.append(anomaly_score)

    # Normalize each metric to [0, 1]
    def _norm(arr):
        mn, mx = min(arr), max(arr)
        if mx > mn:
            return [(v - mn) / (mx - mn) for v in arr]
        return [0.0] * len(arr)

    ed_n = _norm(edge_densities)
    ct_n = _norm(contrasts)
    an_n = _norm(anomaly_scores)

    top_tiles = []
    idx = 0
    for row_i in range(grid_size):
        for col_i in range(grid_size):
            aps = 0.4 * ed_n[idx] + 0.3 * ct_n[idx] + 0.3 * an_n[idx]
            aps_grid[row_i, col_i] = aps
            top_tiles.append({"row": row_i, "col": col_i, "score": round(float(aps), 4)})
            idx += 1

    top_tiles.sort(key=lambda t: -t["score"])
    top_tiles = top_tiles[:10]

    # Upscale APS heatmap to original image size
    aps_upscaled = cv2.resize(aps_grid, (cols, rows), interpolation=cv2.INTER_LINEAR)

    out_path = TEMP_DIR / output_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    driver = gdal.GetDriverByName("GTiff")
    out_ds = driver.Create(str(out_path), cols, rows, 1, gdal.GDT_Float32)
    out_ds.GetRasterBand(1).WriteArray(aps_upscaled.astype(np.float32))
    out_ds.FlushCache()
    out_ds = None

    return {
        "image_path": str(out_path),
        "top_tiles": top_tiles,
        "max_score": round(float(aps_grid.max()), 4),
        "mean_score": round(float(aps_grid.mean()), 4),
    }


if __name__ == "__main__":
    mcp.run()
