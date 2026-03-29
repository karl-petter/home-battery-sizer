"""Battery simulation engine for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from typing import Any

from .const import BATTERY_EFFICIENCY

_LOGGER = logging.getLogger(__name__)


def simulate_battery(
    daily_data: list[dict[str, Any]],
    battery_size: float,
) -> dict[str, Any]:
    """Simulate battery performance across daily energy data.

    Args:
        daily_data: List of dicts with keys:
            - date: str (YYYY-MM-DD)
            - solar_production: float (kWh)
            - grid_import: float (kWh)
            - grid_export: float (kWh)
        battery_size: Battery capacity in kWh

    Returns:
        Dict with keys:
            - self_sufficient_days: int (count of days with 100% self-sufficiency)
            - self_sufficiency_today: float (percentage 0-100)
            - daily_results: list of dicts with simulation details per day
    """

    if not daily_data:
        _LOGGER.warning("No daily data available for simulation")
        return {
            "self_sufficient_days": 0,
            "self_sufficiency_today": 0.0,
            "daily_results": [],
        }

    battery_charge = 0.0
    self_sufficient_days = 0
    daily_results = []

    for day_data in daily_data:
        solar = day_data["solar_production"]
        grid_import = day_data["grid_import"]
        grid_export = day_data["grid_export"]

        # Calculate total consumption
        total_consumption = solar + grid_import - grid_export

        # Calculate deficit (amount that needs to come from battery or grid)
        deficit = max(0, total_consumption - solar)

        # Simulate battery discharge to cover deficit
        battery_discharge = min(deficit, battery_charge)
        battery_charge -= battery_discharge

        # Remaining deficit after battery discharge must come from grid
        remaining_deficit = deficit - battery_discharge

        # Simulate battery charging from solar surplus
        solar_surplus = max(0, solar - total_consumption)
        # Apply round-trip efficiency when charging
        battery_charge_amount = solar_surplus * BATTERY_EFFICIENCY
        battery_charge = min(battery_charge + battery_charge_amount, battery_size)

        # Check if day achieved 100% self-sufficiency
        # (solar + battery covered all consumption without grid import)
        is_self_sufficient = remaining_deficit == 0 and grid_import == 0

        if is_self_sufficient:
            self_sufficient_days += 1

        daily_results.append({
            "date": day_data["date"],
            "solar_production": round(solar, 3),
            "total_consumption": round(total_consumption, 3),
            "deficit": round(deficit, 3),
            "battery_discharge": round(battery_discharge, 3),
            "battery_charge": round(battery_charge_amount, 3),
            "battery_level": round(battery_charge, 3),
            "grid_import_needed": round(remaining_deficit, 3),
            "self_sufficient": is_self_sufficient,
        })

    # Calculate self-sufficiency for today (last day in data)
    today_index = len(daily_results) - 1
    self_sufficiency_today = 0.0

    if today_index >= 0:
        today = daily_results[today_index]
        total_consumption = today["total_consumption"]
        if total_consumption > 0:
            # Self-sufficiency = (solar + battery) / total_consumption * 100
            solar_contributed = min(total_consumption, today["solar_production"])
            battery_contributed = min(
                total_consumption - solar_contributed, today["battery_discharge"]
            )
            self_sufficiency_percentage = (
                (solar_contributed + battery_contributed) / total_consumption * 100
            )
            self_sufficiency_today = min(100.0, max(0.0, self_sufficiency_percentage))

    return {
        "self_sufficient_days": self_sufficient_days,
        "self_sufficiency_today": round(self_sufficiency_today, 1),
        "daily_results": daily_results,
    }
