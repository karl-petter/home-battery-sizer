"""Constants for the Home Battery Sizer integration."""

DOMAIN = "home_battery_sizer"

CONF_SOLAR_SENSOR = "solar_sensor"
CONF_GRID_IMPORT_SENSOR = "grid_import_sensor"
CONF_GRID_EXPORT_SENSOR = "grid_export_sensor"
CONF_BATTERY_SIZE = "battery_size"
CONF_USABLE_CAPACITY_PCT = "usable_capacity_pct"
CONF_MIN_SOC_PCT = "min_soc_pct"

DEFAULT_USABLE_CAPACITY_PCT = 90.0
DEFAULT_MIN_SOC_PCT = 5.0

BATTERY_EFFICIENCY = 0.90  # Fixed 90% round-trip efficiency
