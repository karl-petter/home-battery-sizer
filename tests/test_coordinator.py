"""Tests for data coordinator."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from datetime import timedelta
from homeassistant.core import HomeAssistant

from custom_components.home_battery_sizer.coordinator import HomeBatterySizerCoordinator


@pytest.mark.asyncio
async def test_coordinator_initialization(hass: HomeAssistant) -> None:
    """Test coordinator is initialized correctly."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    assert coordinator.solar_sensor == "sensor.solar"
    assert coordinator.grid_import_sensor == "sensor.import"
    assert coordinator.grid_export_sensor == "sensor.export"
    assert coordinator.battery_size == 10.0
    assert coordinator.update_interval == timedelta(hours=1)


@pytest.mark.asyncio
async def test_coordinator_refresh_success(
    hass: HomeAssistant, sample_daily_data
) -> None:
    """Test successful coordinator data update."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await coordinator.async_config_entry_first_refresh()

    assert coordinator.data is not None
    assert "self_sufficient_days" in coordinator.data
    assert "self_sufficiency_today" in coordinator.data


@pytest.mark.asyncio
async def test_coordinator_refresh_with_mock_data(
    hass: HomeAssistant, sample_daily_data
) -> None:
    """Test coordinator calls simulation with correct data."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ) as mock_get_data:
        await coordinator.async_config_entry_first_refresh()

    # Verify recorder was called with correct parameters
    mock_get_data.assert_called_once()
    call_args = mock_get_data.call_args
    assert call_args[0][1] == "sensor.solar"
    assert call_args[0][2] == "sensor.import"
    assert call_args[0][3] == "sensor.export"
    assert call_args[1]["days"] == 365


@pytest.mark.asyncio
async def test_coordinator_handles_empty_data(hass: HomeAssistant) -> None:
    """Test coordinator handles empty daily data gracefully."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=[],
    ):
        await coordinator.async_config_entry_first_refresh()

    # Should still have valid result structure
    assert coordinator.data is not None
    assert coordinator.data["self_sufficient_days"] == 0
    assert coordinator.data["self_sufficiency_today"] == 0.0


@pytest.mark.asyncio
async def test_coordinator_error_handling(hass: HomeAssistant) -> None:
    """Test coordinator handles errors gracefully."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        side_effect=ValueError("Database connection failed"),
    ):
        # Should raise the error
        with pytest.raises(ValueError):
            await coordinator.async_config_entry_first_refresh()


@pytest.mark.asyncio
async def test_coordinator_different_battery_sizes(
    hass: HomeAssistant, sample_daily_data
) -> None:
    """Test coordinator with different battery sizes produces different results."""
    coordinator_5 = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=5.0,
    )

    coordinator_20 = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=20.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await coordinator_5.async_config_entry_first_refresh()
        await coordinator_20.async_config_entry_first_refresh()

    # Larger battery should have more self-sufficient days
    assert coordinator_5.data["self_sufficient_days"] <= coordinator_20.data["self_sufficient_days"]


@pytest.mark.asyncio
async def test_coordinator_data_structure(hass: HomeAssistant, sample_daily_data) -> None:
    """Test coordinator data has expected structure."""
    coordinator = HomeBatterySizerCoordinator(
        hass,
        solar_sensor="sensor.solar",
        grid_import_sensor="sensor.import",
        grid_export_sensor="sensor.export",
        battery_size=10.0,
    )

    with patch(
        "custom_components.home_battery_sizer.recorder.async_get_daily_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await coordinator.async_config_entry_first_refresh()

    data = coordinator.data
    assert isinstance(data["self_sufficient_days"], int)
    assert isinstance(data["self_sufficiency_today"], float)
    assert isinstance(data["daily_results"], list)
