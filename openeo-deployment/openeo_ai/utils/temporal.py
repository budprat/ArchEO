# ABOUTME: Temporal expression parser for natural language date/time references.
# Handles relative dates, seasons, and regional calendar terms.

"""
Temporal parsing utilities for OpenEO AI Assistant.

Converts natural language temporal expressions to ISO date ranges
suitable for Earth Observation data queries.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dateutil.relativedelta import relativedelta

try:
    import dateparser
    DATEPARSER_AVAILABLE = True
except ImportError:
    DATEPARSER_AVAILABLE = False
    logging.warning("dateparser not available, using basic parsing")

logger = logging.getLogger(__name__)


@dataclass
class TemporalResult:
    """Result of temporal expression parsing."""

    success: bool
    start_date: Optional[str] = None  # ISO format YYYY-MM-DD
    end_date: Optional[str] = None    # ISO format YYYY-MM-DD
    expression: str = ""
    interpretation: str = ""
    confidence: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "expression": self.expression,
            "interpretation": self.interpretation,
            "confidence": self.confidence,
        }
        if self.start_date and self.end_date:
            result["temporal_extent"] = [self.start_date, self.end_date]
            result["start_date"] = self.start_date
            result["end_date"] = self.end_date
        if self.error:
            result["error"] = self.error
        return result


# Season definitions (Northern Hemisphere default)
SEASONS_NH = {
    "spring": (3, 1, 5, 31),   # March 1 - May 31
    "summer": (6, 1, 8, 31),   # June 1 - August 31
    "autumn": (9, 1, 11, 30),  # September 1 - November 30
    "fall": (9, 1, 11, 30),    # Alias for autumn
    "winter": (12, 1, 2, 28),  # December 1 - February 28/29 (crosses year)
}

# Regional seasons
REGIONAL_SEASONS = {
    # Indian subcontinent
    "monsoon": (6, 1, 9, 30),           # June - September
    "pre-monsoon": (3, 1, 5, 31),       # March - May
    "post-monsoon": (10, 1, 11, 30),    # October - November
    "winter season": (12, 1, 2, 28),    # December - February
    "rabi": (10, 15, 3, 15),            # Rabi crop season (Oct-Mar)
    "kharif": (6, 1, 10, 15),           # Kharif crop season (Jun-Oct)

    # Agricultural
    "growing season": (4, 1, 9, 30),    # General growing season
    "harvest": (9, 1, 11, 30),          # General harvest
    "planting": (3, 1, 5, 31),          # General planting

    # Dry/wet
    "dry season": (11, 1, 4, 30),       # General dry season (varies by region)
    "wet season": (5, 1, 10, 31),       # General wet season
    "rainy season": (6, 1, 9, 30),      # Alias for monsoon
}


class TemporalParser:
    """Parser for natural language temporal expressions."""

    def __init__(self, reference_date: Optional[datetime] = None):
        """
        Initialize temporal parser.

        Args:
            reference_date: Reference date for relative expressions (default: now)
        """
        self.reference_date = reference_date or datetime.now()

    def parse(self, expression: str) -> TemporalResult:
        """
        Parse a temporal expression to date range.

        Args:
            expression: Natural language temporal expression

        Returns:
            TemporalResult with date range or error
        """
        expression = expression.strip()
        original = expression

        # Try specific patterns first
        result = self._try_explicit_range(expression)
        if result:
            return result

        result = self._try_year_only(expression)
        if result:
            return result

        result = self._try_season(expression)
        if result:
            return result

        result = self._try_relative(expression)
        if result:
            return result

        result = self._try_month_year(expression)
        if result:
            return result

        # Try dateparser as fallback
        if DATEPARSER_AVAILABLE:
            result = self._try_dateparser(expression)
            if result:
                return result

        return TemporalResult(
            success=False,
            expression=original,
            error=f"Could not parse temporal expression: '{expression}'",
        )

    def _try_explicit_range(self, expr: str) -> Optional[TemporalResult]:
        """Try to parse explicit date range like '2020-01-01 to 2020-12-31'."""
        # Pattern: YYYY-MM-DD to/- YYYY-MM-DD
        pattern = r'(\d{4}-\d{2}-\d{2})\s*(?:to|-|through|until)\s*(\d{4}-\d{2}-\d{2})'
        match = re.search(pattern, expr, re.IGNORECASE)
        if match:
            start, end = match.groups()
            return TemporalResult(
                success=True,
                start_date=start,
                end_date=end,
                expression=expr,
                interpretation=f"From {start} to {end}",
                confidence=1.0,
            )

        # Pattern: YYYY/MM/DD format
        pattern = r'(\d{4}/\d{2}/\d{2})\s*(?:to|-|through)\s*(\d{4}/\d{2}/\d{2})'
        match = re.search(pattern, expr, re.IGNORECASE)
        if match:
            start = match.group(1).replace('/', '-')
            end = match.group(2).replace('/', '-')
            return TemporalResult(
                success=True,
                start_date=start,
                end_date=end,
                expression=expr,
                interpretation=f"From {start} to {end}",
                confidence=1.0,
            )

        return None

    def _try_year_only(self, expr: str) -> Optional[TemporalResult]:
        """Try to parse year-only expressions like '2023' or '2020-2023'."""
        # Range of years
        pattern = r'^(\d{4})\s*[-–to]+\s*(\d{4})$'
        match = re.match(pattern, expr.strip())
        if match:
            start_year, end_year = int(match.group(1)), int(match.group(2))
            return TemporalResult(
                success=True,
                start_date=f"{start_year}-01-01",
                end_date=f"{end_year}-12-31",
                expression=expr,
                interpretation=f"Full years {start_year} to {end_year}",
                confidence=0.95,
            )

        # Single year
        pattern = r'^(\d{4})$'
        match = re.match(pattern, expr.strip())
        if match:
            year = int(match.group(1))
            return TemporalResult(
                success=True,
                start_date=f"{year}-01-01",
                end_date=f"{year}-12-31",
                expression=expr,
                interpretation=f"Full year {year}",
                confidence=0.95,
            )

        return None

    def _try_season(self, expr: str) -> Optional[TemporalResult]:
        """Try to parse seasonal expressions."""
        expr_lower = expr.lower()

        # Check for year in expression
        year_match = re.search(r'(\d{4})', expr)
        year = int(year_match.group(1)) if year_match else self.reference_date.year

        # Check regional seasons first (more specific)
        for season_name, (sm, sd, em, ed) in REGIONAL_SEASONS.items():
            if season_name in expr_lower:
                start_date, end_date = self._season_to_dates(year, sm, sd, em, ed)
                return TemporalResult(
                    success=True,
                    start_date=start_date,
                    end_date=end_date,
                    expression=expr,
                    interpretation=f"{season_name.title()} {year}",
                    confidence=0.9,
                )

        # Check standard seasons
        for season_name, (sm, sd, em, ed) in SEASONS_NH.items():
            if season_name in expr_lower:
                start_date, end_date = self._season_to_dates(year, sm, sd, em, ed)
                return TemporalResult(
                    success=True,
                    start_date=start_date,
                    end_date=end_date,
                    expression=expr,
                    interpretation=f"{season_name.title()} {year}",
                    confidence=0.9,
                )

        return None

    def _season_to_dates(
        self, year: int, sm: int, sd: int, em: int, ed: int
    ) -> Tuple[str, str]:
        """Convert season parameters to date strings, handling year crossover."""
        if em < sm:  # Crosses year boundary (e.g., winter)
            start = f"{year}-{sm:02d}-{sd:02d}"
            end = f"{year + 1}-{em:02d}-{ed:02d}"
        else:
            start = f"{year}-{sm:02d}-{sd:02d}"
            end = f"{year}-{em:02d}-{ed:02d}"
        return start, end

    def _try_relative(self, expr: str) -> Optional[TemporalResult]:
        """Try to parse relative expressions like 'last 3 months'."""
        expr_lower = expr.lower()
        ref = self.reference_date

        # "last/past N days/weeks/months/years"
        pattern = r'(?:last|past)\s+(\d+)\s+(day|week|month|year)s?'
        match = re.search(pattern, expr_lower)
        if match:
            n = int(match.group(1))
            unit = match.group(2)

            if unit == 'day':
                start = ref - timedelta(days=n)
            elif unit == 'week':
                start = ref - timedelta(weeks=n)
            elif unit == 'month':
                start = ref - relativedelta(months=n)
            elif unit == 'year':
                start = ref - relativedelta(years=n)

            return TemporalResult(
                success=True,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=ref.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"Last {n} {unit}(s) from {ref.strftime('%Y-%m-%d')}",
                confidence=0.85,
            )

        # "last month/year/week"
        if 'last month' in expr_lower:
            start = (ref.replace(day=1) - relativedelta(months=1))
            end = ref.replace(day=1) - timedelta(days=1)
            return TemporalResult(
                success=True,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=end.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"Last month ({start.strftime('%B %Y')})",
                confidence=0.9,
            )

        if 'last year' in expr_lower:
            year = ref.year - 1
            return TemporalResult(
                success=True,
                start_date=f"{year}-01-01",
                end_date=f"{year}-12-31",
                expression=expr,
                interpretation=f"Last year ({year})",
                confidence=0.9,
            )

        if 'last week' in expr_lower:
            start = ref - timedelta(days=ref.weekday() + 7)
            end = start + timedelta(days=6)
            return TemporalResult(
                success=True,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=end.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"Last week ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})",
                confidence=0.9,
            )

        # "this month/year"
        if 'this month' in expr_lower:
            start = ref.replace(day=1)
            return TemporalResult(
                success=True,
                start_date=start.strftime('%Y-%m-%d'),
                end_date=ref.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"This month ({start.strftime('%B %Y')})",
                confidence=0.9,
            )

        if 'this year' in expr_lower:
            return TemporalResult(
                success=True,
                start_date=f"{ref.year}-01-01",
                end_date=ref.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"This year ({ref.year})",
                confidence=0.9,
            )

        # "yesterday", "today"
        if 'yesterday' in expr_lower:
            yesterday = ref - timedelta(days=1)
            return TemporalResult(
                success=True,
                start_date=yesterday.strftime('%Y-%m-%d'),
                end_date=yesterday.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"Yesterday ({yesterday.strftime('%Y-%m-%d')})",
                confidence=1.0,
            )

        if 'today' in expr_lower:
            return TemporalResult(
                success=True,
                start_date=ref.strftime('%Y-%m-%d'),
                end_date=ref.strftime('%Y-%m-%d'),
                expression=expr,
                interpretation=f"Today ({ref.strftime('%Y-%m-%d')})",
                confidence=1.0,
            )

        return None

    def _try_month_year(self, expr: str) -> Optional[TemporalResult]:
        """Try to parse month-year expressions like 'January 2024'."""
        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'jun': 6, 'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9,
            'oct': 10, 'nov': 11, 'dec': 12,
        }

        expr_lower = expr.lower()

        for month_name, month_num in months.items():
            if month_name in expr_lower:
                # Find year
                year_match = re.search(r'(\d{4})', expr)
                year = int(year_match.group(1)) if year_match else self.reference_date.year

                # Calculate last day of month
                if month_num == 12:
                    last_day = 31
                else:
                    next_month = datetime(year, month_num + 1, 1)
                    last_day = (next_month - timedelta(days=1)).day

                return TemporalResult(
                    success=True,
                    start_date=f"{year}-{month_num:02d}-01",
                    end_date=f"{year}-{month_num:02d}-{last_day:02d}",
                    expression=expr,
                    interpretation=f"{month_name.title()} {year}",
                    confidence=0.9,
                )

        return None

    def _try_dateparser(self, expr: str) -> Optional[TemporalResult]:
        """Try using dateparser library for complex expressions."""
        if not DATEPARSER_AVAILABLE:
            return None

        try:
            # Try to parse as a date
            parsed = dateparser.parse(
                expr,
                settings={
                    'PREFER_DATES_FROM': 'past',
                    'RELATIVE_BASE': self.reference_date,
                }
            )

            if parsed:
                # For single dates, create a small range (same day)
                return TemporalResult(
                    success=True,
                    start_date=parsed.strftime('%Y-%m-%d'),
                    end_date=parsed.strftime('%Y-%m-%d'),
                    expression=expr,
                    interpretation=f"Parsed date: {parsed.strftime('%Y-%m-%d')}",
                    confidence=0.7,
                )
        except Exception as e:
            logger.debug(f"dateparser failed for '{expr}': {e}")

        return None


# Module-level instance
_parser: Optional[TemporalParser] = None


def get_parser(reference_date: Optional[datetime] = None) -> TemporalParser:
    """Get or create the temporal parser."""
    global _parser
    if _parser is None or reference_date is not None:
        _parser = TemporalParser(reference_date)
    return _parser


def parse_temporal_expression(
    expression: str,
    reference_date: Optional[datetime] = None
) -> TemporalResult:
    """
    Parse a temporal expression to date range.

    This is the main entry point for temporal parsing.

    Args:
        expression: Natural language temporal expression
        reference_date: Reference date for relative expressions

    Returns:
        TemporalResult with date range or error

    Examples:
        >>> result = parse_temporal_expression("last summer")
        >>> result.temporal_extent
        ['2025-06-01', '2025-08-31']

        >>> result = parse_temporal_expression("monsoon 2024")
        >>> result.interpretation
        'Monsoon 2024'
    """
    parser = get_parser(reference_date)
    return parser.parse(expression)


# Convenience function for tools
async def parse_temporal_async(
    expression: str,
    reference_date: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Async wrapper for temporal parsing (for tool use).

    Returns dict suitable for JSON response.
    """
    result = parse_temporal_expression(expression, reference_date)
    return result.to_dict()
