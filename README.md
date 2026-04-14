# Home Battery Sizer

A custom Home Assistant integration that analyzes one year of historical solar and grid data to help you decide on the right home battery size.

## What you get

If you have solar panels, you're probably exporting surplus energy to the grid during the day and importing from the grid at night. A home battery lets you store that surplus and use it later — but what size do you actually need?

This integration answers that question using your own historical data:

- **Self-sufficient days** — how many days in the past year would solar + battery have covered 100% of your consumption (no grid import needed)
- **Self-sufficiency today** — what percentage of today's consumption has been covered by solar + battery so far

Change the battery size in the configuration and watch the numbers update. No spreadsheets, no guesswork — just your real usage data.

## Requirements

- Home Assistant with the Recorder integration enabled (default on most installs)
- At least a few months of history for the three energy sensors (a full year gives the best results)
- Three cumulative kWh sensors:
  - Solar production (e.g. from a Fronius, SolarEdge, or similar inverter)
  - Grid import (energy consumed from the grid)
  - Grid export (energy fed back to the grid)

Sensors are auto-detected from your [Energy dashboard](https://www.home-assistant.io/docs/energy/) if configured, otherwise you select them manually during setup.

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → click the three-dot menu → **Custom repositories**
3. Add this repository URL and select category **Integration**
4. Search for **Home Battery Sizer** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/home_battery_sizer` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

## Setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Home Battery Sizer**
3. Select your solar, grid import, and grid export sensors
4. Enter the battery size (kWh) you want to simulate

![Setup dialog](docs/screenshots/config_flow.png)

After setup, two sensors are created:

| Sensor                                       | Description                                                         |
|----------------------------------------------|---------------------------------------------------------------------|
| `sensor.battery_sim_self_sufficient_days`    | Days in the past year where solar + battery covered all consumption |
| `sensor.battery_sim_self_sufficiency_today`  | Percentage of today's consumption covered by solar + battery        |

![Sensors in HA dashboard](docs/screenshots/sensors.png)

## How it works

For each day in the past year the integration fetches your solar production, grid import, and grid export from the HA recorder. It then simulates a battery of the configured size with a fixed 90% round-trip efficiency:

- Solar surplus charges the battery (up to its capacity)
- When consumption exceeds solar production, the battery discharges to cover the deficit
- Any remaining deficit is grid import

A day counts as "self-sufficient" if no grid import was needed after the battery is factored in.

## Tips

- Start with a small battery size (e.g. 5 kWh) and increase it to see where the returns diminish
- Self-sufficient days will plateau — the last few days of grid import are typically on dark winter days that no realistic battery size can cover
- The integration recalculates once per day
