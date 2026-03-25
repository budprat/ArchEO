"""Tests for openeo_ai/utils/temporal.py.

Verifies ISO date parsing, relative date expressions, seasonal terms,
and edge cases -- all without network access.
"""

import pytest
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from openeo_ai.utils.temporal import (
    TemporalParser,
    TemporalResult,
    SEASONS_NH,
    REGIONAL_SEASONS,
    parse_temporal_expression,
)


# Fixed reference date for deterministic tests
REF_DATE = datetime(2025, 6, 15)


@pytest.fixture
def parser():
    """Create a TemporalParser with a fixed reference date."""
    return TemporalParser(reference_date=REF_DATE)


# ---------------------------------------------------------------------------
# Explicit date ranges
# ---------------------------------------------------------------------------


class TestExplicitRanges:
    """Tests for explicit ISO date range parsing."""

    def test_iso_range_with_to(self, parser):
        """Parse '2020-01-01 to 2020-12-31'."""
        result = parser.parse("2020-01-01 to 2020-12-31")

        assert result.success is True
        assert result.start_date == "2020-01-01"
        assert result.end_date == "2020-12-31"
        assert result.confidence == 1.0

    def test_iso_range_with_dash(self, parser):
        """Parse '2023-03-15 - 2023-06-20'."""
        result = parser.parse("2023-03-15 - 2023-06-20")

        assert result.success is True
        assert result.start_date == "2023-03-15"
        assert result.end_date == "2023-06-20"

    def test_iso_range_with_through(self, parser):
        """Parse '2024-01-01 through 2024-03-31'."""
        result = parser.parse("2024-01-01 through 2024-03-31")

        assert result.success is True
        assert result.start_date == "2024-01-01"
        assert result.end_date == "2024-03-31"

    def test_slash_format_range(self, parser):
        """Parse '2024/01/01 to 2024/06/30' (slash separator)."""
        result = parser.parse("2024/01/01 to 2024/06/30")

        assert result.success is True
        assert result.start_date == "2024-01-01"
        assert result.end_date == "2024-06-30"


# ---------------------------------------------------------------------------
# Year-only expressions
# ---------------------------------------------------------------------------


class TestYearOnly:
    """Tests for year-only expressions."""

    def test_single_year(self, parser):
        """Parse '2023' as full year."""
        result = parser.parse("2023")

        assert result.success is True
        assert result.start_date == "2023-01-01"
        assert result.end_date == "2023-12-31"
        assert result.confidence == 0.95

    def test_year_range(self, parser):
        """Parse '2020-2023' as multi-year range."""
        result = parser.parse("2020-2023")

        assert result.success is True
        assert result.start_date == "2020-01-01"
        assert result.end_date == "2023-12-31"

    def test_year_range_with_to(self, parser):
        """Parse '2019 to 2021'."""
        result = parser.parse("2019 to 2021")

        assert result.success is True
        assert result.start_date == "2019-01-01"
        assert result.end_date == "2021-12-31"


# ---------------------------------------------------------------------------
# Seasonal expressions (Northern Hemisphere)
# ---------------------------------------------------------------------------


class TestSeasons:
    """Tests for seasonal expression parsing."""

    def test_summer_with_year(self, parser):
        """Parse 'summer 2024'."""
        result = parser.parse("summer 2024")

        assert result.success is True
        assert result.start_date == "2024-06-01"
        assert result.end_date == "2024-08-31"
        assert result.confidence == 0.9

    def test_spring_without_year(self, parser):
        """Parse 'spring' -- defaults to reference year."""
        result = parser.parse("spring")

        assert result.success is True
        assert result.start_date == f"{REF_DATE.year}-03-01"
        assert result.end_date == f"{REF_DATE.year}-05-31"

    def test_fall_alias(self, parser):
        """'fall' should be treated as 'autumn'."""
        result = parser.parse("fall 2024")

        assert result.success is True
        assert result.start_date == "2024-09-01"
        assert result.end_date == "2024-11-30"

    def test_winter_crosses_year(self, parser):
        """Winter crosses year boundary (Dec to Feb)."""
        result = parser.parse("winter 2024")

        assert result.success is True
        assert result.start_date == "2024-12-01"
        assert result.end_date == "2025-02-28"


# ---------------------------------------------------------------------------
# Regional / agricultural seasons
# ---------------------------------------------------------------------------


class TestRegionalSeasons:
    """Tests for regional season parsing (monsoon, rabi, kharif, etc.)."""

    def test_monsoon_2024(self, parser):
        """Parse 'monsoon 2024'."""
        result = parser.parse("monsoon 2024")

        assert result.success is True
        assert result.start_date == "2024-06-01"
        assert result.end_date == "2024-09-30"
        assert "Monsoon" in result.interpretation

    def test_kharif_season(self, parser):
        """Parse 'kharif 2023'."""
        result = parser.parse("kharif 2023")

        assert result.success is True
        assert result.start_date == "2023-06-01"
        assert result.end_date == "2023-10-15"

    def test_rabi_crosses_year(self, parser):
        """Rabi season crosses year boundary (Oct-Mar)."""
        result = parser.parse("rabi 2024")

        assert result.success is True
        assert result.start_date == "2024-10-15"
        assert result.end_date == "2025-03-15"

    def test_dry_season(self, parser):
        """Parse 'dry season 2024'."""
        result = parser.parse("dry season 2024")

        assert result.success is True
        assert result.start_date == "2024-11-01"
        assert result.end_date == "2025-04-30"

    def test_rainy_season(self, parser):
        """Parse 'rainy season' without year."""
        result = parser.parse("rainy season")

        assert result.success is True
        assert result.start_date.endswith("-06-01")

    def test_growing_season(self, parser):
        """Parse 'growing season 2024'."""
        result = parser.parse("growing season 2024")

        assert result.success is True
        assert result.start_date == "2024-04-01"
        assert result.end_date == "2024-09-30"


# ---------------------------------------------------------------------------
# Relative expressions
# ---------------------------------------------------------------------------


class TestRelativeExpressions:
    """Tests for relative temporal expressions ('last month', 'past 3 months')."""

    def test_last_3_months(self, parser):
        """Parse 'last 3 months'."""
        result = parser.parse("last 3 months")

        expected_start = (REF_DATE - relativedelta(months=3)).strftime("%Y-%m-%d")
        expected_end = REF_DATE.strftime("%Y-%m-%d")

        assert result.success is True
        assert result.start_date == expected_start
        assert result.end_date == expected_end
        assert result.confidence == 0.85

    def test_past_7_days(self, parser):
        """Parse 'past 7 days'."""
        result = parser.parse("past 7 days")

        expected_start = (REF_DATE - timedelta(days=7)).strftime("%Y-%m-%d")

        assert result.success is True
        assert result.start_date == expected_start

    def test_last_2_weeks(self, parser):
        """Parse 'last 2 weeks'."""
        result = parser.parse("last 2 weeks")

        expected_start = (REF_DATE - timedelta(weeks=2)).strftime("%Y-%m-%d")

        assert result.success is True
        assert result.start_date == expected_start

    def test_past_1_year(self, parser):
        """Parse 'past 1 year'."""
        result = parser.parse("past 1 year")

        expected_start = (REF_DATE - relativedelta(years=1)).strftime("%Y-%m-%d")

        assert result.success is True
        assert result.start_date == expected_start

    def test_last_month(self, parser):
        """Parse 'last month' -- should be the entire previous calendar month."""
        result = parser.parse("last month")

        assert result.success is True
        # Reference is 2025-06-15, so last month is May 2025
        assert result.start_date == "2025-05-01"
        assert result.end_date == "2025-05-31"
        assert result.confidence == 0.9

    def test_last_year(self, parser):
        """Parse 'last year'."""
        result = parser.parse("last year")

        assert result.success is True
        assert result.start_date == "2024-01-01"
        assert result.end_date == "2024-12-31"

    def test_last_week(self, parser):
        """Parse 'last week'."""
        result = parser.parse("last week")

        assert result.success is True
        # Should return a 7-day span
        start = datetime.strptime(result.start_date, "%Y-%m-%d")
        end = datetime.strptime(result.end_date, "%Y-%m-%d")
        assert (end - start).days == 6

    def test_this_month(self, parser):
        """Parse 'this month'."""
        result = parser.parse("this month")

        assert result.success is True
        assert result.start_date == "2025-06-01"
        assert result.end_date == "2025-06-15"

    def test_this_year(self, parser):
        """Parse 'this year'."""
        result = parser.parse("this year")

        assert result.success is True
        assert result.start_date == "2025-01-01"
        assert result.end_date == "2025-06-15"

    def test_yesterday(self, parser):
        """Parse 'yesterday'."""
        result = parser.parse("yesterday")

        assert result.success is True
        assert result.start_date == "2025-06-14"
        assert result.end_date == "2025-06-14"
        assert result.confidence == 1.0

    def test_today(self, parser):
        """Parse 'today'."""
        result = parser.parse("today")

        assert result.success is True
        assert result.start_date == "2025-06-15"
        assert result.end_date == "2025-06-15"


# ---------------------------------------------------------------------------
# Month-year expressions
# ---------------------------------------------------------------------------


class TestMonthYear:
    """Tests for month-year expressions like 'January 2024'."""

    def test_full_month_name(self, parser):
        """Parse 'January 2024'."""
        result = parser.parse("January 2024")

        assert result.success is True
        assert result.start_date == "2024-01-01"
        assert result.end_date == "2024-01-31"

    def test_abbreviated_month(self, parser):
        """Parse 'Sep 2023'."""
        result = parser.parse("Sep 2023")

        assert result.success is True
        assert result.start_date == "2023-09-01"
        assert result.end_date == "2023-09-30"

    def test_february_leap_year(self, parser):
        """February in a leap year should end on the 29th."""
        result = parser.parse("February 2024")

        assert result.success is True
        assert result.start_date == "2024-02-01"
        assert result.end_date == "2024-02-29"

    def test_february_non_leap_year(self, parser):
        """February in a non-leap year should end on the 28th."""
        result = parser.parse("February 2023")

        assert result.success is True
        assert result.end_date == "2023-02-28"

    def test_december(self, parser):
        """Parse 'December 2024'."""
        result = parser.parse("December 2024")

        assert result.success is True
        assert result.start_date == "2024-12-01"
        assert result.end_date == "2024-12-31"

    def test_month_without_year(self, parser):
        """Month without year defaults to reference year."""
        result = parser.parse("March")

        assert result.success is True
        assert result.start_date == f"{REF_DATE.year}-03-01"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and invalid input."""

    def test_empty_string(self, parser):
        """Empty string should fail gracefully."""
        result = parser.parse("")

        assert result.success is False
        assert result.error is not None

    def test_gibberish_input(self, parser):
        """Nonsensical input should fail gracefully."""
        result = parser.parse("xyzzy foobarbaz")

        assert result.success is False

    def test_whitespace_only(self, parser):
        """Whitespace-only input should fail."""
        result = parser.parse("   ")

        assert result.success is False


# ---------------------------------------------------------------------------
# TemporalResult dataclass
# ---------------------------------------------------------------------------


class TestTemporalResult:
    """Tests for the TemporalResult dataclass and its serialization."""

    def test_to_dict_success(self):
        """Verify to_dict for a successful result."""
        tr = TemporalResult(
            success=True,
            start_date="2024-01-01",
            end_date="2024-12-31",
            expression="2024",
            interpretation="Full year 2024",
            confidence=0.95,
        )
        d = tr.to_dict()

        assert d["success"] is True
        assert d["temporal_extent"] == ["2024-01-01", "2024-12-31"]
        assert d["start_date"] == "2024-01-01"

    def test_to_dict_failure(self):
        """Verify to_dict for a failed result."""
        tr = TemporalResult(
            success=False,
            expression="garbage",
            error="Could not parse",
        )
        d = tr.to_dict()

        assert d["success"] is False
        assert d["error"] == "Could not parse"
        assert "temporal_extent" not in d


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------


class TestParseTemporalExpression:
    """Tests for the module-level parse_temporal_expression() function."""

    def test_with_custom_reference_date(self):
        """Verify that a custom reference_date is honoured."""
        ref = datetime(2030, 1, 1)
        result = parse_temporal_expression("last year", reference_date=ref)

        assert result.success is True
        assert result.start_date == "2029-01-01"
        assert result.end_date == "2029-12-31"

    def test_simple_year(self):
        """Parse a simple year via the convenience function."""
        result = parse_temporal_expression("2022")

        assert result.success is True
        assert result.start_date == "2022-01-01"
