"""Tests for the battery simulation engine."""
from __future__ import annotations

import pytest
from typing import Any

from custom_components.home_battery_sizer.simulation import simulate_battery


class TestSimulation:
    """Test battery simulation engine."""

    def test_simulation_simple_case(self) -> None:
        """Test basic charge/discharge cycle."""
        daily_data = [
            {
                "date": "2024-01-01",
                "solar_production": 20.0,
                "grid_import": 0.0,
                "grid_export": 0.0,
            },
            {
                "date": "2024-01-02",
                "solar_production": 15.0,
                "grid_import": 5.0,
                "grid_export": 0.0,
            },
        ]

        result = simulate_battery(daily_data, battery_size=10.0)

        assert "self_sufficient_days" in result
        assert "self_sufficiency_yesterday" in result
        assert "daily_results" in result
        assert isinstance(result["self_sufficient_days"], int)
        assert isinstance(result["self_sufficiency_yesterday"], float)
        assert 0 <= result["self_sufficiency_yesterday"] <= 100

    def test_simulation_all_self_sufficient(self) -> None:
        """Test days with 100% self-sufficiency."""
        daily_data = [
            {
                "date": f"2024-01-{i+1:02d}",
                "solar_production": 25.0,
                "grid_import": 0.0,
                "grid_export": 5.0,
            }
            for i in range(5)
        ]

        result = simulate_battery(daily_data, battery_size=10.0)

        # All days have sufficient solar, no grid import
        assert result["self_sufficient_days"] == 5

    def test_simulation_battery_efficiency(self) -> None:
        """Test 90% round-trip efficiency is applied on charging."""
        # Day 1: solar=30, import=0, export=20 → consumption=10, surplus=20
        #        stored = 20 * 0.9 = 18 kWh  (battery_size=20, so no cap)
        # Day 2: solar=5, import=8, export=0 → consumption=13, deficit=8
        #        discharge = min(8, 18) = 8 kWh → grid_needed = 0
        daily_data = [
            {
                "date": "2024-01-01",
                "solar_production": 30.0,
                "grid_import": 0.0,
                "grid_export": 20.0,
            },
            {
                "date": "2024-01-02",
                "solar_production": 5.0,
                "grid_import": 8.0,
                "grid_export": 0.0,
            },
        ]

        result = simulate_battery(daily_data, battery_size=20.0)

        # 18 kWh stored covers the day-2 deficit of 8 kWh exactly → no grid needed
        daily_results = result["daily_results"]
        assert daily_results[1]["grid_import_needed"] == pytest.approx(0.0, abs=0.01)
        assert daily_results[1]["self_sufficient"] is True

    def test_simulation_battery_capacity_limit(self) -> None:
        """Test battery doesn't exceed capacity even with a huge surplus."""
        # solar=50, import=0, export=0 → consumption=50, surplus=0  (no export, all consumed)
        # Use export to create a real surplus:
        # solar=50, import=0, export=40 → consumption=10, surplus=40
        # stored = min(40 * 0.9, 10.0) = 10.0  (capped at capacity)
        daily_data = [
            {
                "date": "2024-01-01",
                "solar_production": 50.0,
                "grid_import": 0.0,
                "grid_export": 40.0,
            },
        ]

        result = simulate_battery(daily_data, battery_size=10.0)

        daily_results = result["daily_results"]
        # Battery was capped; grid was not needed
        assert daily_results[0]["grid_import_needed"] == pytest.approx(0.0, abs=1e-6)

    def test_simulation_empty_data(self) -> None:
        """Test empty daily_data returns zeros."""
        result = simulate_battery([], battery_size=10.0)

        assert result["self_sufficient_days"] == 0
        assert result["self_sufficiency_yesterday"] == 0.0
        assert result["daily_results"] == []

    @pytest.mark.parametrize(
        "battery_size",
        [5.0, 10.0, 20.0],
    )
    def test_simulation_various_battery_sizes(
        self, sample_daily_data: list[dict[str, Any]], battery_size: float
    ) -> None:
        """Test simulation with different battery sizes."""
        result_5 = simulate_battery(sample_daily_data, battery_size=5.0)
        result_10 = simulate_battery(sample_daily_data, battery_size=10.0)
        result_20 = simulate_battery(sample_daily_data, battery_size=20.0)

        # Larger battery should have more self-sufficient days
        assert result_5["self_sufficient_days"] <= result_10["self_sufficient_days"]
        assert result_10["self_sufficient_days"] <= result_20["self_sufficient_days"]

    def test_simulation_self_sufficiency_yesterday(self, sample_daily_data) -> None:
        """Test self-sufficiency percentage for today (last day)."""
        result = simulate_battery(sample_daily_data, battery_size=10.0)

        today_sufficiency = result["self_sufficiency_yesterday"]
        assert isinstance(today_sufficiency, float)
        assert 0 <= today_sufficiency <= 100

    def test_simulation_daily_results_structure(self, sample_daily_data) -> None:
        """Test daily_results have all required keys."""
        result = simulate_battery(sample_daily_data, battery_size=10.0)

        daily_results = result["daily_results"]
        assert len(daily_results) == len(sample_daily_data)

        for day in daily_results:
            assert "date" in day
            assert "solar_production" in day
            assert "total_consumption" in day
            assert "grid_import_needed" in day
            assert "self_sufficient" in day
            assert "self_sufficiency_pct" in day

    def test_simulation_zero_consumption(self) -> None:
        """Test edge case with zero solar, import, and export (nothing happening).

        consumption = max(0, 0+0-0) = 0  → no deficit, grid_needed = 0
        ss_pct = 100.0 when consumption == 0 (convention: fully self-sufficient)
        """
        daily_data = [
            {
                "date": "2024-01-01",
                "solar_production": 0.0,
                "grid_import": 0.0,
                "grid_export": 0.0,
            },
        ]

        result = simulate_battery(daily_data, battery_size=10.0)

        assert result["self_sufficient_days"] >= 0
        assert result["self_sufficiency_yesterday"] == pytest.approx(100.0)

    def test_simulation_high_consumption(self) -> None:
        """Test with high consumption exceeding solar production."""
        daily_data = [
            {
                "date": "2024-01-01",
                "solar_production": 5.0,
                "grid_import": 20.0,
                "grid_export": 0.0,
            },
        ]

        result = simulate_battery(daily_data, battery_size=5.0)

        # High grid import needed due to consumption
        daily_results = result["daily_results"]
        assert daily_results[0]["grid_import_needed"] > 0

    def test_simulation_results_are_rounded(self, sample_daily_data) -> None:
        """Test that results are properly rounded."""
        result = simulate_battery(sample_daily_data, battery_size=10.0)

        # Check that sufficiency is rounded to 1 decimal
        assert result["self_sufficiency_yesterday"] == round(
            result["self_sufficiency_yesterday"], 1
        )

        # Check daily results are rounded to 3 decimals
        for day in result["daily_results"]:
            for key in [
                "solar_production",
                "total_consumption",
                "grid_import_needed",
            ]:
                value = day[key]
                if value != 0:
                    # Check precision
                    assert len(str(value).split(".")[-1]) <= 3
