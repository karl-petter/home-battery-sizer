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
            "first_self_sufficient_day": None,
            "last_self_sufficient_day": None,
            "max_consecutive_days": 0,
            "daily_results": [],
        }

    battery_charge = 0.0

    # Accumulators per day
    daily_grid_needed: dict[str, float] = defaultdict(float)
    daily_solar: dict[str, float] = defaultdict(float)
    daily_consumption: dict[str, float] = defaultdict(float)

    for hour in hourly_data:
        date = hour["date"]
        solar = hour["solar_production"]
        grid_import_hist = hour["grid_import"]
        grid_export_hist = hour["grid_export"]

        # Estimate actual consumption this hour from historical meter readings.
        # consumption = solar + grid_import - grid_export
        consumption = max(0.0, solar + grid_import_hist - grid_export_hist)

        # Simulate: solar first covers consumption, surplus charges battery
        if solar >= consumption:
            surplus = solar - consumption
            battery_charge = min(battery_charge + surplus * BATTERY_EFFICIENCY, battery_size)
            grid_needed = 0.0
        else:
            deficit = consumption - solar
            discharge = min(deficit, battery_charge)
            battery_charge -= discharge
            grid_needed = deficit - discharge

        daily_grid_needed[date] += grid_needed
        daily_solar[date] += solar
        daily_consumption[date] += consumption

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

    # Longest consecutive streak of self-sufficient days
    max_consecutive_days = 0
    current_streak = 0
    for day in daily_results:
        if day["self_sufficient"]:
            current_streak += 1
            if current_streak > max_consecutive_days:
                max_consecutive_days = current_streak
        else:
            current_streak = 0

    return {
        "self_sufficient_days": self_sufficient_days,
        "self_sufficiency_yesterday": self_sufficiency_yesterday,
        "self_sufficiency_yesterday_date": self_sufficiency_yesterday_date,
        "first_self_sufficient_day": first_self_sufficient_day,
        "last_self_sufficient_day": last_self_sufficient_day,
        "max_consecutive_days": max_consecutive_days,
        "daily_results": daily_results,
    }
