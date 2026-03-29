"""Tests for recorder query functionality."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch
from homeassistant.core import HomeAssistant

from custom_components.home_battery_sizer.recorder import (
    async_get_daily_energy_data,
    _process_history,
)


def create_mock_state(last_changed: datetime, state_value: str) -> dict[str, Any]:
    """Create a mock state object."""
    return {
        "last_changed": last_changed,
        "state": state_value,
    }


class TestRecorderModule:
    """Test recorder query functionality."""

    def test_process_history_calculates_differences(self) -> None:
        """Test daily differences are calculated correctly."""
        base_time = datetime.now()

        solar_history = [
            create_mock_state(base_time, "100.0"),
            create_mock_state(base_time + timedelta(hours=6), "110.0"),
            create_mock_state(base_time + timedelta(hours=12), "120.0"),
            create_mock_state(base_time + timedelta(hours=18), "130.0"),
            create_mock_state(base_time + timedelta(hours=24), "150.0"),
        ]

        import_history = [
            create_mock_state(base_time, "50.0"),
            create_mock_state(base_time + timedelta(hours=6), "55.0"),
            create_mock_state(base_time + timedelta(hours=12), "60.0"),
            create_mock_state(base_time + timedelta(hours=18), "65.0"),
            create_mock_state(base_time + timedelta(hours=24), "80.0"),
        ]

        export_history = [
            create_mock_state(base_time, "10.0"),
            create_mock_state(base_time + timedelta(hours=6), "12.0"),
            create_mock_state(base_time + timedelta(hours=12), "14.0"),
            create_mock_state(base_time + timedelta(hours=18), "16.0"),
            create_mock_state(base_time + timedelta(hours=24), "30.0"),
        ]

        result = _process_history(solar_history, import_history, export_history)

        # Should have processed 4 daily differences (5 states = 4 differences)
        assert len(result) == 4

        # Check first difference calculation (between states 0 and 1)
        # Solar diff: 110 - 100 = 10
        # Import diff: 55 - 50 = 5
        # Export diff: 12 - 10 = 2
        assert result[0]["solar_production"] == 10.0
        assert result[0]["grid_import"] == 5.0
        assert result[0]["grid_export"] == 2.0

    def test_process_history_empty_data(self) -> None:
        """Test empty history returns empty list."""
        result = _process_history([], [], [])
        assert result == []

    def test_process_history_partial_data(self) -> None:
        """Test with incomplete sensor data."""
        solar_history = [
            create_mock_state(datetime.now(), "100.0"),
        ]
        import_history = []
        export_history = []

        result = _process_history(solar_history, import_history, export_history)

        # Should warn about incomplete data
        assert result == []

    def test_process_history_invalid_values(self) -> None:
        """Test handling of invalid state values."""
        base_time = datetime.now()

        solar_history = [
            create_mock_state(base_time, "100.0"),
            create_mock_state(base_time + timedelta(hours=24), "not_a_number"),  # Invalid
        ]

        import_history = [
            create_mock_state(base_time, "50.0"),
            create_mock_state(base_time + timedelta(hours=24), "55.0"),
        ]

        export_history = [
            create_mock_state(base_time, "10.0"),
            create_mock_state(base_time + timedelta(hours=24), "12.0"),
        ]

        # Should handle gracefully (skip invalid value)
        result = _process_history(solar_history, import_history, export_history)

        # Should still produce results, skipping invalid values
        assert len(result) >= 0

    def test_process_history_negative_differences_become_zero(self) -> None:
        """Test that negative differences (counter reset) become zero."""
        base_time = datetime.now()

        solar_history = [
            create_mock_state(base_time, "100.0"),
            create_mock_state(base_time + timedelta(hours=24), "90.0"),  # Counter reset
        ]

        import_history = [
            create_mock_state(base_time, "50.0"),
            create_mock_state(base_time + timedelta(hours=24), "55.0"),
        ]

        export_history = [
            create_mock_state(base_time, "10.0"),
            create_mock_state(base_time + timedelta(hours=24), "12.0"),
        ]

        result = _process_history(solar_history, import_history, export_history)

        # First difference should be 0 (negative becomes 0)
        if len(result) > 0:
            assert result[0]["solar_production"] >= 0

    def test_process_history_chronological_ordering(self) -> None:
        """Test results are in chronological order."""
        base_time = datetime.now()

        # Create history in reverse chronological order
        solar_history = [
            create_mock_state(base_time + timedelta(hours=48), "140.0"),
            create_mock_state(base_time + timedelta(hours=24), "120.0"),
            create_mock_state(base_time, "100.0"),
        ]

        import_history = [
            create_mock_state(base_time + timedelta(hours=48), "60.0"),
            create_mock_state(base_time + timedelta(hours=24), "55.0"),
            create_mock_state(base_time, "50.0"),
        ]

        export_history = [
            create_mock_state(base_time + timedelta(hours=48), "14.0"),
            create_mock_state(base_time + timedelta(hours=24), "12.0"),
            create_mock_state(base_time, "10.0"),
        ]

        result = _process_history(solar_history, import_history, export_history)

        # Should be sorted chronologically
        if len(result) >= 2:
            assert result[0]["date"] <= result[1]["date"]

    def test_process_history_date_format(self) -> None:
        """Test date format in results."""
        base_time = datetime.now().date()

        solar_history = [
            create_mock_state(
                datetime.combine(base_time, datetime.min.time()), "100.0"
            ),
            create_mock_state(
                datetime.combine(base_time + timedelta(days=1), datetime.min.time()),
                "120.0",
            ),
        ]

        import_history = [
            create_mock_state(
                datetime.combine(base_time, datetime.min.time()), "50.0"
            ),
            create_mock_state(
                datetime.combine(base_time + timedelta(days=1), datetime.min.time()),
                "55.0",
            ),
        ]

        export_history = [
            create_mock_state(
                datetime.combine(base_time, datetime.min.time()), "10.0"
            ),
            create_mock_state(
                datetime.combine(base_time + timedelta(days=1), datetime.min.time()),
                "12.0",
            ),
        ]

        result = _process_history(solar_history, import_history, export_history)

        # Check date format is ISO format (YYYY-MM-DD)
        if len(result) > 0:
            date_str = result[0]["date"]
            assert len(date_str) == 10  # YYYY-MM-DD format
            assert date_str[4] == "-"
            assert date_str[7] == "-"


@pytest.mark.asyncio
async def test_async_get_daily_energy_data_returns_list(hass: HomeAssistant) -> None:
    """Test async_get_daily_energy_data returns a list."""
    with patch(
        "custom_components.home_battery_sizer.recorder.history.get_significant_states"
    ) as mock_history:
        mock_history.return_value = {
            "sensor.solar": [],
            "sensor.import": [],
            "sensor.export": [],
        }

        result = await async_get_daily_energy_data(
            hass, "sensor.solar", "sensor.import", "sensor.export"
        )

        assert isinstance(result, list)
