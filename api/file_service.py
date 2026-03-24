"""File upload processing, GDAL metadata extraction, and thumbnail generation."""
import json
import shutil
import uuid
from pathlib import Path

import numpy as np


def extract_metadata(file_path: str) -> dict:
    """Extract image metadata using GDAL.

    Returns a dict with keys: width, height, bands, format, crs, dtype.
    Falls back to rasterio if GDAL fails, then to OpenCV for plain images.
    """
    from osgeo import gdal

    gdal.UseExceptions()
    try:
        ds = gdal.Open(file_path)
        if ds is None:
            raise RuntimeError(f"GDAL could not open {file_path}")

        metadata: dict = {
            "width": ds.RasterXSize,
            "height": ds.RasterYSize,
            "bands": ds.RasterCount,
            "format": ds.GetDriver().ShortName,
            "crs": ds.GetProjection() or None,
            "dtype": None,
        }

        if ds.RasterCount > 0:
            band = ds.GetRasterBand(1)
            metadata["dtype"] = gdal.GetDataTypeName(band.DataType)

        ds = None  # close dataset
        return metadata

    except Exception:
        # Fallback: rasterio handles GeoTIFF and common raster formats
        try:
            import rasterio

            with rasterio.open(file_path) as src:
                crs_str = src.crs.to_string() if src.crs else None
                return {
                    "width": src.width,
                    "height": src.height,
                    "bands": src.count,
                    "format": src.driver,
                    "crs": crs_str,
                    "dtype": str(src.dtypes[0]) if src.dtypes else None,
                }
        except Exception:
            # Last resort: OpenCV for plain images without geo metadata
            import cv2

            img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise RuntimeError(f"Cannot read image: {file_path}")
            h, w = img.shape[:2]
            bands = img.shape[2] if img.ndim == 3 else 1
            return {
                "width": w,
                "height": h,
                "bands": bands,
                "format": Path(file_path).suffix.lstrip(".").upper(),
                "crs": None,
                "dtype": str(img.dtype),
            }


def generate_thumbnail(
    file_path: str, output_path: str, max_size: int = 1024
) -> str:
    """Generate a PNG thumbnail normalized to uint8, max *max_size* px on longest side.

    Returns the output path string.
    """
    import cv2

    img = cv2.imread(file_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        # Try rasterio for multi-band / GeoTIFF
        try:
            import rasterio
            from rasterio.enums import Resampling

            with rasterio.open(file_path) as src:
                # Read first 3 bands (or fewer)
                n_bands = min(src.count, 3)
                data = src.read(
                    list(range(1, n_bands + 1)),
                    out_shape=(
                        n_bands,
                        min(src.height, max_size),
                        min(src.width, max_size),
                    ),
                    resampling=Resampling.bilinear,
                )
                # data shape: (bands, h, w) → (h, w, bands)
                img = np.transpose(data, (1, 2, 0))
        except Exception as exc:
            raise RuntimeError(
                f"Cannot read {file_path} for thumbnail generation"
            ) from exc

    # Normalise to uint8
    if img.dtype != np.uint8:
        img_min, img_max = float(img.min()), float(img.max())
        if img_max > img_min:
            img = ((img - img_min) / (img_max - img_min) * 255).astype(np.uint8)
        else:
            img = np.zeros_like(img, dtype=np.uint8)

    # Resize so longest side ≤ max_size
    h, w = img.shape[:2]
    if max(h, w) > max_size:
        scale = max_size / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    cv2.imwrite(output_path, img)
    return output_path


def process_upload(
    file_path: str, original_name: str, uploads_dir: str
) -> dict:
    """Full upload pipeline.

    1. Generates a UUID-based directory under *uploads_dir*.
    2. Copies the uploaded file into that directory.
    3. Extracts metadata.
    4. Generates a thumbnail (thumbnail.png).
    5. Saves metadata.json.

    Returns a dict with keys: file_id, metadata, thumbnail_url.
    """
    file_id = str(uuid.uuid4())
    dest_dir = Path(uploads_dir) / file_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Preserve original extension
    ext = Path(original_name).suffix or Path(file_path).suffix
    dest_file = dest_dir / f"original{ext}"
    shutil.copy2(file_path, str(dest_file))

    # Metadata
    metadata = extract_metadata(str(dest_file))
    metadata["original_name"] = original_name
    metadata["file_id"] = file_id

    # Thumbnail
    thumbnail_path = str(dest_dir / "thumbnail.png")
    generate_thumbnail(str(dest_file), thumbnail_path)

    # Persist metadata
    metadata_path = dest_dir / "metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)

    return {
        "file_id": file_id,
        "metadata": metadata,
        "thumbnail_url": f"/uploads/{file_id}/thumbnail.png",
    }
