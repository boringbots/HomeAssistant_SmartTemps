"""The Curve Control Energy Optimizer integration."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any
import os

import aiohttp
import async_timeout
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_BACKEND_URL,
    CONF_SUPABASE_URL,
    CONF_USER_ID,
    CONF_AUTH_TOKEN,
    CONF_HOME_SIZE,
    CONF_TARGET_TEMP,
    CONF_LOCATION,
    CONF_TIME_AWAY,
    CONF_TIME_HOME,
    CONF_SAVINGS_LEVEL,
    CONF_THERMOSTAT_ENTITY,
    CONF_WEATHER_ENTITY,
    DEFAULT_BACKEND_URL,
    DEFAULT_SUPABASE_URL,
    DEFAULT_SUPABASE_ANON_KEY,
    INTERVALS_PER_DAY,
    COOLING_RATE_30MIN,
    HEATING_RATE_30MIN,
    DEADBAND_OFFSET,
)
from .data_collector import DataCollector

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.BUTTON, Platform.SELECT]


def _copy_card_file(source_path: str, dest_path: str, www_dir: str) -> bool:
    """Copy card file (runs in executor to avoid blocking)."""
    try:
        import shutil
        # Ensure www directory exists
        os.makedirs(www_dir, exist_ok=True)

        # Copy card file
        shutil.copy2(source_path, dest_path)
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to copy dashboard card: {e}")
        return False


async def _register_dashboard_card(hass: HomeAssistant) -> None:
    """Auto-register the dashboard card resource."""
    # Only register once
    if DOMAIN in hass.data and "card_registered" in hass.data[DOMAIN]:
        return

    # Get paths
    integration_dir = os.path.dirname(__file__)
    source_path = os.path.join(integration_dir, "www", "curve-control-card.js")
    www_dir = hass.config.path("www")
    dest_path = os.path.join(www_dir, "curve-control-card.js")

    # Check if copy is needed (do file checks in executor too)
    def _should_copy() -> bool:
        return not os.path.exists(dest_path) or os.path.getmtime(source_path) > os.path.getmtime(dest_path)

    try:
        should_copy = await hass.async_add_executor_job(_should_copy)

        if should_copy:
            # Copy card file in executor to avoid blocking
            success = await hass.async_add_executor_job(
                _copy_card_file, source_path, dest_path, www_dir
            )

            if success:
                _LOGGER.info(f"Dashboard card copied to {dest_path}")
                _LOGGER.info("=" * 80)
                _LOGGER.info("CURVE CONTROL DASHBOARD CARD SETUP:")
                _LOGGER.info("1. Go to Settings → Dashboards → ⋮ (three dots) → Resources")
                _LOGGER.info("2. Click '+ Add Resource'")
                _LOGGER.info("3. URL: /local/curve-control-card.js")
                _LOGGER.info("4. Resource type: JavaScript Module")
                _LOGGER.info("5. Click 'Create' then refresh your browser (Ctrl+Shift+R)")
                _LOGGER.info("=" * 80)
            else:
                return
    except Exception as e:
        _LOGGER.error(f"Error during card file copy: {e}")
        return

    # Mark as registered
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN]["card_registered"] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Curve Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Auto-register dashboard card resource
    await _register_dashboard_card(hass)

    # Create the data coordinator
    coordinator = CurveControlCoordinator(hass, entry)

    # Set up data collector if user is authenticated
    if coordinator.data_collector:
        await coordinator.data_collector.async_start()

    # Add delay to allow backend processing time before first optimization
    import asyncio
    _LOGGER.info("Calculating optimal temperature schedule...")
    await asyncio.sleep(10)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "config": entry.data,
    }
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_update_schedule(call):
        """Handle schedule update service call - updates config and saves to database."""
        await coordinator.async_update_schedule(call.data, save_to_db=True)

    async def handle_force_optimization(call):
        """Handle force optimization service call."""
        await coordinator.force_optimization()

    async def handle_optimize_schedule(call):
        """Handle optimize schedule service (save to Supabase + immediate optimization)."""
        await coordinator.async_optimize_and_save(immediate=True)

    hass.services.async_register(
        DOMAIN,
        "update_schedule",
        handle_update_schedule,
    )

    hass.services.async_register(
        DOMAIN,
        "force_optimization",
        handle_force_optimization,
    )

    hass.services.async_register(
        DOMAIN,
        "optimize_schedule",
        handle_optimize_schedule,
    )
    
    return True




async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Clean up data collector
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data:
        coordinator = data.get("coordinator")
        if coordinator:
            if coordinator.data_collector:
                await coordinator.data_collector.async_stop()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CurveControlCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Curve Control data from backend."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.hass = hass
        self.entry = entry
        self.backend_url = entry.data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)
        self.supabase_url = entry.data.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL)
        self.user_id = entry.data.get(CONF_USER_ID)
        self.auth_token = entry.data.get(CONF_AUTH_TOKEN)
        self.session = async_get_clientsession(hass)

        # Store configuration
        self.config = {
            "anonymousId": self.user_id,  # For device identification
            "homeSize": entry.data[CONF_HOME_SIZE],
            "homeTemperature": entry.data[CONF_TARGET_TEMP],
            "location": entry.data[CONF_LOCATION],
            "timeAway": str(entry.data[CONF_TIME_AWAY])[:5],  # Convert HH:MM:SS to HH:MM
            "timeHome": str(entry.data[CONF_TIME_HOME])[:5],  # Convert HH:MM:SS to HH:MM
            "savingsLevel": entry.data[CONF_SAVINGS_LEVEL],
        }

        # Initialize data storage
        self.schedule_data = None
        self.optimization_results = None
        self.heat_up_rate = HEATING_RATE_30MIN  # Default heating rate (1.25°F per 30 min)
        self.cool_down_rate = COOLING_RATE_30MIN  # Default cooling rate (-1.9335°F per 30 min)

        # Thermal rates from backend (learned rates)
        self.backend_heating_rate = None
        self.backend_cooling_rate = None
        self.backend_natural_rate = None
        self.thermal_rates_last_fetched = None

        # Debouncing for preventing duplicate service calls
        self._last_update_time = 0
        self._update_debounce_seconds = 2  # Ignore calls within 2 seconds

        # Initialize data collector (if user is authenticated)
        thermostat_entity = entry.data.get(CONF_THERMOSTAT_ENTITY)
        self.data_collector = None
        if self.user_id and self.auth_token and thermostat_entity:
            self.data_collector = DataCollector(
                hass=hass,
                user_id=self.user_id,
                auth_token=self.auth_token,
                temperature_entity=thermostat_entity,  # Use same entity as climate
                hvac_entity=thermostat_entity,
                thermostat_entity=thermostat_entity,
                humidity_entity=None,  # Could be added to config in future
                weather_entity=entry.data.get(CONF_WEATHER_ENTITY),
                supabase_url=self.supabase_url,
                coordinator=self,  # Pass coordinator for optimization_mode tracking
            )
            _LOGGER.info(f"Data collector initialized for user {self.user_id}")

        # Store daily schedule - no automatic polling
        self._daily_schedule = None
        self._schedule_date = None
        self._midnight_listener = None
        self._custom_temperature_schedule = None  # For detailed frontend schedules
        self.optimization_mode = "cool"  # Optimization mode: 'off', 'cool', or 'heat'
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,  # Disable automatic polling
        )
        
        # Set up midnight optimization
        self._setup_midnight_optimization()
    
    def _setup_midnight_optimization(self) -> None:
        """Set up automatic optimization at midnight."""
        import homeassistant.util.dt as dt_util
        from homeassistant.helpers.event import async_track_time_change
        
        # Schedule optimization at midnight every day
        self._midnight_listener = async_track_time_change(
            self.hass,
            self._handle_midnight_optimization,
            hour=0,
            minute=0,
            second=0,
        )
        _LOGGER.info("Scheduled daily optimization at midnight")
    
    async def _handle_midnight_optimization(self, now) -> None:
        """Handle midnight optimization trigger."""
        _LOGGER.info("Running scheduled midnight optimization")
        await self.async_request_refresh()

    async def _async_fetch_thermal_rates_from_backend(self) -> None:
        """Fetch thermal rates from Supabase backend."""
        if not self.user_id or not self.auth_token:
            _LOGGER.debug("Cannot fetch thermal rates - user not authenticated")
            return

        try:
            async with async_timeout.timeout(10):
                response = await self.session.post(
                    f"{self.supabase_url}/functions/v1/calculate-rates",
                    json={"anonymous_id": self.user_id},
                    headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
                )

                if response.status == 200:
                    data = await response.json()

                    if data.get("success") and data.get("thermal_rates"):
                        rates = data["thermal_rates"]
                        self.backend_heating_rate = rates.get("heating_rate")
                        self.backend_cooling_rate = rates.get("cooling_rate")
                        self.backend_natural_rate = rates.get("natural_rate")

                        from datetime import datetime
                        self.thermal_rates_last_fetched = datetime.now()

                        # Update current rates if backend provided valid values
                        if self.backend_heating_rate is not None:
                            self.heat_up_rate = self.backend_heating_rate
                        if self.backend_cooling_rate is not None:
                            self.cool_down_rate = self.backend_cooling_rate

                        _LOGGER.info(
                            f"Fetched thermal rates from backend - "
                            f"Heating: {self.backend_heating_rate:.4f if self.backend_heating_rate else 'N/A'}, "
                            f"Cooling: {self.backend_cooling_rate:.4f if self.backend_cooling_rate else 'N/A'}, "
                            f"Natural: {self.backend_natural_rate:.4f if self.backend_natural_rate else 'N/A'}"
                        )
                    else:
                        _LOGGER.debug("Backend returned no thermal rates - using defaults")
                else:
                    _LOGGER.warning(f"Backend returned status {response.status} when fetching thermal rates")

        except aiohttp.ClientError as err:
            _LOGGER.debug(f"Could not fetch thermal rates from backend: {err}")
        except Exception as err:
            _LOGGER.debug(f"Error fetching thermal rates: {err}")

    async def _async_update_data(self):
        """Fetch data from backend."""
        _LOGGER.debug("_async_update_data() called")
        try:
            # Get current thermostat state if available (for reference, but don't override user preferences)
            thermostat_entity = self.entry.data.get(CONF_THERMOSTAT_ENTITY)
            current_actual_temp = None
            if thermostat_entity:
                state = self.hass.states.get(thermostat_entity)
                if state:
                    current_actual_temp = state.attributes.get("current_temperature")
                    # _LOGGER.debug(f"Current actual thermostat temperature: {current_actual_temp}")
            
            # _LOGGER.debug(f"Config before optimization - homeTemperature: {self.config.get('homeTemperature')}")

            # Fetch thermal rates from backend before optimization
            await self._async_fetch_thermal_rates_from_backend()

            # Generate 30-minute temperature schedule (custom or basic)
            if self._custom_temperature_schedule:
                schedule_data = self._custom_temperature_schedule
                _LOGGER.info("Using custom temperature schedule")
                # _LOGGER.debug(f"Custom schedule has {len(schedule_data.get('highTemperatures', []))} high temps")
            else:
                schedule_data = self._build_30min_temperature_schedule()
                # _LOGGER.info("Using basic temperature schedule")
                # _LOGGER.debug(f"Basic schedule has {len(schedule_data.get('highTemperatures', []))} high temps")

            # Prepare request with schedule data
            request_data = {
                **self.config,
                "temperatureSchedule": schedule_data,
                "heatUpRate": self.heat_up_rate,
                "coolDownRate": self.cool_down_rate,
                "mode": self.optimization_mode,
            }

            # Only send naturalRate if we have a learned value
            # Let Python backend use its mode-aware defaults otherwise:
            # - Cool mode: +0.5535 (house warms naturally in summer)
            # - Heat mode: -0.5535 (house cools naturally in winter)
            if self.backend_natural_rate is not None:
                request_data["naturalRate"] = self.backend_natural_rate

            # _LOGGER.debug(f"Sending to Heroku backend - homeSize: {request_data.get('homeSize')}, location: {request_data.get('location')}")
            # _LOGGER.debug(f"temperatureSchedule high temps (first 4): {schedule_data.get('highTemperatures', [])[:4]}")
            
            # Call backend for optimization
            async with async_timeout.timeout(30):
                response = await self.session.post(
                    f"{self.backend_url}/generate_schedule",
                    json=request_data,
                )
                response.raise_for_status()
                data = await response.json()
                
                # Validate response structure
                if not isinstance(data, dict):
                    raise ValueError("Backend returned invalid data format")
                
                # Store the results with validation
                self.optimization_results = data
                self.schedule_data = data.get("HourlyTemperature", [])
                
                # Store the daily schedule with date
                from datetime import datetime
                self._daily_schedule = data.get("bestTempActual", [])
                self._schedule_date = datetime.now().date()
                
                _LOGGER.info(f"Optimization complete. Received {len(self.schedule_data)} hourly temperatures and {len(self._daily_schedule)} daily setpoints")
                
                return data
                
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Backend communication error: {err}")
            raise UpdateFailed(f"Error communicating with backend: {err}")
        except Exception as err:
            _LOGGER.error(f"Coordinator optimization error: {err}")
            raise UpdateFailed(f"Unexpected error: {err}")
    
    async def async_update_schedule(self, data: dict[str, Any], save_to_db: bool = False) -> None:
        """Update the schedule configuration and trigger immediate optimization."""
        # Debounce: Prevent duplicate calls within 2 seconds
        current_time = time.time()
        time_since_last_update = current_time - self._last_update_time

        if time_since_last_update < self._update_debounce_seconds:
            _LOGGER.warning(f"Ignoring duplicate service call (called {time_since_last_update:.2f}s after previous call)")
            return

        self._last_update_time = current_time
        _LOGGER.info("User updated preferences - triggering optimization")
        # _LOGGER.debug(f"Received service call data: {data}")

        # Update configuration from frontend data
        if "homeSize" in data:
            self.config["homeSize"] = data["homeSize"]
        if "homeTemperature" in data:
            self.config["homeTemperature"] = data["homeTemperature"]
        if "location" in data:
            self.config["location"] = data["location"]
        if "savingsLevel" in data:
            self.config["savingsLevel"] = data["savingsLevel"]
        if "timeAway" in data:
            # Ensure time is in HH:MM format - let it fail if format is wrong
            self.config["timeAway"] = str(data["timeAway"])[:5]
        if "timeHome" in data:
            # Ensure time is in HH:MM format - let it fail if format is wrong
            self.config["timeHome"] = str(data["timeHome"])[:5]
        if "optimizationMode" in data:
            # Update optimization mode from dashboard
            self.optimization_mode = data["optimizationMode"]
            _LOGGER.info(f"Optimization mode set to: {self.optimization_mode}")

        # Store custom temperature schedule if provided (for detailed mode)
        if "temperatureSchedule" in data:
            self._custom_temperature_schedule = data["temperatureSchedule"]
            _LOGGER.info(f"Custom temperature schedule received from frontend")
            _LOGGER.debug(f"Custom schedule - High temps (first 8): {self._custom_temperature_schedule.get('highTemperatures', [])[:8]}")
            _LOGGER.debug(f"Custom schedule - Low temps (first 8): {self._custom_temperature_schedule.get('lowTemperatures', [])[:8]}")
            _LOGGER.debug(f"Custom schedule - Total intervals: {len(self._custom_temperature_schedule.get('highTemperatures', []))}")
        else:
            # Clear custom schedule for basic mode
            self._custom_temperature_schedule = None

        _LOGGER.debug(f"Updated config after service call: {self.config}")

        # Trigger immediate optimization
        _LOGGER.debug("Calling async_request_refresh() to trigger optimization")
        await self.async_request_refresh()
        _LOGGER.debug(f"async_request_refresh() completed. optimization_results: {self.optimization_results is not None}")

        # Save to database if requested (for Apply Settings and Apply Custom Schedule buttons)
        if save_to_db:
            if self.user_id and self.auth_token:
                _LOGGER.info("Saving updated preferences to database")
                await self._save_preferences_to_db()
            else:
                _LOGGER.warning(f"Cannot save to database - user_id: {self.user_id is not None}, auth_token: {self.auth_token is not None}")
    
    async def force_optimization(self) -> None:
        """Force immediate optimization."""
        _LOGGER.info("Forcing immediate optimization")
        await self.async_request_refresh()
    
    def _build_30min_temperature_schedule(self) -> dict:
        """Build 30-minute temperature schedule to send to backend."""
        from datetime import datetime, time
        
        base_temp = self.config["homeTemperature"]
        away_time = self.config["timeAway"]
        home_time = self.config["timeHome"]
        savings_level = self.config["savingsLevel"]
        
        # Convert times to 30-minute intervals
        away_interval = self._time_to_30min_index(away_time)
        home_interval = self._time_to_30min_index(home_time)
        
        # Calculate temperature offsets based on savings level
        savings_offset = self._calculate_savings_offset(savings_level)
        
        high_temps = []
        low_temps = []
        
        for interval in range(INTERVALS_PER_DAY):
            if away_interval <= interval <= home_interval:
                # Away period - allow more temperature variation for savings
                high_temps.append(base_temp + savings_offset + DEADBAND_OFFSET)
                low_temps.append(base_temp - savings_offset - DEADBAND_OFFSET)
            else:
                # Home period - tighter comfort range
                high_temps.append(base_temp + DEADBAND_OFFSET)
                low_temps.append(base_temp - DEADBAND_OFFSET)
        
        return {
            "highTemperatures": high_temps,
            "lowTemperatures": low_temps,
            "intervalMinutes": 30,
            "totalIntervals": INTERVALS_PER_DAY
        }
    
    def _time_to_30min_index(self, time_str: str) -> int:
        """Convert time string to 30-minute interval index (0-47)."""
        try:
            from datetime import datetime
            # Handle both HH:MM and HH:MM:SS formats
            time_str = str(time_str)[:5]  # Ensure HH:MM format
            time_obj = datetime.strptime(time_str, "%H:%M")
            total_minutes = time_obj.hour * 60 + time_obj.minute
            return total_minutes // 30
        except (ValueError, AttributeError):
            return 16  # Default to 8:00 AM
    
    def _calculate_savings_offset(self, savings_level: int) -> float:
        """Convert savings level to temperature offset."""
        savings_map = {1: 2, 2: 6, 3: 12}
        return savings_map.get(savings_level, 6)
    
    def get_current_setpoint(self) -> float | None:
        """Get the current temperature setpoint based on optimization."""
        if not self.optimization_results:
            return None
        
        best_temps = self.optimization_results.get("bestTempActual", [])
        if not best_temps:
            return None
        
        # Get current 30-minute interval
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        if 0 <= interval < len(best_temps):
            return best_temps[interval]
        
        return None
    
    def get_schedule_bounds(self) -> tuple[list, list] | None:
        """Get the high and low temperature bounds for the current schedule."""
        if not self.schedule_data or len(self.schedule_data) < 3:
            return None

        return (self.schedule_data[1], self.schedule_data[2])  # high, low bounds

    async def _save_preferences_to_db(self) -> None:
        """Save current preferences and optimization results to database (without re-running optimization)."""
        if not self.user_id or not self.auth_token:
            _LOGGER.warning("Cannot save to database - user not authenticated")
            return

        try:
            # Get weather forecast if available
            weather_forecast = None
            weather_entity = self.entry.data.get(CONF_WEATHER_ENTITY)
            if weather_entity:
                weather_state = self.hass.states.get(weather_entity)
                if weather_state:
                    forecast_data = []
                    try:
                        forecast_response = await self.hass.services.async_call(
                            "weather",
                            "get_forecasts",
                            {"entity_id": weather_entity, "type": "hourly"},
                            blocking=True,
                            return_response=True,
                        )
                        if forecast_response and weather_entity in forecast_response:
                            forecast_data = forecast_response[weather_entity].get("forecast", [])[:24]
                    except Exception as e:
                        _LOGGER.warning(f"Could not fetch hourly forecast: {e}")

                    weather_forecast = {
                        "condition": weather_state.state,
                        "temperature": weather_state.attributes.get("temperature"),
                        "humidity": weather_state.attributes.get("humidity"),
                        "forecast": forecast_data,
                    }

            # Build temperature schedule
            if self._custom_temperature_schedule:
                schedule_data = self._custom_temperature_schedule
            else:
                schedule_data = self._build_30min_temperature_schedule()

            # Prepare preferences payload
            preferences = {
                "home_size": self.config["homeSize"],
                "base_temperature": self.config["homeTemperature"],
                "target_temperature": self.config["homeTemperature"],
                "location": self.config["location"],
                "savings_level": self.config["savingsLevel"],
                "time_away": self.config["timeAway"],
                "time_home": self.config["timeHome"],
                "high_temperatures": schedule_data.get("highTemperatures"),
                "low_temperatures": schedule_data.get("lowTemperatures"),
                "heating_rate": self.backend_heating_rate,
                "cooling_rate": self.backend_cooling_rate,
                "natural_rate": self.backend_natural_rate,
                "optimization_mode": self.optimization_mode,
            }

            # Call save-preferences edge function with pre-computed optimization results
            payload = {
                "user_id": self.user_id,
                "preferences": preferences,
                "weather_forecast": weather_forecast,
                "immediate_optimization": False,  # Don't re-run optimization
                "optimization_results": self.optimization_results if self.optimization_results else None,
            }

            async with async_timeout.timeout(30):  # Timeout for saving to database
                response = await self.session.post(
                    f"{self.supabase_url}/functions/v1/save-preferences",
                    json=payload,
                    headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
                )
                response.raise_for_status()
                result = await response.json()

                if result.get("status") == "success":
                    _LOGGER.info("Preferences saved to database successfully")

                    # Process returned optimization results
                    if "optimization" in result:
                        optimization_data = result["optimization"]
                        # Store the optimization results
                        self.optimization_results = optimization_data
                        self.schedule_data = optimization_data.get("HourlyTemperature", [])
                        self._daily_schedule = optimization_data.get("bestTempActual", [])

                        from datetime import datetime
                        self._schedule_date = datetime.now().date()

                        _LOGGER.info(
                            f"Optimization outputs saved - Savings: ${optimization_data.get('costSavings', 0):.2f}"
                        )

                        # Trigger coordinator update to notify entities
                        self.async_set_updated_data(optimization_data)
                else:
                    _LOGGER.warning(f"Save preferences returned status: {result.get('status')}")

        except Exception as err:
            _LOGGER.error(f"Error saving preferences to database: {err}")

    async def async_optimize_and_save(self, immediate: bool = True) -> None:
        """Optimize schedule and save preferences to Supabase for nightly runs."""
        if not self.user_id or not self.auth_token:
            _LOGGER.error("Cannot optimize - user not authenticated")
            return

        _LOGGER.info("Optimize button pressed - Running optimization and saving to Supabase")

        try:
            # Get weather forecast if available
            weather_forecast = None
            weather_entity = self.entry.data.get(CONF_WEATHER_ENTITY)
            if weather_entity:
                weather_state = self.hass.states.get(weather_entity)
                if weather_state:
                    # Get 24-hour hourly forecast using the weather.get_forecasts service
                    forecast_data = []
                    try:
                        forecast_response = await self.hass.services.async_call(
                            "weather",
                            "get_forecasts",
                            {"entity_id": weather_entity, "type": "hourly"},
                            blocking=True,
                            return_response=True,
                        )
                        if forecast_response and weather_entity in forecast_response:
                            forecast_data = forecast_response[weather_entity].get("forecast", [])[:24]  # Next 24 hours
                    except Exception as e:
                        _LOGGER.warning(f"Could not fetch hourly forecast: {e}")

                    weather_forecast = {
                        "condition": weather_state.state,
                        "temperature": weather_state.attributes.get("temperature"),
                        "humidity": weather_state.attributes.get("humidity"),
                        "forecast": forecast_data,
                    }

            # Build temperature schedule
            if self._custom_temperature_schedule:
                schedule_data = self._custom_temperature_schedule
            else:
                schedule_data = self._build_30min_temperature_schedule()

            # Prepare preferences payload
            preferences = {
                "home_size": self.config["homeSize"],
                "base_temperature": self.config["homeTemperature"],
                "target_temperature": self.config["homeTemperature"],
                "location": self.config["location"],
                "savings_level": self.config["savingsLevel"],
                "time_away": self.config["timeAway"],
                "time_home": self.config["timeHome"],
                "high_temperatures": schedule_data.get("highTemperatures"),
                "low_temperatures": schedule_data.get("lowTemperatures"),
                "heating_rate": self.backend_heating_rate,
                "cooling_rate": self.backend_cooling_rate,
                "natural_rate": self.backend_natural_rate,
                "optimization_mode": self.optimization_mode,
            }

            # Call save-preferences edge function
            payload = {
                "user_id": self.user_id,
                "preferences": preferences,
                "weather_forecast": weather_forecast,
                "immediate_optimization": immediate,
            }

            async with async_timeout.timeout(60):  # Longer timeout for optimization
                response = await self.session.post(
                    f"{self.supabase_url}/functions/v1/save-preferences",
                    json=payload,
                    headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
                )
                response.raise_for_status()
                result = await response.json()

                if result.get("status") == "success":
                    _LOGGER.info("Preferences saved successfully")

                    # If immediate optimization was requested and returned data
                    if immediate and "optimization" in result:
                        optimization_data = result["optimization"]
                        # Store the optimization results
                        self.optimization_results = optimization_data
                        self.schedule_data = optimization_data.get("HourlyTemperature", [])
                        self._daily_schedule = optimization_data.get("bestTempActual", [])

                        from datetime import datetime
                        self._schedule_date = datetime.now().date()

                        _LOGGER.info(
                            f"Immediate optimization complete - Savings: ${optimization_data.get('costSavings', 0):.2f}"
                        )

                        # Trigger coordinator update to notify entities
                        self.async_set_updated_data(optimization_data)
                    else:
                        _LOGGER.info("Preferences saved for nightly optimization")
                else:
                    _LOGGER.warning(f"Save preferences returned status: {result.get('status')}")

        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error saving preferences to Supabase: {err}")
        except Exception as err:
            _LOGGER.error(f"Unexpected error saving preferences: {err}")