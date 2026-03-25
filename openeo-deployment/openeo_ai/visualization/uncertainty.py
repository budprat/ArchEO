# ABOUTME: Uncertainty quantification for Earth Observation data.
# Calculates statistical uncertainty metrics for data quality assessment.

"""
Uncertainty Quantification for OpenEO AI.

Provides:
- Per-pixel uncertainty from temporal stacks
- Aggregate regional metrics (mean, std, CI, CV)
- Outlier detection using IQR method
- Quality rating based on CV and completeness
"""

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Try to import numpy/scipy for advanced calculations
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not available; using basic calculations")

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


class QualityGrade(Enum):
    """Data quality grades."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    POOR = "poor"


@dataclass
class UncertaintyMetrics:
    """
    Uncertainty metrics for a dataset.

    Attributes:
        mean: Mean value
        std: Standard deviation
        variance: Variance
        cv: Coefficient of variation (std/mean)
        ci_95: 95% confidence interval (lower, upper)
        ci_99: 99% confidence interval (lower, upper)
        min_value: Minimum value
        max_value: Maximum value
        median: Median value
        n_samples: Number of samples/pixels
        n_valid: Number of valid (non-NaN) samples
        completeness: Fraction of valid samples
        outlier_count: Number of outliers detected
        outlier_fraction: Fraction of outliers
    """
    mean: float
    std: float
    variance: float
    cv: float
    ci_95: Tuple[float, float]
    ci_99: Tuple[float, float]
    min_value: float
    max_value: float
    median: float
    n_samples: int
    n_valid: int
    completeness: float
    outlier_count: int = 0
    outlier_fraction: float = 0.0

    @property
    def quality_grade(self) -> QualityGrade:
        """Determine quality grade based on CV and completeness."""
        if self.completeness < 0.5:
            return QualityGrade.POOR
        if self.cv > 0.5 or self.completeness < 0.7:
            return QualityGrade.LOW
        if self.cv > 0.3 or self.completeness < 0.9:
            return QualityGrade.MEDIUM
        return QualityGrade.HIGH

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mean": round(self.mean, 6),
            "std": round(self.std, 6),
            "variance": round(self.variance, 6),
            "cv": round(self.cv, 4),
            "ci_95": [round(self.ci_95[0], 6), round(self.ci_95[1], 6)],
            "ci_99": [round(self.ci_99[0], 6), round(self.ci_99[1], 6)],
            "min": round(self.min_value, 6),
            "max": round(self.max_value, 6),
            "median": round(self.median, 6),
            "n_samples": self.n_samples,
            "n_valid": self.n_valid,
            "completeness": round(self.completeness, 4),
            "outlier_count": self.outlier_count,
            "outlier_fraction": round(self.outlier_fraction, 4),
            "quality_grade": self.quality_grade.value,
        }


@dataclass
class TemporalUncertainty:
    """Uncertainty metrics for temporal data."""
    per_timestamp: List[UncertaintyMetrics]
    aggregate: UncertaintyMetrics
    temporal_variability: float  # CV over time
    trend_slope: Optional[float] = None
    seasonality_strength: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "per_timestamp": [m.to_dict() for m in self.per_timestamp],
            "aggregate": self.aggregate.to_dict(),
            "temporal_variability": round(self.temporal_variability, 4),
            "trend_slope": round(self.trend_slope, 6) if self.trend_slope else None,
            "seasonality_strength": round(self.seasonality_strength, 4) if self.seasonality_strength else None,
        }


@dataclass
class SpatialUncertainty:
    """Uncertainty metrics for spatial data."""
    per_region: Dict[str, UncertaintyMetrics]
    global_metrics: UncertaintyMetrics
    spatial_heterogeneity: float  # Measure of spatial variability

    def to_dict(self) -> Dict[str, Any]:
        return {
            "per_region": {k: v.to_dict() for k, v in self.per_region.items()},
            "global": self.global_metrics.to_dict(),
            "spatial_heterogeneity": round(self.spatial_heterogeneity, 4),
        }


class UncertaintyQuantifier:
    """
    Calculate uncertainty metrics for Earth Observation data.

    Usage:
        quantifier = UncertaintyQuantifier()

        # From array
        metrics = quantifier.calculate(data_array)

        # From temporal stack
        temporal = quantifier.calculate_temporal(time_series)

        # Detect outliers
        outliers = quantifier.detect_outliers(data_array)
    """

    def __init__(self, confidence_levels: List[float] = None):
        """
        Initialize the quantifier.

        Args:
            confidence_levels: Confidence levels for intervals (default: [0.95, 0.99])
        """
        self.confidence_levels = confidence_levels or [0.95, 0.99]

    def calculate(
        self,
        data: Union[List, "np.ndarray", Any],
        detect_outliers: bool = True
    ) -> UncertaintyMetrics:
        """
        Calculate uncertainty metrics for a dataset.

        Args:
            data: Input data (list, numpy array, or xarray)
            detect_outliers: Whether to detect outliers

        Returns:
            UncertaintyMetrics object
        """
        # Convert to list if needed
        if HAS_NUMPY and hasattr(data, 'values'):
            # xarray DataArray
            values = data.values.flatten()
        elif HAS_NUMPY and isinstance(data, np.ndarray):
            values = data.flatten()
        else:
            values = list(data) if not isinstance(data, list) else data

        # Calculate basic statistics
        if HAS_NUMPY:
            values = np.array(values)
            valid_mask = ~np.isnan(values) & ~np.isinf(values)
            valid_values = values[valid_mask]

            n_samples = len(values)
            n_valid = len(valid_values)

            if n_valid == 0:
                return self._empty_metrics(n_samples)

            mean = np.nanmean(valid_values)
            std = np.nanstd(valid_values, ddof=1) if n_valid > 1 else 0.0
            variance = std ** 2
            median = np.nanmedian(valid_values)
            min_val = np.nanmin(valid_values)
            max_val = np.nanmax(valid_values)

        else:
            # Pure Python fallback
            valid_values = [v for v in values if v is not None and not math.isnan(v) and not math.isinf(v)]
            n_samples = len(values)
            n_valid = len(valid_values)

            if n_valid == 0:
                return self._empty_metrics(n_samples)

            mean = sum(valid_values) / n_valid
            variance = sum((x - mean) ** 2 for x in valid_values) / (n_valid - 1) if n_valid > 1 else 0.0
            std = math.sqrt(variance)
            sorted_vals = sorted(valid_values)
            median = sorted_vals[n_valid // 2] if n_valid % 2 == 1 else (sorted_vals[n_valid // 2 - 1] + sorted_vals[n_valid // 2]) / 2
            min_val = min(valid_values)
            max_val = max(valid_values)

        # Coefficient of variation
        cv = std / abs(mean) if mean != 0 else 0.0

        # Confidence intervals
        ci_95 = self._confidence_interval(mean, std, n_valid, 0.95)
        ci_99 = self._confidence_interval(mean, std, n_valid, 0.99)

        # Outlier detection
        outlier_count = 0
        outlier_fraction = 0.0
        if detect_outliers and n_valid > 4:
            outliers = self.detect_outliers_iqr(valid_values)
            outlier_count = len(outliers)
            outlier_fraction = outlier_count / n_valid

        return UncertaintyMetrics(
            mean=float(mean),
            std=float(std),
            variance=float(variance),
            cv=float(cv),
            ci_95=ci_95,
            ci_99=ci_99,
            min_value=float(min_val),
            max_value=float(max_val),
            median=float(median),
            n_samples=n_samples,
            n_valid=n_valid,
            completeness=n_valid / n_samples if n_samples > 0 else 0.0,
            outlier_count=outlier_count,
            outlier_fraction=outlier_fraction,
        )

    def calculate_temporal(
        self,
        time_series: List[Union[List, "np.ndarray"]],
        timestamps: List[str] = None
    ) -> TemporalUncertainty:
        """
        Calculate uncertainty metrics for temporal data.

        Args:
            time_series: List of data arrays per timestamp
            timestamps: Optional timestamp labels

        Returns:
            TemporalUncertainty object
        """
        per_timestamp = []
        all_means = []

        for data in time_series:
            metrics = self.calculate(data)
            per_timestamp.append(metrics)
            all_means.append(metrics.mean)

        # Aggregate metrics
        if HAS_NUMPY:
            all_data = np.concatenate([np.array(d).flatten() for d in time_series])
        else:
            all_data = []
            for d in time_series:
                all_data.extend(list(d) if not isinstance(d, list) else d)

        aggregate = self.calculate(all_data)

        # Temporal variability
        if len(all_means) > 1:
            mean_of_means = sum(all_means) / len(all_means)
            std_of_means = math.sqrt(sum((m - mean_of_means) ** 2 for m in all_means) / (len(all_means) - 1))
            temporal_variability = std_of_means / abs(mean_of_means) if mean_of_means != 0 else 0.0
        else:
            temporal_variability = 0.0

        # Trend analysis
        trend_slope = None
        if len(all_means) >= 3:
            trend_slope = self._calculate_trend(all_means)

        return TemporalUncertainty(
            per_timestamp=per_timestamp,
            aggregate=aggregate,
            temporal_variability=temporal_variability,
            trend_slope=trend_slope,
        )

    def detect_outliers_iqr(
        self,
        data: Union[List, "np.ndarray"],
        k: float = 1.5
    ) -> List[int]:
        """
        Detect outliers using IQR method.

        Args:
            data: Input data
            k: IQR multiplier (default 1.5 for mild outliers, 3.0 for extreme)

        Returns:
            List of outlier indices
        """
        if HAS_NUMPY:
            values = np.array(data).flatten()
            valid_mask = ~np.isnan(values) & ~np.isinf(values)
            valid_values = values[valid_mask]

            if len(valid_values) < 4:
                return []

            q1 = np.percentile(valid_values, 25)
            q3 = np.percentile(valid_values, 75)
            iqr = q3 - q1

            lower_bound = q1 - k * iqr
            upper_bound = q3 + k * iqr

            outlier_mask = (values < lower_bound) | (values > upper_bound)
            return list(np.where(outlier_mask & valid_mask)[0])

        else:
            # Pure Python fallback
            valid_pairs = [(i, v) for i, v in enumerate(data) if v is not None and not math.isnan(v)]
            if len(valid_pairs) < 4:
                return []

            sorted_vals = sorted([p[1] for p in valid_pairs])
            n = len(sorted_vals)
            q1 = sorted_vals[n // 4]
            q3 = sorted_vals[3 * n // 4]
            iqr = q3 - q1

            lower_bound = q1 - k * iqr
            upper_bound = q3 + k * iqr

            return [i for i, v in valid_pairs if v < lower_bound or v > upper_bound]

    def _confidence_interval(
        self,
        mean: float,
        std: float,
        n: int,
        confidence: float
    ) -> Tuple[float, float]:
        """Calculate confidence interval."""
        if n < 2:
            return (mean, mean)

        if HAS_SCIPY:
            # Use t-distribution for small samples
            t_value = stats.t.ppf((1 + confidence) / 2, n - 1)
        else:
            # Approximate z-values
            z_values = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
            t_value = z_values.get(confidence, 1.96)

        margin = t_value * std / math.sqrt(n)
        return (mean - margin, mean + margin)

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend slope using least squares."""
        n = len(values)
        if n < 2:
            return 0.0

        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n

        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        return numerator / denominator if denominator != 0 else 0.0

    def _empty_metrics(self, n_samples: int) -> UncertaintyMetrics:
        """Return empty metrics for invalid data."""
        return UncertaintyMetrics(
            mean=0.0,
            std=0.0,
            variance=0.0,
            cv=0.0,
            ci_95=(0.0, 0.0),
            ci_99=(0.0, 0.0),
            min_value=0.0,
            max_value=0.0,
            median=0.0,
            n_samples=n_samples,
            n_valid=0,
            completeness=0.0,
        )


# Module-level singleton
_quantifier: Optional[UncertaintyQuantifier] = None


def get_uncertainty_quantifier() -> UncertaintyQuantifier:
    """Get the global uncertainty quantifier singleton."""
    global _quantifier
    if _quantifier is None:
        _quantifier = UncertaintyQuantifier()
    return _quantifier


def calculate_uncertainty(data: Any, detect_outliers: bool = True) -> UncertaintyMetrics:
    """
    Convenience function to calculate uncertainty metrics.

    Args:
        data: Input data
        detect_outliers: Whether to detect outliers

    Returns:
        UncertaintyMetrics object
    """
    return get_uncertainty_quantifier().calculate(data, detect_outliers)


def assess_quality(data: Any) -> Dict[str, Any]:
    """
    Assess data quality and return summary.

    Args:
        data: Input data

    Returns:
        Quality assessment dictionary
    """
    metrics = calculate_uncertainty(data)

    return {
        "grade": metrics.quality_grade.value,
        "completeness_pct": round(metrics.completeness * 100, 1),
        "cv_pct": round(metrics.cv * 100, 1),
        "outlier_pct": round(metrics.outlier_fraction * 100, 1),
        "recommendation": _get_quality_recommendation(metrics),
        "metrics": metrics.to_dict(),
    }


def _get_quality_recommendation(metrics: UncertaintyMetrics) -> str:
    """Get recommendation based on quality metrics."""
    if metrics.quality_grade == QualityGrade.HIGH:
        return "Data quality is excellent. Proceed with analysis."

    recommendations = []

    if metrics.completeness < 0.9:
        recommendations.append("Consider extending temporal range to improve data completeness.")

    if metrics.cv > 0.3:
        recommendations.append("High variability detected. Apply temporal compositing (median) to reduce noise.")

    if metrics.outlier_fraction > 0.05:
        recommendations.append("Significant outliers detected. Consider cloud masking or outlier removal.")

    if not recommendations:
        return "Data quality is acceptable."

    return " ".join(recommendations)
