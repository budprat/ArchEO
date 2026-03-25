"""
Earth Observation Knowledge Base.

ABOUTME: Provides educational content about EO concepts, spectral indices,
satellite missions, and data processing best practices.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class ConceptCategory(Enum):
    """Categories of EO concepts."""
    SPECTRAL_INDICES = "spectral_indices"
    SATELLITE_MISSIONS = "satellite_missions"
    DATA_PROCESSING = "data_processing"
    LAND_COVER = "land_cover"
    ATMOSPHERIC = "atmospheric"
    TEMPORAL_ANALYSIS = "temporal_analysis"


@dataclass
class SpectralIndex:
    """Definition of a spectral index."""
    name: str
    abbreviation: str
    formula: str
    description: str
    bands_required: List[str]
    value_range: tuple = (-1.0, 1.0)
    applications: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)

    def get_openeo_formula(self, band_mapping: Dict[str, str] = None) -> str:
        """
        Get the formula for use in OpenEO process graphs.

        Args:
            band_mapping: Optional mapping from generic bands to collection-specific names

        Returns:
            Formula string with actual band names
        """
        formula = self.formula
        if band_mapping:
            for generic, specific in band_mapping.items():
                formula = formula.replace(generic, specific)
        return formula


@dataclass
class EOConcept:
    """Educational concept about Earth Observation."""
    id: str
    title: str
    category: ConceptCategory
    summary: str
    detailed_explanation: str
    examples: List[str] = field(default_factory=list)
    related_concepts: List[str] = field(default_factory=list)
    code_examples: Dict[str, str] = field(default_factory=dict)
    difficulty: str = "beginner"  # beginner, intermediate, advanced
    tags: List[str] = field(default_factory=list)


class KnowledgeBase:
    """
    Central repository of EO knowledge for educational purposes.

    Provides access to:
    - Spectral indices and their formulas
    - Satellite mission information
    - Data processing concepts
    - Best practices and common pitfalls
    """

    def __init__(self):
        """Initialize the knowledge base with default content."""
        self._indices = self._load_spectral_indices()
        self._concepts = self._load_concepts()
        self._band_mappings = self._load_band_mappings()

    def _load_spectral_indices(self) -> Dict[str, SpectralIndex]:
        """Load built-in spectral index definitions."""
        return {
            "ndvi": SpectralIndex(
                name="Normalized Difference Vegetation Index",
                abbreviation="NDVI",
                formula="(nir - red) / (nir + red)",
                description="Measures vegetation health and density. Higher values indicate healthier, denser vegetation.",
                bands_required=["red", "nir"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Vegetation monitoring",
                    "Crop health assessment",
                    "Drought detection",
                    "Deforestation monitoring",
                ],
                references=["Rouse et al., 1973"],
            ),
            "ndwi": SpectralIndex(
                name="Normalized Difference Water Index",
                abbreviation="NDWI",
                formula="(green - nir) / (green + nir)",
                description="Highlights water bodies and moisture content in vegetation.",
                bands_required=["green", "nir"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Water body detection",
                    "Flood mapping",
                    "Irrigation monitoring",
                ],
                references=["McFeeters, 1996"],
            ),
            "ndbi": SpectralIndex(
                name="Normalized Difference Built-up Index",
                abbreviation="NDBI",
                formula="(swir16 - nir) / (swir16 + nir)",
                description="Highlights urban and built-up areas.",
                bands_required=["swir16", "nir"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Urban mapping",
                    "Land use classification",
                    "Urban expansion monitoring",
                ],
                references=["Zha et al., 2003"],
            ),
            "evi": SpectralIndex(
                name="Enhanced Vegetation Index",
                abbreviation="EVI",
                formula="2.5 * ((nir - red) / (nir + 6 * red - 7.5 * blue + 1))",
                description="Improved vegetation index that corrects for atmospheric and soil background effects.",
                bands_required=["blue", "red", "nir"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Vegetation monitoring in high-biomass regions",
                    "Tropical forest monitoring",
                    "Agricultural applications",
                ],
                references=["Huete et al., 2002"],
            ),
            "savi": SpectralIndex(
                name="Soil-Adjusted Vegetation Index",
                abbreviation="SAVI",
                formula="((nir - red) / (nir + red + 0.5)) * 1.5",
                description="Vegetation index that minimizes soil brightness influences.",
                bands_required=["red", "nir"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Vegetation monitoring in sparse vegetation",
                    "Arid region analysis",
                ],
                references=["Huete, 1988"],
            ),
            "ndsi": SpectralIndex(
                name="Normalized Difference Snow Index",
                abbreviation="NDSI",
                formula="(green - swir16) / (green + swir16)",
                description="Distinguishes snow from clouds and other features.",
                bands_required=["green", "swir16"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Snow cover mapping",
                    "Glacier monitoring",
                    "Snow melt analysis",
                ],
                references=["Hall et al., 1995"],
            ),
            "nbr": SpectralIndex(
                name="Normalized Burn Ratio",
                abbreviation="NBR",
                formula="(nir - swir22) / (nir + swir22)",
                description="Identifies burned areas and assesses burn severity.",
                bands_required=["nir", "swir22"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Fire damage assessment",
                    "Burn severity mapping",
                    "Post-fire recovery monitoring",
                ],
                references=["Key & Benson, 2006"],
            ),
            "mndwi": SpectralIndex(
                name="Modified Normalized Difference Water Index",
                abbreviation="MNDWI",
                formula="(green - swir16) / (green + swir16)",
                description="Enhanced water body detection that suppresses built-up land noise.",
                bands_required=["green", "swir16"],
                value_range=(-1.0, 1.0),
                applications=[
                    "Water body extraction in urban areas",
                    "Wetland mapping",
                ],
                references=["Xu, 2006"],
            ),
        }

    def _load_concepts(self) -> Dict[str, EOConcept]:
        """Load built-in EO concepts."""
        return {
            "atmospheric_correction": EOConcept(
                id="atmospheric_correction",
                title="Atmospheric Correction",
                category=ConceptCategory.ATMOSPHERIC,
                summary="Process of removing atmospheric effects from satellite imagery to obtain surface reflectance.",
                detailed_explanation="""
Atmospheric correction converts top-of-atmosphere (TOA) radiance or reflectance
to surface reflectance by accounting for:

1. **Rayleigh scattering**: Scattering by air molecules
2. **Aerosol scattering**: Scattering by particles like dust and smoke
3. **Absorption**: By water vapor, ozone, and other gases

Sentinel-2 L2A products are already atmospherically corrected using Sen2Cor.
Landsat Collection 2 Level-2 products use LaSRC for atmospheric correction.

For most analysis, use Level-2 (surface reflectance) products when available.
                """,
                examples=[
                    "Sentinel-2 L2A vs L1C: L2A is atmospherically corrected",
                    "Landsat Collection 2 Level-2 provides surface reflectance",
                ],
                related_concepts=["surface_reflectance", "cloud_masking"],
                difficulty="intermediate",
                tags=["preprocessing", "calibration"],
            ),
            "cloud_masking": EOConcept(
                id="cloud_masking",
                title="Cloud Masking",
                category=ConceptCategory.DATA_PROCESSING,
                summary="Identifying and removing cloud-contaminated pixels from satellite imagery.",
                detailed_explanation="""
Cloud masking is essential for optical satellite imagery analysis. Clouds block
the view of the Earth's surface and must be identified and excluded.

**Sentinel-2 SCL Band Values:**
- 0: No data
- 1: Saturated or defective
- 2: Dark area pixels
- 3: Cloud shadows
- 4: Vegetation
- 5: Bare soils
- 6: Water
- 7: Unclassified
- 8: Cloud medium probability
- 9: Cloud high probability
- 10: Thin cirrus
- 11: Snow/ice

For clean analysis, mask pixels with SCL values 3, 8, 9, and 10.
                """,
                examples=[
                    "filter_bands(['scl']) then mask where scl not in [4,5,6]",
                ],
                related_concepts=["atmospheric_correction", "quality_flags"],
                code_examples={
                    "openeo": """
# Load with SCL band
cube = load_collection("sentinel-2-l2a", bands=["red", "nir", "scl"])

# Create cloud mask (keep vegetation, soil, water)
cloud_mask = (cube.band("scl") >= 4) & (cube.band("scl") <= 6)

# Apply mask
clean_cube = cube.mask(~cloud_mask)
"""
                },
                difficulty="beginner",
                tags=["preprocessing", "quality"],
            ),
            "temporal_compositing": EOConcept(
                id="temporal_compositing",
                title="Temporal Compositing",
                category=ConceptCategory.TEMPORAL_ANALYSIS,
                summary="Combining multiple images over time to create cloud-free or representative composites.",
                detailed_explanation="""
Temporal compositing reduces cloud contamination and noise by aggregating
multiple observations over a time period.

**Common Methods:**
1. **Median composite**: Robust to outliers, good for general use
2. **Maximum NDVI**: Best for vegetation peak detection
3. **Mean composite**: Sensitive to outliers but preserves signal
4. **Percentile**: Flexible control over outlier handling

**Typical Time Windows:**
- Weekly: High temporal resolution, may have cloud gaps
- Monthly: Good balance of coverage and temporal detail
- Seasonal: Best cloud-free coverage, loses temporal detail
                """,
                examples=[
                    "Monthly median NDVI for vegetation monitoring",
                    "Annual maximum NDVI for peak greenness mapping",
                ],
                related_concepts=["cloud_masking", "time_series_analysis"],
                difficulty="intermediate",
                tags=["temporal", "compositing"],
            ),
            "spatial_resolution": EOConcept(
                id="spatial_resolution",
                title="Spatial Resolution",
                category=ConceptCategory.SATELLITE_MISSIONS,
                summary="The size of the smallest feature that can be detected in an image.",
                detailed_explanation="""
Spatial resolution determines what you can see in satellite imagery.

**Common Resolutions:**
- **Sentinel-2**: 10m (RGB, NIR), 20m (red edge, SWIR), 60m (atmospheric)
- **Landsat 8/9**: 30m (multispectral), 15m (panchromatic), 100m (thermal)
- **MODIS**: 250m-1km depending on band
- **Copernicus DEM**: 30m or 90m

**Choosing Resolution:**
- Urban analysis: Need 10m or better
- Agricultural fields: 10-30m usually sufficient
- Regional vegetation: 30-250m acceptable
- Global studies: 1km+ often used

Higher resolution = more detail but more data and processing time.
                """,
                examples=[
                    "10m Sentinel-2 for field-level crop monitoring",
                    "30m Landsat for regional land cover change",
                ],
                related_concepts=["spectral_resolution", "temporal_resolution"],
                difficulty="beginner",
                tags=["fundamentals", "resolution"],
            ),
        }

    def _load_band_mappings(self) -> Dict[str, Dict[str, str]]:
        """Load band name mappings for different collections."""
        return {
            "sentinel-2-l2a": {
                "blue": "blue",
                "green": "green",
                "red": "red",
                "nir": "nir",
                "nir08": "nir08",
                "swir16": "swir16",
                "swir22": "swir22",
                "scl": "scl",
            },
            "landsat-c2-l2": {
                "blue": "blue",
                "green": "green",
                "red": "red",
                "nir": "nir08",
                "swir16": "swir16",
                "swir22": "swir22",
            },
        }

    def get_index(self, name: str) -> Optional[SpectralIndex]:
        """
        Get a spectral index by name or abbreviation.

        Args:
            name: Index name or abbreviation (case-insensitive)

        Returns:
            SpectralIndex or None if not found
        """
        name_lower = name.lower()
        if name_lower in self._indices:
            return self._indices[name_lower]

        # Search by abbreviation
        for idx in self._indices.values():
            if idx.abbreviation.lower() == name_lower:
                return idx

        return None

    def list_indices(self, category: str = None) -> List[SpectralIndex]:
        """
        List all spectral indices.

        Args:
            category: Optional filter by application category

        Returns:
            List of SpectralIndex objects
        """
        indices = list(self._indices.values())

        if category:
            indices = [
                idx for idx in indices
                if any(category.lower() in app.lower() for app in idx.applications)
            ]

        return indices

    def get_concept(self, concept_id: str) -> Optional[EOConcept]:
        """
        Get an EO concept by ID.

        Args:
            concept_id: Concept identifier

        Returns:
            EOConcept or None if not found
        """
        return self._concepts.get(concept_id)

    def list_concepts(
        self,
        category: ConceptCategory = None,
        difficulty: str = None
    ) -> List[EOConcept]:
        """
        List EO concepts with optional filtering.

        Args:
            category: Filter by category
            difficulty: Filter by difficulty level

        Returns:
            List of EOConcept objects
        """
        concepts = list(self._concepts.values())

        if category:
            concepts = [c for c in concepts if c.category == category]

        if difficulty:
            concepts = [c for c in concepts if c.difficulty == difficulty]

        return concepts

    def get_band_mapping(self, collection_id: str) -> Dict[str, str]:
        """
        Get band name mapping for a collection.

        Args:
            collection_id: Collection identifier

        Returns:
            Dictionary mapping generic band names to collection-specific names
        """
        return self._band_mappings.get(collection_id, {})

    def explain_index(self, index_name: str) -> str:
        """
        Get a human-readable explanation of a spectral index.

        Args:
            index_name: Name or abbreviation of the index

        Returns:
            Formatted explanation string
        """
        idx = self.get_index(index_name)
        if not idx:
            return f"Unknown index: {index_name}"

        explanation = f"""
**{idx.name} ({idx.abbreviation})**

{idx.description}

**Formula:** `{idx.formula}`

**Required Bands:** {', '.join(idx.bands_required)}

**Value Range:** {idx.value_range[0]} to {idx.value_range[1]}

**Applications:**
{chr(10).join(f'- {app}' for app in idx.applications)}
"""
        return explanation.strip()

    def search(self, query: str) -> Dict[str, Any]:
        """
        Search the knowledge base for relevant content.

        Args:
            query: Search query

        Returns:
            Dictionary with matching indices and concepts
        """
        query_lower = query.lower()
        results = {
            "indices": [],
            "concepts": [],
        }

        # Search indices
        for idx in self._indices.values():
            if (query_lower in idx.name.lower() or
                query_lower in idx.abbreviation.lower() or
                query_lower in idx.description.lower() or
                any(query_lower in app.lower() for app in idx.applications)):
                results["indices"].append(idx)

        # Search concepts
        for concept in self._concepts.values():
            if (query_lower in concept.title.lower() or
                query_lower in concept.summary.lower() or
                any(query_lower in tag.lower() for tag in concept.tags)):
                results["concepts"].append(concept)

        return results
