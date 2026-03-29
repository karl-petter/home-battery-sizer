"""Recorder query functionality for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components import recorder
from homeassistant.components.recorder.models import StatisticData
from sqlalchemy import func

_LOGGER = logging.getLogger(__name__)


async def async_get_daily_energy_data(
    hass: HomeAssistant,
    solar_sensor: str,
    grid_import_sensor: str,
    grid_export_sensor: str,
    days: int = 365,
) -> list[dict[str, Any]]:
    """Fetch daily energy data from recorder for the past N days.

    Returns a list of dicts with keys:
    - date: str (YYYY-MM-DD)
    - solar_production: float (kWh, difference from previous day)
    - grid_import: float (kWh, difference from previous day)
    - grid_export: float (kWh, difference from previous day)
    """

    def _get_history() -> list[dict[str, Any]]:
        """Query history from recorder database."""
        from homeassistant.components.recorder import history

        start_time = datetime.now() - timedelta(days=days)
        end_time = datetime.now()

        # Fetch history for all three sensors
        solar_history = history.get_significant_states(
            hass, start_time, end_time, entity_ids=[solar_sensor]
        ).get(solar_sensor, [])

        grid_import_history = history.get_significant_states(
            hass, start_time, end_time, entity_ids=[grid_import_sensor]
        ).get(grid_import_sensor, [])

        grid_export_history = history.get_significant_states(
            hass, start_time, end_time, entity_ids=[grid_export_sensor]
        ).get(grid_export_sensor, [])

        # Process history and calculate daily differences
        daily_data = _process_history(
            solar_history, grid_import_history, grid_export_history
        )

        return daily_data

    # Run the blocking query in the recorder's executor
    return await hass.async_add_executor_job(_get_history)


def _process_history(
    solar_history: list[dict[str, Any]],
    grid_import_history: list[dict[str, Any]],
    grid_export_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Process raw history data and calculate daily differences."""

    # Convert history to dict with datetime as key for easier lookups
    def _to_dict(history: list[dict[str, Any]]) -> dict[datetime, float]:
        result = {}
        for state in history:
            try:
                dt = state.last_changed if hasattr(state, 'last_changed') else state.get('last_changed')
                value = float(state.state if hasattr(state, 'state') else state.get('state', 0))
                if dt and value is not None:
                    result[dt] = value
            except (ValueError, TypeError):
                pass
        return result

    solar_dict = _to_dict(solar_history)
    import_dict = _to_dict(grid_import_history)
    export_dict = _to_dict(grid_export_history)

    if not (solar_dict and import_dict and export_dict):
        _LOGGER.warning("Incomplete sensor history available")
        return []

    # Get all unique dates
    all_datetimes = set(solar_dict.keys()) | set(import_dict.keys()) | set(export_dict.keys())
    sorted_datetimes = sorted(all_datetimes)

    # Calculate daily differences
    daily_data = []
    prev_solar = None
    prev_import = None
    prev_export = None

    for dt in sorted_datetimes:
        solar_value = solar_dict.get(dt, prev_solar)
        import_value = import_dict.get(dt, prev_import)
        export_value = export_dict.get(dt, prev_export)

        if prev_solar is not None and prev_import is not None and prev_export is not None:
            # Calculate daily differences
            solar_production = max(0, solar_value - prev_solar)
            grid_import = max(0, import_value - prev_import)
            grid_export = max(0, export_value - prev_export)

            daily_data.append({
                "date": dt.date().isoformat(),
                "solar_production": solar_production,
                "grid_import": grid_import,
                "grid_export": grid_export,
            })

        prev_solar = solar_value
        prev_import = import_value
        prev_export = export_value

    return daily_data
