# ABOUTME: MCP-UI compatible chart visualization components.
# Generates time series, bar charts, histograms, pie charts, and scatter plots.

"""
Chart visualization components for OpenEO AI Assistant.

Provides MCP-UI compatible chart components for displaying:
- Time series data
- Bar charts for statistics
- Histograms for distributions
"""

import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)


class ChartComponent:
    """
    Create MCP-UI compatible chart visualizations.

    Generates interactive chart components for time series,
    statistics, and distributions.
    """

    def __init__(self):
        """Initialize chart component."""
        pass

    async def create_time_series(
        self,
        values: List[float],
        dates: List[str],
        title: str = "Time Series",
        ylabel: str = "Value",
        series_name: str = "Data",
        color: str = "#4CAF50"
    ) -> Dict[str, Any]:
        """
        Create a time series line chart.

        Args:
            values: List of values
            dates: List of date strings (ISO format)
            title: Chart title
            ylabel: Y-axis label
            series_name: Name for the data series
            color: Line color

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating time series chart: {title}")

        # Validate array lengths match
        if len(values) != len(dates):
            raise ValueError(
                f"Values and dates must have same length: {len(values)} vs {len(dates)}"
            )

        # Parse and validate dates
        parsed_dates = [self._parse_date(d) for d in dates]

        # Calculate statistics
        stats = self._calculate_stats(values)

        return {
            "type": "chart",
            "spec": {
                "chart_type": "line",
                "title": title,
                "data": {
                    "x": parsed_dates,
                    "y": values,
                    "series_name": series_name
                },
                "xaxis": {
                    "type": "time",
                    "title": "Date"
                },
                "yaxis": {
                    "title": ylabel
                },
                "style": {
                    "color": color,
                    "fill": True
                },
                "statistics": stats
            }
        }

    async def create_multi_time_series(
        self,
        series: List[Dict[str, Any]],
        dates: List[str],
        title: str = "Time Series Comparison",
        ylabel: str = "Value"
    ) -> Dict[str, Any]:
        """
        Create a time series chart with multiple series.

        Args:
            series: List of {name, values, color} dicts
            dates: List of date strings (ISO format)
            title: Chart title
            ylabel: Y-axis label

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating multi-series time chart: {title}")

        parsed_dates = [self._parse_date(d) for d in dates]

        default_colors = [
            "#4CAF50", "#2196F3", "#FF9800", "#E91E63",
            "#9C27B0", "#00BCD4", "#FFC107", "#795548"
        ]

        datasets = []
        for i, s in enumerate(series):
            color = s.get("color", default_colors[i % len(default_colors)])
            datasets.append({
                "label": s.get("name", f"Series {i+1}"),
                "data": s["values"],
                "borderColor": color,
                "backgroundColor": self._alpha(color, 0.1),
                "fill": False,
                "tension": 0.1
            })

        return {
            "type": "chart",
            "spec": {
                "chart_type": "line",
                "title": title,
                "data": {
                    "x": parsed_dates,
                    "series": datasets
                },
                "xaxis": {
                    "type": "time",
                    "title": "Date"
                },
                "yaxis": {
                    "title": ylabel
                }
            }
        }

    async def create_bar_chart(
        self,
        categories: List[str],
        values: List[float],
        title: str = "Statistics",
        ylabel: str = "Value",
        color: str = "#2196F3",
        horizontal: bool = False
    ) -> Dict[str, Any]:
        """
        Create a bar chart for categorical data.

        Args:
            categories: Category labels
            values: Values for each category
            title: Chart title
            ylabel: Y-axis label
            color: Bar color
            horizontal: Whether to display horizontally

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating bar chart: {title}")

        return {
            "type": "chart",
            "spec": {
                "chart_type": "bar",
                "title": title,
                "data": {
                    "x": categories,
                    "y": values
                },
                "xaxis": {
                    "title": "Category"
                },
                "yaxis": {
                    "title": ylabel
                },
                "style": {
                    "color": color,
                    "horizontal": horizontal
                }
            }
        }

    async def create_histogram(
        self,
        values: List[float],
        bins: int = 20,
        title: str = "Distribution",
        xlabel: str = "Value",
        ylabel: str = "Frequency",
        color: str = "#9C27B0"
    ) -> Dict[str, Any]:
        """
        Create a histogram for value distribution.

        Args:
            values: Data values
            bins: Number of bins
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Bar color

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating histogram: {title}")

        # Calculate histogram
        import numpy as np

        counts, bin_edges = np.histogram(values, bins=bins)

        # Create bin labels
        bin_labels = [
            f"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}"
            for i in range(len(counts))
        ]

        return {
            "type": "chart",
            "spec": {
                "chart_type": "histogram",
                "title": title,
                "bins": bins,
                "data": {
                    "x": bin_labels,
                    "y": counts.tolist()
                },
                "xaxis": {
                    "title": xlabel
                },
                "yaxis": {
                    "title": ylabel
                },
                "style": {
                    "color": color
                },
                "statistics": self._calculate_stats(values)
            }
        }

    async def create_pie_chart(
        self,
        labels: List[str],
        values: List[float],
        title: str = "Distribution",
        colors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a pie chart for proportional data.

        Args:
            labels: Category labels
            values: Values for each category
            title: Chart title
            colors: Optional custom colors

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating pie chart: {title}")

        default_colors = [
            "#4CAF50", "#2196F3", "#FF9800", "#E91E63",
            "#9C27B0", "#00BCD4", "#FFC107", "#795548",
            "#607D8B", "#3F51B5"
        ]

        chart_colors = colors or [
            default_colors[i % len(default_colors)]
            for i in range(len(labels))
        ]

        return {
            "type": "chart",
            "spec": {
                "chart_type": "pie",
                "title": title,
                "data": {
                    "labels": labels,
                    "values": values
                },
                "style": {
                    "colors": chart_colors
                }
            }
        }

    async def create_scatter_plot(
        self,
        x_values: List[float],
        y_values: List[float],
        title: str = "Scatter Plot",
        xlabel: str = "X",
        ylabel: str = "Y",
        color: str = "#FF5722",
        show_regression: bool = False
    ) -> Dict[str, Any]:
        """
        Create a scatter plot.

        Args:
            x_values: X-axis values
            y_values: Y-axis values
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            color: Point color
            show_regression: Whether to show regression line

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating scatter plot: {title}")

        # Format data points
        data_points = [
            {"x": x, "y": y}
            for x, y in zip(x_values, y_values)
        ]

        datasets = [
            {
                "label": "Data",
                "data": data_points,
                "backgroundColor": color,
                "borderColor": self._darken(color, 0.2),
                "pointRadius": 4
            }
        ]

        # Add regression line if requested
        if show_regression:
            import numpy as np

            x_arr = np.array(x_values)
            y_arr = np.array(y_values)

            # Calculate linear regression
            slope, intercept = np.polyfit(x_arr, y_arr, 1)

            x_min, x_max = x_arr.min(), x_arr.max()
            regression_data = [
                {"x": float(x_min), "y": float(slope * x_min + intercept)},
                {"x": float(x_max), "y": float(slope * x_max + intercept)}
            ]

            datasets.append({
                "label": f"Regression (y = {slope:.2f}x + {intercept:.2f})",
                "data": regression_data,
                "type": "line",
                "borderColor": "#666666",
                "borderDash": [5, 5],
                "fill": False,
                "pointRadius": 0
            })

        return {
            "type": "chart",
            "spec": {
                "chart_type": "scatter",
                "title": title,
                "data": {
                    "x": x_values,
                    "y": y_values,
                    "regression": datasets[1] if show_regression and len(datasets) > 1 else None
                },
                "xaxis": {
                    "title": xlabel
                },
                "yaxis": {
                    "title": ylabel
                },
                "style": {
                    "color": color,
                    "show_regression": show_regression
                }
            }
        }

    async def create_stats_summary(
        self,
        data: Dict[str, float],
        title: str = "Statistics Summary"
    ) -> Dict[str, Any]:
        """
        Create a statistics summary card.

        Args:
            data: Dictionary of stat name -> value
            title: Summary title

        Returns:
            MCP-UI component specification
        """
        logger.info(f"Creating stats summary: {title}")

        items = [
            {"label": k, "value": self._format_value(v)}
            for k, v in data.items()
        ]

        return {
            "type": "stats",
            "spec": {
                "title": title,
                "items": items
            }
        }

    def _parse_date(self, date_str: str) -> str:
        """Parse and standardize date string."""
        try:
            # Try ISO format
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.isoformat()
        except ValueError:
            # Return as-is if parsing fails
            return date_str

    def _calculate_stats(self, values: List[float]) -> Dict[str, float]:
        """Calculate basic statistics."""
        import numpy as np

        arr = np.array(values)
        return {
            "min": float(np.nanmin(arr)),
            "max": float(np.nanmax(arr)),
            "mean": float(np.nanmean(arr)),
            "median": float(np.nanmedian(arr)),
            "std": float(np.nanstd(arr)),
            "count": int(len(arr))
        }

    def _alpha(self, hex_color: str, alpha: float) -> str:
        """Add alpha to hex color."""
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    def _darken(self, hex_color: str, factor: float) -> str:
        """Darken a hex color."""
        hex_color = hex_color.lstrip("#")
        r = max(0, int(int(hex_color[0:2], 16) * (1 - factor)))
        g = max(0, int(int(hex_color[2:4], 16) * (1 - factor)))
        b = max(0, int(int(hex_color[4:6], 16) * (1 - factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _format_value(self, value: Union[int, float]) -> str:
        """Format numeric value for display."""
        if isinstance(value, int):
            return f"{value:,}"
        elif abs(value) >= 1000:
            return f"{value:,.2f}"
        elif abs(value) >= 1:
            return f"{value:.2f}"
        else:
            return f"{value:.4f}"
