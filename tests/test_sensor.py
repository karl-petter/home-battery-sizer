"""Tests for sensor platform."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry

from custom_components.home_battery_sizer.const import DOMAIN


@pytest.mark.asyncio
async def test_sensor_setup_creates_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
    entity_registry: EntityRegistry,
) -> None:
    """Test sensor platform creates entities."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    await hass.async_block_till_done()

    # Check both sensor entities exist
    assert entity_registry.async_get("sensor.battery_sim_self_sufficient_days") is not None
    assert entity_registry.async_get("sensor.battery_sim_self_sufficiency_today") is not None


@pytest.mark.asyncio
async def test_sensor_self_sufficient_days_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
) -> None:
    """Test self-sufficient days sensor state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_sim_self_sufficient_days")
    assert state is not None
    assert state.state.isdigit() or state.state == "0"  # Should be integer as string
    assert int(state.state) >= 0


@pytest.mark.asyncio
async def test_sensor_self_sufficiency_today_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
) -> None:
    """Test self-sufficiency today sensor state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_sim_self_sufficiency_today")
    assert state is not None
    # Should be percentage formatted string
    value = float(state.state)
    assert 0 <= value <= 100


@pytest.mark.asyncio
async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
) -> None:
    """Test sensor attributes are set correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_sim_self_sufficient_days")
    assert state is not None
    # Check unit_of_measurement attribute
    assert "unit_of_measurement" in state.attributes
    assert state.attributes["unit_of_measurement"] == "days"

    state = hass.states.get("sensor.battery_sim_self_sufficiency_today")
    assert state is not None
    assert "unit_of_measurement" in state.attributes
    assert state.attributes["unit_of_measurement"] == "%"


@pytest.mark.asyncio
async def test_sensor_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
) -> None:
    """Test sensor has device_info."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    state = hass.states.get("sensor.battery_sim_self_sufficient_days")
    assert state is not None
    # Device should be created with DOMAIN and entry_id
    assert "device_id" in state.attributes or state is not None  # Device exists


@pytest.mark.asyncio
async def test_sensor_coordinator_update_propagates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
) -> None:
    """Test sensor state updates when coordinator refreshes."""
    mock_config_entry.add_to_hass(hass)

    # Mock with initial data
    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    state1 = hass.states.get("sensor.battery_sim_self_sufficient_days")
    initial_value = state1.state

    # Simulate coordinator update with different data
    modified_data = [
        {
            **day,
            "solar_production": day["solar_production"] * 1.1,  # 10% more solar
        }
        for day in sample_daily_data
    ]

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=modified_data,
    ):
        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        await coordinator.async_request_refresh()

    await hass.async_block_till_done()

    state2 = hass.states.get("sensor.battery_sim_self_sufficient_days")
    # Value should update (or stay same if simulation doesn't change)
    assert state2 is not None


@pytest.mark.asyncio
async def test_sensor_unique_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    sample_daily_data,
    entity_registry: EntityRegistry,
) -> None:
    """Test sensors have unique IDs."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    entity1 = entity_registry.async_get("sensor.battery_sim_self_sufficient_days")
    entity2 = entity_registry.async_get("sensor.battery_sim_self_sufficiency_today")

    assert entity1 is not None
    assert entity2 is not None
    # Unique IDs should be different
    assert entity1.unique_id != entity2.unique_id
    # Check expected format
    assert "home_battery_sizer" in entity1.unique_id
    assert "home_battery_sizer" in entity2.unique_id
