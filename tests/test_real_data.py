"""Simulation tests against real HA recorder data.

The CSV in tests/test-data/ was exported directly from the live HA SQLite DB
on 2026-04-29. It covers 9 calendar dates (2026-04-21 07:00 → 2026-04-29 19:00)
for three sensors:
  - solar  (Wh cumulative, converted to kWh deltas in the CSV)
  - import (kWh deltas)
  - export (kWh deltas)

The dataset starts at 07:00 on April 21 so the battery starts charging from the
first hour rather than cold-starting in the middle of the night.

Night hours have no solar entry from the inverter; the CSV shows an empty
solar_kwh_delta for those rows. We treat those as 0 (fixed in recorder.py).

Ground-truth daily totals for April 28 (the sunniest complete day) are
computed here directly from the CSV so assertions don't rely on the simulation
being correct — they rely only on arithmetic.
"""
from __future__ import annotations

import csv
from pathlib import Path
from collections import defaultdict

import pytest

from custom_components.home_battery_sizer.simulation import simulate_battery

CSV_PATH = Path(__file__).parent / "test-data" / "ha_hourly_deltas_8days.csv"


def load_hourly_data() -> list[dict]:
    """Read the delta CSV and return simulation-ready hourly records."""
    rows = []
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            imp = row["import_kwh_delta"]
            exp = row["export_kwh_delta"]
            if not imp or not exp:
                continue  # first row has no previous hour

            hour = row["hour"]  # "2026-04-28 14:00:00"
            rows.append({
                "datetime": hour.replace(" ", "T"),
                "date": hour[:10],
                "solar_production": float(row["solar_kwh_delta"]) if row["solar_kwh_delta"] else 0.0,
                "grid_import": float(imp),
                "grid_export": float(exp),
            })
    return rows


def daily_totals(hourly_data: list[dict]) -> dict[str, dict]:
    """Sum solar, import, export per calendar day."""
    totals: dict[str, dict] = defaultdict(lambda: {"solar": 0.0, "import": 0.0, "export": 0.0})
    for h in hourly_data:
        d = h["date"]
        totals[d]["solar"]  += h["solar_production"]
        totals[d]["import"] += h["grid_import"]
        totals[d]["export"] += h["grid_export"]
    return dict(totals)


@pytest.fixture(scope="module")
def hourly_data():
    return load_hourly_data()


@pytest.fixture(scope="module")
def day_totals(hourly_data):
    return daily_totals(hourly_data)


# ---------------------------------------------------------------------------
# Ground-truth sanity checks on the raw data (no simulation)
# ---------------------------------------------------------------------------

def test_csv_covers_nine_dates(day_totals):
    # April 21 (partial from 07:00) through April 29 (partial to 19:00)
    assert len(day_totals) == 9


def test_april28_was_sunny(day_totals):
    """April 28 had significant solar production and large net export."""
    d = day_totals["2026-04-28"]
    assert d["solar"] > 30, "Expected >30 kWh solar on the sunny day"
    assert d["export"] > 20, "Expected >20 kWh exported on the sunny day"


def test_april28_had_large_night_import(day_totals):
    """April 28 still had significant grid import (overnight) despite the sun."""
    d = day_totals["2026-04-28"]
    assert d["import"] > 10, "Expected >10 kWh grid import on April 28"


def test_no_battery_self_sufficiency_april28(hourly_data):
    """Without a battery, self-sufficiency for April 28 matches hourly meter arithmetic.

    The simulation computes per hour:
      consumption_h = max(0, solar + import - export)
      grid_needed_h = max(0, import - export)   [no battery → no discharge]
    so this test replicates that arithmetic directly from the raw hourly data.
    """
    april28 = [h for h in hourly_data if h["date"] == "2026-04-28"]
    total_consumption = sum(
        max(0.0, h["solar_production"] + h["grid_import"] - h["grid_export"])
        for h in april28
    )
    total_grid_needed = sum(
        max(0.0, h["grid_import"] - h["grid_export"])
        for h in april28
    )
    expected_ss = (total_consumption - total_grid_needed) / total_consumption * 100

    result = simulate_battery(hourly_data, battery_size=0.0)
    day = next(r for r in result["daily_results"] if r["date"] == "2026-04-28")

    assert day["self_sufficiency_pct"] == pytest.approx(expected_ss, abs=0.1), (
        f"0-battery self-sufficiency should match raw meter data. "
        f"Expected ~{expected_ss:.1f}%, got {day['self_sufficiency_pct']:.1f}%"
    )


# ---------------------------------------------------------------------------
# Simulation sanity checks
# ---------------------------------------------------------------------------

def test_values_in_valid_range(hourly_data):
    for size in (0.0, 1.0, 5.0, 10.0, 20.0):
        result = simulate_battery(hourly_data, battery_size=size)
        for day in result["daily_results"]:
            assert 0.0 <= day["self_sufficiency_pct"] <= 100.0, (
                f"battery={size}: {day['date']} self_sufficiency_pct out of range: "
                f"{day['self_sufficiency_pct']}"
            )


def test_larger_battery_never_worse(hourly_data):
    """A bigger battery can only help, never hurt, over the same dataset."""
    results = {
        size: simulate_battery(hourly_data, battery_size=size)
        for size in (0.0, 1.0, 5.0, 10.0, 20.0)
    }
    sizes = sorted(results)
    for small, large in zip(sizes, sizes[1:]):
        assert results[small]["self_sufficient_days"] <= results[large]["self_sufficient_days"], (
            f"{large} kWh battery should have >= self-sufficient days vs {small} kWh"
        )


def test_1kwh_battery_not_trivially_self_sufficient(hourly_data):
    """1 kWh battery must NOT show ~100% for April 28.

    This was the symptom of the Wh/kWh + missing-night-hours bug.
    April 28 had >10 kWh of night grid import — a 1 kWh battery can save
    at most 1 kWh, so self-sufficiency must be well below 100%.
    """
    result = simulate_battery(hourly_data, battery_size=1.0)
    day = next(r for r in result["daily_results"] if r["date"] == "2026-04-28")
    assert day["self_sufficiency_pct"] < 80.0, (
        f"1 kWh battery on April 28 should be well below 80%, "
        f"got {day['self_sufficiency_pct']:.1f}% — Wh/kWh or night-hours bug may be back"
    )


def test_20kwh_meaningfully_better_than_1kwh_april28(hourly_data):
    """20 kWh battery should show noticeably higher self-sufficiency on April 28 than 1 kWh.

    April 28 was a very sunny day with >30 kWh solar; a larger battery captures
    more of the daytime surplus for overnight use. The 8-day dataset has no fully
    self-sufficient day even at 20 kWh (night imports exceed battery capacity),
    so we compare the percentage for the best day rather than self_sufficient_days count.
    """
    r1  = simulate_battery(hourly_data, battery_size=1.0)
    r20 = simulate_battery(hourly_data, battery_size=20.0)
    day1  = next(r for r in r1["daily_results"]  if r["date"] == "2026-04-28")
    day20 = next(r for r in r20["daily_results"] if r["date"] == "2026-04-28")
    assert day20["self_sufficiency_pct"] > day1["self_sufficiency_pct"] + 10.0, (
        f"20 kWh battery on April 28 should be >10% better than 1 kWh: "
        f"1kWh={day1['self_sufficiency_pct']:.1f}%, 20kWh={day20['self_sufficiency_pct']:.1f}%"
    )


def test_grid_needed_decreases_with_larger_battery_april28(hourly_data):
    """On April 28, grid_import_needed must fall as battery size grows."""
    prev_grid = float("inf")
    for size in (0.0, 1.0, 5.0, 10.0, 20.0):
        result = simulate_battery(hourly_data, battery_size=size)
        day = next(r for r in result["daily_results"] if r["date"] == "2026-04-28")
        assert day["grid_import_needed"] <= prev_grid + 0.01, (
            f"grid_needed should not increase from {size} kWh: got {day['grid_import_needed']:.2f}"
        )
        prev_grid = day["grid_import_needed"]
