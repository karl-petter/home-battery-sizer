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

For each day:
- **Solar production** = diff of cumulative solar sensor
- **Grid import** = diff of cumulative grid import sensor
- **Grid export** = diff of cumulative grid export sensor
- **Total consumption** = solar + grid import − grid export
- **Deficit** = max(0, consumption − solar)

Battery simulation per day:
- Battery charges from solar surplus (solar − consumption), capped at battery capacity
- Battery discharges to cover deficit, capped at current charge level
- Round-trip efficiency: **fixed at 90%**
- User configures battery size in kWh

## Key decisions

- Uses **historical data** from HA recorder (1 year lookback), not forward simulation
- Efficiency is a fixed constant (90%), not user-configurable
- Battery size is user-configurable
- Built as a proper **custom integration** with ConfigFlow

## Integration structure (planned)

- **ConfigFlow** — setup UI that auto-detects sensors from Energy dashboard, with manual override option
- **Coordinator** — queries recorder, runs simulation, caches results
- **Sensors** — exposes results back to HA as entities

## Output sensors

| Sensor | Description |
|--------|-------------|
| `sensor.battery_sim_self_sufficient_days` | Count of days where solar + battery covered 100% of consumption (no grid import needed) |
| `sensor.battery_sim_self_sufficiency_today` | Percentage of today's consumption covered by solar + battery (0–100%) |

## What was considered and rejected

- **battery_sim (HACS)** — only simulates going forward, no historical backfill
- **AppDaemon** — overkill for this use case
- **Template sensors** — cannot backfill history
- **External analysis** — user wants everything inside HA

## Next steps

1. Define output sensors/metrics
2. Set up GitHub repo and VSCode
3. Scaffold the integration structure
4. Implement recorder query
5. Implement battery simulation
6. Wire up ConfigFlow and sensors
