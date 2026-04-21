"""Tests for integration setup and unload."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

pytest.importorskip("tests.common", reason="Requires HA test infrastructure (tests.common)")
from tests.common import MockConfigEntry

from custom_components.home_battery_sizer.const import DOMAIN


@pytest.mark.asyncio
async def test_async_setup_entry_valid_config(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup from config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=[
            {
                "date": "2024-01-01",
                "solar_production": 15.0,
                "grid_import": 5.0,
                "grid_export": 0.0,
            }
        ],
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is True
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_async_setup_entry_creates_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that coordinator is created and stored."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    # Check coordinator stored in hass.data
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert "coordinator" in hass.data[DOMAIN][mock_config_entry.entry_id]


@pytest.mark.asyncio
async def test_async_setup_entry_first_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, sample_daily_data
) -> None:
    """Test that initial coordinator refresh is called."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ) as mock_get_data:
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    # Check that coordinator was refreshed
    assert mock_get_data.called


@pytest.mark.asyncio
async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test cleanup on entry removal."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)

    await hass.async_block_till_done()

    # Verify coordinator was stored
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Unload entry
    result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert result is True
    await hass.async_block_till_done()

    # Verify cleanup
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_setup_entry_with_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup handles errors gracefully."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        side_effect=Exception("Database error"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Setup should fail if coordinator fails
    assert result is False
