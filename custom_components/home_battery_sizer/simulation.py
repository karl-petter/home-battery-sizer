"""Battery simulation engine for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from .const import BATTERY_EFFICIENCY

_LOGGER = logging.getLogger(__name__)


def simulate_battery(
    hourly_data: list[dict[str, Any]],
    battery_size: float,
    usable_capacity_pct: float = 90.0,
    min_soc_pct: float = 5.0,
) -> dict[str, Any]:
    """Simulate battery performance across hourly energy data.

    Works hour by hour so that the nightly discharge (no solar) and daytime
    charging are modelled correctly. Daily totals are insufficient because
    solar only produces during daylight hours.

    Args:
        hourly_data: List of dicts with keys:
            - datetime: str (ISO, hour start)
            - date: str (YYYY-MM-DD)
            - solar_production: float (kWh this hour)
            - grid_import: float (kWh this hour, historical — used to estimate consumption)
            - grid_export: float (kWh this hour, historical)
        battery_size: Battery capacity in kWh (0 = no battery)

    Returns:
        Dict with simulation results including per-day self-sufficiency.
    """
    if not hourly_data:
        _LOGGER.warning("No hourly data available for simulation")
        return {
            "self_sufficient_days": 0,
            "self_sufficiency_yesterday": 0.0,
            "self_sufficiency_yesterday_date": None,
            "current_year": None,
            "previous_year": None,
            "years": {},
            "daily_results": [],
        }

    effective_max = battery_size * (usable_capacity_pct / 100)
    effective_min = battery_size * (min_soc_pct / 100)
    battery_charge = effective_min

    # Accumulators per day
    daily_grid_needed: dict[str, float] = defaultdict(float)
    daily_solar: dict[str, float] = defaultdict(float)
    daily_consumption: dict[str, float] = defaultdict(float)
    daily_battery_delivered: dict[str, float] = defaultdict(float)
    daily_grid_export: dict[str, float] = defaultdict(float)

    for hour in hourly_data:
        date = hour["date"]
        solar = hour["solar_production"]
        grid_import_hist = hour["grid_import"]
        grid_export_hist = hour["grid_export"]

        # Estimate actual consumption this hour from historical meter readings.
        # consumption = solar + grid_import - grid_export
        consumption = max(0.0, solar + grid_import_hist - grid_export_hist)

        # Simulate: solar first covers consumption, surplus charges the battery,
        # and whatever the battery can't accept is exported to the grid.
        if solar >= consumption:
            surplus = solar - consumption
            stored = min(surplus * BATTERY_EFFICIENCY, effective_max - battery_charge)
            battery_charge += stored
            # Charging draws stored/efficiency from the surplus; the rest is
            # simulated export — surplus that didn't fit in the battery.
            sim_export = max(0.0, surplus - stored / BATTERY_EFFICIENCY)
            grid_needed = 0.0
            discharge = 0.0
        else:
            deficit = consumption - solar
            available = max(0.0, battery_charge - effective_min)
            discharge = min(deficit, available)
            battery_charge -= discharge
            grid_needed = deficit - discharge
            sim_export = 0.0

        daily_grid_needed[date] += grid_needed
        daily_solar[date] += solar
        daily_consumption[date] += consumption
        daily_battery_delivered[date] += discharge
        daily_grid_export[date] += sim_export

    # Build daily results
    self_sufficient_days = 0
    first_self_sufficient_day: str | None = None
    last_self_sufficient_day: str | None = None
    daily_results = []

    for date in sorted(daily_grid_needed):
        grid_needed = daily_grid_needed[date]
        consumption = daily_consumption[date]

        is_self_sufficient = grid_needed < 0.01  # small epsilon for floating point

        if consumption > 0:
            ss_pct = round(min(100.0, (consumption - grid_needed) / consumption * 100), 1)
        else:
            ss_pct = 100.0

        if is_self_sufficient:
            self_sufficient_days += 1
            if first_self_sufficient_day is None:
                first_self_sufficient_day = date
            last_self_sufficient_day = date

        daily_results.append({
            "date": date,
            "solar_production": round(daily_solar[date], 3),
            "total_consumption": round(consumption, 3),
            "grid_import_needed": round(grid_needed, 3),
            "battery_kwh_delivered": round(daily_battery_delivered[date], 3),
            "grid_export_kwh": round(daily_grid_export[date], 3),
            "self_sufficient": is_self_sufficient,
            "self_sufficiency_pct": ss_pct,
        })

    # Last complete day's self-sufficiency.
    # The final entry in daily_results is always a partial day (the current calendar
    # day in long-term statistics). Use the second-to-last entry so we always report
    # a full 24-hour day. Fall back to the last entry if there's only one day.
    if len(daily_results) >= 2:
        last_complete = daily_results[-2]
    elif daily_results:
        last_complete = daily_results[-1]
    else:
        last_complete = None

    self_sufficiency_yesterday = last_complete["self_sufficiency_pct"] if last_complete else 0.0
    self_sufficiency_yesterday_date = last_complete["date"] if last_complete else None

    # Per-calendar-year season summaries. A Northern Hemisphere solar season sits
    # inside one calendar year, so first/last self-sufficient day and span stay
    # meaningful, and every battery size is summarised over the same windows —
    # directly comparable.
    days_by_year: dict[str, list[dict]] = {}
    for day in daily_results:
        days_by_year.setdefault(day["date"][:4], []).append(day)

    years = {year: _year_summary(days) for year, days in days_by_year.items()}

    current_year = daily_results[-1]["date"][:4]
    previous_year = str(int(current_year) - 1)

    return {
        "self_sufficient_days": self_sufficient_days,
        "self_sufficiency_yesterday": self_sufficiency_yesterday,
        "self_sufficiency_yesterday_date": self_sufficiency_yesterday_date,
        "current_year": current_year,
        "previous_year": previous_year,
        "years": years,
        "daily_results": daily_results,
    }


def _year_summary(days: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise one calendar year of daily simulation results."""
    ss_days = [day["date"] for day in days if day["self_sufficient"]]

    max_consecutive_days = 0
    current_streak = 0
    for day in days:
        if day["self_sufficient"]:
            current_streak += 1
            if current_streak > max_consecutive_days:
                max_consecutive_days = current_streak
        else:
            current_streak = 0

    # Energy-based self-sufficiency: share of the year's consumption covered by
    # solar + battery. Monotone in battery size — the headline sizing metric.
    consumption_kwh = sum(d["total_consumption"] for d in days)
    grid_import_kwh = sum(d["grid_import_needed"] for d in days)
    if consumption_kwh > 0:
        energy_self_sufficiency_pct = round(
            (consumption_kwh - grid_import_kwh) / consumption_kwh * 100, 1
        )
    else:
        energy_self_sufficiency_pct = 100.0

    return {
        "self_sufficient_days": len(ss_days),
        "days_with_data": len(days),
        "energy_self_sufficiency_pct": energy_self_sufficiency_pct,
        "consumption_kwh": round(consumption_kwh, 1),
        "grid_import_kwh": round(grid_import_kwh, 1),
        "first_self_sufficient_day": ss_days[0] if ss_days else None,
        "last_self_sufficient_day": ss_days[-1] if ss_days else None,
        "max_consecutive_days": max_consecutive_days,
        "battery_kwh_delivered": round(sum(d["battery_kwh_delivered"] for d in days), 1),
        "grid_export_kwh": round(sum(d["grid_export_kwh"] for d in days), 1),
    }
