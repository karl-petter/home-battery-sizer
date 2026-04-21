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
    from homeassistant.components.recorder.statistics import statistics_during_period

    start_time = datetime.now(timezone.utc) - timedelta(days=days + 1)
    end_time = datetime.now(timezone.utc)
    statistic_ids = {solar_sensor, grid_import_sensor, grid_export_sensor}

    def _fetch() -> dict[str, list]:
        return statistics_during_period(
            hass,
            start_time,
            end_time,
            statistic_ids,
            "hour",
            None,
            {"sum"},
        )

    instance = get_instance(hass)
    stats = await instance.async_add_executor_job(_fetch)

    return _process_statistics(stats, solar_sensor, grid_import_sensor, grid_export_sensor)


def _process_statistics(
    stats: dict[str, list],
    solar_sensor: str,
    grid_import_sensor: str,
    grid_export_sensor: str,
) -> list[dict[str, Any]]:
    """Convert hourly cumulative statistics into per-hour energy deltas."""

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

    if not (solar_by_hour and import_by_hour and export_by_hour):
        _LOGGER.warning(
            "No long-term statistics found for energy sensors. "
            "Make sure the sensors have state_class: total_increasing and have been running long enough."
        )
        return []

    common_hours = sorted(
        set(solar_by_hour) & set(import_by_hour) & set(export_by_hour)
    )
    _LOGGER.info(
        "Hourly data points for all three sensors: %d (%.1f days)",
        len(common_hours),
        len(common_hours) / 24,
    )

    hourly_data = []
    for i in range(1, len(common_hours)):
        this_hour = common_hours[i]
        prev_hour = common_hours[i - 1]

        solar = max(0.0, solar_by_hour[this_hour] - solar_by_hour[prev_hour])
        grid_import = max(0.0, import_by_hour[this_hour] - import_by_hour[prev_hour])
        grid_export = max(0.0, export_by_hour[this_hour] - export_by_hour[prev_hour])

        hourly_data.append({
            "datetime": this_hour.isoformat(),
            "date": this_hour.date().isoformat(),
            "solar_production": solar,
            "grid_import": grid_import,
            "grid_export": grid_export,
        })

    return hourly_data
