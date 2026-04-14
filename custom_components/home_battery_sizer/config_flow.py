"""Config flow for Home Battery Sizer integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_SIZE,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_SOLAR_SENSOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HomebatterysizeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Battery Sizer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that sensors exist
            try:
                self._validate_sensor(user_input[CONF_SOLAR_SENSOR])
                self._validate_sensor(user_input[CONF_GRID_IMPORT_SENSOR])
                self._validate_sensor(user_input[CONF_GRID_EXPORT_SENSOR])
            except ValueError as err:
                errors["base"] = "invalid_sensor"
                _LOGGER.warning("Invalid sensor: %s", err)
            else:
                return self.async_create_entry(
                    title="Home Battery Sizer",
                    data=user_input,
                )

        # Try to auto-detect sensors from Energy dashboard
        suggested_values = await self._get_energy_dashboard_sensors()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOLAR_SENSOR,
                    description={
                        "suggested_value": suggested_values.get(CONF_SOLAR_SENSOR, "sensor.solar_production"),
                        "description": "Select the cumulative solar energy sensor in kWh.",
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_IMPORT_SENSOR,
                    description={
                        "suggested_value": suggested_values.get(CONF_GRID_IMPORT_SENSOR, "sensor.grid_import"),
                        "description": "Select the cumulative grid import energy sensor in kWh.",
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_EXPORT_SENSOR,
                    description={
                        "suggested_value": suggested_values.get(CONF_GRID_EXPORT_SENSOR, "sensor.grid_export"),
                        "description": "Select the cumulative grid export energy sensor in kWh.",
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_BATTERY_SIZE,
                    description={
                        "suggested_value": 10.0,
                        "description": "Enter the battery capacity estimate in kWh.",
                    },
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    def _validate_sensor(self, sensor_id: str) -> None:
        """Validate that a sensor entity exists."""
        entity_registry = self.hass.data.get("entity_components", {}).get("sensor", None)
        if entity_registry is None:
            # We can't validate without entity registry, but we won't error
            return

        if sensor_id not in self.hass.states.async_entity_ids("sensor"):
            raise ValueError(f"Sensor {sensor_id} not found")

    async def _get_energy_dashboard_sensors(self) -> dict[str, str]:
        """Try to detect sensors from Energy dashboard configuration."""
        suggested = {}

        # Get energy config entries
        energy_entries = self.hass.config_entries.async_entries("energy")
        if not energy_entries:
            return suggested

        # Use the first energy config entry
        energy_config = energy_entries[0].data

        # Extract sensors from energy sources
        energy_sources = energy_config.get("energy_sources", [])

        for source in energy_sources:
            source_type = source.get("type")

            if source_type == "solar":
                # Solar production sensor
                if "entity_id" in source:
                    suggested[CONF_SOLAR_SENSOR] = source["entity_id"]

            elif source_type == "grid":
                # Grid consumption (import) and production (export) sensors
                if "entity_id" in source:
                    suggested[CONF_GRID_IMPORT_SENSOR] = source["entity_id"]
                if "entity_id_production" in source:
                    suggested[CONF_GRID_EXPORT_SENSOR] = source["entity_id_production"]

        return suggested

