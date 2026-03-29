"""Tests for config flow."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from custom_components.home_battery_sizer.const import DOMAIN


@pytest.mark.asyncio
async def test_config_flow_user_step(hass: HomeAssistant) -> None:
    """Test initial user config flow step."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "flow_id" in result


@pytest.mark.asyncio
async def test_config_flow_valid_input(hass: HomeAssistant) -> None:
    """Test valid user input submission."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Create mock sensors in hass states
    hass.states.async_set("sensor.solar_production", "0", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.grid_import", "0", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.grid_export", "0", {"unit_of_measurement": "kWh"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "battery_size": 10.0,
        },
    )

    assert result["type"] == "create_entries"
    assert len(result["result"]) == 1
    assert result["result"][0].data["battery_size"] == 10.0


@pytest.mark.asyncio
async def test_config_flow_battery_size_validation(hass: HomeAssistant) -> None:
    """Test battery size validation."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Create mock sensors
    hass.states.async_set("sensor.solar_production", "0")
    hass.states.async_set("sensor.grid_import", "0")
    hass.states.async_set("sensor.grid_export", "0")

    # Test too small battery size
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "battery_size": 0.05,  # Too small, min is 0.1
        },
    )

    # Should return form with error
    assert result["type"] == "form"
    assert "errors" in result


@pytest.mark.asyncio
async def test_config_flow_battery_size_valid_min(hass: HomeAssistant) -> None:
    """Test battery size at minimum valid value."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Create mock sensors
    hass.states.async_set("sensor.solar_production", "0")
    hass.states.async_set("sensor.grid_import", "0")
    hass.states.async_set("sensor.grid_export", "0")

    # Test minimum valid battery size
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "battery_size": 0.1,  # Minimum valid value
        },
    )

    # Should succeed
    assert result["type"] == "create_entries"


@pytest.mark.asyncio
async def test_config_flow_invalid_sensor(hass: HomeAssistant) -> None:
    """Test validation error for nonexistent sensor."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Only create two sensors
    hass.states.async_set("sensor.solar_production", "0")
    hass.states.async_set("sensor.grid_import", "0")
    # grid_export is missing

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.nonexistent_grid_export",  # Invalid
            "battery_size": 10.0,
        },
    )

    # Should show error
    assert result["type"] == "form"
    assert "errors" in result
    assert result["errors"]["base"] == "invalid_sensor"


@pytest.mark.asyncio
async def test_config_flow_float_battery_size(hass: HomeAssistant) -> None:
    """Test battery size accepts float values."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    hass.states.async_set("sensor.solar_production", "0")
    hass.states.async_set("sensor.grid_import", "0")
    hass.states.async_set("sensor.grid_export", "0")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "battery_size": 13.5,  # Float value
        },
    )

    assert result["type"] == "create_entries"
    assert result["result"][0].data["battery_size"] == 13.5
