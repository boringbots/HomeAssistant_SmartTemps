"""Constants for the Curve Control integration."""
from typing import Final

DOMAIN: Final = "curve_control"

# Configuration keys
CONF_BACKEND_URL: Final = "backend_url"
CONF_SUPABASE_URL: Final = "supabase_url"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_EMAIL: Final = "email"
CONF_USER_ID: Final = "user_id"
CONF_AUTH_TOKEN: Final = "auth_token"
CONF_HOME_SIZE: Final = "home_size"
CONF_TARGET_TEMP: Final = "target_temperature"
CONF_LOCATION: Final = "location"
CONF_TIME_AWAY: Final = "time_away"
CONF_TIME_HOME: Final = "time_home"
CONF_SAVINGS_LEVEL: Final = "savings_level"
CONF_THERMOSTAT_ENTITY: Final = "thermostat_entity"
CONF_WEATHER_ENTITY: Final = "weather_entity"

# Defaults
DEFAULT_BACKEND_URL: Final = "https://ha-smart-temps-backend-b95c9357605a.herokuapp.com"
DEFAULT_SUPABASE_URL: Final = "https://wrbtjomwnovcnuelxioe.supabase.co"
DEFAULT_SUPABASE_ANON_KEY: Final = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IndyYnRqb213bm92Y251ZWx4aW9lIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjEwNzUxNjMsImV4cCI6MjA3NjY1MTE2M30.DygiIzKqLjZWUrC79CWn46DNzVQKeOCkGokiEqyFHNY"
DEFAULT_HOME_SIZE: Final = 2000
DEFAULT_TARGET_TEMP: Final = 72
DEFAULT_LOCATION: Final = 1
DEFAULT_TIME_AWAY: Final = "08:00"
DEFAULT_TIME_HOME: Final = "17:00"
DEFAULT_SAVINGS_LEVEL: Final = 1

# Update interval in minutes (DEPRECATED - now event-driven)
# UPDATE_INTERVAL: Final = 30

# Time intervals
INTERVALS_PER_HOUR: Final = 2  # 30-minute intervals
INTERVALS_PER_DAY: Final = 48  # 24 hours * 2 intervals

# Location options
LOCATIONS: Final = {
    1: "San Diego Gas & Electric TOU-DR1",
    2: "San Diego Gas & Electric TOU-DR2",
    3: "San Diego Gas & Electric TOU-DR-P",
    4: "San Diego Gas & Electric TOU-ELEC",
    5: "San Diego Gas & Electric Standard DR",
    6: "New Hampshire TOU Whole House Domestic",
    7: "Texas XCEL Time-Of-Use",
    8: "NYC ConEdison Residential TOU",
}

# Savings levels
SAVINGS_LEVELS: Final = {
    1: "Low (2°F offset)",
    2: "Medium (6°F offset)",
    3: "High (12°F offset)",
}

# Attributes
ATTR_COST_SAVINGS: Final = "cost_savings"
ATTR_PERCENT_SAVINGS: Final = "percent_savings"
ATTR_CO2_AVOIDED: Final = "co2_avoided"
ATTR_CARS_EQUIVALENT: Final = "cars_equivalent"
ATTR_SCHEDULE_HIGH: Final = "schedule_high"
ATTR_SCHEDULE_LOW: Final = "schedule_low"
ATTR_BEST_TEMP_ACTUAL: Final = "best_temperature_actual"
ATTR_HEAT_UP_RATE: Final = "heat_up_rate"
ATTR_COOL_DOWN_RATE: Final = "cool_down_rate"
ATTR_CURRENT_INTERVAL: Final = "current_interval"
ATTR_NEXT_SETPOINT: Final = "next_setpoint"
ATTR_OPTIMIZATION_STATUS: Final = "optimization_status"

# Service names
SERVICE_UPDATE_SCHEDULE: Final = "update_schedule"
SERVICE_FORCE_OPTIMIZATION: Final = "force_optimization"
SERVICE_UPDATE_RATES: Final = "update_rates"

# Entity IDs
ENTITY_CLIMATE: Final = "climate.curve_control_thermostat"
ENTITY_SENSOR_SAVINGS: Final = "sensor.curve_control_savings"
ENTITY_SENSOR_CO2: Final = "sensor.curve_control_co2_avoided"
ENTITY_SENSOR_STATUS: Final = "sensor.curve_control_status"

# Temperature calculation constants (signed convention)
COOLING_RATE_30MIN: Final = -1.9335  # Negative for cooling (degrees F per 30 min when AC is ON)
HEATING_RATE_30MIN: Final = 1.25  # Positive for heating (degrees F per 30 min when heat is ON)
NATURAL_DRIFT_30MIN: Final = 0.5535  # Natural temperature rise when HVAC is OFF (summer baseline)
DEADBAND_OFFSET: Final = 1.4  # Deadband temperature offset
NORMAL_AWAY_OFFSET: Final = 3  # Normal away temperature offset

# Deprecated - use signed constants above
COOL_30MIN: Final = -1.9335  # Legacy - use COOLING_RATE_30MIN
HEAT_30MIN: Final = 0.5535  # Legacy - use NATURAL_DRIFT_30MIN

# HVAC constants
AREA_CONVERSION: Final = 20  # BTU/h minimum size AC for house conversion
SEER2: Final = 14  # BTU/h-W conversion rate
NUMBER_DAYS: Final = 120  # Number of days for cost calculation

# Solar hours (30-minute intervals)
SUNRISE_INDEX: Final = 15  # Average US sunrise is 7:28am
SUNSET_INDEX: Final = 34   # Average US sunset is 5:12pm

# CO2 calculation constants
CO2_CONVERSION: Final = 0.000699  # Metric tons of CO2 per kWh
CAR_CONVERSION: Final = 4.6  # Metric tons per year per car