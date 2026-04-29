# Test data — real HA recorder export

Exported 2026-04-29 from the live HA instance via SQLite query on `/config/home-assistant_v2.db`.

## Sensors

| Sensor | Unit | Role |
| --- | --- | --- |
| `sensor.symo_12_5_3_m_1_total_energy` | **Wh** | Solar production (cumulative) |
| `sensor.energy_consumed_luxembourg` | kWh | Grid import (cumulative) |
| `sensor.energy_produced_luxembourg` | kWh | Grid export (cumulative) |

## Files

### `ha_hourly_cumulative_5days.csv`
Raw cumulative values per sensor per hour, long format (one row per sensor per hour).

### `ha_hourly_deltas_5days.csv`
Wide format with one row per hour, showing both cumulative values and the
computed per-hour deltas (what the simulation uses). Key columns:

- `solar_kwh_delta` — Wh delta divided by 1000 → kWh
- `import_kwh_delta` — grid energy bought this hour (kWh)
- `export_kwh_delta` — grid energy sold this hour (kWh)
- `est_consumption_kwh` — estimated house consumption = solar + import − export

## Known issues visible in this data (now fixed)

1. **Solar sensor is in Wh, not kWh** — the raw cumulative goes up by ~7000 per sunny
   hour, which is 7 kWh, not 7000 kWh. The recorder now detects the unit via
   `list_statistic_ids` and divides by 1000 automatically.

2. **Solar has no records at night** — `solar_wh_cum` is null from ~21:00 to ~04:00
   because the inverter pushes no statistics when output is zero. Previously the
   simulation used the intersection of all three sensors, silently dropping all
   night hours and all their grid imports. Fixed by using import+export as the
   authoritative hour set and filling solar with 0 for missing hours.
