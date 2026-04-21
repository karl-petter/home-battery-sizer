"""Targeted tests for core battery behaviour, recorder processing, and self-sufficiency tracking.

Tests use the actual public/private APIs and match the real data structures.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from custom_components.home_battery_sizer.simulation import simulate_battery
from custom_components.home_battery_sizer.recorder import _process_statistics
from custom_components.home_battery_sizer.const import BATTERY_EFFICIENCY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hour(date: str, hour: int) -> dict[str, Any]:
    """Build a minimal hourly entry with zero energy values."""
    return {
        "datetime": f"{date}T{hour:02d}:00:00",
        "date": date,
        "solar_production": 0.0,
        "grid_import": 0.0,
        "grid_export": 0.0,
    }


def _stat_entry(dt: datetime, cumulative: float) -> dict[str, Any]:
    """Build a statistics entry in dict format (as returned by HA recorder)."""
    return {"start": dt, "sum": cumulative}


SOLAR = "sensor.solar"
IMPORT = "sensor.import"
EXPORT = "sensor.export"


# ---------------------------------------------------------------------------
# 1. Simulation logic — charge / discharge hour by hour
# ---------------------------------------------------------------------------

class TestHourlyChargeDischarge:
    """Verify that the battery SOC evolves correctly across individual hours.

    The simulation derives consumption as:
        consumption = max(0, solar + grid_import_hist - grid_export_hist)

    Historical grid_import_hist reflects what was actually imported (added to consumption);
    grid_export_hist reflects what was actually exported (subtracted from consumption).
    To create a surplus (solar > consumption) the historical data must show net export,
    i.e. grid_export_hist > grid_import_hist.
    """

    def test_surplus_hour_charges_battery_with_efficiency(self) -> None:
        """Surplus solar charges the battery with the 90 % efficiency factor.

        solar=5, grid_import=0, grid_export=3
        → consumption = 5 + 0 - 3 = 2 kWh
        → surplus    = 5 - 2     = 3 kWh
        → stored     = 3 × 0.90  = 2.7 kWh   (grid_needed = 0)
        """
        data = [
            {**_hour("2024-06-01", 12),
             "solar_production": 5.0, "grid_import": 0.0, "grid_export": 3.0},
        ]
        result = simulate_battery(data, battery_size=10.0)

        day = result["daily_results"][0]
        assert day["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)

    def test_deficit_hour_draws_from_battery(self) -> None:
        """When solar is insufficient the battery covers the deficit.

        Hour 1 (noon):  solar=5, export=3 → consumption=2, surplus=3, stored=2.7 kWh
        Hour 2 (night): solar=0, import=2 → consumption=2, deficit=2, discharge=2 → grid=0
        Net day grid_import_needed = 0.
        """
        data = [
            {**_hour("2024-06-01", 12),
             "solar_production": 5.0, "grid_import": 0.0, "grid_export": 3.0},
            {**_hour("2024-06-01", 22),
             "solar_production": 0.0, "grid_import": 2.0, "grid_export": 0.0},
        ]
        result = simulate_battery(data, battery_size=10.0)

        day = result["daily_results"][0]
        assert day["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)

    def test_battery_empty_forces_grid_import(self) -> None:
        """When the battery is empty a deficit falls back to grid.

        Night hour, no solar, battery starts at 0 → all 3 kWh from grid.
        """
        data = [
            {**_hour("2024-06-01", 22),
             "solar_production": 0.0, "grid_import": 3.0, "grid_export": 0.0},
        ]
        result = simulate_battery(data, battery_size=10.0)

        day = result["daily_results"][0]
        assert day["grid_import_needed"] == pytest.approx(3.0, abs=1e-6)

    def test_battery_state_carries_over_between_days(self) -> None:
        """Charge accumulated on day 1 must be available to cover night loads on day 2.

        Day 1 noon: solar=20, export=10 → consumption=10, surplus=10, stored=9.0 kWh
        Day 2 night: solar=0, import=5 → consumption=5, deficit=5, discharge=5 → grid=0
        """
        data = [
            {**_hour("2024-06-01", 12),
             "solar_production": 20.0, "grid_import": 0.0, "grid_export": 10.0},
            {**_hour("2024-06-02", 22),
             "solar_production": 0.0,  "grid_import": 5.0, "grid_export": 0.0},
        ]
        result = simulate_battery(data, battery_size=10.0)

        day2 = result["daily_results"][1]
        # 9 kWh in battery covers the 5 kWh night deficit cleanly
        assert day2["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)
        assert day2["self_sufficient"] is True

    def test_partial_battery_coverage_leaves_residual_grid_import(self) -> None:
        """Battery only partially covers a large deficit; the rest comes from the grid.

        Hour 1 (noon):  solar=5, export=3 → consumption=2, surplus=3, stored=2.7 kWh
        Hour 2 (night): solar=0, import=8 → consumption=8, deficit=8
                        discharge=2.7, grid_needed=8-2.7=5.3 kWh
        """
        data = [
            {**_hour("2024-06-01", 12),
             "solar_production": 5.0, "grid_import": 0.0, "grid_export": 3.0},
            {**_hour("2024-06-01", 20),
             "solar_production": 0.0, "grid_import": 8.0, "grid_export": 0.0},
        ]
        result = simulate_battery(data, battery_size=10.0)

        day = result["daily_results"][0]
        expected_stored = 3.0 * BATTERY_EFFICIENCY   # 2.7 kWh
        expected_grid   = 8.0 - expected_stored       # 5.3 kWh
        assert day["grid_import_needed"] == pytest.approx(expected_grid, abs=1e-6)


# ---------------------------------------------------------------------------
# 2. Self-sufficient day detection
# ---------------------------------------------------------------------------

class TestSelfSufficientDayDetection:
    """A day with zero grid import is self-sufficient; any import disqualifies it."""

    def test_day_with_zero_grid_needed_is_self_sufficient(self) -> None:
        """Confirm is_self_sufficient=True when grid_import_needed < 0.01."""
        data = [
            {**_hour("2024-06-01", h), "solar_production": 5.0, "grid_import": 0.0}
            for h in range(6, 18)  # 12 sunny hours, zero consumption outside
        ]
        result = simulate_battery(data, battery_size=10.0)

        assert result["daily_results"][0]["self_sufficient"] is True
        assert result["self_sufficient_days"] == 1

    def test_day_with_any_grid_import_is_not_self_sufficient(self) -> None:
        """Even a tiny grid draw makes the day not self-sufficient."""
        data = [
            # 11 free hours
            *[{**_hour("2024-06-01", h), "solar_production": 5.0, "grid_import": 0.0}
              for h in range(6, 17)],
            # One hour with a tiny deficit that cannot be covered (battery starts empty)
            {**_hour("2024-06-01", 3), "solar_production": 0.0, "grid_import": 0.1},
        ]
        result = simulate_battery(data, battery_size=0.0)  # no battery

        assert result["daily_results"][0]["self_sufficient"] is False
        assert result["self_sufficient_days"] == 0

    def test_count_across_multiple_days(self) -> None:
        """Only fully covered days increment the counter."""
        # Day 1: fully solar-covered
        # Day 2: needs 3 kWh from grid (battery = 0)
        # Day 3: fully solar-covered
        data = [
            {**_hour("2024-06-01", 12), "solar_production": 10.0, "grid_import": 0.0},
            {**_hour("2024-06-02", 22), "solar_production": 0.0, "grid_import": 3.0},
            {**_hour("2024-06-03", 12), "solar_production": 10.0, "grid_import": 0.0},
        ]
        result = simulate_battery(data, battery_size=0.0)

        assert result["self_sufficient_days"] == 2


# ---------------------------------------------------------------------------
# 3. Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Zero battery, full battery, solar-only, consumption-only."""

    def test_zero_capacity_battery_never_stores_energy(self) -> None:
        """With battery_size=0 the battery plays no role — all deficits hit the grid."""
        data = [
            {**_hour("2024-06-01", 12), "solar_production": 10.0, "grid_import": 0.0},
            {**_hour("2024-06-01", 22), "solar_production": 0.0, "grid_import": 4.0},
        ]
        result = simulate_battery(data, battery_size=0.0)

        day = result["daily_results"][0]
        # Night deficit must come entirely from grid
        assert day["grid_import_needed"] == pytest.approx(4.0, abs=1e-6)

    def test_battery_exactly_full_surplus_is_capped(self) -> None:
        """Surplus beyond battery capacity is silently capped — grid_needed stays 0."""
        # Battery = 5 kWh, surplus = 20 kWh → battery should cap at 5 kWh
        data = [
            {**_hour("2024-06-01", 12), "solar_production": 20.0, "grid_import": 0.0},
        ]
        result = simulate_battery(data, battery_size=5.0)

        day = result["daily_results"][0]
        assert day["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)
        assert day["self_sufficient"] is True

    def test_consumption_with_no_solar_draws_from_grid(self) -> None:
        """Purely night/cloudy scenario: all consumption must come from grid (no battery)."""
        data = [
            {**_hour("2024-06-01", h), "solar_production": 0.0, "grid_import": 2.0}
            for h in range(0, 8)
        ]
        result = simulate_battery(data, battery_size=0.0)

        day = result["daily_results"][0]
        assert day["grid_import_needed"] == pytest.approx(16.0, abs=1e-3)
        assert day["self_sufficient"] is False

    def test_solar_with_no_consumption_charges_battery(self) -> None:
        """Pure export scenario: solar covers zero consumption, surplus all goes to battery."""
        # 10 kWh solar, 0 grid_import → consumption = max(0, 10+0-0) = 10 kWh
        # Wait — with no grid export in history, consumption estimate = solar
        # So surplus = 0 → nothing stored.
        # For a true "no consumption" scenario we need export = solar
        data = [
            {
                **_hour("2024-06-01", 12),
                "solar_production": 10.0,
                "grid_import": 0.0,
                "grid_export": 10.0,   # all excess exported → consumption = 0
            },
        ]
        result = simulate_battery(data, battery_size=10.0)

        day = result["daily_results"][0]
        # consumption = max(0, 10 + 0 - 10) = 0, so solar covers everything trivially
        assert day["total_consumption"] == pytest.approx(0.0, abs=1e-6)
        assert day["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)

    def test_single_hour_empty_data_returns_default_structure(self) -> None:
        """Empty input list returns a well-defined result, not an exception."""
        result = simulate_battery([], battery_size=10.0)

        assert result["self_sufficient_days"] == 0
        assert result["self_sufficiency_today"] == 0.0
        assert result["first_self_sufficient_day"] is None
        assert result["last_self_sufficient_day"] is None
        assert result["daily_results"] == []

    def test_self_sufficiency_pct_capped_at_100(self) -> None:
        """self_sufficiency_pct must never exceed 100, even with floating-point surplus."""
        data = [
            {**_hour("2024-06-01", 12), "solar_production": 50.0, "grid_import": 0.0},
        ]
        result = simulate_battery(data, battery_size=100.0)

        day = result["daily_results"][0]
        assert day["self_sufficiency_pct"] <= 100.0


# ---------------------------------------------------------------------------
# 4. Recorder processing — _process_statistics
# ---------------------------------------------------------------------------

class TestProcessStatistics:
    """_process_statistics converts cumulative HA stats into per-hour deltas."""

    def _make_stats(
        self,
        solar_vals: list[tuple[datetime, float]],
        import_vals: list[tuple[datetime, float]],
        export_vals: list[tuple[datetime, float]],
    ) -> dict[str, list]:
        return {
            SOLAR:  [_stat_entry(dt, v) for dt, v in solar_vals],
            IMPORT: [_stat_entry(dt, v) for dt, v in import_vals],
            EXPORT: [_stat_entry(dt, v) for dt, v in export_vals],
        }

    def test_basic_delta_calculation(self) -> None:
        """Deltas are computed as (this_hour - prev_hour) for each sensor."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)
        h2 = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)

        stats = self._make_stats(
            [(h0, 100.0), (h1, 103.0), (h2, 107.0)],   # solar +3, +4
            [(h0,  50.0), (h1,  51.0), (h2,  52.0)],   # import +1, +1
            [(h0,  20.0), (h1,  20.5), (h2,  21.0)],   # export +0.5, +0.5
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 2
        assert result[0]["solar_production"] == pytest.approx(3.0)
        assert result[0]["grid_import"]       == pytest.approx(1.0)
        assert result[0]["grid_export"]       == pytest.approx(0.5)
        assert result[1]["solar_production"]  == pytest.approx(4.0)

    def test_counter_reset_produces_zero_not_negative(self) -> None:
        """A meter rollover (decreasing cumulative) must yield 0, not a negative value."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)

        stats = self._make_stats(
            [(h0, 999.9), (h1, 1.0)],   # solar resets
            [(h0,  50.0), (h1, 51.0)],
            [(h0,  20.0), (h1, 20.5)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        assert result[0]["solar_production"] == pytest.approx(0.0)

    def test_output_has_datetime_date_and_energy_keys(self) -> None:
        """Each output row must carry all keys expected by simulate_battery."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)

        stats = self._make_stats(
            [(h0, 0.0), (h1, 2.0)],
            [(h0, 0.0), (h1, 0.5)],
            [(h0, 0.0), (h1, 0.0)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        row = result[0]
        assert "datetime" in row
        assert "date" in row
        assert "solar_production" in row
        assert "grid_import" in row
        assert "grid_export" in row

    def test_missing_one_sensor_returns_empty_list(self) -> None:
        """If any sensor has no data the function returns [] and logs a warning."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)

        # EXPORT sensor is absent
        stats = {
            SOLAR:  [_stat_entry(h0, 0.0), _stat_entry(h1, 2.0)],
            IMPORT: [_stat_entry(h0, 0.0), _stat_entry(h1, 0.5)],
        }

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)
        assert result == []

    def test_non_overlapping_hours_are_excluded(self) -> None:
        """Hours not present in all three sensors are skipped (inner join)."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)
        h2 = datetime(2024, 6, 1, 12, tzinfo=timezone.utc)

        stats = self._make_stats(
            [(h0, 0.0), (h1, 1.0), (h2, 2.0)],  # 3 entries
            [(h0, 0.0), (h1, 0.5)],              # only 2 entries (h2 missing)
            [(h0, 0.0), (h1, 0.0), (h2, 0.0)],  # 3 entries
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        # h2 is absent from import → common hours = [h0, h1] → 1 delta
        assert len(result) == 1

    def test_object_format_entries_are_handled(self) -> None:
        """_process_statistics supports both dict entries and attribute-style objects."""
        h0 = datetime(2024, 6, 1, 10, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 1, 11, tzinfo=timezone.utc)

        class FakeStat:
            def __init__(self, start, sum_val):
                self.start = start
                self.sum = sum_val

        stats = {
            SOLAR:  [FakeStat(h0, 0.0), FakeStat(h1, 3.0)],
            IMPORT: [FakeStat(h0, 0.0), FakeStat(h1, 1.0)],
            EXPORT: [FakeStat(h0, 0.0), FakeStat(h1, 0.0)],
        }

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        assert result[0]["solar_production"] == pytest.approx(3.0)

    def test_date_field_matches_hour_date(self) -> None:
        """The 'date' field must match the calendar date of the hour bucket."""
        h0 = datetime(2024, 6, 1, 23, tzinfo=timezone.utc)
        h1 = datetime(2024, 6, 2,  0, tzinfo=timezone.utc)

        stats = self._make_stats(
            [(h0, 0.0), (h1, 1.0)],
            [(h0, 0.0), (h1, 0.5)],
            [(h0, 0.0), (h1, 0.0)],
        )

        result = _process_statistics(stats, SOLAR, IMPORT, EXPORT)

        assert len(result) == 1
        assert result[0]["date"] == "2024-06-02"


# ---------------------------------------------------------------------------
# 5. First / last self-sufficient day tracking
# ---------------------------------------------------------------------------

class TestFirstLastSelfSufficientDay:
    """Verify first_self_sufficient_day and last_self_sufficient_day are set correctly."""

    def _solar_day(self, date: str) -> dict[str, Any]:
        """One fully solar-covered hour (no consumption outside solar)."""
        return {**_hour(date, 12), "solar_production": 10.0, "grid_import": 0.0}

    def _grid_day(self, date: str) -> dict[str, Any]:
        """One hour with only grid import (no battery to cover it)."""
        return {**_hour(date, 22), "solar_production": 0.0, "grid_import": 5.0}

    def test_both_none_when_no_self_sufficient_day_exists(self) -> None:
        data = [self._grid_day("2024-06-01"), self._grid_day("2024-06-02")]
        result = simulate_battery(data, battery_size=0.0)

        assert result["first_self_sufficient_day"] is None
        assert result["last_self_sufficient_day"] is None

    def test_single_self_sufficient_day_sets_both_fields(self) -> None:
        data = [self._solar_day("2024-06-01")]
        result = simulate_battery(data, battery_size=0.0)

        assert result["first_self_sufficient_day"] == "2024-06-01"
        assert result["last_self_sufficient_day"] == "2024-06-01"

    def test_first_is_earliest_qualifying_day(self) -> None:
        data = [
            self._grid_day("2024-06-01"),   # not sufficient
            self._solar_day("2024-06-02"),  # first sufficient
            self._solar_day("2024-06-03"),
        ]
        result = simulate_battery(data, battery_size=0.0)

        assert result["first_self_sufficient_day"] == "2024-06-02"

    def test_last_is_latest_qualifying_day(self) -> None:
        data = [
            self._solar_day("2024-06-01"),
            self._solar_day("2024-06-02"),
            self._grid_day("2024-06-03"),   # not sufficient
        ]
        result = simulate_battery(data, battery_size=0.0)

        assert result["last_self_sufficient_day"] == "2024-06-02"

    def test_first_and_last_differ_across_gap(self) -> None:
        """A gap of insufficient days between two sufficient ones is handled correctly."""
        data = [
            self._solar_day("2024-06-01"),
            self._grid_day("2024-06-02"),
            self._grid_day("2024-06-03"),
            self._solar_day("2024-06-04"),
        ]
        result = simulate_battery(data, battery_size=0.0)

        assert result["first_self_sufficient_day"] == "2024-06-01"
        assert result["last_self_sufficient_day"] == "2024-06-04"
        assert result["self_sufficient_days"] == 2

    def test_self_sufficiency_today_reflects_last_day(self) -> None:
        """self_sufficiency_today must equal the last daily_results entry's pct."""
        data = [
            self._solar_day("2024-06-01"),
            self._grid_day("2024-06-02"),
        ]
        result = simulate_battery(data, battery_size=0.0)

        last_pct = result["daily_results"][-1]["self_sufficiency_pct"]
        assert result["self_sufficiency_today"] == pytest.approx(last_pct)
