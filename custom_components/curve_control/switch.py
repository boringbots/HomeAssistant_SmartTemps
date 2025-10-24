"""Switch platform for Curve Control integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Curve Control switch entity from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    
    async_add_entities(
        [CurveControlOptimizationSwitch(coordinator, entry)],
        True,
    )


class CurveControlOptimizationSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable temperature optimization."""
    
    _attr_has_entity_name = True
    _attr_name = "Use Optimized Temperatures"
    _attr_icon = "mdi:chart-line"
    
    def __init__(
        self,
        coordinator: CurveControlCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_optimization_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Curve Control Energy Optimizer",
            "manufacturer": "Curve Control",
            "model": "Energy Optimizer v1.0",
        }
        
        # Initialize as ON by default
        self._is_on = True
        coordinator.optimization_enabled = True
    
    @property
    def is_on(self) -> bool:
        """Return true if optimization is enabled."""
        return self._is_on
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {
            "mode": "Optimized" if self._is_on else "Manual",
            "description": "Controls whether the thermostat follows the optimized schedule or manual setpoints"
        }
        
        if self._is_on and self.coordinator.optimization_results:
            attrs["active_optimization"] = True
            attrs["schedule_loaded"] = True
        else:
            attrs["active_optimization"] = False
            
        return attrs
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on optimization."""
        self._is_on = True
        self.coordinator.optimization_enabled = True
        _LOGGER.info("Temperature optimization enabled")
        
        # Find and notify the climate entity to resume control
        climate_entity = None
        for entity_id in self.hass.states.async_entity_ids("climate"):
            if "curve_control" in entity_id:
                climate_entity = entity_id
                break
        
        if climate_entity:
            # Trigger immediate setpoint application
            _LOGGER.info(f"Notifying {climate_entity} to resume optimization")
            if self.coordinator.get_current_setpoint():
                setpoint = self.coordinator.get_current_setpoint()
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": climate_entity,
                        "temperature": setpoint,
                    },
                    blocking=False,
                )
        
        self.async_write_ha_state()
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off optimization."""
        self._is_on = False
        self.coordinator.optimization_enabled = False
        _LOGGER.info("Temperature optimization disabled - manual control active")
        
        # Stop any pending setpoint changes
        # The climate entity will check this flag and stop auto-control
        
        self.async_write_ha_state()
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()