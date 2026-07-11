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
        self.battery_delivered_statistic_id = f"{DOMAIN}:battery_delivered_daily_{size_slug}kwh"
        self.ss_days_statistic_id = f"{DOMAIN}:self_sufficient_days_{size_slug}kwh"
        # Consumption and direct solar use don't vary by battery size — shared statistic IDs.
        self.consumption_statistic_id = f"{DOMAIN}:consumption_daily"
        self.direct_use_statistic_id = f"{DOMAIN}:solar_direct_use_daily"
        self._bd_metadata_checked = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from recorder and run simulation."""
        try:
            hourly_data = await async_get_hourly_energy_data(
                self.hass,
                self.solar_sensor,
                self.grid_import_sensor,
                self.grid_export_sensor,
                # Two years back so the previous calendar year is fully covered
                # for the per-year season sensors.
                days=730,
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
            from homeassistant.components.recorder import get_instance
            from homeassistant.components.recorder.statistics import (
                async_add_external_statistics,
                StatisticData,
                StatisticMetaData,
                StatisticMeanType,
            )
            from homeassistant.components.recorder.tasks import ClearStatisticsTask
            from datetime import date, timedelta

            if not self._bd_metadata_checked:
                self._bd_metadata_checked = True
                # Clear once per coordinator lifetime so stale mean-only metadata is
                # removed and recreated correctly with has_sum=True below.
                # queue_task is the async-safe way to enqueue recorder work in HA 2026.4.
                get_instance(self.hass).queue_task(
                    ClearStatisticsTask(
                        on_done=None,
                        statistic_ids=[self.battery_delivered_statistic_id],
                    )
                )
                _LOGGER.info("Cleared %s for metadata migration", self.battery_delivered_statistic_id)

            metadata = StatisticMetaData(
                has_mean=True,
                has_sum=False,
                mean_type=StatisticMeanType.ARITHMETIC,
                name=f"Battery sim: daily self-sufficiency ({self.battery_size:.0f} kWh)",
                source=DOMAIN,
                statistic_id=self.statistic_id,
                unit_of_measurement=PERCENTAGE,
            )

            # battery_delivered is sum-based (running cumulative total) so that
            # stat_types: [change] works in statistics-graph alongside actual
            # cumulative energy sensors. mean_type=NONE signals no mean is stored.
            metadata_bd = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name=f"Battery sim: daily battery delivered ({self.battery_size:.0f} kWh)",
                source=DOMAIN,
                statistic_id=self.battery_delivered_statistic_id,
                unit_of_measurement="kWh",
                unit_class=None,
            )

            # Cumulative count of self-sufficient days. Sum-based so a statistics
            # card with stat_types: [change] shows the count for any period the
            # user selects (month, year, ...), Energy-dashboard style.
            metadata_ss_days = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name=f"Battery sim: self-sufficient days ({self.battery_size:.0f} kWh)",
                source=DOMAIN,
                statistic_id=self.ss_days_statistic_id,
                unit_of_measurement="days",
                unit_class=None,
            )

            metadata_consumption = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name="Battery sim: daily house consumption",
                source=DOMAIN,
                statistic_id=self.consumption_statistic_id,
                unit_of_measurement="kWh",
                unit_class=None,
            )

            # Solar consumed directly (production minus surplus) — battery-
            # independent, shared across entries. Enables stacked "where does
            # the production go" cards: direct use + battery delivered + export.
            metadata_direct = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                mean_type=StatisticMeanType.NONE,
                name="Battery sim: daily solar direct use",
                source=DOMAIN,
                statistic_id=self.direct_use_statistic_id,
                unit_of_measurement="kWh",
                unit_class=None,
            )

            # Build lookups of simulation results by date
            ss_by_date = {day["date"]: day.get("self_sufficiency_pct", 0.0) for day in daily_results}
            bd_by_date = {day["date"]: day.get("battery_kwh_delivered", 0.0) for day in daily_results}
            cons_by_date = {day["date"]: day.get("total_consumption", 0.0) for day in daily_results}
            ss_flag_by_date = {day["date"]: day.get("self_sufficient", False) for day in daily_results}
            direct_by_date = {
                day["date"]: max(0.0, day.get("solar_production", 0.0) - day.get("solar_surplus_kwh", 0.0))
                for day in daily_results
            }

            # Cover every calendar day from first to last date in range
            first_date = date.fromisoformat(daily_results[0]["date"])
            last_date = date.fromisoformat(daily_results[-1]["date"])

            stat_data = []
            stat_data_bd = []
            stat_data_cons = []
            stat_data_ss_days = []
            stat_data_direct = []
            bd_cumsum = 0.0
            cons_cumsum = 0.0
            ss_days_cumsum = 0
            direct_cumsum = 0.0
            current = first_date
            while current <= last_date:
                date_str = current.isoformat()
                start = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
                stat_data.append(StatisticData(start=start, mean=ss_by_date.get(date_str, 0.0)))
                bd_cumsum += bd_by_date.get(date_str, 0.0)
                stat_data_bd.append(StatisticData(start=start, sum=round(bd_cumsum, 3)))
                cons_cumsum += cons_by_date.get(date_str, 0.0)
                stat_data_cons.append(StatisticData(start=start, sum=round(cons_cumsum, 3)))
                if ss_flag_by_date.get(date_str, False):
                    ss_days_cumsum += 1
                stat_data_ss_days.append(StatisticData(start=start, sum=ss_days_cumsum))
                direct_cumsum += direct_by_date.get(date_str, 0.0)
                stat_data_direct.append(StatisticData(start=start, sum=round(direct_cumsum, 3)))
                current += timedelta(days=1)

            async_add_external_statistics(self.hass, metadata, stat_data)
            async_add_external_statistics(self.hass, metadata_bd, stat_data_bd)
            async_add_external_statistics(self.hass, metadata_consumption, stat_data_cons)
            async_add_external_statistics(self.hass, metadata_ss_days, stat_data_ss_days)
            async_add_external_statistics(self.hass, metadata_direct, stat_data_direct)
            _LOGGER.info(
                "Injected %d daily stats for battery %.0f kWh",
                len(stat_data),
                self.battery_size,
            )

        except Exception:
            _LOGGER.warning("Could not inject daily self-sufficiency statistics", exc_info=True)
