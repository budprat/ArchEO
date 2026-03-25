"""Band name mapping for different satellite collections.

Maps between OpenEO common band names and collection-specific STAC band names.
This enables users to use common names like 'red', 'nir' across different
collections (Sentinel-2, Landsat, etc.) without knowing the specific band IDs.
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Sentinel-2 band mappings (STAC band ID -> common name)
SENTINEL2_TO_COMMON: Dict[str, str] = {
    # 10m bands
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B08": "nir",
    # 20m bands
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B8A": "nir08",
    "B11": "swir16",
    "B12": "swir22",
    # 60m bands
    "B01": "coastal",
    "B09": "nir09",
    # Classification layers
    "SCL": "scl",
    # Pass-through identity mappings (when user uses common names directly)
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir": "nir",
    "swir16": "swir16",
    "swir22": "swir22",
    "coastal": "coastal",
    "rededge1": "rededge1",
    "rededge2": "rededge2",
    "rededge3": "rededge3",
}

# Reverse mapping: common name -> Sentinel-2 band ID
COMMON_TO_SENTINEL2: Dict[str, str] = {
    "blue": "B02",
    "green": "B03",
    "red": "B04",
    "nir": "B08",
    "rededge1": "B05",
    "rededge2": "B06",
    "rededge3": "B07",
    "nir08": "B8A",
    "swir16": "B11",
    "swir22": "B12",
    "coastal": "B01",
    "nir09": "B09",
    "scl": "SCL",
}

# Landsat Collection 2 band mappings
LANDSAT_TO_COMMON: Dict[str, str] = {
    "SR_B1": "coastal",
    "SR_B2": "blue",
    "SR_B3": "green",
    "SR_B4": "red",
    "SR_B5": "nir",
    "SR_B6": "swir16",
    "SR_B7": "swir22",
    "QA_PIXEL": "qa",
    # Pass-through
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir": "nir",
}

# Reverse mapping: common name -> Landsat band ID
COMMON_TO_LANDSAT: Dict[str, str] = {
    "coastal": "SR_B1",
    "blue": "SR_B2",
    "green": "SR_B3",
    "red": "SR_B4",
    "nir": "SR_B5",
    "swir16": "SR_B6",
    "swir22": "SR_B7",
    "qa": "QA_PIXEL",
}

# MODIS band mappings
MODIS_TO_COMMON: Dict[str, str] = {
    "sur_refl_b01": "red",
    "sur_refl_b02": "nir",
    "sur_refl_b03": "blue",
    "sur_refl_b04": "green",
    "sur_refl_b06": "swir16",
    "sur_refl_b07": "swir22",
}

COMMON_TO_MODIS: Dict[str, str] = {
    "red": "sur_refl_b01",
    "nir": "sur_refl_b02",
    "blue": "sur_refl_b03",
    "green": "sur_refl_b04",
    "swir16": "sur_refl_b06",
    "swir22": "sur_refl_b07",
}

# AWS Earth Search band mappings - uses common names directly!
# https://earth-search.aws.element84.com/v1/ uses: red, green, blue, nir, etc.
AWS_EARTH_SEARCH_IDENTITY: Dict[str, str] = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir": "nir",
    "nir08": "nir08",
    "nir09": "nir09",
    "swir16": "swir16",
    "swir22": "swir22",
    "coastal": "coastal",
    "rededge1": "rededge1",
    "rededge2": "rededge2",
    "rededge3": "rededge3",
    "scl": "scl",
    # Also support B## notation (map to common names)
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B08": "nir",
    "B8A": "nir08",
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B11": "swir16",
    "B12": "swir22",
    "B01": "coastal",
    "B09": "nir09",
    "SCL": "scl",
}


class BandMapper:
    """Maps between OpenEO common band names and collection-specific names.

    Example usage:
        mapper = BandMapper("sentinel-2-l2a")
        stac_bands = mapper.to_stac_names(["red", "nir"])  # Returns ["red", "nir"] for AWS Earth Search
        common_names = mapper.get_common_names(["red", "nir"])  # Returns ["red", "nir"]

    Note: AWS Earth Search (earth-search.aws.element84.com) uses common band names directly
    (red, nir, etc.) instead of standard Sentinel-2 codes (B04, B08).
    """

    # Collection ID patterns to mapping tables
    COLLECTION_MAPPINGS = {
        "sentinel-2": (SENTINEL2_TO_COMMON, COMMON_TO_SENTINEL2),
        "sentinel2": (SENTINEL2_TO_COMMON, COMMON_TO_SENTINEL2),
        "landsat": (LANDSAT_TO_COMMON, COMMON_TO_LANDSAT),
        "modis": (MODIS_TO_COMMON, COMMON_TO_MODIS),
    }

    def __init__(self, collection_id: str):
        """Initialize mapper for a specific collection.

        Args:
            collection_id: Collection identifier (e.g., "sentinel-2-l2a", "landsat-c2-l2")
        """
        import os
        self.collection_id = collection_id.lower()
        self.use_aws_identity = self._is_aws_earth_search()
        self.to_common, self.from_common = self._get_mappings()
        logger.debug(f"BandMapper initialized for {collection_id}, aws_identity={self.use_aws_identity}")

    def _is_aws_earth_search(self) -> bool:
        """Check if using AWS Earth Search STAC catalog."""
        import os
        stac_url = os.environ.get("STAC_API_URL", "")
        return "earth-search.aws" in stac_url or "element84.com" in stac_url

    def _get_mappings(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Get the appropriate mapping tables for the collection."""
        # AWS Earth Search uses common names directly for Sentinel-2
        if self.use_aws_identity and ("sentinel-2" in self.collection_id or "sentinel2" in self.collection_id):
            logger.info(f"Using AWS Earth Search identity mapping for {self.collection_id}")
            return AWS_EARTH_SEARCH_IDENTITY, AWS_EARTH_SEARCH_IDENTITY

        for pattern, mappings in self.COLLECTION_MAPPINGS.items():
            if pattern in self.collection_id:
                return mappings

        # Default: identity mappings (pass-through)
        logger.warning(
            f"No band mapping found for collection '{self.collection_id}', "
            "using identity mapping"
        )
        return {}, {}

    def to_stac_names(self, bands: List[str]) -> List[str]:
        """Convert OpenEO common band names to STAC band names.

        Args:
            bands: List of band names (e.g., ["red", "nir"])

        Returns:
            List of STAC band names (e.g., ["B04", "B08"] for Sentinel-2)
        """
        if not bands:
            return bands

        result = []
        for band in bands:
            # Try to map from common name to collection-specific name
            if band in self.from_common:
                mapped = self.from_common[band]
                result.append(mapped)
                logger.debug(f"Mapped band '{band}' -> '{mapped}'")
            elif band.upper() in self.from_common:
                # Try uppercase
                mapped = self.from_common[band.upper()]
                result.append(mapped)
            else:
                # Pass through unchanged
                result.append(band)
                logger.debug(f"Band '{band}' passed through unchanged")

        logger.info(f"Band mapping: {bands} -> {result}")
        return result

    def get_common_names(self, stac_bands: List[str]) -> List[str]:
        """Get common names for STAC band names.

        This is used to add the 'common_name' coordinate to DataArrays,
        enabling band selection by common name (e.g., data.sel(common_name='nir')).

        Args:
            stac_bands: List of STAC band names (e.g., ["B04", "B08"])

        Returns:
            List of common names (e.g., ["red", "nir"])
        """
        if not stac_bands:
            return stac_bands

        result = []
        for band in stac_bands:
            # Try to map from STAC name to common name
            if band in self.to_common:
                result.append(self.to_common[band])
            elif band.upper() in self.to_common:
                result.append(self.to_common[band.upper()])
            else:
                # Use band name as-is if no mapping found
                result.append(band)

        logger.debug(f"Common names for {stac_bands}: {result}")
        return result

    def from_common_name(self, common_name: str) -> str:
        """Convert a single common name to collection-specific band ID.

        Args:
            common_name: Common band name (e.g., "nir")

        Returns:
            Collection-specific band ID (e.g., "B08" for Sentinel-2)
        """
        if common_name in self.from_common:
            return self.from_common[common_name]
        return common_name

    def get_ndvi_bands(self) -> Tuple[str, str]:
        """Get the correct band names for NDVI calculation.

        Returns:
            Tuple of (NIR band name, RED band name) for the collection
        """
        nir = self.from_common.get("nir", "nir")
        red = self.from_common.get("red", "red")
        logger.debug(f"NDVI bands for {self.collection_id}: NIR={nir}, RED={red}")
        return (nir, red)

    def get_ndwi_bands(self) -> Tuple[str, str]:
        """Get the correct band names for NDWI calculation.

        Returns:
            Tuple of (GREEN band name, NIR band name) for the collection
        """
        green = self.from_common.get("green", "green")
        nir = self.from_common.get("nir", "nir")
        return (green, nir)

    def get_ndsi_bands(self) -> Tuple[str, str]:
        """Get the correct band names for NDSI (snow index) calculation.

        Returns:
            Tuple of (GREEN band name, SWIR band name) for the collection
        """
        green = self.from_common.get("green", "green")
        swir = self.from_common.get("swir16", "swir16")
        return (green, swir)


def get_mapper_for_collection(collection_id: str) -> BandMapper:
    """Factory function to get a BandMapper for a collection.

    Args:
        collection_id: Collection identifier

    Returns:
        BandMapper instance configured for the collection
    """
    return BandMapper(collection_id)


def get_scale_factor(collection_id: str) -> float:
    """Get the reflectance scale factor for a collection.

    Satellite data is often stored as integers with a scale factor
    that converts to physical reflectance values (0-1).

    Args:
        collection_id: Collection identifier

    Returns:
        Scale factor (multiply DN by this to get reflectance)
    """
    collection_lower = collection_id.lower()

    if "sentinel-2" in collection_lower or "sentinel2" in collection_lower:
        return 0.0001  # Sentinel-2 L2A uses 0-10000 -> 0-1

    if "landsat" in collection_lower:
        return 0.0000275  # Landsat Collection 2 scale factor

    if "modis" in collection_lower:
        return 0.0001  # MODIS reflectance scale

    # Default: assume already in reflectance (0-1)
    return 1.0


def get_offset(collection_id: str) -> float:
    """Get the reflectance offset for a collection.

    Args:
        collection_id: Collection identifier

    Returns:
        Offset value (add this after scaling)
    """
    collection_lower = collection_id.lower()

    if "landsat" in collection_lower:
        return -0.2  # Landsat Collection 2 offset

    return 0.0
