"""Tests for data coordinator."""
from __future__ import annotations

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
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
        "custom_components.home_battery_sizer.coordinator.async_get_hourly_energy_data",
        new_callable=AsyncMock,
        return_value=sample_daily_data,
    ):
        await coordinator.async_config_entry_first_refresh()

    data = coordinator.data
    assert isinstance(data["self_sufficient_days"], int)
    assert isinstance(data["self_sufficiency_today"], float)
    assert isinstance(data["daily_results"], list)


def _make_coordinator_with_mock_hass():
    """Create a coordinator with a minimal mock hass (no real HA needed)."""
    mock_hass = MagicMock()
    # HomeBatterySizerCoordinator calls super().__init__ which needs hass.loop etc.
    with patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__", return_value=None):
        coordinator = HomeBatterySizerCoordinator.__new__(HomeBatterySizerCoordinator)
        coordinator.hass = mock_hass
        coordinator.entry_id = "test_entry_id"
        coordinator.solar_sensor = "sensor.solar"
        coordinator.grid_import_sensor = "sensor.import"
        coordinator.grid_export_sensor = "sensor.export"
        coordinator.battery_size = 10.0
        coordinator.statistic_id = "home_battery_sizer:self_sufficiency_daily_10kwh"
    return coordinator


def _fake_recorder_module(captured: list):
    """Return a fake homeassistant.components.recorder.statistics module."""
    mod = MagicMock()
    mod.StatisticData = lambda **kwargs: kwargs
    mod.StatisticMetaData = MagicMock(return_value=MagicMock())
    mod.async_add_external_statistics = lambda hass, meta, data: captured.extend(data)
    return mod


@pytest.mark.asyncio
async def test_inject_statistics_fills_date_gaps() -> None:
    """Gap dates between first and last should be written with mean=0.0."""
    coordinator = _make_coordinator_with_mock_hass()
    daily_results = [
        {"date": "2024-06-01", "self_sufficiency_pct": 80.0},
        {"date": "2024-06-03", "self_sufficiency_pct": 60.0},
    ]
    captured = []
    fake_mod = _fake_recorder_module(captured)

    with patch.dict(sys.modules, {"homeassistant.components.recorder.statistics": fake_mod}):
        await coordinator._inject_daily_statistics(daily_results)

    assert len(captured) == 3
    dates = [s["start"] for s in captured]
    assert dates[0] == datetime(2024, 6, 1, tzinfo=timezone.utc)
    assert dates[1] == datetime(2024, 6, 2, tzinfo=timezone.utc)
    assert dates[2] == datetime(2024, 6, 3, tzinfo=timezone.utc)
    assert captured[1]["mean"] == 0.0  # gap day filled with 0%


@pytest.mark.asyncio
async def test_inject_statistics_uses_correct_pct_values() -> None:
    """Days present in daily_results should carry their actual self_sufficiency_pct."""
    coordinator = _make_coordinator_with_mock_hass()
    daily_results = [
        {"date": "2024-06-01", "self_sufficiency_pct": 80.0},
        {"date": "2024-06-02", "self_sufficiency_pct": 50.0},
        {"date": "2024-06-03", "self_sufficiency_pct": 60.0},
    ]
    captured = []
    fake_mod = _fake_recorder_module(captured)

    with patch.dict(sys.modules, {"homeassistant.components.recorder.statistics": fake_mod}):
        await coordinator._inject_daily_statistics(daily_results)

    assert len(captured) == 3
    assert captured[0]["mean"] == 80.0
    assert captured[1]["mean"] == 50.0
    assert captured[2]["mean"] == 60.0


@pytest.mark.asyncio
async def test_inject_statistics_skips_empty_input() -> None:
    """Empty daily_results should not call async_add_external_statistics at all."""
    coordinator = _make_coordinator_with_mock_hass()
    captured = []
    fake_mod = _fake_recorder_module(captured)

    with patch.dict(sys.modules, {"homeassistant.components.recorder.statistics": fake_mod}):
        await coordinator._inject_daily_statistics([])

    assert captured == []


@pytest.mark.asyncio
async def test_inject_statistics_single_day() -> None:
    """Single-day input produces exactly one stat entry."""
    coordinator = _make_coordinator_with_mock_hass()
    daily_results = [{"date": "2024-06-15", "self_sufficiency_pct": 75.0}]
    captured = []
    fake_mod = _fake_recorder_module(captured)

    with patch.dict(sys.modules, {"homeassistant.components.recorder.statistics": fake_mod}):
        await coordinator._inject_daily_statistics(daily_results)

    assert len(captured) == 1
    assert captured[0]["mean"] == 75.0
    assert captured[0]["start"] == datetime(2024, 6, 15, tzinfo=timezone.utc)
