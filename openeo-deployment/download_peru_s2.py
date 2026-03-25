#!/usr/bin/env python3
"""Download 100x100 pixel Sentinel-2 data (all bands) for a point in Peru."""

import sys
import os
import numpy as np

# Ensure environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "openeo_app"))

from openeo_app.processes.load_collection import load_collection

# Center point - Nazca/Ica region, Peru
LON, LAT = -75.234734, -14.478330

# 100 pixels at 10m = 1km ≈ 0.009° lat, 0.0093° lon at this latitude
# Use 0.005° offset each side
OFFSET = 0.005

bbox = {
    "west": LON - OFFSET,
    "south": LAT - OFFSET,
    "east": LON + OFFSET,
    "north": LAT + OFFSET,
}

print(f"Center: ({LAT}, {LON})")
print(f"BBox: {bbox}")
print(f"Loading Sentinel-2 L2A (all bands)...")

# All Sentinel-2 bands (AWS Earth Search names)
ALL_BANDS = [
    "blue", "green", "red",
    "rededge1", "rededge2", "rededge3",
    "nir", "nir08", "nir09",
    "swir16", "swir22",
    "scl",
]

# Single recent timestamp window
data = load_collection(
    id="sentinel-2-l2a",
    spatial_extent=bbox,
    temporal_extent=["2024-06-01", "2024-06-10"],
    bands=ALL_BANDS,
)

print(f"\n--- Lazy DataArray ---")
print(f"Shape: {data.shape}")
print(f"Dims:  {data.dims}")

# Compute (actually download)
print("\nComputing (downloading data)...")
result = data.compute()

print(f"\n--- Computed Result ---")
print(f"Shape: {result.shape}")
print(f"Dtype: {result.dtype}")
print(f"Size:  {result.nbytes / 1024:.1f} KB")

# Select first timestamp if multiple
if "time" in result.dims and result.sizes["time"] > 1:
    print(f"Multiple timestamps found ({result.sizes['time']}), selecting first...")
    result = result.isel(time=0)
    print(f"Shape after time selection: {result.shape}")

# Save as GeoTIFF
output_path = os.path.join(os.path.dirname(__file__), "peru_nazca_s2_100x100.tif")
import rioxarray  # noqa: E402

if result.rio.crs is None:
    result = result.rio.write_crs("EPSG:4326")

# Handle time dim for GeoTIFF
if "time" in result.dims:
    result = result.isel(time=0)

result.rio.to_raster(output_path)
print(f"\n✅ Saved: {output_path}")
print(f"   Bands: {len(ALL_BANDS)}")
print(f"   Spatial: ~100x100 pixels at 10m")
print(f"   Center: ({LAT}, {LON})")
