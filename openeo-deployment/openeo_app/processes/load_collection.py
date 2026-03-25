"""Implementation of the load_collection process for OpenEO.

Enhanced with:
- Collection-specific chunking strategies (2048x2048 for Sentinel-2)
- Band name mapping (B04->red, B08->nir)
- Cloud-optimized GeoTIFF configuration
- Common name coordinate for NDVI band selection
"""

import logging
import os
from typing import Optional, List

import numpy as np
import xarray as xr
import odc.stac
import pystac_client

from .band_mapper import BandMapper, get_scale_factor
from .chunking import ChunkingStrategy, get_chunks_for_collection

logger = logging.getLogger(__name__)

# Standard OpenEO band name -> AWS Earth Search name translation.
# Users can use either format; this dict translates B## codes to STAC names.
OPENEO_TO_AWS_BANDS = {
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B08": "nir",
    "B8A": "nir08",
    "B09": "nir09",
    "B11": "swir16",
    "B12": "swir22",
    "SCL": "scl",
}


def _translate_band_names(bands: Optional[List[str]]) -> Optional[List[str]]:
    """Translate standard OpenEO band names to AWS Earth Search names.

    Accepts both formats - e.g. 'B04' is translated to 'red', while 'red'
    passes through unchanged.

    Args:
        bands: List of band names (may use B## or common name format)

    Returns:
        List with all names translated to AWS Earth Search format
    """
    if not bands:
        return bands

    translated = []
    for band in bands:
        # Check exact match first, then case-insensitive
        aws_name = OPENEO_TO_AWS_BANDS.get(band)
        if aws_name is None:
            aws_name = OPENEO_TO_AWS_BANDS.get(band.upper())
        if aws_name is not None:
            logger.info(f"Band auto-translated: {band} -> {aws_name}")
            translated.append(aws_name)
        else:
            translated.append(band)

    return translated


# Configure odc.stac for cloud-optimized access (16x fewer HTTP requests)
try:
    odc.stac.configure_rio(cloud_defaults=True)
    logger.info("Configured odc.stac for cloud-optimized access")
except Exception as e:
    logger.warning(f"Could not configure odc.stac cloud defaults: {e}")

# Maximum number of STAC items to load (prevents huge queries)
MAX_STAC_ITEMS = int(os.environ.get("MAX_STAC_ITEMS", "5"))

# Get STAC API URL from environment
STAC_API_URL = os.environ.get(
    "STAC_API_URL",
    "https://earth-search.aws.element84.com/v1/"
)

# Collection ID to STAC URL mapping
# These map OpenEO collection IDs to their STAC collection URLs
COLLECTION_STAC_MAP = {
    # AWS Earth Search collections
    "sentinel-2-l2a": f"{STAC_API_URL}collections/sentinel-2-l2a",
    "sentinel-2-l1c": f"{STAC_API_URL}collections/sentinel-2-l1c",
    "sentinel-1-grd": f"{STAC_API_URL}collections/sentinel-1-grd",
    "landsat-c2-l2": f"{STAC_API_URL}collections/landsat-c2-l2",
    "cop-dem-glo-30": f"{STAC_API_URL}collections/cop-dem-glo-30",
    "cop-dem-glo-90": f"{STAC_API_URL}collections/cop-dem-glo-90",
    "naip": f"{STAC_API_URL}collections/naip",
    "sentinel-2-c1-l2a": f"{STAC_API_URL}collections/sentinel-2-c1-l2a",
    "landsat-c2-l1": f"{STAC_API_URL}collections/landsat-c2-l1",
}


def load_collection(
    id: str,
    spatial_extent: Optional[dict] = None,
    temporal_extent: Optional[list] = None,
    bands: Optional[list] = None,
    properties: Optional[dict] = None,
    named_parameters: Optional[dict] = None,  # Accept but ignore this parameter from graph executor
    **kwargs,
) -> xr.DataArray:
    """
    Load a collection by its ID.

    This implementation maps collection IDs to STAC URLs and uses
    the openeo-processes-dask load_stac function for actual data loading.

    Args:
        id: Collection identifier (e.g., "sentinel-2-l2a")
        spatial_extent: Bounding box dict with west, south, east, north, crs
        temporal_extent: List of [start, end] datetime strings
        bands: List of band names to load
        properties: Additional STAC query properties
        **kwargs: Additional arguments passed to load_stac

    Returns:
        xarray.DataArray with requested data (lazy Dask array)
    """
    from openeo_processes_dask.process_implementations.cubes.load import load_stac
    from openeo_pg_parser_networkx.pg_schema import BoundingBox, TemporalInterval

    # Auto-translate standard OpenEO band names (B02, B04, B08, etc.)
    # to AWS Earth Search names (blue, red, nir, etc.)
    bands = _translate_band_names(bands)

    logger.info(f"Loading collection: {id}")
    logger.info(f"  spatial_extent: {spatial_extent}")
    logger.info(f"  temporal_extent: {temporal_extent}")
    logger.info(f"  bands (after translation): {bands}")
    logger.info(f"  kwargs: {kwargs}")

    # Get STAC URL for collection
    stac_url = COLLECTION_STAC_MAP.get(id)

    if stac_url is None:
        # Try constructing URL from STAC_API_URL
        stac_url = f"{STAC_API_URL}collections/{id}"
        logger.warning(
            f"Collection '{id}' not in predefined map, "
            f"trying: {stac_url}"
        )

    # Convert spatial_extent to BoundingBox
    bbox = None
    if spatial_extent is not None:
        if isinstance(spatial_extent, dict):
            bbox = BoundingBox(
                west=spatial_extent.get("west"),
                south=spatial_extent.get("south"),
                east=spatial_extent.get("east"),
                north=spatial_extent.get("north"),
                crs=spatial_extent.get("crs", "EPSG:4326"),
            )
        elif isinstance(spatial_extent, BoundingBox):
            bbox = spatial_extent

    # Convert temporal_extent to list of timestamps
    # openeo-pg-parser-networkx passes this as a TemporalInterval object
    temporal = None
    if temporal_extent is not None:
        import pandas as pd

        try:
            # Extract datetime values from TemporalInterval
            # TemporalInterval has .start and .end properties that return DateTime/Date objects
            # Those objects have a __root__ attribute with the actual pendulum datetime
            if hasattr(temporal_extent, 'start') and hasattr(temporal_extent, 'end'):
                # TemporalInterval from openeo-pg-parser-networkx
                start_obj = temporal_extent.start
                end_obj = temporal_extent.end

                # Extract the actual datetime from the wrapper objects
                start_val = start_obj.__root__ if hasattr(start_obj, '__root__') else start_obj
                end_val = end_obj.__root__ if hasattr(end_obj, '__root__') else end_obj

                # Convert to pandas Timestamp
                if start_val is not None:
                    start = pd.to_datetime(str(start_val))
                else:
                    start = None
                if end_val is not None:
                    end = pd.to_datetime(str(end_val))
                else:
                    end = None

                if start is not None and end is not None:
                    temporal = [start, end]
                    logger.info(f"Parsed temporal extent: {temporal}")

            elif isinstance(temporal_extent, (list, tuple)) and len(temporal_extent) >= 2:
                # Direct list format
                start = pd.to_datetime(temporal_extent[0]) if temporal_extent[0] else None
                end = pd.to_datetime(temporal_extent[1]) if temporal_extent[1] else None
                if start is not None and end is not None:
                    temporal = [start, end]
                    logger.info(f"Parsed temporal extent: {temporal}")
            else:
                logger.warning(f"Unknown temporal_extent type: {type(temporal_extent)}")

        except Exception as e:
            logger.error(f"Failed to parse temporal_extent: {e}")

    # Load data via STAC with item limit
    try:
        # Use custom loading with item limit for better control
        data = _load_stac_limited(
            collection_url=stac_url,
            spatial_extent=bbox,
            temporal_extent=temporal,
            bands=bands,
            max_items=MAX_STAC_ITEMS,
        )

        logger.info(f"Successfully loaded collection {id}, shape: {data.shape}")
        return data

    except Exception as e:
        logger.error(f"Failed to load collection {id}: {e}")
        raise


def _load_stac_limited(
    collection_url: str,
    spatial_extent=None,
    temporal_extent=None,
    bands: Optional[List[str]] = None,
    max_items: int = 5,
) -> xr.DataArray:
    """
    Load STAC data with optimized chunking and band mapping.

    Features:
    - Collection-specific chunk sizes (2048x2048 for Sentinel-2)
    - Band name translation (OpenEO names -> STAC names)
    - Common name coordinate for NDVI band selection
    - Cloud-optimized S3 access configuration
    """
    # Parse collection URL to get catalog and collection ID
    # URL format: https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a
    parts = collection_url.rsplit("/collections/", 1)
    catalog_url = parts[0]
    collection_id = parts[1] if len(parts) > 1 else None

    logger.info(f"Searching STAC catalog: {catalog_url}")
    logger.info(f"Collection: {collection_id}, max_items: {max_items}")

    # Initialize band mapper for this collection
    mapper = BandMapper(collection_id) if collection_id else None

    # Open catalog with timeout protection
    stac_timeout = int(os.environ.get("STAC_TIMEOUT_SECONDS", "30"))
    try:
        # pystac_client expects int/float timeout, not httpx.Timeout
        catalog = pystac_client.Client.open(
            catalog_url,
            timeout=stac_timeout,
        )
    except Exception as e:
        from ..core.exceptions import STACQueryError
        raise STACQueryError(
            f"Failed to connect to STAC catalog: {e}",
            catalog_url=catalog_url,
            collection_id=collection_id,
        )

    # Build search parameters
    search_params = {"limit": max_items}

    if collection_id:
        search_params["collections"] = [collection_id]

    if spatial_extent is not None:
        bbox = [
            spatial_extent.west,
            spatial_extent.south,
            spatial_extent.east,
            spatial_extent.north,
        ]
        search_params["bbox"] = bbox
        logger.info(f"Bbox: {bbox}")

    logger.info(f"DEBUG: temporal_extent={temporal_extent}")
    if temporal_extent is not None:
        # Convert to ISO 8601 format for STAC API (must have T separator, not space)
        def to_iso(dt):
            if dt is None:
                return None
            if hasattr(dt, "isoformat"):
                return dt.isoformat()
            return str(dt).replace(" ", "T")

        start = to_iso(temporal_extent[0])
        end = to_iso(temporal_extent[1])
        if start and end:
            search_params["datetime"] = f"{start}/{end}"
            logger.info(f"Temporal: {start} to {end}")

    # Search for items with error handling
    logger.info(f"Starting STAC search with params: {search_params}")
    try:
        search = catalog.search(**search_params)
        logger.info("STAC search initiated, fetching items...")
        all_items = list(search.items())
        logger.info(f"STAC search complete, got {len(all_items)} items")
    except Exception as e:
        from ..core.exceptions import STACQueryError
        raise STACQueryError(
            f"STAC search failed: {e}",
            catalog_url=catalog_url,
            collection_id=collection_id,
        )

    # Slice to max_items (limit param is page size, not total limit)
    items = all_items[:max_items]

    logger.info(f"Found {len(all_items)} STAC items, using first {len(items)}")

    if len(items) == 0:
        from ..core.exceptions import DataSourceUnavailableError
        raise DataSourceUnavailableError(
            f"No STAC items found for query: {search_params}"
        )

    # Get optimized chunk configuration for this collection
    chunks = ChunkingStrategy.for_collection(collection_id or "default", len(items))

    # Configure S3 access for anonymous public data
    try:
        stac_cfg = odc.stac.configure_s3_access(
            aws_unsigned=True,
            cloud_defaults=True,
        )
    except Exception as e:
        logger.warning(f"Could not configure S3 access: {e}")
        stac_cfg = None

    # Build load parameters with optimized chunking
    load_params = {
        "chunks": chunks.to_dict(),
        "crs": "EPSG:4326",
        "resolution": 0.0001,  # ~10m at equator
        "groupby": "solar_day",  # Group by acquisition date
    }

    if stac_cfg:
        load_params["stac_cfg"] = stac_cfg

    if spatial_extent is not None:
        load_params["bbox"] = bbox

    # Map band names to STAC names if we have a mapper
    original_bands = bands
    if bands and mapper:
        bands = mapper.to_stac_names(bands)
        logger.info(f"Band mapping: {original_bands} -> {bands}")

    # Load data with odc.stac
    try:
        if bands:
            logger.info(f"Loading bands: {bands}")
            ds = odc.stac.load(items, bands=bands, **load_params)
        else:
            ds = odc.stac.load(items, **load_params)
    except ValueError as e:
        if "No such band/alias" in str(e):
            from ..core.exceptions import BandSelectionError
            raise BandSelectionError(
                f"Band mapping failed for {original_bands}: {e}"
            )
        raise

    # Convert to DataArray
    data = ds.to_dataarray(dim="bands")

    # CRITICAL: Apply scale factor to convert DN to reflectance (0-1)
    # Sentinel-2 L2A uses 0-10000 -> multiply by 0.0001 to get 0-1
    # This is essential for NDVI calculations to produce valid [-1, 1] results
    scale_factor = get_scale_factor(collection_id or "")
    offset = 0.0  # Sentinel-2 has no offset, Landsat does

    if scale_factor != 1.0:
        logger.info(f"Applying scale factor {scale_factor} for {collection_id}")
        data = data * scale_factor
        if offset != 0.0:
            data = data + offset

    # CRITICAL: Add common_name coordinate for NDVI band selection
    # This enables data.sel(common_name='nir') for vegetation indices
    if mapper and bands:
        common_names = mapper.get_common_names(bands)
        data = data.assign_coords(common_name=("bands", common_names))
        logger.info(f"Added common_name coordinate: {common_names}")

    logger.info(f"Loaded data shape: {data.shape}, dims: {data.dims}")
    logger.info(f"Chunking: {chunks.to_dict()}")

    return data


def register_collection(collection_id: str, stac_url: str):
    """
    Register a new collection mapping.

    Args:
        collection_id: The OpenEO collection ID
        stac_url: The STAC collection URL
    """
    COLLECTION_STAC_MAP[collection_id] = stac_url
    logger.info(f"Registered collection {collection_id} -> {stac_url}")


def get_available_collections() -> list:
    """
    Get list of available collection IDs.

    Returns:
        List of collection ID strings
    """
    return list(COLLECTION_STAC_MAP.keys())


def get_collection_stac_url(collection_id: str) -> Optional[str]:
    """
    Get the STAC URL for a collection.

    Args:
        collection_id: The collection ID

    Returns:
        The STAC URL or None if not found
    """
    return COLLECTION_STAC_MAP.get(collection_id)
