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
            LastSelfSufficientDaySensor(coordinator, entry),
            MaxConsecutiveSelfSufficientDaysSensor(coordinator, entry),
            SolarSeasonSpanSensor(coordinator, entry),
            SelfSufficientPctInSpanSensor(coordinator, entry),
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


class SelfSufficientDaysSensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for count of self-sufficient days."""

    _attr_translation_key = "self_sufficient_days"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_self_sufficient_days_{entry.entry_id}"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("self_sufficient_days")

    @property
    def extra_state_attributes(self) -> dict:
        """Expose diagnostic info for verification."""
        if self.coordinator.data is None:
            return {}
        daily = self.coordinator.data.get("daily_results", [])
        return {
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


class FirstSelfSufficientDaySensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for the first self-sufficient day in the past year."""

    _attr_translation_key = "first_self_sufficient_day"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_first_self_sufficient_day_{entry.entry_id}"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        """Return the date of the first self-sufficient day."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get("first_self_sufficient_day")
        if value is None:
            return None
        from datetime import date
        return date.fromisoformat(value)


class LastSelfSufficientDaySensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for the most recent self-sufficient day in the past year."""

    _attr_translation_key = "last_self_sufficient_day"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_last_self_sufficient_day_{entry.entry_id}"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self):
        """Return the date of the last self-sufficient day."""
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get("last_self_sufficient_day")
        if value is None:
            return None
        from datetime import date
        return date.fromisoformat(value)


class MaxConsecutiveSelfSufficientDaysSensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for the longest consecutive streak of self-sufficient days."""

    _attr_translation_key = "max_consecutive_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_max_consecutive_days_{entry.entry_id}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("max_consecutive_days")


class SolarSeasonSpanSensor(BatterySizerSensorBase, SensorEntity):
    """Calendar days between first and last self-sufficient day."""

    _attr_translation_key = "solar_season_span"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_solar_season_span_{entry.entry_id}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("span_days")

    @property
    def extra_state_attributes(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return {
            "first_day": self.coordinator.data.get("first_self_sufficient_day"),
            "last_day": self.coordinator.data.get("last_self_sufficient_day"),
        }


class SelfSufficientPctInSpanSensor(BatterySizerSensorBase, SensorEntity):
    """Percentage of solar-season days that were self-sufficient."""

    _attr_translation_key = "self_sufficient_pct_in_span"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_self_sufficient_pct_in_span_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("self_sufficient_pct_in_span")

    @property
    def extra_state_attributes(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return {
            "self_sufficient_days": self.coordinator.data.get("self_sufficient_days"),
            "span_days": self.coordinator.data.get("span_days"),
        }


class BatteryKwhDeliveredSensor(BatterySizerSensorBase, SensorEntity):
    """kWh the battery discharged into the house during the solar season."""

    _attr_translation_key = "battery_kwh_delivered"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_battery_kwh_delivered_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("battery_kwh_delivered")


class GridExportKwhSensor(BatterySizerSensorBase, SensorEntity):
    """kWh exported to the grid during the solar season (surplus the battery couldn't store)."""

    _attr_translation_key = "grid_export_kwh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"home_battery_sizer_grid_export_kwh_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("grid_export_kwh")
