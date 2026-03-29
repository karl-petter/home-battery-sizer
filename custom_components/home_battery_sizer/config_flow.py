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

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SOLAR_SENSOR,
                    description={"suggested_value": "sensor.solar_production"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_IMPORT_SENSOR,
                    description={"suggested_value": "sensor.grid_import"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_EXPORT_SENSOR,
                    description={"suggested_value": "sensor.grid_export"},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_BATTERY_SIZE,
                    description={"suggested_value": 10.0},
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

