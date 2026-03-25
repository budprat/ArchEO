#!/usr/bin/env python3
"""Download Sentinel-2 imagery of the Nazca Monkey geoglyph.

500x500 pixels, all bands, saved as multi-band GeoTIFF.

Usage:
    cd /Users/macbookpro/openeo-deployment
    source .env && source venv/bin/activate
    python download_nazca_monkey.py
"""

import numpy as np
import pystac_client
import odc.stac
import rioxarray

# --- Configuration ---
STAC_URL = "https://earth-search.aws.element84.com/v1/"
COLLECTION = "sentinel-2-l2a"

# Nazca Monkey geoglyph center (~14.6937S, 75.1228W)
CENTER_LAT = -14.6937
CENTER_LON = -75.1228

# 500px at 10m = 5km; half-extent in degrees
# 1 deg lat ~ 111km, 1 deg lon ~ 107.3km at this latitude
HALF_LAT = 0.0225   # ~2.5km
HALF_LON = 0.0233   # ~2.5km

BBOX = [
    CENTER_LON - HALF_LON,  # west
    CENTER_LAT - HALF_LAT,  # south
    CENTER_LON + HALF_LON,  # east
    CENTER_LAT + HALF_LAT,  # north
]

# All Sentinel-2 L2A bands (AWS Earth Search names)
ALL_BANDS = [
    "coastal",     # B01 - 60m
    "blue",        # B02 - 10m
    "green",       # B03 - 10m
    "red",         # B04 - 10m
    "rededge1",    # B05 - 20m
    "rededge2",    # B06 - 20m
    "rededge3",    # B07 - 20m
    "nir",         # B08 - 10m
    "nir08",       # B8A - 20m
    "nir09",       # B09 - 60m
    "swir16",      # B11 - 20m
    "swir22",      # B12 - 20m
    "scl",         # Scene Classification - 20m
]

# Date range - Nazca is desert (dry year-round), expand range
DATE_RANGE = "2024-01-01/2025-12-31"

# Output
OUTPUT_FILE = "nazca_monkey_all_bands_500x500.tif"
TARGET_SIZE = 500


def main():
    print(f"Searching STAC catalog for Sentinel-2 over Nazca Monkey...")
    print(f"  BBOX: {BBOX}")
    print(f"  Date range: {DATE_RANGE}")
    print(f"  Bands: {len(ALL_BANDS)} total")

    # 1. Search STAC catalog
    catalog = pystac_client.Client.open(STAC_URL)
    search = catalog.search(
        collections=[COLLECTION],
        bbox=BBOX,
        datetime=DATE_RANGE,
        query={"eo:cloud_cover": {"lt": 20}},  # <20% cloud cover
        max_items=20,
    )

    items = list(search.items())
    if not items:
        print("No items found! Try expanding date range or cloud cover threshold.")
        return

    # Sort by cloud cover and use the least cloudy scene
    items.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
    best = items[0]
    cloud_pct = best.properties.get("eo:cloud_cover", "?")
    print(f"\nBest scene: {best.id}")
    print(f"  Date: {best.datetime}")
    print(f"  Cloud cover: {cloud_pct}%")

    # 2. Check which bands are actually available in this item
    available_assets = set(best.assets.keys())
    bands_to_load = [b for b in ALL_BANDS if b in available_assets]
    skipped = [b for b in ALL_BANDS if b not in available_assets]
    if skipped:
        print(f"  Skipping unavailable bands: {skipped}")
    print(f"  Loading {len(bands_to_load)} bands: {bands_to_load}")

    # 3. Load data with odc-stac (resampled to 10m → 500x500)
    print(f"\nLoading data (resampling all bands to 10m for {TARGET_SIZE}x{TARGET_SIZE})...")
    data = odc.stac.load(
        [best],
        bands=bands_to_load,
        bbox=BBOX,
        resolution=10,        # 10m resolution
        crs="EPSG:32718",     # UTM zone 18S (covers Nazca)
        chunks={},            # Use dask for memory efficiency
    )

    # 4. Compute (trigger download)
    print("Downloading and computing...")
    data = data.compute()

    # Squeeze time dimension (single scene)
    if "time" in data.dims:
        data = data.isel(time=0)

    # 5. Resize to exactly 500x500 if needed
    print(f"  Raw shape per band: y={data.dims.get('y', '?')}, x={data.dims.get('x', '?')}")

    # Stack all bands into a single DataArray
    band_arrays = []
    band_names = []
    for band in bands_to_load:
        if band in data:
            arr = data[band].values
            # Resize to 500x500 using simple slicing/padding
            arr_resized = _resize_to_target(arr, TARGET_SIZE, TARGET_SIZE)
            band_arrays.append(arr_resized)
            band_names.append(band)

    if not band_arrays:
        print("ERROR: No band data loaded!")
        return

    # Stack into (bands, y, x)
    stacked = np.stack(band_arrays, axis=0)
    print(f"  Final shape: {stacked.shape} (bands, y, x)")
    print(f"  Bands: {band_names}")

    # 6. Save as multi-band GeoTIFF
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS

    # Get spatial reference from the loaded data
    sample_band = bands_to_load[0]
    xs = data.x.values
    ys = data.y.values

    # Compute transform for the 500x500 output
    transform = from_bounds(
        xs.min(), ys.min(), xs.max(), ys.max(),
        TARGET_SIZE, TARGET_SIZE
    )

    with rasterio.open(
        OUTPUT_FILE,
        "w",
        driver="GTiff",
        height=TARGET_SIZE,
        width=TARGET_SIZE,
        count=len(band_names),
        dtype=stacked.dtype,
        crs=CRS.from_epsg(32718),
        transform=transform,
        compress="deflate",
    ) as dst:
        for i, name in enumerate(band_names):
            dst.write(stacked[i], i + 1)
            dst.set_band_description(i + 1, name)

    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"  Size: {TARGET_SIZE}x{TARGET_SIZE} pixels")
    print(f"  Bands: {len(band_names)}")
    print(f"  CRS: EPSG:32718 (UTM 18S)")
    print(f"  Dtype: {stacked.dtype}")


def _resize_to_target(arr, target_h, target_w):
    """Resize 2D array to target size via slicing or zero-padding."""
    h, w = arr.shape
    out = np.zeros((target_h, target_w), dtype=arr.dtype)
    copy_h = min(h, target_h)
    copy_w = min(w, target_w)
    out[:copy_h, :copy_w] = arr[:copy_h, :copy_w]
    return out


if __name__ == "__main__":
    main()
