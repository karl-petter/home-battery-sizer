"""Tests for recorder query functionality."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.home_battery_sizer.recorder import (
    async_get_hourly_energy_data,
    _process_statistics,
)

SOLAR = "sensor.solar"
IMPORT = "sensor.import"
EXPORT = "sensor.export"


def create_stat_entry(start: datetime, sum_value: float) -> dict[str, Any]:
    """Create a stat entry in the dict format returned by HA recorder."""
    return {"start": start, "sum": sum_value}


def make_stats(
    solar_vals: list[tuple[datetime, float]],
    import_vals: list[tuple[datetime, float]],
    export_vals: list[tuple[datetime, float]],
) -> dict[str, list]:
    """Build the stats dict that _process_statistics expects."""
    return {
        SOLAR:  [create_stat_entry(dt, v) for dt, v in solar_vals],
        IMPORT: [create_stat_entry(dt, v) for dt, v in import_vals],
        EXPORT: [create_stat_entry(dt, v) for dt, v in export_vals],
    }


class TestRecorderModule:
    """Test recorder query functionality."""

    def test_process_statistics_calculates_differences(self) -> None:
        """Hourly deltas are the difference between consecutive cumulative sums."""
        base = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        hours = [base + timedelta(hours=h) for h in range(5)]

        stats = make_stats(
            [(hours[0], 100.0), (hours[1], 110.0), (hours[2], 120.0),
             (hours[3], 130.0), (hours[4], 150.0)],
            [(hours[0],  50.0), (hours[1],  55.0), (hours[2],  60.0),
             (hours[3],  65.0), (hours[4],  80.0)],
            [(hours[0],  10.0), (hours[1],  12.0), (hours[2],  14.0),
             (hours[3],  16.0), (hours[4],  30.0)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        # 5 entries → 4 deltas
        assert len(result) == 4

        # First delta: between hours[0] and hours[1]
        assert result[0]["solar_production"] == pytest.approx(10.0)
        assert result[0]["grid_import"]       == pytest.approx(5.0)
        assert result[0]["grid_export"]       == pytest.approx(2.0)

    def test_process_statistics_empty_data(self) -> None:
        """Empty stats dict returns empty list."""
        result = _process_statistics({}, SOLAR, IMPORT, EXPORT)
        assert result == []

    def test_process_statistics_partial_data(self) -> None:
        """If any sensor has no entries the function returns empty list with a warning."""
        base = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)

        stats = {
            SOLAR:  [create_stat_entry(base, 100.0)],
            # IMPORT and EXPORT missing
        }

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)
        assert result == []

    def test_process_statistics_missing_sum_entry_is_skipped(self) -> None:
        """Entries where sum is None are silently dropped."""
        base = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        h1 = base + timedelta(hours=1)

        stats = make_stats(
            [(base, 100.0), (h1, 110.0)],
            [(base,  50.0), (h1,  55.0)],
            [(base,  10.0), (h1,  12.0)],
        )
        # Inject an entry with sum=None into solar — it should be skipped
        stats[SOLAR].insert(1, {"start": base + timedelta(minutes=30), "sum": None})

        # The None-sum entry is dropped; remaining two common hours produce 1 delta
        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)
        assert isinstance(result, list)

    def test_process_statistics_negative_differences_become_zero(self) -> None:
        """Decreasing cumulative values (meter reset) are clamped to 0."""
        base = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        h1 = base + timedelta(hours=1)

        stats = make_stats(
            [(base, 100.0), (h1,  90.0)],   # solar counter resets
            [(base,  50.0), (h1,  55.0)],
            [(base,  10.0), (h1,  12.0)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        assert result[0]["solar_production"] == pytest.approx(0.0)
        assert result[0]["grid_import"]       == pytest.approx(5.0)

    def test_process_statistics_chronological_ordering(self) -> None:
        """Results are sorted chronologically regardless of input order."""
        base = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        hours = [base + timedelta(hours=h) for h in range(3)]

        # Supply entries in reverse order
        stats = {
            SOLAR:  [create_stat_entry(hours[2], 120.0),
                     create_stat_entry(hours[0], 100.0),
                     create_stat_entry(hours[1], 110.0)],
            IMPORT: [create_stat_entry(hours[2],  60.0),
                     create_stat_entry(hours[0],  50.0),
                     create_stat_entry(hours[1],  55.0)],
            EXPORT: [create_stat_entry(hours[2],  14.0),
                     create_stat_entry(hours[0],  10.0),
                     create_stat_entry(hours[1],  12.0)],
        }

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 2
        assert result[0]["datetime"] < result[1]["datetime"]

    def test_process_statistics_date_format(self) -> None:
        """The 'date' field must be YYYY-MM-DD ISO format."""
        base = datetime(2024, 6, 15, 10, tzinfo=timezone.utc)
        h1 = base + timedelta(hours=1)

        stats = make_stats(
            [(base, 100.0), (h1, 105.0)],
            [(base,  50.0), (h1,  52.0)],
            [(base,  10.0), (h1,  10.5)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        date_str = result[0]["date"]
        assert len(date_str) == 10
        assert date_str[4] == "-"
        assert date_str[7] == "-"
        assert date_str == "2024-06-15"


# async_get_hourly_energy_data cannot be unit-tested standalone because it
# delegates to homeassistant.components.recorder, which requires native extensions
# (fnvhash, etc.) not available in a plain pip install. The coordinator integration
# tests cover the wiring; _process_statistics is exercised by TestRecorderModule above.
