"""Thermal learning module for calculating heat-up and cool-down rates."""
from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .const import (
    DOMAIN,
    COOL_30MIN,
    HEAT_30MIN,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = "thermal_learning"

# Learning parameters
MIN_TEMP_CHANGE = 0.5  # Minimum temperature change to consider valid
MAX_TEMP_CHANGE = 10.0  # Maximum temperature change to consider valid
MIN_INTERVAL_MINUTES = 20  # Minimum time interval for measurement
MAX_INTERVAL_MINUTES = 60  # Maximum time interval for measurement  
MIN_SAMPLES_FOR_CALCULATION = 5  # Minimum samples before calculating rates
ROLLING_WINDOW_DAYS = 7  # Number of days for rolling average


class ThermalDataPoint:
    """Single thermal measurement data point."""
    
    def __init__(
        self,
        timestamp: datetime,
        temp_start: float,
        temp_end: float,
        hvac_action: str,
        interval_minutes: float,
    ):
        self.timestamp = timestamp
        self.temp_start = temp_start
        self.temp_end = temp_end
        self.hvac_action = hvac_action  # 'heating', 'cooling', 'idle', 'off'
        self.interval_minutes = interval_minutes
        self.temp_change = temp_end - temp_start
        self.rate_per_30min = (self.temp_change / interval_minutes) * 30 if interval_minutes > 0 else 0


class ThermalLearningManager:
    """Manages thermal learning for a thermostat."""
    
    def __init__(self, hass: HomeAssistant, thermostat_entity_id: str):
        """Initialize thermal learning manager."""
        self.hass = hass
        self.thermostat_entity_id = thermostat_entity_id
        self.store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{thermostat_entity_id.replace('.', '_')}")
        
        # In-memory data storage
        self.thermal_data: deque[ThermalDataPoint] = deque(maxlen=1000)  # Keep last 1000 points
        self.last_measurement: Optional[Dict] = None
        
        # Calculated rates
        self.heating_rate: Optional[float] = None      # When heater is ON
        self.cooling_rate: Optional[float] = None      # When AC is ON
        self.natural_rate: Optional[float] = None      # When HVAC is OFF/idle
        self.last_calculation: Optional[datetime] = None
        
        # State tracking
        self._unsubscribe_state_listener = None
        
    async def async_setup(self) -> None:
        """Set up thermal learning."""
        # Load existing data
        await self._async_load_data()
        
        # Start state monitoring
        self._start_state_monitoring()
        
        # Calculate initial rates
        await self._async_calculate_rates()
        
    async def async_cleanup(self) -> None:
        """Clean up thermal learning."""
        if self._unsubscribe_state_listener:
            self._unsubscribe_state_listener()
        await self._async_save_data()
    
    def _start_state_monitoring(self) -> None:
        """Start monitoring thermostat state changes."""
        self._unsubscribe_state_listener = async_track_state_change_event(
            self.hass,
            [self.thermostat_entity_id],
            self._async_state_changed_listener
        )
        
        # Get initial state
        state = self.hass.states.get(self.thermostat_entity_id)
        if state:
            self._record_initial_state(state)
    
    @callback
    def _record_initial_state(self, state) -> None:
        """Record initial thermostat state."""
        try:
            current_temp = float(state.attributes.get('current_temperature', 0))
            hvac_action = state.attributes.get('hvac_action', 'unknown')
            
            self.last_measurement = {
                'timestamp': datetime.now(),
                'temperature': current_temp,
                'hvac_action': hvac_action,
            }
            
        except (ValueError, TypeError) as err:
            _LOGGER.debug(f"Could not record initial state: {err}")
    
    @callback
    def _async_state_changed_listener(self, event) -> None:
        """Handle thermostat state changes."""
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
            
        # Schedule processing of state change
        self.hass.async_create_task(self._async_process_state_change(new_state))
    
    async def _async_process_state_change(self, state) -> None:
        """Process a thermostat state change."""
        try:
            current_temp = float(state.attributes.get('current_temperature', 0))
            hvac_action = state.attributes.get('hvac_action', 'unknown')
            now = datetime.now()
            
            # Check if we have a previous measurement
            if self.last_measurement is None:
                self.last_measurement = {
                    'timestamp': now,
                    'temperature': current_temp,
                    'hvac_action': hvac_action,
                }
                return
            
            # Calculate time interval
            time_diff = now - self.last_measurement['timestamp']
            interval_minutes = time_diff.total_seconds() / 60
            
            # Check if interval is valid for learning
            if MIN_INTERVAL_MINUTES <= interval_minutes <= MAX_INTERVAL_MINUTES:
                temp_change = current_temp - self.last_measurement['temperature']
                
                # Check if temperature change is significant enough
                if abs(temp_change) >= MIN_TEMP_CHANGE and abs(temp_change) <= MAX_TEMP_CHANGE:
                    # Create thermal data point
                    data_point = ThermalDataPoint(
                        timestamp=now,
                        temp_start=self.last_measurement['temperature'],
                        temp_end=current_temp,
                        hvac_action=self.last_measurement['hvac_action'],
                        interval_minutes=interval_minutes,
                    )
                    
                    # Add to our data collection
                    self.thermal_data.append(data_point)
                    
                    _LOGGER.debug(
                        f"Recorded thermal data: {temp_change:.1f}°F over {interval_minutes:.1f}min "
                        f"during {hvac_action} = {data_point.rate_per_30min:.3f}°F/30min"
                    )
                    
                    # Recalculate rates periodically
                    if (self.last_calculation is None or 
                        now - self.last_calculation > timedelta(hours=1)):
                        await self._async_calculate_rates()
            
            # Update last measurement
            self.last_measurement = {
                'timestamp': now,
                'temperature': current_temp,
                'hvac_action': hvac_action,
            }
            
        except (ValueError, TypeError) as err:
            _LOGGER.debug(f"Error processing state change: {err}")
    
    async def _async_calculate_rates(self) -> None:
        """Calculate heating, cooling, and natural rates from collected data."""
        now = datetime.now()
        cutoff_date = now - timedelta(days=ROLLING_WINDOW_DAYS)

        # Filter recent data
        recent_data = [
            point for point in self.thermal_data
            if point.timestamp > cutoff_date
        ]

        # Separate data by HVAC action and temperature change direction
        heating_rates = []      # When heater is ON and temp rises
        cooling_rates = []      # When AC is ON and temp drops
        natural_rates = []      # When HVAC is OFF/idle (any temp change)

        for point in recent_data:
            if point.hvac_action == 'heating' and point.temp_change > 0:
                # Heater is on and temperature is rising
                heating_rates.append(point.rate_per_30min)
            elif point.hvac_action == 'cooling' and point.temp_change < 0:
                # AC is on and temperature is dropping (use absolute value for positive rate)
                cooling_rates.append(abs(point.rate_per_30min))
            elif point.hvac_action in ['idle', 'off']:
                # HVAC is off - natural temperature change (can be positive or negative)
                natural_rates.append(point.rate_per_30min)

        # Calculate averages if we have enough data
        if len(heating_rates) >= MIN_SAMPLES_FOR_CALCULATION:
            self.heating_rate = sum(heating_rates) / len(heating_rates)
            _LOGGER.info(f"Calculated heating rate: {self.heating_rate:.4f}°F/30min from {len(heating_rates)} samples")

        if len(cooling_rates) >= MIN_SAMPLES_FOR_CALCULATION:
            self.cooling_rate = sum(cooling_rates) / len(cooling_rates)
            _LOGGER.info(f"Calculated cooling rate: {self.cooling_rate:.4f}°F/30min from {len(cooling_rates)} samples")

        if len(natural_rates) >= MIN_SAMPLES_FOR_CALCULATION:
            self.natural_rate = sum(natural_rates) / len(natural_rates)
            _LOGGER.info(f"Calculated natural rate: {self.natural_rate:.4f}°F/30min from {len(natural_rates)} samples")

        self.last_calculation = now

        # Save updated data
        await self._async_save_data()
    
    def get_thermal_rates(self) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Get current thermal rates: (heating, cooling, natural)."""
        return self.heating_rate, self.cooling_rate, self.natural_rate

    def get_thermal_rates_with_fallback(self) -> Tuple[float, float, float]:
        """Get thermal rates with fallback to defaults: (heating, cooling, natural)."""
        heating_rate = self.heating_rate if self.heating_rate is not None else HEAT_30MIN * 3  # Heating should be faster than natural
        cooling_rate = self.cooling_rate if self.cooling_rate is not None else COOL_30MIN
        natural_rate = self.natural_rate if self.natural_rate is not None else HEAT_30MIN  # Natural heat gain
        return heating_rate, cooling_rate, natural_rate
    
    def has_sufficient_data(self) -> bool:
        """Check if we have sufficient data for reliable calculations."""
        now = datetime.now()
        cutoff_date = now - timedelta(days=ROLLING_WINDOW_DAYS)

        recent_data = [
            point for point in self.thermal_data
            if point.timestamp > cutoff_date
        ]

        heating_count = sum(1 for p in recent_data if p.hvac_action == 'heating' and p.temp_change > 0)
        cooling_count = sum(1 for p in recent_data if p.hvac_action == 'cooling' and p.temp_change < 0)
        natural_count = sum(1 for p in recent_data if p.hvac_action in ['idle', 'off'])

        # Require sufficient data for at least 2 of the 3 categories
        sufficient_categories = sum([
            heating_count >= MIN_SAMPLES_FOR_CALCULATION,
            cooling_count >= MIN_SAMPLES_FOR_CALCULATION,
            natural_count >= MIN_SAMPLES_FOR_CALCULATION
        ])

        return sufficient_categories >= 2
    
    def get_data_summary(self) -> Dict:
        """Get summary of collected thermal data."""
        now = datetime.now()
        cutoff_date = now - timedelta(days=ROLLING_WINDOW_DAYS)

        recent_data = [
            point for point in self.thermal_data
            if point.timestamp > cutoff_date
        ]

        heating_data = [p for p in recent_data if p.hvac_action == 'heating' and p.temp_change > 0]
        cooling_data = [p for p in recent_data if p.hvac_action == 'cooling' and p.temp_change < 0]
        natural_data = [p for p in recent_data if p.hvac_action in ['idle', 'off']]

        return {
            'total_data_points': len(self.thermal_data),
            'recent_data_points': len(recent_data),
            'heating_samples': len(heating_data),
            'cooling_samples': len(cooling_data),
            'natural_samples': len(natural_data),
            'heating_rate': self.heating_rate,
            'cooling_rate': self.cooling_rate,
            'natural_rate': self.natural_rate,
            'last_calculation': self.last_calculation.isoformat() if self.last_calculation else None,
            'has_sufficient_data': self.has_sufficient_data(),
        }
    
    async def _async_load_data(self) -> None:
        """Load thermal data from storage."""
        try:
            data = await self.store.async_load()
            if data:
                # Load thermal data points
                thermal_data_raw = data.get('thermal_data', [])
                for point_data in thermal_data_raw:
                    try:
                        point = ThermalDataPoint(
                            timestamp=datetime.fromisoformat(point_data['timestamp']),
                            temp_start=point_data['temp_start'],
                            temp_end=point_data['temp_end'],
                            hvac_action=point_data['hvac_action'],
                            interval_minutes=point_data['interval_minutes'],
                        )
                        self.thermal_data.append(point)
                    except (KeyError, ValueError) as err:
                        _LOGGER.debug(f"Could not load thermal data point: {err}")
                
                # Load calculated rates (support both old and new format)
                self.heating_rate = data.get('heating_rate', data.get('heat_up_rate'))  # Backward compatibility
                self.cooling_rate = data.get('cooling_rate', data.get('cool_down_rate'))  # Backward compatibility
                self.natural_rate = data.get('natural_rate')
                
                if data.get('last_calculation'):
                    self.last_calculation = datetime.fromisoformat(data['last_calculation'])
                
                _LOGGER.info(f"Loaded {len(self.thermal_data)} thermal data points from storage")
        
        except Exception as err:
            _LOGGER.warning(f"Could not load thermal learning data: {err}")
    
    async def _async_save_data(self) -> None:
        """Save thermal data to storage."""
        try:
            # Convert thermal data to serializable format
            thermal_data_raw = []
            for point in self.thermal_data:
                thermal_data_raw.append({
                    'timestamp': point.timestamp.isoformat(),
                    'temp_start': point.temp_start,
                    'temp_end': point.temp_end,
                    'hvac_action': point.hvac_action,
                    'interval_minutes': point.interval_minutes,
                })
            
            data = {
                'thermal_data': thermal_data_raw,
                'heating_rate': self.heating_rate,
                'cooling_rate': self.cooling_rate,
                'natural_rate': self.natural_rate,
                'last_calculation': self.last_calculation.isoformat() if self.last_calculation else None,
            }
            
            await self.store.async_save(data)
            
        except Exception as err:
            _LOGGER.warning(f"Could not save thermal learning data: {err}")