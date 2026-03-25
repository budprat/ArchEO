"""
Visualization module for OpenEO AI Assistant.

ABOUTME: MCP-UI compatible visualization components for geospatial data.
Provides maps, charts, comparison views, and uncertainty quantification.
"""

from .maps import MapComponent
from .charts import ChartComponent
from .components import VisualizationEngine, get_visualization_engine
from .quality_dashboard import QualityDashboard, generate_quality_html
from .uncertainty import (
    UncertaintyQuantifier,
    UncertaintyMetrics,
    TemporalUncertainty,
    SpatialUncertainty,
    QualityGrade,
    get_uncertainty_quantifier,
    calculate_uncertainty,
    assess_quality,
)

__all__ = [
    "MapComponent",
    "ChartComponent",
    "VisualizationEngine",
    "get_visualization_engine",
    "QualityDashboard",
    "generate_quality_html",
    "UncertaintyQuantifier",
    "UncertaintyMetrics",
    "TemporalUncertainty",
    "SpatialUncertainty",
    "QualityGrade",
    "get_uncertainty_quantifier",
    "calculate_uncertainty",
    "assess_quality",
]
