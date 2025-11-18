"""Data collector for Curve Control - collects sensor data for thermal learning."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval, async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_SUPABASE_URL, DEFAULT_SUPABASE_ANON_KEY

_LOGGER = logging.getLogger(__name__)


class DataCollector:
    """Collects raw sensor readings every 5 minutes and sends to Supabase."""

    def __init__(
        self,
        hass: HomeAssistant,
        user_id: str,
        auth_token: str,
        temperature_entity: str,
        hvac_entity: str,
        thermostat_entity: str,
        humidity_entity: Optional[str] = None,
        weather_entity: Optional[str] = None,
        supabase_url: str = DEFAULT_SUPABASE_URL,
        coordinator=None,
    ):
        """Initialize the data collector."""
        self.hass = hass
        self.user_id = user_id
        self.auth_token = auth_token
        self.temperature_entity = temperature_entity
        self.hvac_entity = hvac_entity
        self.thermostat_entity = thermostat_entity
        self.humidity_entity = humidity_entity
        self.weather_entity = weather_entity
        self.supabase_url = supabase_url
        self.coordinator = coordinator

        # Storage for pending readings
        self.pending_readings: List[Dict] = []
        self.user_inputs_today: List[Dict] = []

        # Track unsubscribe functions
        self._unsub_5min = None
        self._unsub_hourly = None
        self._unsub_midnight = None

    async def async_start(self):
        """Start the data collection."""
        _LOGGER.info(f"Starting data collection for user {self.user_id}")

        # Collect readings every 5 minutes at even intervals (00, 05, 10, 15, etc.)
        self._unsub_5min = async_track_time_change(
            self.hass,
            self._collect_reading,
            minute=[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
            second=0,
        )

        # Send hourly batch at the top of each hour (1 second after to avoid race condition)
        self._unsub_hourly = async_track_time_change(
            self.hass,
            self._send_sensor_batch,
            minute=0,
            second=1,  # Wait 1 second after XX:00:00 reading is collected
        )

        # Send daily summary at midnight
        self._unsub_midnight = async_track_time_change(
            self.hass,
            self._send_daily_summary,
            hour=0,
            minute=5,  # 5 minutes after midnight to ensure day rollover
            second=0,
        )

        # Collect initial reading
        await self._collect_reading(None)

    async def async_stop(self):
        """Stop the data collection."""
        if self._unsub_5min:
            self._unsub_5min()
        if self._unsub_hourly:
            self._unsub_hourly()
        if self._unsub_midnight:
            self._unsub_midnight()

    async def _collect_reading(self, _):
        """Collect a single sensor reading."""
        try:
            # Get current sensor values
            temp_state = self.hass.states.get(self.temperature_entity)
            hvac_state = self.hass.states.get(self.hvac_entity)
            thermostat_state = self.hass.states.get(self.thermostat_entity)

            if not temp_state or not hvac_state or not thermostat_state:
                _LOGGER.warning("Missing required sensor states")
                return

            # Get humidity if available
            humidity = None
            if self.humidity_entity:
                humidity_state = self.hass.states.get(self.humidity_entity)
                if humidity_state and humidity_state.state not in [
                    "unknown",
                    "unavailable",
                ]:
                    try:
                        humidity = float(humidity_state.state)
                    except (ValueError, TypeError):
                        pass

            # Get HVAC mode (the user-set mode: heat, cool, auto, off, etc.)
            hvac_mode = hvac_state.state if hvac_state.state not in ["unknown", "unavailable"] else None

            # Get HVAC action from climate entity (what it's actually doing)
            hvac_action = hvac_state.attributes.get("hvac_action", "off").upper()
            # Map Home Assistant actions to our expected values
            if hvac_action in ["HEATING"]:
                hvac_action = "HEAT"
            elif hvac_action in ["COOLING"]:
                hvac_action = "COOL"
            else:
                hvac_action = "OFF"

            # Get fan mode (the user-set fan mode: auto, on, low, high, etc.)
            fan_mode = hvac_state.attributes.get("fan_mode", None)

            # Get fan state (current fan state/action if available)
            fan_state = hvac_state.attributes.get("fan_state", None)

            # Get current temperature (from climate entity attributes or sensor state)
            indoor_temp = None
            if "current_temperature" in temp_state.attributes:
                # Climate entity - temperature is in attributes
                indoor_temp = float(temp_state.attributes.get("current_temperature"))
            elif temp_state.state not in ["unknown", "unavailable"]:
                # Temperature sensor - temperature is the state
                try:
                    indoor_temp = float(temp_state.state)
                except (ValueError, TypeError):
                    _LOGGER.warning(f"Could not convert temperature state to float: {temp_state.state}")
                    return

            if indoor_temp is None:
                _LOGGER.warning("Could not read indoor temperature")
                return

            # Create reading
            reading = {
                "timestamp": datetime.now().isoformat(),
                "indoor_temp": indoor_temp,
                "indoor_humidity": humidity,
                "hvac_mode": hvac_mode,
                "hvac_state": hvac_action,
                "fan_mode": fan_mode,
                "fan_state": fan_state,
                "target_temp": float(thermostat_state.attributes.get("temperature", 0)),
                "optimization_mode": self.coordinator.optimization_mode if self.coordinator else "cool",
            }

            self.pending_readings.append(reading)

        except Exception as e:
            _LOGGER.error(f"Error collecting sensor reading: {e}")

    async def _send_sensor_batch(self, _=None):
        """Send a batch of sensor readings to Supabase."""
        if not self.pending_readings:
            return

        try:
            session = async_get_clientsession(self.hass)

            payload = {"user_id": self.user_id, "readings": self.pending_readings}

            async with session.post(
                f"{self.supabase_url}/functions/v1/sensor-data",
                json=payload,
                headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    _LOGGER.debug(f"Sent {len(self.pending_readings)} sensor readings")
                    self.pending_readings.clear()
                else:
                    error_text = await response.text()
                    _LOGGER.error(
                        f"Failed to send sensor readings: {response.status} - {error_text}"
                    )

        except Exception as e:
            _LOGGER.error(f"Error sending sensor readings: {e}")

    async def _send_daily_summary(self, _):
        """Send daily summary at midnight."""
        try:
            # Send any pending readings first
            if self.pending_readings:
                await self._send_sensor_batch()

            # Get weather forecast for next 24 hours
            weather_forecast = None
            if self.weather_entity:
                weather_state = self.hass.states.get(self.weather_entity)
                if weather_state:
                    # Get 24-hour hourly forecast using the weather.get_forecasts service
                    forecast_data = []
                    try:
                        forecast_response = await self.hass.services.async_call(
                            "weather",
                            "get_forecasts",
                            {"entity_id": self.weather_entity, "type": "hourly"},
                            blocking=True,
                            return_response=True,
                        )
                        if forecast_response and self.weather_entity in forecast_response:
                            forecast_data = forecast_response[self.weather_entity].get("forecast", [])[:24]  # Next 24 hours
                    except Exception as e:
                        _LOGGER.warning(f"Could not fetch hourly forecast: {e}")

                    weather_forecast = {
                        "condition": weather_state.state,
                        "temperature": weather_state.attributes.get("temperature"),
                        "humidity": weather_state.attributes.get("humidity"),
                        "forecast": forecast_data,
                    }

            # Prepare user inputs (services called today)
            user_inputs = {
                "inputs_today": len(self.user_inputs_today),
                "services_used": self.user_inputs_today,
            }

            # Send daily summary
            session = async_get_clientsession(self.hass)

            payload = {
                "user_id": self.user_id,
                "date": (datetime.now() - timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                ),  # Yesterday's data
                "user_inputs": user_inputs,
                "weather_forecast": weather_forecast,
                "optimization_mode": self.coordinator.optimization_mode if self.coordinator else "cool",
            }

            async with session.post(
                f"{self.supabase_url}/functions/v1/daily-summary",
                json=payload,
                headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    thermal_rates = result.get("thermal_rates", {})

                    _LOGGER.info(f"Daily summary sent. Thermal rates: {thermal_rates}")

                    # Return thermal rates for coordinator to use
                    return thermal_rates
                else:
                    error_text = await response.text()
                    _LOGGER.error(
                        f"Failed to send daily summary: {response.status} - {error_text}"
                    )
                    return None

            # Reset daily counters
            self.user_inputs_today.clear()

        except Exception as e:
            _LOGGER.error(f"Error sending daily summary: {e}")
            return None

    def log_user_input(self, service: str, data: Dict):
        """Log a user input/service call for today's summary."""
        self.user_inputs_today.append(
            {
                "timestamp": datetime.now().isoformat(),
                "service": service,
                "data": data,
            }
        )

    async def get_thermal_rates_from_supabase(self) -> Optional[Dict]:
        """Fetch the latest thermal rates from daily_summaries table."""
        try:
            # This could be enhanced to query Supabase directly
            # For now, thermal rates are returned by the daily summary endpoint
            pass
        except Exception as e:
            _LOGGER.error(f"Error fetching thermal rates: {e}")
            return None
