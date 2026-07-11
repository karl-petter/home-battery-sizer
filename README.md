# Home Battery Sizer

A Home Assistant integration for homeowners with solar panels who are thinking about adding a home battery. It uses your own historical solar and grid data to simulate different battery sizes, so you can see the real impact before you buy.

## What you get

If you have solar panels, you're probably exporting surplus energy to the grid during the day and importing from the grid at night. A home battery lets you store that surplus and use it later — but what size do you actually need?

This integration answers that question using your own historical data. Add one entry per battery size you want to compare (e.g. 5, 10, 15, 20 kWh) and watch the sensors update side by side.

For each simulated battery size you get two groups of sensors. Entity IDs are `sensor.home_battery_sizer_{size}_kwh` plus the suffix below. (Entity IDs are fixed when an entity is first created — installs from older versions keep their original IDs; rename them under Settings → Entities if you want them to match.)

**Battery activity & energy** — what the battery does and how much of your consumption it covers:

| Sensor | Entity ID suffix | Description |
| --- | --- | --- |
| Energy self-sufficiency | `_energy_self_sufficiency` | Share of the year's consumption covered by solar + battery — **the headline number for comparing sizes** |
| Energy self-sufficiency yesterday | `_energy_self_sufficiency_yesterday` | Share of yesterday's consumption covered by solar + battery |
| Battery discharge | `_battery_discharge` | kWh the battery supplied to the house this year |
| Battery uncaptured surplus | `_battery_uncaptured_surplus` | Solar surplus the battery could not store — this energy still flows to the grid, so comparing it with your real export shows what the battery would absorb. The number a bigger battery shrinks. |

**Calendar** — how many days, and when in the year, you'd be fully grid-free:

| Sensor | Entity ID suffix | Description |
| --- | --- | --- |
| Self-sufficient days | `_self_sufficient_days` | Days this year where solar + battery covered 100% of consumption |
| Max consecutive self-sufficient days | `_max_consecutive_self_sufficient_days` | Longest unbroken grid-free streak this year |
| First self-sufficient day | `_first_self_sufficient_day` | First fully grid-free day of the year (spring) |
| Last self-sufficient day | `_last_self_sufficient_day` | Most recent fully grid-free day of the year (autumn) |

The two date sensors carry context dates as attributes — useful at high latitudes where panels are dark all winter: `first_solar_production_day` / `last_solar_production_day` (first/last day with meaningful production, > 0.1 kWh) and `first_solar_surplus_day` / `last_solar_surplus_day` (first/last day solar exceeded consumption, i.e. when a battery has something to store). Spring reads: production starts → surplus starts → fully grid-free; the gap between the last two is what a bigger battery shrinks.

Every yearly sensor also exists in a **previous year** variant (append `_previous_year` to the entity ID), so a partial current year can be compared against the last complete one. All sensors are computed over calendar years — the same window for every battery size — and Energy self-sufficiency and the day counts can only improve with a bigger battery, so different sizes are always directly comparable.

### Derived numbers

A few ratios are deliberately *not* sensors, because they are one-line calculations on the sensors above. Paste these into a markdown card, or create a [template sensor helper](https://www.home-assistant.io/integrations/template/) if you want history (replace `20_kwh` with your battery size):

Self-sufficient period length — days from first to last self-sufficient day, inclusive:

```jinja
{{ (states('sensor.home_battery_sizer_20_kwh_last_self_sufficient_day') | as_datetime
  - states('sensor.home_battery_sizer_20_kwh_first_self_sufficient_day') | as_datetime).days + 1 }}
```

Share of that period that was fully self-sufficient:

```jinja
{% set first = states('sensor.home_battery_sizer_20_kwh_first_self_sufficient_day') | as_datetime %}
{% set last  = states('sensor.home_battery_sizer_20_kwh_last_self_sufficient_day') | as_datetime %}
{% set days  = states('sensor.home_battery_sizer_20_kwh_self_sufficient_days') | int %}
{{ (100 * days / ((last - first).days + 1)) | round(1) }}
```

Share of the year so far that was fully self-sufficient:

```jinja
{{ (100 * states('sensor.home_battery_sizer_20_kwh_self_sufficient_days') | int
       / now().timetuple().tm_yday) | round(1) }}
```

(If your recorded history does not cover the whole year, divide by the `days_with_data` attribute of the days sensor instead of the day-of-year.)

The battery carries charge between days, so a sunny day can power the house through the following night and into the next morning — just like a real battery would.

![Dashboard cards showing daily self-sufficiency and a bar chart comparing energy self-sufficiency per battery size](images/screenshot-cards.png)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=karl-petter&repository=home-battery-sizer&category=integration)

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

### Card 1 — Daily self-sufficiency over time

Each battery entry writes daily self-sufficiency percentages as an external statistic. Plot all battery sizes together using a **Statistics graph** card.

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
  - entity: home_battery_sizer:self_sufficiency_daily_25kwh
    name: 25 kWh
  - entity: home_battery_sizer:self_sufficiency_daily_30kwh
    name: 30 kWh
```

Adjust the list to match the battery sizes you have configured. The statistic ID format is always `home_battery_sizer:self_sufficiency_daily_{size}kwh` (e.g. `_7_5kwh` for 7.5 kWh).

**Monthly alternative** — the same statistic aggregated per month over a full year. This view makes the seasons obvious: the winter months where no battery helps, and the summer months where the sizes separate (a size that never reaches ~100% in June/July is too small to bridge your nights). Same card, three changed lines:

```yaml
type: statistics-graph
chart_type: bar
title: Monthly self-sufficiency
days_to_show: 365
period: month
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
  - entity: home_battery_sizer:self_sufficiency_daily_25kwh
    name: 25 kWh
  - entity: home_battery_sizer:self_sufficiency_daily_30kwh
    name: 30 kWh
```

Pick whichever reads best for you — daily for the recent detail, monthly for the year at a glance.

> **Note:** The visual editor will show validation warnings for these entries — that is expected. Save via the YAML editor and the card will render correctly.

### Card 2 — Battery size vs self-sufficiency chart

Visualises the diminishing returns as battery size grows. Requires [apexcharts-card](https://github.com/RomRider/apexcharts-card) (available via HACS).

```yaml
type: custom:apexcharts-card
graph_span: 2h
header:
  show: true
  title: Battery size vs energy self-sufficiency (previous year)
apex_config:
  chart:
    type: bar
    height: 300
  plotOptions:
    bar:
      horizontal: false
      columnWidth: 70%
  dataLabels:
    enabled: true
    formatter: |
      EVAL:function(val) { return val ? val.toFixed(1) + '%' : ''; }
  yaxis:
    min: 0
    title:
      text: "% of consumption covered"
  xaxis:
    labels:
      show: false
    axisTicks:
      show: false
all_series_config:
  group_by:
    func: last
    duration: 2h
  show:
    legend_value: true
series:
  - entity: sensor.home_battery_sizer_5_kwh_energy_self_sufficiency_previous_year
    name: "5 kWh"
  - entity: sensor.home_battery_sizer_10_kwh_energy_self_sufficiency_previous_year
    name: "10 kWh"
  - entity: sensor.home_battery_sizer_15_kwh_energy_self_sufficiency_previous_year
    name: "15 kWh"
  - entity: sensor.home_battery_sizer_20_kwh_energy_self_sufficiency_previous_year
    name: "20 kWh"
  - entity: sensor.home_battery_sizer_25_kwh_energy_self_sufficiency_previous_year
    name: "25 kWh"
  - entity: sensor.home_battery_sizer_30_kwh_energy_self_sufficiency_previous_year
    name: "30 kWh"
```

The y-axis is deliberately not pinned to 100%: yearly self-sufficiency includes the winter months where every battery scores the same, so the differences between sizes are only a few percentage points and would vanish on a full 0–100 scale.

### Card 3 — Daily production, consumption, export & battery coverage

Combines actual solar production and grid export alongside simulated daily house consumption and the kWh each battery would deliver. House consumption includes solar used directly — it cannot be read from a grid meter alone. No extra integrations needed.

Replace `sensor.your_solar_production_sensor` and `sensor.your_grid_export_sensor` with the sensor entity IDs you selected during integration setup.

```yaml
type: statistics-graph
chart_type: bar
title: Daily production, consumption, export & battery coverage
days_to_show: 21
period: day
stat_types:
  - change
entities:
  - entity: sensor.your_solar_production_sensor
    name: Solar production
  - entity: home_battery_sizer:consumption_daily
    name: House consumption
  - entity: sensor.your_grid_export_sensor
    name: Grid export (actual, without battery)
  - entity: home_battery_sizer:battery_delivered_daily_5kwh
    name: Battery 5 kWh
  - entity: home_battery_sizer:battery_delivered_daily_10kwh
    name: Battery 10 kWh
  - entity: home_battery_sizer:battery_delivered_daily_15kwh
    name: Battery 15 kWh
  - entity: home_battery_sizer:battery_delivered_daily_20kwh
    name: Battery 20 kWh
  - entity: home_battery_sizer:battery_delivered_daily_25kwh
    name: Battery 25 kWh
  - entity: home_battery_sizer:battery_delivered_daily_30kwh
    name: Battery 30 kWh
```

Adjust the battery size series to match the sizes you have configured. You can also add `home_battery_sizer:solar_direct_use_daily` as a series ("Consumed directly") to see how much of the production the house uses while the sun is up — production minus direct use minus a battery's bar is the surplus that battery fails to capture. On a sunny day with a small battery you will see high production, high export, and low battery coverage — larger batteries pull export down and battery coverage up.

> **Note:** The visual editor will show validation warnings for the `home_battery_sizer:` entries — that is expected. Save via the YAML editor and the card will render correctly.

### Card 4 — Solar year milestones

Shows the previous (complete) year's sequence for one battery size: when the panels wake up, when there is first surplus to store, from when to when the house is fully grid-free, and how the year winds down. The first two dates are attributes on the date sensors (see the Calendar sensor table), displayed with core `attribute` rows — no extra integrations needed.

```yaml
type: entities
title: Solar year milestones (20 kWh, previous year)
entities:
  - entity: sensor.home_battery_sizer_20_kwh_first_self_sufficient_day_previous_year
    type: attribute
    attribute: first_solar_production_day
    name: First production date
    icon: mdi:white-balance-sunny
  - entity: sensor.home_battery_sizer_20_kwh_first_self_sufficient_day_previous_year
    type: attribute
    attribute: first_solar_surplus_day
    name: First surplus date
    icon: mdi:battery-plus
  - entity: sensor.home_battery_sizer_20_kwh_first_self_sufficient_day_previous_year
    name: First fully grid-free date
  - entity: sensor.home_battery_sizer_20_kwh_last_self_sufficient_day_previous_year
    name: Last fully grid-free date
  - entity: sensor.home_battery_sizer_20_kwh_last_self_sufficient_day_previous_year
    type: attribute
    attribute: last_solar_surplus_day
    name: Last surplus date
    icon: mdi:battery-minus
  - entity: sensor.home_battery_sizer_20_kwh_last_self_sufficient_day_previous_year
    type: attribute
    attribute: last_solar_production_day
    name: Last production date
    icon: mdi:weather-sunset-down
```

Drop the `_previous_year` suffixes to follow the current year as it unfolds instead.

## How it works

The simulation runs hourly across all available data (up to two years). For each hour:

1. Consumption is estimated as `solar + grid_import − grid_export` from your historical meter readings
2. Solar first covers consumption directly
3. Any surplus charges the battery (90% round-trip efficiency)
4. Any deficit draws from the battery, then falls back to grid import if the battery is empty

Battery charge carries over between hours and days. A day counts as "self-sufficient" if total grid import needed after the battery is factored in is less than 10 Wh.

Results update every hour.

## Simulation assumptions

The simulation models two real-world battery characteristics that you configure during setup:

- **Usable capacity** (default 90%) — batteries cannot use 100% of their rated kWh due to chemistry and internal losses. A new battery typically delivers 85–95% of its rated capacity; this figure decreases as the battery ages.
- **Minimum state of charge** (default 5%) — most batteries reserve a buffer at the bottom to protect cell longevity. Check your battery's manual for the exact figure.

Two simplifications remain:

- **No charge/discharge rate limit** — the simulation assumes the battery can absorb or deliver any amount within a single hour. Real inverters have a maximum power rating (e.g. 5 kW).
- **Fixed round-trip efficiency** — a flat 90% is applied to every charge cycle regardless of temperature or state of charge.

## Tips

- Add a 0 kWh entry (no battery) as a baseline to see your current self-sufficiency from solar alone
- Enter the battery's *rated* capacity during setup — the usable capacity and minimum SoC settings handle the rest
- Self-sufficient days will plateau as you increase battery size — the last few days of grid import are typically dark winter days that no realistic battery can cover
- The "max consecutive days" sensor shows the longest summer streak — useful for understanding how long a run of good weather the battery can sustain
