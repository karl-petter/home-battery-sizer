"""Recorder query functionality for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_get_hourly_energy_data(
    hass: HomeAssistant,
    solar_sensor: str,
    grid_import_sensor: str,
    grid_export_sensor: str,
    days: int = 365,
) -> list[dict[str, Any]]:
    """Fetch hourly energy data from long-term statistics for the past N days.

    Returns hourly deltas so the simulation can model the battery charging
    during daylight and discharging at night — daily totals are not sufficient
    because solar production is zero at night.

    Returns a list of dicts with keys:
    - datetime: str (ISO format, hour start)
    - date: str (YYYY-MM-DD, for grouping by day)
    - solar_production: float (kWh this hour)
    - grid_import: float (kWh this hour)
    - grid_export: float (kWh this hour)
    """
    from homeassistant.components.recorder import get_instance
    from homeassistant.components.recorder.statistics import (
        statistics_during_period,
        list_statistic_ids,
    )

    start_time = datetime.now(timezone.utc) - timedelta(days=days + 1)
    end_time = datetime.now(timezone.utc)
    statistic_ids = {solar_sensor, grid_import_sensor, grid_export_sensor}

    def _fetch():
        stats = statistics_during_period(
            hass,
            start_time,
            end_time,
            statistic_ids,
            "hour",
            None,
            {"sum"},
        )
        # Fetch units so we can normalise Wh → kWh if needed
        meta = list_statistic_ids(hass, statistic_ids=statistic_ids)
        units = {m["statistic_id"]: m.get("unit_of_measurement", "kWh") for m in meta}
        return stats, units

    instance = get_instance(hass)
    stats, units = await instance.async_add_executor_job(_fetch)

    solar_unit = units.get(solar_sensor, "kWh")

    return _process_statistics(
        stats,
        solar_sensor,
        grid_import_sensor,
        grid_export_sensor,
        solar_wh=(solar_unit == "Wh"),
    )


def _process_statistics(
    stats: dict[str, list],
    solar_sensor: str,
    grid_import_sensor: str,
    grid_export_sensor: str,
    solar_wh: bool = False,
) -> list[dict[str, Any]]:
    """Convert hourly cumulative statistics into per-hour energy deltas.

    Grid import and export sensors are used as the authoritative hour set because
    they record every hour (including at night). Solar is filled with 0 for hours
    where the inverter pushes no statistics (typically overnight).
    """

    def _to_hour_sum(stat_list: list) -> dict[datetime, float]:
        result: dict[datetime, float] = {}
        for entry in stat_list:
            if isinstance(entry, dict):
                start = entry.get("start")
                total = entry.get("sum")
            else:
                start = getattr(entry, "start", None)
                total = getattr(entry, "sum", None)

            if start is None or total is None:
                continue

            if not isinstance(start, datetime):
                start = datetime.fromtimestamp(float(start), tz=timezone.utc)

            result[start] = float(total)
        return result

    solar_by_hour = _to_hour_sum(stats.get(solar_sensor, []))
    import_by_hour = _to_hour_sum(stats.get(grid_import_sensor, []))
    export_by_hour = _to_hour_sum(stats.get(grid_export_sensor, []))

    if not (import_by_hour and export_by_hour):
        _LOGGER.warning(
            "No long-term statistics found for grid sensors. "
            "Make sure the sensors have state_class: total_increasing and have been running long enough."
        )
        return []

    if not solar_by_hour:
        _LOGGER.warning("No long-term statistics found for solar sensor.")
        return []

    if solar_wh:
        _LOGGER.info("Solar sensor unit is Wh — converting to kWh")

    # Use import+export as the authoritative hour set (they record every hour).
    # Solar is missing at night; fill those hours with 0 using the last known
    # cumulative value so the delta comes out as 0.
    base_hours = sorted(set(import_by_hour) & set(export_by_hour))

    _LOGGER.info(
        "Base hours from grid sensors: %d (%.1f days); solar has %d distinct hours",
        len(base_hours),
        len(base_hours) / 24,
        len(solar_by_hour),
    )

    # Fill solar gaps: carry the last known cumulative forward for night hours.
    last_solar_sum = None
    solar_filled: dict[datetime, float] = {}
    for hour in base_hours:
        if hour in solar_by_hour:
            last_solar_sum = solar_by_hour[hour]
        if last_solar_sum is not None:
            solar_filled[hour] = last_solar_sum
        # Hours before the first solar reading are left out of solar_filled;
        # they will be treated as 0 production.

    hourly_data = []
    for i in range(1, len(base_hours)):
        this_hour = base_hours[i]
        prev_hour = base_hours[i - 1]

        solar_this = solar_filled.get(this_hour, 0.0)
        solar_prev = solar_filled.get(prev_hour, 0.0)
        solar_delta = max(0.0, solar_this - solar_prev)

        if solar_wh:
            solar_delta /= 1000.0

        grid_import = max(0.0, import_by_hour[this_hour] - import_by_hour[prev_hour])
        grid_export = max(0.0, export_by_hour[this_hour] - export_by_hour[prev_hour])

        hourly_data.append({
            "datetime": this_hour.isoformat(),
            "date": this_hour.date().isoformat(),
            "solar_production": round(solar_delta, 4),
            "grid_import": round(grid_import, 4),
            "grid_export": round(grid_export, 4),
        })

    return hourly_data
