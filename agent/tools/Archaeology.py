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


@mcp.tool(description='''
Description:
Apply Canny edge detection to an image and save the result as a GeoTIFF.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the output edge image
                     (e.g., "results/edges_canny.tif").
- low_threshold (float, optional): Lower hysteresis threshold. Default = 50.
- high_threshold (float, optional): Upper hysteresis threshold. Default = 150.

Returns:
- str: Path to the saved edge detection result image.
''')
def edge_detection_canny(
    image_path: str,
    output_path: str,
    low_threshold: float = 50,
    high_threshold: float = 150,
) -> str:
    """
    Description:
        Apply Canny edge detection to an input image. The image is read via GDAL
        (supporting GeoTIFF and other formats), normalized to uint8, converted to
        grayscale if needed, then processed with the Canny operator.

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the result GeoTIFF.
        low_threshold (float, default=50):
            Lower bound for the hysteresis thresholding step.
        high_threshold (float, default=150):
            Upper bound for the hysteresis thresholding step.

    Returns:
        str:
            Absolute path to the saved edge image.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(image_path)

    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

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

    img = read_image_uint8(image_path)

    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
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

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the annotated output image
                     (e.g., "results/lines.tif").
- min_line_length (int, optional): Minimum line length in pixels. Default = 50.
- max_line_gap (int, optional): Maximum allowed gap between line segments to treat
                                them as a single line. Default = 10.

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
    min_line_length: int = 50,
    max_line_gap: int = 10,
) -> dict:
    """
    Description:
        Detect linear features using the Probabilistic Hough Line Transform.
        Canny edge detection is applied first; detected lines are drawn on a copy
        of the grayscale image and the result is saved. Orientation angles (0-180°)
        are computed for each line segment.

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the annotated result GeoTIFF.
        min_line_length (int, default=50):
            Minimum pixel length for a segment to be retained.
        max_line_gap (int, default=10):
            Maximum gap in pixels between collinear points to bridge.

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

    img = read_image_uint8(image_path)

    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
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
shape descriptors. Useful for detecting regular or irregular archaeological
features such as enclosures, pits, or mounds.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- output_path (str): Relative file path to save the annotated output image
                     (e.g., "results/shapes.tif").
- min_area (int, optional): Minimum contour area in pixels to include. Default = 100.

Returns:
- dict: {
    "image_path": str,   # Path to the saved annotated image
    "shapes": list[dict],# List of shape descriptors per contour
    "count": int         # Number of shapes detected
  }
  Each shape dict contains:
    "area" (float), "perimeter" (float), "circularity" (float),
    "aspect_ratio" (float), "bounding_box" ([x, y, w, h])
''')
def geometric_pattern_analysis(
    image_path: str,
    output_path: str,
    min_area: int = 100,
) -> dict:
    """
    Description:
        Detect contours in the image and compute shape descriptors including
        area, perimeter, circularity (4π·area/perimeter²), aspect ratio
        (bounding box width / height), and the bounding box [x, y, w, h].
        Contours below min_area are filtered out.

    Parameters:
        image_path (str):
            Path to the input raster image.
        output_path (str):
            Relative path (within TEMP_DIR) to write the annotated result GeoTIFF.
        min_area (int, default=100):
            Minimum contour area in pixels to retain.

    Returns:
        dict with keys:
            image_path (str): Path to annotated output image.
            shapes (list[dict]): Shape descriptors per contour.
            count (int): Number of retained contours.
    """
    import cv2
    import numpy as np
    from osgeo import gdal

    img = read_image_uint8(image_path)

    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

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

        cv2.drawContours(out_img, [cnt], -1, (0, 255, 0), 1)
        shapes.append({
            "area": round(area, 2),
            "perimeter": round(perimeter, 2),
            "circularity": round(float(circularity), 4),
            "aspect_ratio": round(aspect_ratio, 4),
            "bounding_box": [int(x), int(y), int(w), int(h)],
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

    ds = gdal.Open(dem_path)
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
feature boundaries.

Parameters:
- image_path (str): Path to the input image (any GDAL-supported format, e.g. GeoTIFF).
- distances (list[int], optional): List of pixel-pair distances for GLCM computation.
                                   Default = [1].
- angles (list[float], optional): List of angles in radians for GLCM computation.
                                  Default = [0] (0 radians = horizontal).

Returns:
- dict: {
    "contrast"    (float): Measures local intensity variation.
    "homogeneity" (float): Measures closeness of element distribution to GLCM diagonal.
    "entropy"     (float): Measures randomness of texture.
    "correlation" (float): Measures linear dependency of intensity levels.
    "energy"      (float): Sum of squared GLCM elements (angular second moment).
  }
''')
def texture_analysis_glcm(
    image_path: str,
    distances: list = None,
    angles: list = None,
) -> dict:
    """
    Description:
        Compute GLCM-based texture features from an input image.
        The image is read via GDAL, normalized to uint8, and reduced to 8 gray
        levels to keep the GLCM tractable. scikit-image's graycomatrix and
        graycoprops are used to compute the standard features.

    Parameters:
        image_path (str):
            Path to the input raster image.
        distances (list[int], default=[1]):
            Pixel-pair distances for GLCM computation.
        angles (list[float], default=[0]):
            Angles in radians (e.g., [0, np.pi/4, np.pi/2, 3*np.pi/4]).

    Returns:
        dict with keys:
            contrast (float), homogeneity (float), entropy (float),
            correlation (float), energy (float).
            Each value is the mean over all distance/angle combinations.
    """
    import numpy as np
    from skimage.feature import graycomatrix, graycoprops

    if distances is None:
        distances = [1]
    if angles is None:
        angles = [0]

    img = read_image_uint8(image_path)

    if img.ndim == 3:
        import cv2
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img

    # Reduce to 8 levels for efficient GLCM
    levels = 8
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

    # Entropy: -sum(p * log2(p + eps))
    eps = 1e-10
    glcm_norm = glcm / (glcm.sum(axis=(0, 1), keepdims=True) + eps)
    entropy = float(-np.sum(glcm_norm * np.log2(glcm_norm + eps)))

    return {
        "contrast": round(contrast, 6),
        "homogeneity": round(homogeneity, 6),
        "entropy": round(entropy, 6),
        "correlation": round(correlation, 6),
        "energy": round(energy, 6),
    }


if __name__ == "__main__":
    mcp.run()
