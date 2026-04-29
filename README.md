# Home Battery Sizer

A custom Home Assistant integration that analyses one year of historical solar and grid data to help you decide on the right home battery size.

## What you get

If you have solar panels, you're probably exporting surplus energy to the grid during the day and importing from the grid at night. A home battery lets you store that surplus and use it later — but what size do you actually need?

This integration answers that question using your own historical data. Add one entry per battery size you want to compare (e.g. 5, 10, 15, 20 kWh) and watch the sensors update side by side.

For each simulated battery size you get:

| Sensor | Description |
| --- | --- |
| Self-sufficient days | Days in the past year where solar + battery covered 100% of consumption |
| Self-sufficiency yesterday | Percentage of yesterday's consumption covered by solar + battery |
| First self-sufficient day | Earliest day in the past year the house was fully self-sufficient |
| Last self-sufficient day | Most recent day the house was fully self-sufficient |
| Max consecutive self-sufficient days | Longest unbroken streak of fully self-sufficient days |

The battery carries charge between days, so a sunny day can power the house through the following night and into the next morning — just like a real battery would.

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

To compare multiple battery sizes, add the integration again with a different battery size. Each entry runs its own simulation independently.

## Visualising results

Each battery entry writes daily self-sufficiency percentages as an external statistic. You can plot all battery sizes on a single graph using a **Statistics graph** card.

Add a new card, switch to the YAML editor, and paste:

```yaml
type: statistics-graph
chart_type: bar
title: Daily self-sufficiency
days_to_show: 21
stat_types:
  - mean
unit: "%"
entities:
  - entity: home_battery_sizer:self_sufficiency_daily_5kwh
    name: 5 kWh
  - entity: home_battery_sizer:self_sufficiency_daily_10kwh
    name: 10 kWh
  - entity: home_battery_sizer:self_sufficiency_daily_15kwh
    name: 15 kWh
  - entity: home_battery_sizer:self_sufficiency_daily_20kwh
    name: 20 kWh
```

Adjust the list to match the battery sizes you have configured. The statistic ID format is always `home_battery_sizer:self_sufficiency_daily_{size}kwh` (e.g. `_7_5kwh` for 7.5 kWh).

> **Note:** The visual editor will show validation warnings for these entries — that is expected. Save via the YAML editor and the card will render correctly.

## How it works

The simulation runs hourly across all available data (up to one year). For each hour:

1. Consumption is estimated as `solar + grid_import − grid_export` from your historical meter readings
2. Solar first covers consumption directly
3. Any surplus charges the battery (90% round-trip efficiency)
4. Any deficit draws from the battery, then falls back to grid import if the battery is empty

Battery charge carries over between hours and days. A day counts as "self-sufficient" if total grid import needed after the battery is factored in is less than 10 Wh.

Results update every hour.

## Tips

- Add a 0 kWh entry (no battery) as a baseline to see your current self-sufficiency from solar alone
- Self-sufficient days will plateau as you increase battery size — the last few days of grid import are typically dark winter days that no realistic battery can cover
- The "max consecutive days" sensor shows the longest summer streak — useful for understanding how long a run of good weather the battery can sustain
