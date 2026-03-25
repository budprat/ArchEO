"""Tests for band name mapping."""

import os
import pytest
from unittest.mock import patch

from openeo_app.processes.band_mapper import (
    BandMapper,
    get_mapper_for_collection,
    get_scale_factor,
    get_offset,
    SENTINEL2_TO_COMMON,
    COMMON_TO_SENTINEL2,
    LANDSAT_TO_COMMON,
    COMMON_TO_LANDSAT,
)

# Use a non-AWS STAC URL to get standard Sentinel-2 band codes (B04, B08, etc.)
_NON_AWS_ENV = {"STAC_API_URL": "https://example.com/stac/v1"}
# Use the real AWS Earth Search URL to get identity mapping (red, nir, etc.)
_AWS_ENV = {"STAC_API_URL": "https://earth-search.aws.element84.com/v1/"}


class TestBandMapper:
    """Tests for BandMapper class."""

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_sentinel2_band_mapping_to_stac(self):
        """Test B04->red, B08->nir mapping for Sentinel-2 (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        # Common names to STAC names
        result = mapper.to_stac_names(["red", "nir"])

        assert result == ["B04", "B08"]

    def test_sentinel2_band_mapping_get_common(self):
        """Test getting common names from STAC band names."""
        mapper = BandMapper("sentinel-2-l2a")

        # STAC names to common names
        result = mapper.get_common_names(["B04", "B08", "B02", "B03"])

        assert result == ["red", "nir", "blue", "green"]

    def test_landsat_band_mapping(self):
        """Test SR_B4->red, SR_B5->nir mapping for Landsat."""
        mapper = BandMapper("landsat-c2-l2")

        # Common names to STAC names
        result = mapper.to_stac_names(["red", "nir"])

        assert result == ["SR_B4", "SR_B5"]

    def test_landsat_get_common_names(self):
        """Test getting common names from Landsat band names."""
        mapper = BandMapper("landsat-c2-l2")

        result = mapper.get_common_names(["SR_B4", "SR_B5"])

        assert result == ["red", "nir"]

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_get_ndvi_bands_sentinel2(self):
        """Test get_ndvi_bands returns correct pair for Sentinel-2 (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        nir, red = mapper.get_ndvi_bands()

        assert nir == "B08"
        assert red == "B04"

    def test_get_ndvi_bands_landsat(self):
        """Test get_ndvi_bands returns correct pair for Landsat."""
        mapper = BandMapper("landsat-c2-l2")

        nir, red = mapper.get_ndvi_bands()

        assert nir == "SR_B5"
        assert red == "SR_B4"

    def test_passthrough_unknown_bands(self):
        """Test that unknown band names pass through unchanged."""
        mapper = BandMapper("sentinel-2-l2a")

        result = mapper.to_stac_names(["unknown_band", "custom"])

        assert result == ["unknown_band", "custom"]

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_identity_mapping_for_common_names(self):
        """Test that common names map to STAC codes (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        # Using common names that are in the mapping
        result = mapper.to_stac_names(["red", "blue"])

        assert "B04" in result  # red -> B04
        assert "B02" in result  # blue -> B02

    def test_unknown_collection_uses_default(self):
        """Test that unknown collection uses identity mapping."""
        mapper = BandMapper("unknown-collection")

        # Should pass through unchanged
        result = mapper.to_stac_names(["band1", "band2"])

        assert result == ["band1", "band2"]

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_case_variations(self):
        """Test that collection ID matching is case-insensitive (non-AWS STAC)."""
        mapper1 = BandMapper("SENTINEL-2-L2A")
        mapper2 = BandMapper("Sentinel-2-L2A")
        mapper3 = BandMapper("sentinel-2-l2a")

        # All should produce same mapping
        result1 = mapper1.to_stac_names(["red"])
        result2 = mapper2.to_stac_names(["red"])
        result3 = mapper3.to_stac_names(["red"])

        assert result1 == result2 == result3 == ["B04"]

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_from_common_name_single(self):
        """Test converting single common name to STAC name (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        result = mapper.from_common_name("nir")

        assert result == "B08"

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_get_ndwi_bands(self):
        """Test get_ndwi_bands returns correct pair (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        green, nir = mapper.get_ndwi_bands()

        assert green == "B03"
        assert nir == "B08"

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_get_ndsi_bands(self):
        """Test get_ndsi_bands returns correct pair (non-AWS STAC)."""
        mapper = BandMapper("sentinel-2-l2a")

        green, swir = mapper.get_ndsi_bands()

        assert green == "B03"
        assert swir == "B11"


class TestScaleFactors:
    """Tests for scale factor functions."""

    def test_sentinel2_scale_factor(self):
        """Test Sentinel-2 scale factor is 0.0001."""
        scale = get_scale_factor("sentinel-2-l2a")
        assert scale == 0.0001

    def test_landsat_scale_factor(self):
        """Test Landsat scale factor."""
        scale = get_scale_factor("landsat-c2-l2")
        assert scale == 0.0000275

    def test_unknown_collection_scale(self):
        """Test unknown collection returns 1.0 (no scaling)."""
        scale = get_scale_factor("unknown-collection")
        assert scale == 1.0

    def test_sentinel2_offset(self):
        """Test Sentinel-2 offset is 0."""
        offset = get_offset("sentinel-2-l2a")
        assert offset == 0.0

    def test_landsat_offset(self):
        """Test Landsat offset."""
        offset = get_offset("landsat-c2-l2")
        assert offset == -0.2


class TestMappingDictionaries:
    """Tests for mapping dictionaries."""

    def test_sentinel2_mapping_complete(self):
        """Test Sentinel-2 mapping covers all main bands."""
        expected_stac = ["B02", "B03", "B04", "B08", "B11", "B12"]
        for band in expected_stac:
            assert band in SENTINEL2_TO_COMMON, f"{band} not in mapping"

    def test_common_to_sentinel2_reverse(self):
        """Test reverse mapping is consistent."""
        for common, stac in COMMON_TO_SENTINEL2.items():
            # Check that STAC name maps back to common
            assert SENTINEL2_TO_COMMON.get(stac) == common

    def test_landsat_mapping_complete(self):
        """Test Landsat mapping covers surface reflectance bands."""
        expected_stac = ["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6", "SR_B7"]
        for band in expected_stac:
            assert band in LANDSAT_TO_COMMON, f"{band} not in mapping"


class TestGetMapperForCollection:
    """Tests for factory function."""

    def test_returns_band_mapper(self):
        """Test factory returns BandMapper instance."""
        mapper = get_mapper_for_collection("sentinel-2-l2a")
        assert isinstance(mapper, BandMapper)

    @patch.dict(os.environ, _NON_AWS_ENV)
    def test_mapper_is_configured(self):
        """Test returned mapper is properly configured (non-AWS STAC)."""
        mapper = get_mapper_for_collection("sentinel-2-l2a")
        result = mapper.to_stac_names(["red"])
        assert result == ["B04"]


class TestAWSEarthSearchMapping:
    """Tests for AWS Earth Search identity mapping behavior."""

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_sentinel2_uses_identity_mapping(self):
        """AWS Earth Search should use common names directly for Sentinel-2."""
        mapper = BandMapper("sentinel-2-l2a")
        result = mapper.to_stac_names(["red", "nir"])
        assert result == ["red", "nir"]

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_ndvi_bands_use_common_names(self):
        """NDVI bands should be common names on AWS Earth Search."""
        mapper = BandMapper("sentinel-2-l2a")
        nir, red = mapper.get_ndvi_bands()
        assert nir == "nir"
        assert red == "red"

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_ndwi_bands_use_common_names(self):
        """NDWI bands should be common names on AWS Earth Search."""
        mapper = BandMapper("sentinel-2-l2a")
        green, nir = mapper.get_ndwi_bands()
        assert green == "green"
        assert nir == "nir"

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_from_common_name_identity(self):
        """from_common_name should return the same name on AWS Earth Search."""
        mapper = BandMapper("sentinel-2-l2a")
        assert mapper.from_common_name("nir") == "nir"
        assert mapper.from_common_name("red") == "red"

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_b_codes_map_to_common_names(self):
        """B## codes should map to common names on AWS Earth Search."""
        mapper = BandMapper("sentinel-2-l2a")
        result = mapper.get_common_names(["B04", "B08"])
        assert result == ["red", "nir"]

    @patch.dict(os.environ, _AWS_ENV)
    def test_aws_does_not_affect_landsat(self):
        """Landsat should still use standard mapping even on AWS."""
        mapper = BandMapper("landsat-c2-l2")
        result = mapper.to_stac_names(["red", "nir"])
        assert result == ["SR_B4", "SR_B5"]
