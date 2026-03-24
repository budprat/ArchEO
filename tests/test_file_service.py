"""Tests for api/file_service.py."""
import json
import struct
import tempfile
import zlib
from pathlib import Path

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_png(path: str, width: int, height: int, channels: int = 3) -> None:
    """Write a minimal valid PNG file without Pillow."""
    import cv2

    if channels == 3:
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[..., 0] = 100  # B
        img[..., 1] = 150  # G
        img[..., 2] = 200  # R
    else:
        img = np.zeros((height, width), dtype=np.uint8)
        img[:] = 128

    cv2.imwrite(path, img)


def _write_geotiff(path: str, width: int, height: int, bands: int = 3) -> None:
    """Write a minimal GeoTIFF with EPSG:4326 CRS using rasterio."""
    import rasterio
    from rasterio.transform import from_bounds

    transform = from_bounds(0, 0, 1, 1, width, height)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=bands,
        dtype="uint16",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        for b in range(1, bands + 1):
            data = np.random.randint(0, 1000, (height, width), dtype=np.uint16)
            dst.write(data, b)


# ---------------------------------------------------------------------------
# extract_metadata
# ---------------------------------------------------------------------------

class TestExtractMetadata:
    def test_png_basic(self, tmp_path):
        """extract_metadata returns correct dims for a plain PNG."""
        from api.file_service import extract_metadata

        png_path = str(tmp_path / "test.png")
        _write_png(png_path, width=100, height=100, channels=3)

        meta = extract_metadata(png_path)

        assert meta["width"] == 100
        assert meta["height"] == 100
        assert meta["bands"] == 3

    def test_geotiff_with_crs(self, tmp_path):
        """extract_metadata returns CRS info for a GeoTIFF."""
        from api.file_service import extract_metadata

        tiff_path = str(tmp_path / "test.tif")
        _write_geotiff(tiff_path, width=64, height=64, bands=3)

        meta = extract_metadata(tiff_path)

        assert meta["width"] == 64
        assert meta["height"] == 64
        assert meta["bands"] == 3
        # CRS should be present and reference EPSG:4326
        assert meta["crs"] is not None
        assert "4326" in str(meta["crs"])

    def test_metadata_keys_present(self, tmp_path):
        """extract_metadata always returns the required keys."""
        from api.file_service import extract_metadata

        png_path = str(tmp_path / "keys_test.png")
        _write_png(png_path, width=50, height=50)

        meta = extract_metadata(png_path)
        for key in ("width", "height", "bands", "format", "crs", "dtype"):
            assert key in meta, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# generate_thumbnail
# ---------------------------------------------------------------------------

class TestGenerateThumbnail:
    def test_thumbnail_created(self, tmp_path):
        """generate_thumbnail produces a valid PNG file."""
        import cv2
        from api.file_service import generate_thumbnail

        src = str(tmp_path / "src.png")
        dst = str(tmp_path / "thumb.png")
        _write_png(src, width=200, height=150)

        result_path = generate_thumbnail(src, dst, max_size=1024)

        assert Path(result_path).exists()
        img = cv2.imread(result_path, cv2.IMREAD_UNCHANGED)
        assert img is not None

    def test_thumbnail_respects_max_size(self, tmp_path):
        """Large images are downscaled to fit within max_size."""
        import cv2
        from api.file_service import generate_thumbnail

        src = str(tmp_path / "large.png")
        dst = str(tmp_path / "thumb_small.png")
        _write_png(src, width=2000, height=1500)

        generate_thumbnail(src, dst, max_size=1024)

        img = cv2.imread(dst, cv2.IMREAD_UNCHANGED)
        assert img is not None
        h, w = img.shape[:2]
        assert max(h, w) <= 1024

    def test_thumbnail_small_image_unchanged_size(self, tmp_path):
        """Images smaller than max_size are not upscaled."""
        import cv2
        from api.file_service import generate_thumbnail

        src = str(tmp_path / "small.png")
        dst = str(tmp_path / "thumb_keep.png")
        _write_png(src, width=100, height=80)

        generate_thumbnail(src, dst, max_size=1024)

        img = cv2.imread(dst, cv2.IMREAD_UNCHANGED)
        h, w = img.shape[:2]
        assert w == 100
        assert h == 80

    def test_thumbnail_uint8_output(self, tmp_path):
        """Thumbnail pixels are in uint8 range."""
        import cv2
        from api.file_service import generate_thumbnail

        src = str(tmp_path / "uint16.tif")
        dst = str(tmp_path / "thumb_u8.png")
        _write_geotiff(src, width=64, height=64, bands=1)

        generate_thumbnail(src, dst, max_size=1024)

        img = cv2.imread(dst, cv2.IMREAD_UNCHANGED)
        assert img is not None
        assert img.dtype == np.uint8


# ---------------------------------------------------------------------------
# process_upload
# ---------------------------------------------------------------------------

class TestProcessUpload:
    def test_directory_structure_created(self, tmp_path):
        """process_upload creates file_id dir with metadata.json + thumbnail.png."""
        from api.file_service import process_upload

        src = str(tmp_path / "input.png")
        uploads_dir = str(tmp_path / "uploads")
        _write_png(src, width=120, height=80)

        result = process_upload(src, "input.png", uploads_dir)

        file_id = result["file_id"]
        dest_dir = Path(uploads_dir) / file_id

        assert dest_dir.is_dir()
        assert (dest_dir / "metadata.json").exists()
        assert (dest_dir / "thumbnail.png").exists()

    def test_metadata_json_contents(self, tmp_path):
        """metadata.json contains expected keys."""
        from api.file_service import process_upload

        src = str(tmp_path / "check.png")
        uploads_dir = str(tmp_path / "uploads")
        _write_png(src, width=60, height=40)

        result = process_upload(src, "check.png", uploads_dir)
        file_id = result["file_id"]

        meta_path = Path(uploads_dir) / file_id / "metadata.json"
        with open(meta_path) as fh:
            saved = json.load(fh)

        for key in ("width", "height", "bands", "format", "crs", "dtype",
                    "original_name", "file_id"):
            assert key in saved, f"Missing key in metadata.json: {key}"
        assert saved["original_name"] == "check.png"
        assert saved["file_id"] == file_id

    def test_return_dict_structure(self, tmp_path):
        """process_upload return value has file_id, metadata, thumbnail_url."""
        from api.file_service import process_upload

        src = str(tmp_path / "ret.png")
        uploads_dir = str(tmp_path / "uploads")
        _write_png(src, width=50, height=50)

        result = process_upload(src, "ret.png", uploads_dir)

        assert "file_id" in result
        assert "metadata" in result
        assert "thumbnail_url" in result
        assert result["thumbnail_url"].startswith("/uploads/")
        assert result["thumbnail_url"].endswith("thumbnail.png")

    def test_geotiff_upload(self, tmp_path):
        """process_upload works end-to-end for a GeoTIFF."""
        from api.file_service import process_upload

        src = str(tmp_path / "geo.tif")
        uploads_dir = str(tmp_path / "uploads")
        _write_geotiff(src, width=64, height=64, bands=3)

        result = process_upload(src, "geo.tif", uploads_dir)

        assert result["metadata"]["width"] == 64
        assert result["metadata"]["bands"] == 3
        file_id = result["file_id"]
        assert (Path(uploads_dir) / file_id / "thumbnail.png").exists()
