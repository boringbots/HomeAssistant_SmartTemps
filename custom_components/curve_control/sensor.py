"""Sensor platform for Curve Control integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CurveControlCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Curve Control sensor entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    
    sensors = [
        CurveControlSavingsSensor(coordinator, entry),
        CurveControlCO2Sensor(coordinator, entry),
        CurveControlStatusSensor(coordinator, entry),
        CurveControlNextSetpointSensor(coordinator, entry),
        CurveControlCurrentIntervalSensor(coordinator, entry),
        CurveControlScheduleChartSensor(coordinator, entry),
        CurveControlThermalLearningSensor(coordinator, entry),
    ]
    
    async_add_entities(sensors, True)


class CurveControlBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Curve Control sensors."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: CurveControlCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Curve Control Energy Optimizer",
            "manufacturer": "Curve Control",
            "model": "Energy Optimizer v1.0",
        }


class CurveControlSavingsSensor(CurveControlBaseSensor):
    """Sensor for energy savings information."""
    
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "$"
    _attr_icon = "mdi:piggy-bank"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the savings sensor."""
        super().__init__(coordinator, entry, "savings", "Energy Savings")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return self.coordinator.optimization_results.get("costSavings", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        if self.coordinator.optimization_results:
            results = self.coordinator.optimization_results
            attrs["percent_savings"] = f"{results.get('percentSavings', 0)}%"
            attrs["calculation_period"] = "120 days"
            attrs["last_updated"] = datetime.now().isoformat()
        
        return attrs


class CurveControlCO2Sensor(CurveControlBaseSensor):
    """Sensor for CO2 emissions avoided."""
    
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "metric tons"
    _attr_icon = "mdi:molecule-co2"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the CO2 sensor."""
        super().__init__(coordinator, entry, "co2_avoided", "CO2 Avoided")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return self.coordinator.optimization_results.get("co2Avoided", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        if self.coordinator.optimization_results:
            results = self.coordinator.optimization_results
            attrs["cars_equivalent"] = f"{results.get('carsEquivalent', 0)} cars"
            attrs["calculation_period"] = "120 days"
        
        return attrs


class CurveControlStatusSensor(CurveControlBaseSensor):
    """Sensor for optimization status."""
    
    _attr_icon = "mdi:chart-line"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, entry, "status", "Optimization Status")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.optimization_results:
            return "Optimized"
        elif self.coordinator.last_update_success:
            return "Active"
        else:
            return "Pending"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        from datetime import datetime
        attrs = {
            "last_update": datetime.now().isoformat() if self.coordinator.last_update_success else None,
            "update_success": self.coordinator.last_update_success,
        }
        
        if self.coordinator.optimization_results:
            # Add timing information
            from datetime import datetime
            now = datetime.now()
            interval = (now.hour * 2) + (now.minute // 30)
            
            attrs["current_30min_interval"] = interval
            attrs["intervals_per_day"] = 48
            attrs["heat_up_rate"] = f"{self.coordinator.heat_up_rate}°F/30min"
            attrs["cool_down_rate"] = f"{self.coordinator.cool_down_rate}°F/30min"
        
        return attrs


class CurveControlNextSetpointSensor(CurveControlBaseSensor):
    """Sensor for next temperature setpoint."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_icon = "mdi:thermometer"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the next setpoint sensor."""
        super().__init__(coordinator, entry, "next_setpoint", "Next Temperature Setpoint")
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.coordinator.get_current_setpoint()
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {}
        
        bounds = self.coordinator.get_schedule_bounds()
        if bounds:
            # Get current and next intervals
            from datetime import datetime
            now = datetime.now()
            current_interval = (now.hour * 2) + (now.minute // 30)
            next_interval = (current_interval + 1) % 48
            
            if 0 <= current_interval < len(bounds[0]):
                attrs["current_high_bound"] = bounds[0][current_interval]
                attrs["current_low_bound"] = bounds[1][current_interval]
            
            if 0 <= next_interval < len(bounds[0]):
                attrs["next_high_bound"] = bounds[0][next_interval]
                attrs["next_low_bound"] = bounds[1][next_interval]
                
                # Calculate time until next interval
                minutes_until_next = 30 - (now.minute % 30)
                attrs["minutes_until_next_interval"] = minutes_until_next
        
        return attrs


class CurveControlCurrentIntervalSensor(CurveControlBaseSensor):
    """Sensor for current time interval."""
    
    _attr_icon = "mdi:clock-outline"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the current interval sensor."""
        super().__init__(coordinator, entry, "current_interval", "Current Time Interval")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        # Format as time range
        start_hour = interval // 2
        start_min = (interval % 2) * 30
        end_hour = (interval + 1) // 2
        end_min = ((interval + 1) % 2) * 30
        
        if end_hour == 24:
            end_hour = 0
        
        return f"{start_hour:02d}:{start_min:02d} - {end_hour:02d}:{end_min:02d}"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        from datetime import datetime
        now = datetime.now()
        interval = (now.hour * 2) + (now.minute // 30)
        
        attrs = {
            "interval_number": interval + 1,  # 1-indexed for display
            "total_intervals": 48,
            "minutes_into_interval": now.minute % 30,
            "minutes_remaining": 30 - (now.minute % 30),
        }
        
        # Add price information if available
        if self.coordinator.config:
            location = self.coordinator.config.get("location", 1)
            # This would need to be expanded with actual price data
            attrs["rate_period"] = self._get_rate_period(interval, location)
        
        return attrs
    
    def _get_rate_period(self, interval: int, location: int) -> str:
        """Determine the rate period based on interval and location."""
        # This is a simplified version - would need full rate schedule
        hour = interval // 2
        
        # Example for location 1 (SDG&E TOU-DR1)
        if location == 1:
            if 16 <= hour < 21:  # 4pm - 9pm
                return "On-Peak"
            elif 6 <= hour < 16 or 21 <= hour < 24:  # 6am-4pm, 9pm-12am
                return "Off-Peak"
            else:  # 12am - 6am
                return "Super Off-Peak"
        
        return "Standard"


class CurveControlScheduleChartSensor(CurveControlBaseSensor):
    """Sensor that provides temperature schedule and pricing data for UI plots."""
    
    _attr_icon = "mdi:chart-line-variant"
    
    def __init__(self, coordinator: CurveControlCoordinator, entry: ConfigEntry) -> None:
        """Initialize the schedule chart sensor."""
        super().__init__(coordinator, entry, "schedule_chart", "Temperature Schedule Chart")
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator._daily_schedule:
            return f"Schedule loaded ({len(self.coordinator._daily_schedule)} intervals)"
        return "No schedule"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return chart data for temperature schedule vs pricing."""
        attrs = {}
        
        if not self.coordinator._daily_schedule:
            attrs["graph_data"] = None
            return attrs
        
        # Get the temperature schedule and bounds
        schedule = self.coordinator._daily_schedule
        location = self.coordinator.config.get("location", 1)
        
        # Get high/low temperature bounds from coordinator
        bounds = self.coordinator.get_schedule_bounds()
        high_temps = bounds[0] if bounds else [75] * 48  # Default if no bounds
        low_temps = bounds[1] if bounds else [68] * 48   # Default if no bounds
        
        # Generate time labels for 30-minute intervals
        time_labels = []
        hourly_labels = []  # For cleaner hourly display
        for i in range(48):  # 48 30-minute intervals
            hour = i // 2
            minute = (i % 2) * 30
            time_labels.append(f"{hour:02d}:{minute:02d}")
            if i % 2 == 0:  # Every hour
                hourly_labels.append(f"{hour:02d}:00")
        
        # Get pricing data and convert to numeric values for graphing
        pricing_schedule, price_values = self._generate_pricing_with_values(location)
        
        # Create graph-ready data structure
        graph_data = {
            "time_labels": time_labels,
            "hourly_labels": hourly_labels,
            "datasets": [
                {
                    "label": "Target Temperature",
                    "data": schedule,
                    "borderColor": "rgb(75, 192, 192)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "yAxisID": "y-temperature"
                },
                {
                    "label": "High Limit",
                    "data": high_temps,
                    "borderColor": "rgb(255, 99, 132)",
                    "backgroundColor": "rgba(255, 99, 132, 0.1)",
                    "borderDash": [5, 5],
                    "yAxisID": "y-temperature"
                },
                {
                    "label": "Low Limit",
                    "data": low_temps,
                    "borderColor": "rgb(54, 162, 235)",
                    "backgroundColor": "rgba(54, 162, 235, 0.1)",
                    "borderDash": [5, 5],
                    "yAxisID": "y-temperature"
                },
                {
                    "label": "Electricity Price",
                    "data": price_values,
                    "borderColor": "rgb(255, 206, 86)",
                    "backgroundColor": "rgba(255, 206, 86, 0.3)",
                    "type": "bar",
                    "yAxisID": "y-price"
                }
            ],
            "current_interval": self._get_current_interval(),
            "schedule_date": str(self.coordinator._schedule_date) if self.coordinator._schedule_date else None,
        }
        
        attrs["graph_data"] = graph_data
        attrs["pricing_periods"] = pricing_schedule  # Text labels for pricing
        attrs["chart_type"] = "temperature_vs_pricing"
        attrs["update_timestamp"] = datetime.now().isoformat()
        
        # Add summary statistics
        if schedule:
            attrs["min_temp"] = min(schedule)
            attrs["max_temp"] = max(schedule)
            attrs["avg_temp"] = sum(schedule) / len(schedule)
            attrs["temp_range"] = max(schedule) - min(schedule)
        
        return attrs
    
    def _generate_pricing_with_values(self, location: int) -> tuple[list[str], list[float]]:
        """Generate pricing schedule with actual pricing values for graphing."""
        # Actual pricing data from backend (cents per kWh)
        pricing_data = {
            1: [24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7, 24.7,
                36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8,
                36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8, 59.7, 59.7, 59.7, 59.7,
                59.7, 59.7, 59.7, 59.7, 59.7, 59.7, 36.8, 36.8, 36.8, 36.8, 36.8, 36.8],

            2: [31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6,
                31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6,
                31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6, 60.3, 60.3, 60.3, 60.3,
                60.3, 60.3, 60.3, 60.3, 60.3, 60.3, 31.6, 31.6, 31.6, 31.6, 31.6, 31.6],

            3: [27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9, 27.9,
                39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3,
                39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3, 47.6, 47.6, 47.6, 47.6,
                47.6, 47.6, 47.6, 47.6, 47.6, 47.6, 39.3, 39.3, 39.3, 39.3, 39.3, 39.3],

            4: [31.72222222, 31.72222222, 31.72222222, 31.72222222, 31.72222222, 31.72222222,
                31.72222222, 31.72222222, 31.72222222, 31.72222222, 31.72222222, 31.72222222,
                35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222,
                35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222,
                35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222,
                35.32222222, 35.32222222, 62.32222222, 62.32222222, 62.32222222, 62.32222222,
                62.32222222, 62.32222222, 62.32222222, 62.32222222, 62.32222222, 62.32222222,
                35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222, 35.32222222],

            5: [40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4,
                40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4,
                40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4,
                40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4, 40.4],

            6: [8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778,
                8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778,
                12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778,
                12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778,
                12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778, 12.09077778,
                24.25577778, 24.25577778, 24.25577778, 24.25577778, 24.25577778, 24.25577778,
                24.25577778, 24.25577778, 24.25577778, 24.25577778, 8.384777778, 8.384777778,
                8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778, 8.384777778],

            7: [9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333,
                9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333,
                9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333,
                9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333,
                9.375933333, 9.375933333, 26.10743333, 26.10743333, 26.10743333, 26.10743333,
                26.10743333, 26.10743333, 26.10743333, 26.10743333, 26.10743333, 26.10743333,
                26.10743333, 26.10743333, 9.375933333, 9.375933333, 9.375933333, 9.375933333,
                9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333, 9.375933333],

            8: [8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86,
                8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86, 8.86,
                8.86, 42.7835, 42.7835, 42.7835, 42.7835, 42.7835, 42.7835, 42.7835, 42.7835,
                113.7835, 113.7835, 113.7835, 113.7835, 113.7835, 42.7835, 42.7835, 8.86, 8.86,
                8.86, 8.86, 8.86, 8.86, 8.86, 8.86]
        }

        # Get the pricing for this location, fallback to location 1 if not found
        prices = pricing_data.get(location, pricing_data[1])

        # Generate labels based on price tiers
        pricing_labels = []
        pricing_values = []

        for price in prices:
            # Categorize based on price level
            if price <= 15:
                label = "Super Off-Peak"
            elif price <= 30:
                label = "Off-Peak"
            elif price <= 45:
                label = "Standard"
            elif price <= 65:
                label = "On-Peak"
            else:
                label = "Super Peak"

            pricing_labels.append(label)
            pricing_values.append(price)

        return pricing_labels, pricing_values
    
    def _generate_pricing_schedule(self, location: int) -> list[str]:
        """Generate pricing schedule based on location (legacy method)."""
        labels, _ = self._generate_pricing_with_values(location)
        return labels
    
    def _get_current_interval(self) -> int:
        """Get current 30-minute interval index."""
        from datetime import datetime
        now = datetime.now()
        return (now.hour * 2) + (now.minute // 30)


class CurveControlThermalLearningSensor(CurveControlBaseSensor):
    """Sensor for thermal learning data."""
    
    _attr_name = "Thermal Learning"
    _attr_icon = "mdi:thermometer-auto"
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "thermal_learning", "Thermal Learning")
        self._attr_unique_id = f"{entry.entry_id}_thermal_learning"
    
    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.thermal_learning:
            return "Disabled"
        
        if self.coordinator.thermal_learning.has_sufficient_data():
            return "Learning Complete"
        else:
            return "Learning"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        if not self.coordinator.thermal_learning:
            return {
                "status": "No thermostat configured",
                "heating_rate_learned": None,
                "cooling_rate_learned": None,
                "natural_rate_learned": None,
            }
        
        # Get thermal learning summary
        summary = self.coordinator.thermal_learning.get_data_summary()
        heating_rate, cooling_rate, natural_rate = self.coordinator.thermal_learning.get_thermal_rates()
        
        # Get default rates for comparison
        from .const import HEAT_30MIN, COOL_30MIN
        
        return {
            "heating_rate_learned": heating_rate,
            "cooling_rate_learned": cooling_rate,
            "natural_rate_learned": natural_rate,
            "heat_up_rate_default": HEAT_30MIN,
            "cool_down_rate_default": COOL_30MIN,
            "heat_up_rate_current": self.coordinator.heat_up_rate,
            "cool_down_rate_current": self.coordinator.cool_down_rate,
            "total_data_points": summary.get("total_data_points"),
            "recent_data_points": summary.get("recent_data_points"),
            "heating_samples": summary.get("heating_samples"),
            "cooling_samples": summary.get("cooling_samples"),
            "natural_samples": summary.get("natural_samples"),
            "has_sufficient_data": summary.get("has_sufficient_data"),
            "last_calculation": summary.get("last_calculation"),
            "learning_window_days": 7,
            "status": "Learning Complete" if summary.get("has_sufficient_data") else "Collecting Data",
        }