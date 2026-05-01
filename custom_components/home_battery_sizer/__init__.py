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
    CONF_MIN_SOC_PCT,
    CONF_SOLAR_SENSOR,
    CONF_USABLE_CAPACITY_PCT,
    DEFAULT_MIN_SOC_PCT,
    DEFAULT_USABLE_CAPACITY_PCT,
    DOMAIN,
)
from .coordinator import HomeBatterySizerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Home Battery Sizer from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # All numeric settings can be overridden via options after initial setup
    def _get(key, default):
        return entry.options.get(key, entry.data.get(key, default))

    battery_size = _get(CONF_BATTERY_SIZE, 10.0)
    usable_capacity_pct = _get(CONF_USABLE_CAPACITY_PCT, DEFAULT_USABLE_CAPACITY_PCT)
    min_soc_pct = _get(CONF_MIN_SOC_PCT, DEFAULT_MIN_SOC_PCT)

    # Create coordinator
    coordinator = HomeBatterySizerCoordinator(
        hass,
        entry_id=entry.entry_id,
        solar_sensor=entry.data[CONF_SOLAR_SENSOR],
        grid_import_sensor=entry.data[CONF_GRID_IMPORT_SENSOR],
        grid_export_sensor=entry.data[CONF_GRID_EXPORT_SENSOR],
        battery_size=battery_size,
        usable_capacity_pct=usable_capacity_pct,
        min_soc_pct=min_soc_pct,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
