"""Pytest configuration and shared fixtures for Home Battery Sizer tests."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

# Import HomeAssistant fixtures only if available
try:
    from homeassistant.core import HomeAssistant
    from tests.common import MockConfigEntry
    HA_AVAILABLE = True
except ImportError:
    HA_AVAILABLE = False


@pytest.fixture
def hass():
    """Create Home Assistant test instance (requires homeassistant package)."""
    if not HA_AVAILABLE:
        pytest.skip("homeassistant package not installed")

    from homeassistant.core import HomeAssistant
    import asyncio

    hass = HomeAssistant()
    yield hass
    try:
        asyncio.run(hass.async_block_till_done())
        asyncio.run(hass.async_stop())
    except:
        pass


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    if not HA_AVAILABLE:
        pytest.skip("homeassistant package not installed")

    from tests.common import MockConfigEntry

    return MockConfigEntry(
        domain="home_battery_sizer",
        title="Home Battery Sizer",
        data={
            "solar_sensor": "sensor.solar_production",
            "grid_import_sensor": "sensor.grid_import",
            "grid_export_sensor": "sensor.grid_export",
            "battery_size": 10.0,
        },
        version=1,
    )


@pytest.fixture
def sample_daily_data() -> list[dict[str, Any]]:
    """Return sample 30 days of daily energy data."""
    data = []
    base_date = datetime.now().date() - timedelta(days=29)

    for i in range(30):
        date = base_date + timedelta(days=i)
        # Simulate realistic daily patterns
        solar = 15.0 + (10.0 if i % 2 == 0 else 5.0)  # 15-25 kWh per day
        consumption = 20.0 + (5.0 if i % 3 == 0 else 0.0)  # 20-25 kWh per day

        # Grid import/export based on surplus/deficit
        if solar > consumption:
            grid_import = 0.0
            grid_export = solar - consumption
        else:
            grid_import = consumption - solar
            grid_export = 0.0

        data.append({
            "date": date.isoformat(),
            "solar_production": round(solar, 3),
            "grid_import": round(grid_import, 3),
            "grid_export": round(grid_export, 3),
        })

    return data


@pytest.fixture
def mock_async_get_daily_energy_data(sample_daily_data):
    """Return mock for async_get_daily_energy_data."""
    return AsyncMock(return_value=sample_daily_data)

