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
            SelfSufficiencyTodaySensor(coordinator, entry),
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
        return {
            "identifiers": {(DOMAIN, self.entry.entry_id)},
            "name": "Home Battery Sizer",
            "manufacturer": "Home Assistant",
        }


class SelfSufficientDaysSensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for count of self-sufficient days."""

    _attr_unique_id = "home_battery_sizer_self_sufficient_days"
    _attr_translation_key = "self_sufficient_days"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "days"

    @property
    def native_value(self) -> int | None:
        """Return the value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("self_sufficient_days")


class SelfSufficiencyTodaySensor(BatterySizerSensorBase, SensorEntity):
    """Sensor for today's self-sufficiency percentage."""

    _attr_unique_id = "home_battery_sizer_self_sufficiency_today"
    _attr_translation_key = "self_sufficiency_today"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self) -> float | None:
        """Return the value of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("self_sufficiency_today")
