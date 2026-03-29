"""Data coordinator for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .recorder import async_get_daily_energy_data
from .simulation import simulate_battery

_LOGGER = logging.getLogger(__name__)


class HomeBatterySizerCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data and run battery simulation."""

    def __init__(
        self,
        hass: HomeAssistant,
        solar_sensor: str,
        grid_import_sensor: str,
        grid_export_sensor: str,
        battery_size: float,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Home Battery Sizer",
            update_interval=timedelta(hours=1),
        )
        self.solar_sensor = solar_sensor
        self.grid_import_sensor = grid_import_sensor
        self.grid_export_sensor = grid_export_sensor
        self.battery_size = battery_size

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from recorder and run simulation."""
        try:
            # Fetch daily energy data from recorder
            daily_data = await async_get_daily_energy_data(
                self.hass,
                self.solar_sensor,
                self.grid_import_sensor,
                self.grid_export_sensor,
                days=365,
            )

            # Run battery simulation
            result = simulate_battery(daily_data, self.battery_size)

            return result
        except Exception as err:
            _LOGGER.error("Error updating battery sizer data: %s", err)
            raise
