"""Download Sentinel-2 data from AWS Earth Search STAC API."""
import asyncio
import uuid
from pathlib import Path

import numpy as np

STAC_URL = "https://earth-search.aws.element84.com/v1/"
BANDS = [
    "blue", "green", "red", "rededge1", "rededge2", "rededge3",
    "nir", "nir08", "swir16", "swir22",
]

# Track download jobs
_download_jobs: dict = {}


def download_sentinel2(
    lat: float, lon: float, size: int = 100, output_dir: str = "/tmp"
) -> tuple[str, str, float]:
    """Download Sentinel-2 multi-band GeoTIFF for given coordinates.

    Returns (path_to_file, datetime_str, cloud_cover).
    """
    import pystac_client
    import odc.stac
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS

    # ~1km box at 10m resolution for 100px
    half_deg = size * 10 / 111000 / 2  # Convert pixels*resolution to degrees
    bbox = [lon - half_deg, lat - half_deg, lon + half_deg, lat + half_deg]

    catalog = pystac_client.Client.open(STAC_URL)
    items = list(catalog.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime="2024-01-01/2025-12-31",
        query={"eo:cloud_cover": {"lt": 15}},
        max_items=10,
    ).items())

    if not items:
        raise RuntimeError("No Sentinel-2 scenes found for this location")

    items.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
    best = items[0]

    bands = [b for b in BANDS if b in best.assets]
    data = odc.stac.load(
        [best], bands=bands, bbox=bbox, resolution=10,
        crs="EPSG:32718", chunks={},
    ).compute()
    if "time" in data.dims:
        data = data.isel(time=0)

    arrays = [data[b].values[:size, :size] for b in bands if b in data]
    stacked = np.stack(arrays, axis=0)

    xs, ys = data.x.values, data.y.values
    tf = from_bounds(xs.min(), ys.min(), xs.max(), ys.max(), size, size)

    file_id = str(uuid.uuid4())[:8]
    outfile = f"{output_dir}/sentinel2_{file_id}.tif"
    with rasterio.open(
        outfile, "w", driver="GTiff", height=size, width=size,
        count=len(bands), dtype=stacked.dtype,
        crs=CRS.from_epsg(32718), transform=tf, compress="deflate",
    ) as dst:
        for i, name in enumerate(bands):
            dst.write(stacked[i], i + 1)
            dst.set_band_description(i + 1, name)

    date_str = best.datetime.isoformat() if best.datetime else ""
    cloud_cover = best.properties.get("eo:cloud_cover", 0)
    return outfile, date_str, cloud_cover


async def start_download(lat: float, lon: float, size: int = 100) -> str:
    """Start async download job. Returns job_id."""
    job_id = str(uuid.uuid4())[:8]
    _download_jobs[job_id] = {"status": "downloading", "lat": lat, "lon": lon}

    async def _run():
        try:
            loop = asyncio.get_event_loop()
            outfile, date, cloud = await loop.run_in_executor(
                None, download_sentinel2, lat, lon, size, "/tmp"
            )
            _download_jobs[job_id].update({
                "status": "done",
                "file_path": outfile,
                "date": date,
                "cloud_cover": cloud,
            })
        except Exception as e:
            _download_jobs[job_id].update({"status": "error", "error": str(e)})

    asyncio.create_task(_run())
    return job_id


def get_download_status(job_id: str) -> dict:
    """Return current status of a download job."""
    return _download_jobs.get(job_id, {"status": "not_found"})
