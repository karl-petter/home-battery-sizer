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

    @staticmethod
    @config_entries.callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return HomeBatterySizerOptionsFlow(config_entry)

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
                        "suggested_value": suggested_values.get(CONF_SOLAR_SENSOR),
                        "description": "Select the cumulative solar energy sensor in kWh.",
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_IMPORT_SENSOR,
                    description={
                        "suggested_value": suggested_values.get(CONF_GRID_IMPORT_SENSOR),
                        "description": "Select the cumulative grid import energy sensor in kWh.",
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_GRID_EXPORT_SENSOR,
                    description={
                        "suggested_value": suggested_values.get(CONF_GRID_EXPORT_SENSOR),
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
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
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

        try:
            import json

            storage_path = self.hass.config.path(".storage/energy")

            def _read_storage():
                with open(storage_path) as f:
                    return json.load(f)

            storage = await self.hass.async_add_executor_job(_read_storage)
            sources = storage.get("data", {}).get("energy_sources", [])
            _LOGGER.debug("Energy sources found: %s", sources)

            for source in sources:
                source_type = source.get("type")

                if source_type == "solar":
                    stat = source.get("stat_energy_from")
                    if stat:
                        suggested[CONF_SOLAR_SENSOR] = stat
                        _LOGGER.debug("Auto-detected solar sensor: %s", stat)

                elif source_type == "grid":
                    stat = source.get("stat_energy_from")
                    if stat:
                        suggested[CONF_GRID_IMPORT_SENSOR] = stat
                        _LOGGER.debug("Auto-detected grid import sensor: %s", stat)

                    stat = source.get("stat_energy_to")
                    if stat:
                        suggested[CONF_GRID_EXPORT_SENSOR] = stat
                        _LOGGER.debug("Auto-detected grid export sensor: %s", stat)

        except Exception:
            _LOGGER.warning("Could not read Energy dashboard configuration", exc_info=True)

        if not suggested:
            _LOGGER.warning("No sensors auto-detected from Energy dashboard")
        else:
            _LOGGER.info("Auto-detected sensors: %s", suggested)

        return suggested


class HomeBatterySizerOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Home Battery Sizer (allows changing battery size after setup)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_size = self._config_entry.options.get(
            CONF_BATTERY_SIZE,
            self._config_entry.data.get(CONF_BATTERY_SIZE, 10.0),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BATTERY_SIZE, default=current_size): vol.All(
                        vol.Coerce(float), vol.Range(min=0)
                    ),
                }
            ),
        )

