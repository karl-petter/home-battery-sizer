"""The Home Battery Sizer integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_BATTERY_SIZE,
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_SOLAR_SENSOR,
    DOMAIN,
)
from .coordinator import HomeBatterySizerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Battery Sizer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create coordinator
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor=entry.data[CONF_SOLAR_SENSOR],
        grid_import_sensor=entry.data[CONF_GRID_IMPORT_SENSOR],
        grid_export_sensor=entry.data[CONF_GRID_EXPORT_SENSOR],
        battery_size=entry.data[CONF_BATTERY_SIZE],
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
