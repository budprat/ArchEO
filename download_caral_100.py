#!/usr/bin/env python3
"""Download 100x100 pixel Sentinel-2 multi-band GeoTIFF of Caral, Peru."""
import numpy as np
import pystac_client
import odc.stac
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

STAC_URL = "https://earth-search.aws.element84.com/v1/"
BBOX = [-77.5250, -10.8978, -77.5156, -10.8888]  # ~1km box over Caral
BANDS = ["blue", "green", "red", "rededge1", "rededge2", "rededge3", "nir", "nir08", "swir16", "swir22"]

print("Searching STAC for Sentinel-2 over Caral...")
catalog = pystac_client.Client.open(STAC_URL)
items = list(catalog.search(
    collections=["sentinel-2-l2a"], bbox=BBOX,
    datetime="2024-06-01/2024-11-30",
    query={"eo:cloud_cover": {"lt": 10}}, max_items=5
).items())
print(f"Found {len(items)} scenes")

items.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
best = items[0]
print(f"Best: {best.datetime}, cloud={best.properties.get('eo:cloud_cover')}%")

bands = [b for b in BANDS if b in best.assets]
print(f"Loading {len(bands)} bands: {bands}")

data = odc.stac.load([best], bands=bands, bbox=BBOX, resolution=10, crs="EPSG:32718", chunks={}).compute()
if "time" in data.dims:
    data = data.isel(time=0)

arrays = [data[b].values[:100, :100] for b in bands if b in data]
stacked = np.stack(arrays, axis=0)
print(f"Shape: {stacked.shape}")

xs, ys = data.x.values, data.y.values
tf = from_bounds(xs.min(), ys.min(), xs.max(), ys.max(), 100, 100)
out = "caral_100x100_10bands.tif"
with rasterio.open(out, "w", driver="GTiff", height=100, width=100,
                   count=len(bands), dtype=stacked.dtype,
                   crs=CRS.from_epsg(32718), transform=tf, compress="deflate") as dst:
    for i, name in enumerate(bands):
        dst.write(stacked[i], i + 1)
        dst.set_band_description(i + 1, name)

print(f"Saved: {out} ({stacked.shape[0]} bands, 100x100, 10m resolution)")
