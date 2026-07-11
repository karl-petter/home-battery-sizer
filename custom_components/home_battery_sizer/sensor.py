"""Sensor platform for Home Battery Sizer integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HomeBatterySizerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: HomeBatterySizerCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    async_add_entities(
        [
            SelfSufficientDaysSensor(coordinator, entry),
            SelfSufficiencyYesterdaySensor(coordinator, entry),
            FirstSelfSufficientDaySensor(coordinator, entry),
            FirstSelfSufficientDaySensor(coordinator, entry, previous_year=True),
            LastSelfSufficientDaySensor(coordinator, entry),
            LastSelfSufficientDaySensor(coordinator, entry, previous_year=True),
            MaxConsecutiveSelfSufficientDaysSensor(coordinator, entry),
            SolarSeasonSpanSensor(coordinator, entry),
            SolarSeasonSpanSensor(coordinator, entry, previous_year=True),
            SelfSufficientPctInSpanSensor(coordinator, entry),
            SelfSufficientPctInSpanSensor(coordinator, entry, previous_year=True),
            BatteryKwhDeliveredSensor(coordinator, entry),
            GridExportKwhSensor(coordinator, entry),
        ]
    )


class BatterySizerSensorBase(CoordinatorEntity):
    """Base class for battery sizer sensors."""

    def __init__(
        self,
        coordinator: HomeBatterySizerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        size = self.coordinator.battery_size
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": f"Home Battery Sizer {size:.0f} kWh",
            "manufacturer": "Home Assistant",
        }


class YearSummarySensorBase(BatterySizerSensorBase, SensorEntity):
    """Base for sensors reading a per-calendar-year season summary.

    All battery sizes summarise the same calendar year, so their values are
    directly comparable. Instantiated once for the current year and once for
    the previous year.
    """

    _base_key: str

    def __init__(self, coordinator, entry, previous_year: bool = False):
        super().__init__(coordinator, entry)
        self._previous_year = previous_year
        suffix = "_prev_year" if previous_year else ""
        self._attr_translation_key = f"{self._base_key}{suffix}"
        self._attr_unique_id = (
            f"home_battery_sizer_{self._base_key}{suffix}_{entry.entry_id}"
        )

    @property
    def _year(self) -> str | None:
        """The calendar year this sensor reports on."""
        if self.coordinator.data is None:
            return None
        key = "previous_year" if self._previous_year else "current_year"
        return self.coordinator.data.get(key)

    @property
    def _summary(self) -> dict[str, Any] | None:
        """The season summary for this sensor's year, or None if no data."""
        if self.coordinator.data is None or self._year is None:
            return None
        return self.coordinator.data.get("years", {}).get(self._year)

    @property
    def extra_state_attributes(self) -> dict:
        return {"year": self._year}


class SelfSufficientDaysSensor(YearSummarySensorBase):
    """Count of self-sufficient days in the current calendar year."""

    _base_key = "self_sufficient_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        summary = self._summary
        if summary is None:
            return None
        return summary.get("self_sufficient_days")

    @property
    def extra_state_attributes(self) -> dict:
        """Expose diagnostic info for verification."""
        if self.coordinator.data is None:
            return {}
        daily = self.coordinator.data.get("daily_results", [])
        years = self.coordinator.data.get("years", {})
        return {
            "year": self._year,
            "days_per_year": {
                year: summary["self_sufficient_days"]
                for year, summary in sorted(years.items())
            },
            "days_of_data": len(daily),
            "data_from": daily[0]["date"] if daily else None,
            "data_to": daily[-1]["date"] if daily else None,
            "battery_size_kwh": self.coordinator.battery_size,
        }


class SelfSufficiencyYesterdaySensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for yesterday's (last complete day's) simulated self-sufficiency."""

    _attr_translation_key = "self_sufficiency_yesterday"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_self_sufficiency_yesterday_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("self_sufficiency_yesterday")

    @property
    def extra_state_attributes(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return {"date": self.coordinator.data.get("self_sufficiency_yesterday_date")}


class FirstSelfSufficientDaySensor(YearSummarySensorBase):
    """Date of the first self-sufficient day in the year."""

    _base_key = "first_self_sufficient_day"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        """Return the date of the first self-sufficient day."""
        summary = self._summary
        if summary is None:
            return None
        value = summary.get("first_self_sufficient_day")
        if value is None:
            return None
        from datetime import date
        return date.fromisoformat(value)


class LastSelfSufficientDaySensor(YearSummarySensorBase):
    """Date of the last self-sufficient day in the year."""

    _base_key = "last_self_sufficient_day"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        """Return the date of the last self-sufficient day."""
        summary = self._summary
        if summary is None:
            return None
        value = summary.get("last_self_sufficient_day")
        if value is None:
            return None
        from datetime import date
        return date.fromisoformat(value)


class MaxConsecutiveSelfSufficientDaysSensor(YearSummarySensorBase):
    """Longest consecutive streak of self-sufficient days in the current year."""

    _base_key = "max_consecutive_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        summary = self._summary
        if summary is None:
            return None
        return summary.get("max_consecutive_days")


class SolarSeasonSpanSensor(YearSummarySensorBase):
    """Calendar days between first and last self-sufficient day of the year."""

    _base_key = "solar_season_span"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        summary = self._summary
        if summary is None:
            return None
        return summary.get("span_days")

    @property
    def extra_state_attributes(self) -> dict:
        summary = self._summary or {}
        return {
            "year": self._year,
            "first_day": summary.get("first_self_sufficient_day"),
            "last_day": summary.get("last_self_sufficient_day"),
        }


class SelfSufficientPctInSpanSensor(YearSummarySensorBase):
    """Percentage of solar-season days that were self-sufficient."""

    _base_key = "self_sufficient_pct_in_span"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        summary = self._summary
        if summary is None:
            return None
        return summary.get("self_sufficient_pct_in_span")

    @property
    def extra_state_attributes(self) -> dict:
        summary = self._summary or {}
        return {
            "year": self._year,
            "self_sufficient_days": summary.get("self_sufficient_days"),
            "span_days": summary.get("span_days"),
        }


class BatteryKwhDeliveredSensor(YearSummarySensorBase):
    """kWh the battery discharged into the house during the current year."""

    _base_key = "battery_kwh_delivered"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self) -> float | None:
        summary = self._summary
        if summary is None:
            return None
        return summary.get("battery_kwh_delivered")


class GridExportKwhSensor(YearSummarySensorBase):
    """kWh exported to the grid during the current year (surplus the battery couldn't store)."""

    _base_key = "grid_export_kwh"
    _attr_state_class = SensorStateClass.TOTAL
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self) -> float | None:
        summary = self._summary
        if summary is None:
            return None
        return summary.get("grid_export_kwh")
