# Home Battery Sizer - Testing Guide

## Quick Start

### 1. Install Test Dependencies
```bash
pip install -r requirements-test.txt
```

### 2. Run Unit Tests
```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test file
pytest tests/test_simulation.py

# Run specific test
pytest tests/test_simulation.py::TestSimulation::test_simulation_simple_case

# Run with coverage
pytest tests/ --cov=custom_components.home_battery_sizer
```

### 3. View Test Results
Tests output will show:
- ✓ Passed tests (green)
- ✗ Failed tests (red)
- ⊘ Skipped tests (yellow)

---

## Unit Test Structure

### Test Files and Coverage

| Test File | Module Tested | Test Cases | Purpose |
|-----------|---------------|-----------|---------|
| `test_simulation.py` | `simulation.py` | 11 | Battery simulation engine |
| `test_coordinator.py` | `coordinator.py` | 7 | Data updating and caching |
| `test_init.py` | `__init__.py` | 5 | Integration setup/unload |
| `test_config_flow.py` | `config_flow.py` | 7 | ConfigFlow setup wizard |
| `test_sensor.py` | `sensor.py` | 8 | Sensor entity creation |
| `test_recorder.py` | `recorder.py` | 8 | Historical data queries |

### Running Tests by Category

**Core Business Logic:**
```bash
pytest tests/test_simulation.py -v  # Most critical
pytest tests/test_recorder.py -v
```

**Integration:**
```bash
pytest tests/test_coordinator.py -v
pytest tests/test_init.py -v
```

**Configuration & UI:**
```bash
pytest tests/test_config_flow.py -v
pytest tests/test_sensor.py -v
```

---

## What Each Test Category Tests

### Simulation Tests (test_simulation.py)
Tests the core battery simulation algorithm:
- ✓ Basic charge/discharge cycles
- ✓ Self-sufficiency calculations
- ✓ 90% efficiency applied correctly
- ✓ Battery capacity limits enforced
- ✓ Empty data handling
- ✓ Multiple battery sizes
- ✓ Edge cases (zero consumption, high consumption)

**To run:**
```bash
pytest tests/test_simulation.py -v
```

**Expected result:** 11 passed

---

### Coordinator Tests (test_coordinator.py)
Tests data fetching and coordination:
- ✓ Coordinator initialization
- ✓ Successful data refresh
- ✓ Correct function calls to recorder
- ✓ Empty data handling
- ✓ Error handling and reporting
- ✓ Different battery sizes produce different results
- ✓ Data structure validation

**To run:**
```bash
pytest tests/test_coordinator.py -v
```

**Expected result:** 7 passed

---

### Setup/Unload Tests (test_init.py)
Tests integration lifecycle:
- ✓ Valid config entry setup succeeds
- ✓ Coordinator created and stored in hass.data
- ✓ Initial refresh called on setup
- ✓ Unload removes coordinator from hass.data
- ✓ Error handling on setup failure

**To run:**
```bash
pytest tests/test_init.py -v
```

**Expected result:** 5 passed

---

### ConfigFlow Tests (test_config_flow.py)
Tests the setup UI:
- ✓ User flow form displays
- ✓ Valid input accepted
- ✓ Battery size validated (min 0.1 kWh)
- ✓ Nonexistent sensor rejected with error
- ✓ Float battery sizes accepted
- ✓ Config entry created with correct data

**To run:**
```bash
pytest tests/test_config_flow.py -v
```

**Expected result:** 7 passed

---

### Sensor Tests (test_sensor.py)
Tests sensor entities:
- ✓ Both sensors created
- ✓ Correct state values
- ✓ Attributes set (units, etc.)
- ✓ Device info created
- ✓ Coordinator updates propagate to sensors
- ✓ Unique IDs assigned

**To run:**
```bash
pytest tests/test_sensor.py -v
```

**Expected result:** 8 passed

---

### Recorder Tests (test_recorder.py)
Tests historical data retrieval:
- ✓ Daily differences calculated
- ✓ Empty data handled
- ✓ Partial data handled
- ✓ Invalid values skipped
- ✓ Negative differences (counter reset) become zero
- ✓ Results in chronological order
- ✓ Date format correct

**To run:**
```bash
pytest tests/test_recorder.py -v
```

**Expected result:** 8 passed

---

## Troubleshooting Tests

### ImportError: No module named 'homeassistant'
Home Assistant package not installed. The integration requires Home Assistant core:
```bash
# Install Home Assistant
pip install homeassistant

# Or install full test dependencies
pip install -r requirements-test.txt
```

### Tests fail with "MockConfigEntry not found"
Make sure you have tests/conftest.py with the fixtures:
```bash
ls tests/conftest.py
```

### Asyncio and coroutine errors
Ensure pytest-asyncio is installed and asyncio_mode is set in pytest.ini:
```bash
grep asyncio_mode pytest.ini
```

### "No such file or directory" errors
Make sure you're running pytest from project root:
```bash
pwd  # Should show ...home-battery-sizer
pytest tests/
```

---

## Manual Testing in Home Assistant

### Prerequisites
- Running Home Assistant instance
- Integration copied to `custom_components/home_battery_sizer`
- At least 3 mock sensors:
  - Solar production (cumulative kWh)
  - Grid import (cumulative kWh)
  - Grid export (cumulative kWh)

### Setup Steps

#### 1. Create Mock Sensors (Optional but recommended)
Add to your `configuration.yaml`:
```yaml
template:
  - sensor:
    - name: "Solar Production"
      unique_id: mock_solar
      unit_of_measurement: kWh
      state_class: total_increasing
      state: "{{ state_attr('sensor.solar_production', 'value') | default(0) }}"
      attributes:
        value: "{{ (state_attr('sensor.solar_production', 'value') | default(0) | float(0)) + 0.1 }}"

    - name: "Grid Import"
      unique_id: mock_import
      unit_of_measurement: kWh
      state_class: total_increasing
      state: "{{ state_attr('sensor.grid_import', 'value') | default(0) }}"

    - name: "Grid Export"
      unique_id: mock_export
      unit_of_measurement: kWh
      state_class: total_increasing
      state: "{{ state_attr('sensor.grid_export', 'value') | default(0) }}"
```

#### 2. Add Integration via UI
1. Go to **Settings** → **Devices & Services**
2. Click **Create Integration**
3. Search for "Home Battery Sizer"
4. Select your sensors
5. Enter battery size (e.g., 10 kWh)
6. Click **Create**

#### 3. Verify in Developer Tools
1. Go to **Developer Tools** → **States**
2. Look for:
   - `sensor.battery_sim_self_sufficient_days` (should show integer)
   - `sensor.battery_sim_self_sufficiency_today` (should show 0-100%)

---

## Manual Test Checklist

### ConfigFlow & Setup
- [ ] Integration appears in integ rations list
- [ ] Setup form shows sensor dropdowns
- [ ] Can select sensors from dropdown
- [ ] Can enter battery size
- [ ] Entry created successfully
- [ ] No errors in Home Assistant logs

### Sensors
- [ ] Both sensor entities appear in entity list
- [ ] Self-sufficient days shows 0 or greater
- [ ] Self-sufficiency today shows 0-100%
- [ ] Device appears with name "Home Battery Sizer"

### Data Updates
- [ ] Sensors show numeric values
- [ ] Values reasonable (not NaN, not -999, etc.)
- [ ] Coordinator updates hourly (check logs)
- [ ] States remain stable on reload

### Error Handling
- [ ] Change sensor to nonexistent → Integration shows error
- [ ] Invalid battery size → Form rejects with error
- [ ] Missing sensors → Integration handles gracefully
- [ ] Fix error and reconfigure → Integration recovers

### Integration Lifecycle
- [ ] Disable integration → Sensors become unavailable
- [ ] Re-enable integration → Sensors come back
- [ ] Reload integrations → Data persists
- [ ] Remove integration → Sensors removed

### Logs
- [ ] No ERROR level logs
- [ ] No WARNING level logs (except first setup)
- [ ] Check for "Error updating battery sizer data" → Should not appear on success

---

## Running Full Test Suite

```bash
# Run all tests with full report
pytest tests/ -v --tb=short

# Run with coverage report
pytest tests/ --cov=custom_components.home_battery_sizer --cov-report=html

# Then open htmlcov/index.html to see coverage

# Run only failing tests (useful after fixing)
pytest tests/ --lf

# Run with warnings
pytest tests/ -W default
```

---

## Expected Test Results

Running `pytest tests/ -v` should show:

```
tests/test_simulation.py::TestSimulation::test_simulation_simple_case PASSED
tests/test_simulation.py::TestSimulation::test_simulation_all_self_sufficient PASSED
... (43 more tests)

============== 46 passed in 2.34s ==============
```

---

## Tips for Test Development

### Adding New Tests
1. Create test function in appropriate test_{module}.py
2. Name: `test_<feature_being_tested>`
3. Use fixtures from conftest.py
4. Use @pytest.mark.asyncio for async tests
5. Run: `pytest tests/test_{module}.py::test_<function_name>`

### Debugging Failed Tests
```bash
# Run with print statements visible
pytest tests/test_simulation.py -v -s

# Run with full traceback
pytest tests/test_simulation.py -v --tb=long

# Stop on first failure
pytest tests/test_simulation.py -x
```

### Mocking
```python
from unittest.mock import AsyncMock, patch

with patch("module.function", new_callable=AsyncMock) as mock_func:
    mock_func.return_value = test_data
    # Your test code
    assert mock_func.called
```

---

## Next Steps After Tests Pass

1. **Unit Tests Pass** → Code is logically correct
2. **Manual Testing** → Integration works in real Home Assistant
3. **Ready for Publishing** → Can submit to HACS

---

## Useful Commands

```bash
# Run only tests matching pattern
pytest tests/ -k simulation

# Verbose output with print statements
pytest tests/ -vv -s

# Stop after first failure
pytest tests/ -x

# Show slowest tests
pytest tests/ --durations=10

# Generate JUnit XML (for CI/CD)
pytest tests/ --junit-xml=test-results.xml

# Generate HTML report (requires pytest-html)
pytest tests/ --html=report.html
```

---

## Home Assistant Test Fixtures Available

In conftest.py:

```python
hass                            # Home Assistant test instance
mock_config_entry               # Pre-configured MockConfigEntry
sample_daily_data               # 30 days of realistic energy data
mock_async_get_daily_energy_data # AsyncMock for recorder query
```

Use them in tests:
```python
async def test_something(hass, mock_config_entry, sample_daily_data):
    # Your test code
    pass
```

---

## Questions?

If tests fail:
1. Check error message and traceback
2. Verify Home Assistant package is installed
3. Check pytest.ini is in project root
4. Verify all import paths are correct
5. Check conftest.py has all required fixtures

Most common issue: Missing `homeassistant` package → `pip install homeassistant`
