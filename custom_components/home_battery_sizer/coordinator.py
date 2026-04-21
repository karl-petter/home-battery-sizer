"""Data coordinator for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .recorder import async_get_hourly_energy_data
from .simulation import simulate_battery

_LOGGER = logging.getLogger(__name__)

STATISTIC_ID = f"{DOMAIN}:self_sufficiency_daily"


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
            hourly_data = await async_get_hourly_energy_data(
                self.hass,
                self.solar_sensor,
                self.grid_import_sensor,
                self.grid_export_sensor,
                days=365,
            )

            result = simulate_battery(hourly_data, self.battery_size)

            await self._inject_daily_statistics(result["daily_results"])

            return result
        except Exception as err:
            _LOGGER.error("Error updating battery sizer data: %s", err)
            raise

    async def _inject_daily_statistics(self, daily_results: list[dict[str, Any]]) -> None:
        """Inject per-day self-sufficiency as external HA statistics for historical graphing."""
        if not daily_results:
            return

        try:
            from homeassistant.components.recorder.statistics import (
                async_add_external_statistics,
                StatisticData,
                StatisticMetaData,
            )

            metadata = StatisticMetaData(
                has_mean=True,
                has_sum=False,
                name="Battery sim: daily self-sufficiency",
                source=DOMAIN,
                statistic_id=STATISTIC_ID,
                unit_of_measurement=PERCENTAGE,
            )

            stat_data = []
            for day in daily_results:
                d = datetime.fromisoformat(day["date"])
                start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
                stat_data.append(
                    StatisticData(
                        start=start,
                        mean=day.get("self_sufficiency_pct", 0.0),
                    )
                )

            async_add_external_statistics(self.hass, metadata, stat_data)

        except Exception:
            _LOGGER.warning("Could not inject daily self-sufficiency statistics", exc_info=True)
