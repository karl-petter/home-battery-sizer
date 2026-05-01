"""Data coordinator for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, DEFAULT_USABLE_CAPACITY_PCT, DEFAULT_MIN_SOC_PCT
from .recorder import async_get_hourly_energy_data
from .simulation import simulate_battery

_LOGGER = logging.getLogger(__name__)


class HomeBatterySizerCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data and run battery simulation."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        solar_sensor: str,
        grid_import_sensor: str,
        grid_export_sensor: str,
        battery_size: float,
        usable_capacity_pct: float = DEFAULT_USABLE_CAPACITY_PCT,
        min_soc_pct: float = DEFAULT_MIN_SOC_PCT,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Home Battery Sizer",
            update_interval=timedelta(hours=1),
        )
        self.entry_id = entry_id
        self.solar_sensor = solar_sensor
        self.grid_import_sensor = grid_import_sensor
        self.grid_export_sensor = grid_export_sensor
        self.battery_size = battery_size
        self.usable_capacity_pct = usable_capacity_pct
        self.min_soc_pct = min_soc_pct
        size_slug = f"{battery_size:g}".replace(".", "_")
        self.statistic_id = f"{DOMAIN}:self_sufficiency_daily_{size_slug}kwh"

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

            result = simulate_battery(
                hourly_data,
                self.battery_size,
                usable_capacity_pct=self.usable_capacity_pct,
                min_soc_pct=self.min_soc_pct,
            )

            await self._inject_daily_statistics(result["daily_results"])

            return result
        except Exception as err:
            _LOGGER.error("Error updating battery sizer data: %s", err)
            raise

    async def _inject_daily_statistics(self, daily_results: list[dict[str, Any]]) -> None:
        """Inject per-day self-sufficiency as external HA statistics for historical graphing.

        Covers every calendar day in the full date range, writing 0% for days that
        have no simulation data (e.g. winter days dropped from the sensor intersection).
        This ensures stale values from previous runs are always overwritten.
        """
        if not daily_results:
            return

        try:
            from homeassistant.components.recorder.statistics import (
                async_add_external_statistics,
                StatisticData,
                StatisticMetaData,
                StatisticMeanType,
            )
            from datetime import date, timedelta

            metadata = StatisticMetaData(
                has_mean=True,
                has_sum=False,
                mean_type=StatisticMeanType.ARITHMETIC,
                name=f"Battery sim: daily self-sufficiency ({self.battery_size:.0f} kWh)",
                source=DOMAIN,
                statistic_id=self.statistic_id,
                unit_of_measurement=PERCENTAGE,
            )

            # Build a lookup of simulation results by date
            results_by_date = {day["date"]: day.get("self_sufficiency_pct", 0.0) for day in daily_results}

            # Cover every calendar day from first to last date in range
            first_date = date.fromisoformat(daily_results[0]["date"])
            last_date = date.fromisoformat(daily_results[-1]["date"])

            stat_data = []
            current = first_date
            while current <= last_date:
                date_str = current.isoformat()
                pct = results_by_date.get(date_str, 0.0)
                start = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
                stat_data.append(StatisticData(start=start, mean=pct))
                current += timedelta(days=1)

            async_add_external_statistics(self.hass, metadata, stat_data)
            _LOGGER.info(
                "Injected %d daily stats into %s (battery %.0f kWh)",
                len(stat_data),
                self.statistic_id,
                self.battery_size,
            )

        except Exception:
            _LOGGER.warning("Could not inject daily self-sufficiency statistics", exc_info=True)
