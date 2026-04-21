# HA Battery Sizing — Design Document

## Goal

A custom Home Assistant integration that analyzes one year of historical solar and grid data to help the user decide on the right home battery size. Intended to be reusable and eventually publishable via HACS.

## Input sensors

| Sensor | Description | Type |
|--------|-------------|------|
| `sensor.symo_12_5_3_m_1_total_energy` | Solar production (Fronius Symo 12.5) | Cumulative kWh |
| `sensor.energy_consumed_luxembourg` | Grid import (Slimmelezer) | Cumulative kWh |
| `sensor.energy_produced_luxembourg` | Grid export (Slimmelezer) | Cumulative kWh |

These are the developer's own sensors. The integration automatically detects sensors from the Home Assistant Energy dashboard configuration when available, otherwise allows manual configuration via ConfigFlow.

## Core calculation

The simulation runs **hour by hour** (not per day). Daily totals are insufficient because solar only produces during daylight hours — a house always needs power at night, so even on days where total solar production exceeds total consumption, a battery is still needed to carry surplus from midday to cover the night.

For each hour:

- **Solar production** = delta of cumulative solar sensor since previous hour
- **Grid import** = delta of cumulative grid import sensor since previous hour
- **Grid export** = delta of cumulative grid export sensor since previous hour
- **Consumption** = solar + grid import − grid export

Battery simulation per hour:

- If solar ≥ consumption: surplus charges the battery (capped at capacity), no grid import needed
- If solar < consumption: battery discharges to cover deficit; any remaining deficit = grid import needed
- Round-trip efficiency: **fixed at 90%** (applied on charge)
- Battery state carries over continuously between hours

A day is counted as **self-sufficient** if the simulated grid import needed was zero for every hour of that day.

## Data source

Energy data is read from **HA long-term statistics** (`statistics_during_period`, `period="hour"`), not from the short-term state history.

### Why hourly resolution

- Hourly correctly models the day/night cycle, which is the critical factor for battery sizing
- Hourly is the finest resolution available from long-term statistics (kept indefinitely)
- Sub-hourly statistics (5-minute) exist in HA but are only retained for a short period — insufficient for a 1-year lookback
- Hourly resolution is standard in professional energy modeling for battery sizing; the errors from within-hour averaging are small compared to real-world uncertainties

### Why long-term statistics (not `get_significant_states`)

- Short-term state history is subject to HA's recorder retention setting (often 10 days)
- Long-term statistics are stored indefinitely and cover the full year needed

## Key decisions

- Uses **historical data** from HA recorder (1 year lookback), not forward simulation
- **Hourly granularity** — coarsest resolution that correctly models day/night solar cycles while still allowing a full year of data
- Efficiency is a fixed constant (90%), not user-configurable
- Battery size is user-configurable (including 0 kWh for a solar-only baseline)
- Built as a proper **custom integration** with ConfigFlow and OptionsFlow

## Integration structure

- **ConfigFlow** — setup UI that auto-detects sensors from Energy dashboard, with manual override
- **OptionsFlow** — allows changing battery size without reinstalling
- **Coordinator** — queries long-term statistics, runs hourly simulation, injects daily self-sufficiency as external statistics
- **Sensors** — exposes results back to HA as entities

## Output

### Sensors

| Sensor | Description |
|--------|-------------|
| `sensor.home_battery_sizer_self_sufficient_days` | Count of days in the past year where solar + battery covered 100% of consumption |
| `sensor.home_battery_sizer_self_sufficiency_today` | Percentage of today's consumption covered by solar + battery so far |
| `sensor.home_battery_sizer_first_self_sufficient_day` | Date of the first self-sufficient day in the past year |
| `sensor.home_battery_sizer_last_self_sufficient_day` | Date of the most recent self-sufficient day in the past year |

### External statistics (for historical graphs)

| Statistic ID                                  | Description                                                                             |
|-----------------------------------------------|-----------------------------------------------------------------------------------------|
| `home_battery_sizer:self_sufficiency_daily`   | Daily self-sufficiency percentage — graphable in Lovelace via `statistics-graph` card   |

## What was considered and rejected

- **battery_sim (HACS)** — only simulates going forward, no historical backfill
- **AppDaemon** — overkill for this use case
- **Template sensors** — cannot backfill history
- **External analysis** — user wants everything inside HA
- **Daily granularity** — rejected because daily solar/consumption totals hide the fact that solar is zero at night; a battery is needed to bridge the gap even on net-positive days
- **Sub-hourly granularity** — rejected because HA only retains 5-minute statistics for a short period, making a 1-year lookback impossible at that resolution
