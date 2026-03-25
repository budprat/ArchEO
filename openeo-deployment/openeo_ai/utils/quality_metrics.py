# ABOUTME: Quality metrics and uncertainty indicators for Earth Observation data.
# Provides cloud coverage estimation, temporal coverage analysis, and data completeness checks.

"""
Quality metrics and uncertainty indicators for OpenEO AI Assistant.

Provides metrics for:
- Cloud coverage percentage estimation
- Temporal coverage analysis (dates available vs requested)
- Valid pixel percentage
- Data completeness indicators
- Uncertainty quantification
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import math

logger = logging.getLogger(__name__)


# Collection-specific metadata
COLLECTION_METADATA = {
    "sentinel-2-l2a": {
        "typical_cloud_cover": 0.3,  # 30% average cloud cover globally
        "revisit_days": 5,
        "has_cloud_mask": True,
        "cloud_band": "scl",  # Scene Classification Layer
        "cloud_values": [8, 9, 10],  # Cloud medium, high, cirrus
        "resolution_m": 10,
        "bands_count": 13,
    },
    "sentinel-2-l1c": {
        "typical_cloud_cover": 0.35,
        "revisit_days": 5,
        "has_cloud_mask": True,
        "cloud_band": "qa60",
        "resolution_m": 10,
        "bands_count": 13,
    },
    "landsat-c2-l2": {
        "typical_cloud_cover": 0.35,
        "revisit_days": 16,
        "has_cloud_mask": True,
        "cloud_band": "qa_pixel",
        "resolution_m": 30,
        "bands_count": 7,
    },
    "sentinel-1-grd": {
        "typical_cloud_cover": 0.0,  # SAR - no cloud issues
        "revisit_days": 6,
        "has_cloud_mask": False,
        "resolution_m": 10,
        "bands_count": 2,
    },
    "cop-dem-glo-30": {
        "typical_cloud_cover": 0.0,  # Static dataset
        "revisit_days": None,  # Static
        "has_cloud_mask": False,
        "resolution_m": 30,
        "bands_count": 1,
    },
}

# Regional cloud cover adjustments (seasonal/geographic)
REGIONAL_CLOUD_FACTORS = {
    "tropical": 1.3,  # Higher cloud cover
    "monsoon": 1.5,  # Much higher during monsoon
    "arid": 0.5,  # Lower cloud cover
    "polar": 0.8,  # Lower but more persistent
    "temperate": 1.0,  # Baseline
}


@dataclass
class CloudCoverageEstimate:
    """Estimated cloud coverage for a query."""

    estimated_percentage: float
    confidence: str  # "high", "medium", "low"
    typical_for_collection: float
    regional_adjustment: float
    seasonal_adjustment: float
    usable_scenes_estimate: int
    total_scenes_estimate: int
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimated_cloud_cover_pct": round(self.estimated_percentage * 100, 1),
            "confidence": self.confidence,
            "typical_for_collection_pct": round(self.typical_for_collection * 100, 1),
            "regional_adjustment": round(self.regional_adjustment, 2),
            "seasonal_adjustment": round(self.seasonal_adjustment, 2),
            "usable_scenes_estimate": self.usable_scenes_estimate,
            "total_scenes_estimate": self.total_scenes_estimate,
            "warnings": self.warnings,
        }


@dataclass
class TemporalCoverageEstimate:
    """Estimated temporal coverage for a query."""

    requested_days: int
    expected_acquisitions: int
    expected_cloud_free: int
    coverage_percentage: float
    gaps_likely: bool
    gap_warning: Optional[str] = None
    acquisition_dates_estimate: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "requested_days": self.requested_days,
            "expected_acquisitions": self.expected_acquisitions,
            "expected_cloud_free": self.expected_cloud_free,
            "coverage_percentage": round(self.coverage_percentage * 100, 1),
            "gaps_likely": self.gaps_likely,
            "gap_warning": self.gap_warning,
        }


@dataclass
class DataQualityMetrics:
    """Comprehensive data quality metrics."""

    cloud_coverage: CloudCoverageEstimate
    temporal_coverage: TemporalCoverageEstimate
    spatial_completeness: float  # 0-1
    data_freshness: str  # "current", "recent", "historical"
    overall_quality_score: float  # 0-1
    quality_grade: str  # "A", "B", "C", "D", "F"
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cloud_coverage": self.cloud_coverage.to_dict(),
            "temporal_coverage": self.temporal_coverage.to_dict(),
            "spatial_completeness_pct": round(self.spatial_completeness * 100, 1),
            "data_freshness": self.data_freshness,
            "overall_quality_score": round(self.overall_quality_score * 100, 1),
            "quality_grade": self.quality_grade,
            "recommendations": self.recommendations,
        }


class QualityMetricsCalculator:
    """Calculates quality metrics for EO data queries."""

    def __init__(self):
        """Initialize quality metrics calculator."""
        self.collection_metadata = COLLECTION_METADATA
        self.regional_factors = REGIONAL_CLOUD_FACTORS

    def estimate_cloud_coverage(
        self,
        collection: str,
        spatial_extent: Dict[str, float],
        temporal_extent: Optional[List[str]] = None,
    ) -> CloudCoverageEstimate:
        """
        Estimate cloud coverage for a query.

        Args:
            collection: Collection ID
            spatial_extent: Bounding box
            temporal_extent: Date range [start, end]

        Returns:
            CloudCoverageEstimate
        """
        warnings = []

        # Get collection metadata
        meta = self.collection_metadata.get(collection, {})
        typical_cloud = meta.get("typical_cloud_cover", 0.3)
        revisit_days = meta.get("revisit_days", 10)

        # Regional adjustment based on latitude
        mid_lat = (spatial_extent["south"] + spatial_extent["north"]) / 2
        regional_adjustment = self._get_regional_factor(mid_lat)

        # Seasonal adjustment
        seasonal_adjustment = 1.0
        if temporal_extent and len(temporal_extent) >= 2:
            seasonal_adjustment = self._get_seasonal_factor(temporal_extent)

        # Calculate estimated cloud cover
        estimated_cloud = typical_cloud * regional_adjustment * seasonal_adjustment
        estimated_cloud = min(estimated_cloud, 0.95)  # Cap at 95%

        # Estimate number of scenes
        total_scenes = 1
        if temporal_extent and len(temporal_extent) >= 2 and revisit_days:
            try:
                start = datetime.fromisoformat(temporal_extent[0].replace("Z", ""))
                end = datetime.fromisoformat(temporal_extent[1].replace("Z", ""))
                days = (end - start).days
                total_scenes = max(1, days // revisit_days)
            except (ValueError, TypeError):
                pass

        usable_scenes = int(total_scenes * (1 - estimated_cloud))

        # Determine confidence
        if collection in self.collection_metadata:
            confidence = "medium"
        else:
            confidence = "low"
            warnings.append(f"Unknown collection '{collection}' - using default estimates")

        if estimated_cloud > 0.6:
            warnings.append("High cloud cover expected - consider cloud masking")

        if estimated_cloud > 0.8:
            warnings.append("Very high cloud cover - data quality may be poor")

        return CloudCoverageEstimate(
            estimated_percentage=estimated_cloud,
            confidence=confidence,
            typical_for_collection=typical_cloud,
            regional_adjustment=regional_adjustment,
            seasonal_adjustment=seasonal_adjustment,
            usable_scenes_estimate=usable_scenes,
            total_scenes_estimate=total_scenes,
            warnings=warnings,
        )

    def estimate_temporal_coverage(
        self,
        collection: str,
        temporal_extent: List[str],
        cloud_coverage: Optional[CloudCoverageEstimate] = None,
    ) -> TemporalCoverageEstimate:
        """
        Estimate temporal coverage for a query.

        Args:
            collection: Collection ID
            temporal_extent: Date range [start, end]
            cloud_coverage: Optional pre-calculated cloud estimate

        Returns:
            TemporalCoverageEstimate
        """
        meta = self.collection_metadata.get(collection, {})
        revisit_days = meta.get("revisit_days")

        # Parse dates
        try:
            start = datetime.fromisoformat(temporal_extent[0].replace("Z", ""))
            end = datetime.fromisoformat(temporal_extent[1].replace("Z", ""))
            requested_days = max(1, (end - start).days)
        except (ValueError, TypeError, IndexError):
            return TemporalCoverageEstimate(
                requested_days=0,
                expected_acquisitions=0,
                expected_cloud_free=0,
                coverage_percentage=0,
                gaps_likely=True,
                gap_warning="Invalid temporal extent",
            )

        # Static datasets
        if revisit_days is None:
            return TemporalCoverageEstimate(
                requested_days=requested_days,
                expected_acquisitions=1,
                expected_cloud_free=1,
                coverage_percentage=1.0,
                gaps_likely=False,
                gap_warning=None,
            )

        # Calculate expected acquisitions
        expected_acquisitions = max(1, requested_days // revisit_days)

        # Account for cloud cover
        cloud_factor = 1 - (cloud_coverage.estimated_percentage if cloud_coverage else 0.3)
        expected_cloud_free = int(expected_acquisitions * cloud_factor)

        # Calculate coverage
        coverage_pct = expected_cloud_free / max(1, requested_days / revisit_days)
        coverage_pct = min(coverage_pct, 1.0)

        # Determine if gaps are likely
        gaps_likely = coverage_pct < 0.7
        gap_warning = None

        if gaps_likely:
            if coverage_pct < 0.3:
                gap_warning = "Significant data gaps expected - consider extending temporal range"
            else:
                gap_warning = "Some data gaps may occur due to cloud cover"

        return TemporalCoverageEstimate(
            requested_days=requested_days,
            expected_acquisitions=expected_acquisitions,
            expected_cloud_free=expected_cloud_free,
            coverage_percentage=coverage_pct,
            gaps_likely=gaps_likely,
            gap_warning=gap_warning,
        )

    def calculate_quality_metrics(
        self,
        collection: str,
        spatial_extent: Dict[str, float],
        temporal_extent: Optional[List[str]] = None,
        bands: Optional[List[str]] = None,
    ) -> DataQualityMetrics:
        """
        Calculate comprehensive quality metrics.

        Args:
            collection: Collection ID
            spatial_extent: Bounding box
            temporal_extent: Date range
            bands: List of bands

        Returns:
            DataQualityMetrics
        """
        recommendations = []

        # Cloud coverage
        cloud_estimate = self.estimate_cloud_coverage(
            collection=collection,
            spatial_extent=spatial_extent,
            temporal_extent=temporal_extent,
        )

        # Temporal coverage
        if temporal_extent:
            temporal_estimate = self.estimate_temporal_coverage(
                collection=collection,
                temporal_extent=temporal_extent,
                cloud_coverage=cloud_estimate,
            )
        else:
            temporal_estimate = TemporalCoverageEstimate(
                requested_days=1,
                expected_acquisitions=1,
                expected_cloud_free=1,
                coverage_percentage=1.0,
                gaps_likely=False,
            )

        # Spatial completeness (assume good unless polar/edge cases)
        spatial_completeness = 1.0
        mid_lat = (spatial_extent["south"] + spatial_extent["north"]) / 2
        if abs(mid_lat) > 80:
            spatial_completeness = 0.7
            recommendations.append("Polar region may have limited coverage")

        # Data freshness
        data_freshness = "historical"
        if temporal_extent and len(temporal_extent) >= 2:
            try:
                end = datetime.fromisoformat(temporal_extent[1].replace("Z", ""))
                days_ago = (datetime.now() - end).days
                if days_ago < 7:
                    data_freshness = "current"
                elif days_ago < 30:
                    data_freshness = "recent"
            except (ValueError, TypeError):
                pass

        # Calculate overall quality score
        cloud_score = 1 - cloud_estimate.estimated_percentage
        temporal_score = temporal_estimate.coverage_percentage
        overall_score = (cloud_score * 0.4 + temporal_score * 0.4 + spatial_completeness * 0.2)

        # Grade
        if overall_score >= 0.9:
            quality_grade = "A"
        elif overall_score >= 0.75:
            quality_grade = "B"
        elif overall_score >= 0.6:
            quality_grade = "C"
        elif overall_score >= 0.4:
            quality_grade = "D"
        else:
            quality_grade = "F"

        # Recommendations
        if cloud_estimate.estimated_percentage > 0.5:
            recommendations.append("Consider using cloud masking (SCL band for Sentinel-2)")

        if temporal_estimate.gaps_likely:
            recommendations.append("Extend temporal range or use temporal aggregation")

        if data_freshness == "historical" and collection in ["sentinel-2-l2a", "landsat-c2-l2"]:
            recommendations.append("Check for more recent data availability")

        meta = self.collection_metadata.get(collection, {})
        if meta.get("has_cloud_mask") and cloud_estimate.estimated_percentage > 0.3:
            recommendations.append(f"Use {meta.get('cloud_band', 'cloud mask')} for filtering")

        return DataQualityMetrics(
            cloud_coverage=cloud_estimate,
            temporal_coverage=temporal_estimate,
            spatial_completeness=spatial_completeness,
            data_freshness=data_freshness,
            overall_quality_score=overall_score,
            quality_grade=quality_grade,
            recommendations=recommendations,
        )

    def _get_regional_factor(self, latitude: float) -> float:
        """Get cloud cover adjustment factor based on latitude."""
        abs_lat = abs(latitude)

        if abs_lat < 10:
            return 1.3  # Tropical - high clouds
        elif abs_lat < 25:
            return 1.1  # Subtropical
        elif abs_lat < 40:
            return 1.0  # Temperate
        elif abs_lat < 60:
            return 0.95  # Higher temperate
        else:
            return 0.85  # Polar - less cloud but more persistent

    def _get_seasonal_factor(self, temporal_extent: List[str]) -> float:
        """Get cloud cover adjustment factor based on season."""
        try:
            start = datetime.fromisoformat(temporal_extent[0].replace("Z", ""))
            end = datetime.fromisoformat(temporal_extent[1].replace("Z", ""))
            mid_date = start + (end - start) / 2
            month = mid_date.month

            # Northern hemisphere seasons (adjust for southern)
            if month in [6, 7, 8]:  # Summer
                return 0.85
            elif month in [12, 1, 2]:  # Winter
                return 1.15
            elif month in [3, 4, 5]:  # Spring
                return 1.1
            else:  # Fall
                return 1.0

        except (ValueError, TypeError):
            return 1.0


# Module-level calculator instance
_calculator: Optional[QualityMetricsCalculator] = None


def get_calculator() -> QualityMetricsCalculator:
    """Get or create quality metrics calculator."""
    global _calculator
    if _calculator is None:
        _calculator = QualityMetricsCalculator()
    return _calculator


def estimate_cloud_coverage(
    collection: str,
    spatial_extent: Dict[str, float],
    temporal_extent: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Estimate cloud coverage (convenience function).

    Returns dict suitable for JSON response.
    """
    calculator = get_calculator()
    estimate = calculator.estimate_cloud_coverage(
        collection=collection,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
    )
    return estimate.to_dict()


def estimate_temporal_coverage(
    collection: str,
    temporal_extent: List[str],
) -> Dict[str, Any]:
    """
    Estimate temporal coverage (convenience function).

    Returns dict suitable for JSON response.
    """
    calculator = get_calculator()
    estimate = calculator.estimate_temporal_coverage(
        collection=collection,
        temporal_extent=temporal_extent,
    )
    return estimate.to_dict()


def get_quality_metrics(
    collection: str,
    spatial_extent: Dict[str, float],
    temporal_extent: Optional[List[str]] = None,
    bands: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Get comprehensive quality metrics (convenience function).

    Returns dict suitable for JSON response.
    """
    calculator = get_calculator()
    metrics = calculator.calculate_quality_metrics(
        collection=collection,
        spatial_extent=spatial_extent,
        temporal_extent=temporal_extent,
        bands=bands,
    )
    return metrics.to_dict()
