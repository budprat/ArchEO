#!/usr/bin/env python3
"""
Download Sentinel-2 L2A data with ALL bands for Peru site.

Coordinates (polygon bbox):
  West: -75.2, South: -14.4, East: -75.1, North: -14.3
  ~10km x ~11km area
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "openeo_app"))

from openeo_app.processes.load_collection import load_collection

# Bounding box from polygon coordinates
bbox = {
    "west": -75.2,
    "south": -14.4,
    "east": -75.1,
    "north": -14.3,
}

# All Sentinel-2 L2A bands (AWS Earth Search names)
ALL_BANDS = [
    "coastal",      # B01 - Coastal aerosol (60m)
    "blue",         # B02 - Blue (10m)
    "green",        # B03 - Green (10m)
    "red",          # B04 - Red (10m)
    "rededge1",     # B05 - Red Edge 1 (20m)
    "rededge2",     # B06 - Red Edge 2 (20m)
    "rededge3",     # B07 - Red Edge 3 (20m)
    "nir",          # B08 - NIR (10m)
    "nir08",        # B8A - NIR narrow (20m)
    "nir09",        # B09 - Water vapor (60m)
    "swir16",       # B11 - SWIR 1610nm (20m)
    "swir22",       # B12 - SWIR 2190nm (20m)
    "scl",          # Scene Classification Layer (20m)
]

# Temporal window - recent cloud-free period for Peru dry season
TEMPORAL_EXTENT = ["2024-06-01", "2024-06-30"]

print("=" * 60)
print("Sentinel-2 L2A Download - Peru Site (All Bands)")
print("=" * 60)
print(f"BBox: west={bbox['west']}, south={bbox['south']}, east={bbox['east']}, north={bbox['north']}")
print(f"Area: ~{abs(bbox['east']-bbox['west'])*111:.1f} km x ~{abs(bbox['north']-bbox['south'])*111:.1f} km")
print(f"Temporal: {TEMPORAL_EXTENT[0]} to {TEMPORAL_EXTENT[1]}")
print(f"Bands: {len(ALL_BANDS)} ({', '.join(ALL_BANDS)})")
print()

print("Loading collection (lazy)...")
data = load_collection(
    id="sentinel-2-l2a",
    spatial_extent=bbox,
    temporal_extent=TEMPORAL_EXTENT,
    bands=ALL_BANDS,
)

print(f"\n--- Lazy DataArray ---")
print(f"Shape: {data.shape}")
print(f"Dims:  {data.dims}")
if hasattr(data, 'coords') and 'bands' in data.coords:
    print(f"Bands: {list(data.coords['bands'].values)}")

print("\nComputing (downloading data from AWS)...")
result = data.compute()

print(f"\n--- Computed Result ---")
print(f"Shape: {result.shape}")
print(f"Dtype: {result.dtype}")
print(f"Size:  {result.nbytes / (1024*1024):.1f} MB")

# Show time dimension info
if "time" in result.dims:
    n_times = result.sizes["time"]
    print(f"Timestamps: {n_times}")
    if hasattr(result, 'coords') and 'time' in result.coords:
        times = result.coords['time'].values
        for i, t in enumerate(times):
            print(f"  [{i}] {t}")

# Band statistics
print("\n--- Band Statistics ---")
for band in ALL_BANDS:
    try:
        if 'bands' in result.dims:
            band_data = result.sel(bands=band)
        else:
            continue
        valid = band_data.values[~np.isnan(band_data.values)] if np.issubdtype(band_data.dtype, np.floating) else band_data.values
        if len(valid) > 0:
            print(f"  {band:12s}: min={np.nanmin(valid):8.1f}, max={np.nanmax(valid):8.1f}, mean={np.nanmean(valid):8.1f}")
        else:
            print(f"  {band:12s}: no valid data")
    except Exception as e:
        print(f"  {band:12s}: error - {e}")

# Save as GeoTIFF
import rioxarray  # noqa: E402

output_dir = os.path.dirname(os.path.abspath(__file__))

# Save each timestamp separately if multiple
if "time" in result.dims and result.sizes["time"] > 0:
    for t_idx in range(result.sizes["time"]):
        single = result.isel(time=t_idx)

        if single.rio.crs is None:
            single = single.rio.write_crs("EPSG:4326")

        if hasattr(result.coords, 'time'):
            ts = str(result.coords['time'].values[t_idx])[:10]
        else:
            ts = f"t{t_idx}"

        output_path = os.path.join(output_dir, f"peru_s2_allbands_{ts}.tif")
        single.rio.to_raster(output_path)
        print(f"\n>> Saved: {output_path}")
        print(f"   Shape: {single.shape}")
else:
    # No time dim or single
    save_data = result
    if save_data.rio.crs is None:
        save_data = save_data.rio.write_crs("EPSG:4326")
    output_path = os.path.join(output_dir, "peru_s2_allbands.tif")
    save_data.rio.to_raster(output_path)
    print(f"\n>> Saved: {output_path}")

print(f"\n{'='*60}")
print(f"Download complete!")
print(f"  Bands: {len(ALL_BANDS)}")
print(f"  Location: Peru ({bbox['south']}N to {bbox['north']}N, {bbox['west']}E to {bbox['east']}E)")
print(f"{'='*60}")
