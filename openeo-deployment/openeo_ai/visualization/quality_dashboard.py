# ABOUTME: Quality metrics dashboard visualization component.
# Displays cloud coverage, temporal coverage, and data quality grades in the UI.

"""
Quality metrics dashboard for OpenEO AI Assistant.

Provides visual display of:
- Cloud coverage estimates
- Temporal coverage and gaps
- Overall quality grades
- Recommendations for improvement
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class QualityDashboard:
    """
    Create quality metrics dashboard visualizations.

    Generates MCP-UI compatible dashboard components for
    displaying data quality information.
    """

    def __init__(self):
        """Initialize quality dashboard."""
        # Color schemes for different quality grades
        self.grade_colors = {
            "A": "#4CAF50",  # Green
            "B": "#8BC34A",  # Light Green
            "C": "#FFC107",  # Amber
            "D": "#FF9800",  # Orange
            "F": "#F44336",  # Red
        }

        self.severity_colors = {
            "ok": "#4CAF50",
            "info": "#2196F3",
            "warning": "#FF9800",
            "error": "#F44336",
        }

    async def create_quality_dashboard(
        self,
        metrics: Dict[str, Any],
        title: str = "Data Quality Assessment"
    ) -> Dict[str, Any]:
        """
        Create a comprehensive quality dashboard.

        Args:
            metrics: Quality metrics from get_quality_metrics()
            title: Dashboard title

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating quality dashboard: {title}")

        quality_grade = metrics.get("quality_grade", "C")
        quality_score = metrics.get("overall_quality_score", 50)
        cloud_data = metrics.get("cloud_coverage", {})
        temporal_data = metrics.get("temporal_coverage", {})
        recommendations = metrics.get("recommendations", [])

        # Build dashboard sections
        sections = []

        # Overall quality score section
        sections.append(self._create_score_section(quality_grade, quality_score))

        # Cloud coverage section
        sections.append(self._create_cloud_section(cloud_data))

        # Temporal coverage section
        sections.append(self._create_temporal_section(temporal_data))

        # Recommendations section
        if recommendations:
            sections.append(self._create_recommendations_section(recommendations))

        return {
            "type": "quality_dashboard",
            "spec": {
                "title": title,
                "grade": quality_grade,
                "score": quality_score,
                "sections": sections,
                "color": self.grade_colors.get(quality_grade, "#9E9E9E")
            }
        }

    def _create_score_section(
        self,
        grade: str,
        score: float
    ) -> Dict[str, Any]:
        """Create the overall quality score section."""
        color = self.grade_colors.get(grade, "#9E9E9E")

        return {
            "type": "score",
            "title": "Overall Quality",
            "content": {
                "grade": grade,
                "score": round(score, 1),
                "description": self._get_grade_description(grade),
                "color": color
            }
        }

    def _create_cloud_section(
        self,
        cloud_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create the cloud coverage section."""
        cloud_pct = cloud_data.get("estimated_cloud_cover_pct", 0)
        usable_scenes = cloud_data.get("usable_scenes_estimate", 0)
        total_scenes = cloud_data.get("total_scenes_estimate", 0)
        confidence = cloud_data.get("confidence", "low")
        warnings = cloud_data.get("warnings", [])

        # Determine severity
        if cloud_pct > 70:
            severity = "error"
        elif cloud_pct > 50:
            severity = "warning"
        elif cloud_pct > 30:
            severity = "info"
        else:
            severity = "ok"

        return {
            "type": "metric",
            "title": "Cloud Coverage",
            "content": {
                "value": cloud_pct,
                "unit": "%",
                "severity": severity,
                "color": self.severity_colors.get(severity, "#9E9E9E"),
                "details": [
                    f"Confidence: {confidence}",
                    f"Usable scenes: ~{usable_scenes} of {total_scenes}",
                ],
                "warnings": warnings,
                "icon": "cloud"
            }
        }

    def _create_temporal_section(
        self,
        temporal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create the temporal coverage section."""
        coverage_pct = temporal_data.get("coverage_percentage", 0)
        requested_days = temporal_data.get("requested_days", 0)
        expected_acquisitions = temporal_data.get("expected_acquisitions", 0)
        expected_cloud_free = temporal_data.get("expected_cloud_free", 0)
        gaps_likely = temporal_data.get("gaps_likely", False)
        gap_warning = temporal_data.get("gap_warning")

        # Determine severity
        if coverage_pct < 30:
            severity = "error"
        elif coverage_pct < 50 or gaps_likely:
            severity = "warning"
        elif coverage_pct < 70:
            severity = "info"
        else:
            severity = "ok"

        details = [
            f"Requested period: {requested_days} days",
            f"Expected acquisitions: {expected_acquisitions}",
            f"Cloud-free expected: {expected_cloud_free}",
        ]

        warnings = []
        if gap_warning:
            warnings.append(gap_warning)

        return {
            "type": "metric",
            "title": "Temporal Coverage",
            "content": {
                "value": coverage_pct,
                "unit": "%",
                "severity": severity,
                "color": self.severity_colors.get(severity, "#9E9E9E"),
                "details": details,
                "warnings": warnings,
                "icon": "calendar"
            }
        }

    def _create_recommendations_section(
        self,
        recommendations: List[str]
    ) -> Dict[str, Any]:
        """Create the recommendations section."""
        return {
            "type": "recommendations",
            "title": "Recommendations",
            "content": {
                "items": [
                    {"text": rec, "icon": "lightbulb"}
                    for rec in recommendations
                ],
                "color": "#2196F3"
            }
        }

    def _get_grade_description(self, grade: str) -> str:
        """Get description for a quality grade."""
        descriptions = {
            "A": "Excellent data quality - low cloud cover, good temporal coverage",
            "B": "Good data quality - some cloud cover but usable",
            "C": "Moderate quality - consider cloud masking or extending time range",
            "D": "Poor quality - significant cloud cover or data gaps expected",
            "F": "Very poor quality - recommend different time period or location",
        }
        return descriptions.get(grade, "Unknown quality")

    async def create_simple_quality_badge(
        self,
        grade: str,
        score: float
    ) -> Dict[str, Any]:
        """
        Create a simple quality badge for inline display.

        Args:
            grade: Quality grade (A-F)
            score: Quality score (0-100)

        Returns:
            MCP-UI badge component
        """
        return {
            "type": "badge",
            "spec": {
                "text": f"Quality: {grade}",
                "score": round(score, 1),
                "color": self.grade_colors.get(grade, "#9E9E9E"),
                "tooltip": self._get_grade_description(grade)
            }
        }

    async def create_cloud_indicator(
        self,
        cloud_pct: float,
        usable_scenes: int,
        total_scenes: int
    ) -> Dict[str, Any]:
        """
        Create a cloud coverage indicator widget.

        Args:
            cloud_pct: Estimated cloud coverage percentage
            usable_scenes: Expected usable scenes
            total_scenes: Total expected scenes

        Returns:
            MCP-UI indicator component
        """
        # Determine severity
        if cloud_pct > 70:
            severity = "error"
            icon = "cloud-rain"
        elif cloud_pct > 50:
            severity = "warning"
            icon = "cloud"
        elif cloud_pct > 30:
            severity = "info"
            icon = "cloud-sun"
        else:
            severity = "ok"
            icon = "sun"

        return {
            "type": "indicator",
            "spec": {
                "label": "Cloud Cover",
                "value": f"{cloud_pct:.0f}%",
                "severity": severity,
                "color": self.severity_colors.get(severity, "#9E9E9E"),
                "icon": icon,
                "subtitle": f"~{usable_scenes}/{total_scenes} usable scenes"
            }
        }


def generate_quality_html(metrics: Dict[str, Any]) -> str:
    """
    Generate HTML for quality dashboard display.

    Args:
        metrics: Quality metrics from get_quality_metrics()

    Returns:
        HTML string for embedding in web interface
    """
    grade = metrics.get("quality_grade", "C")
    score = metrics.get("overall_quality_score", 50)
    cloud_data = metrics.get("cloud_coverage", {})
    temporal_data = metrics.get("temporal_coverage", {})
    recommendations = metrics.get("recommendations", [])

    # Grade colors
    grade_colors = {
        "A": "#4CAF50", "B": "#8BC34A", "C": "#FFC107",
        "D": "#FF9800", "F": "#F44336"
    }
    grade_color = grade_colors.get(grade, "#9E9E9E")

    # Cloud severity
    cloud_pct = cloud_data.get("estimated_cloud_cover_pct", 0)
    cloud_color = "#4CAF50" if cloud_pct < 30 else "#FF9800" if cloud_pct < 60 else "#F44336"

    # Temporal severity
    temporal_pct = temporal_data.get("coverage_percentage", 0)
    temporal_color = "#4CAF50" if temporal_pct > 70 else "#FF9800" if temporal_pct > 40 else "#F44336"

    html = f"""
    <div class="quality-dashboard" style="
        background: linear-gradient(135deg, #1e1e2e 0%, #2d2d3d 100%);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    ">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
            <h3 style="margin: 0; color: #fff;">Data Quality Assessment</h3>
            <div style="
                background: {grade_color};
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 18px;
            ">Grade: {grade} ({score:.0f}%)</div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <!-- Cloud Coverage -->
            <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 15px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                    <span style="font-size: 20px;">☁️</span>
                    <span style="color: #aaa; font-size: 14px;">Cloud Coverage</span>
                </div>
                <div style="font-size: 28px; font-weight: bold; color: {cloud_color};">
                    {cloud_pct:.0f}%
                </div>
                <div style="color: #888; font-size: 12px; margin-top: 5px;">
                    ~{cloud_data.get('usable_scenes_estimate', 0)}/{cloud_data.get('total_scenes_estimate', 0)} usable scenes
                </div>
            </div>

            <!-- Temporal Coverage -->
            <div style="background: rgba(255,255,255,0.05); border-radius: 8px; padding: 15px;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px;">
                    <span style="font-size: 20px;">📅</span>
                    <span style="color: #aaa; font-size: 14px;">Temporal Coverage</span>
                </div>
                <div style="font-size: 28px; font-weight: bold; color: {temporal_color};">
                    {temporal_pct:.0f}%
                </div>
                <div style="color: #888; font-size: 12px; margin-top: 5px;">
                    {temporal_data.get('expected_cloud_free', 0)} cloud-free scenes expected
                </div>
            </div>
        </div>
    """

    # Add recommendations if any
    if recommendations:
        html += """
        <div style="margin-top: 15px; padding: 15px; background: rgba(33, 150, 243, 0.1); border-radius: 8px; border-left: 3px solid #2196F3;">
            <div style="color: #2196F3; font-weight: bold; margin-bottom: 8px;">💡 Recommendations</div>
            <ul style="margin: 0; padding-left: 20px; color: #ccc;">
        """
        for rec in recommendations:
            html += f'<li style="margin: 4px 0;">{rec}</li>'
        html += """
            </ul>
        </div>
        """

    html += "</div>"
    return html
