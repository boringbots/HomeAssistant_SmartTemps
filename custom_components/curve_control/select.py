"""Select entity platform for Curve Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Curve Control select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities([CurveControlOptimizationModeSelect(coordinator, entry)])


class CurveControlOptimizationModeSelect(SelectEntity):
    """Optimization mode selector for Curve Control."""

    _attr_has_entity_name = True
    _attr_name = "Optimization Mode"
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the optimization mode selector."""
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_optimization_mode"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "Curve Control",
            "manufacturer": "Curve Control",
            "model": "Smart Thermostat Optimizer",
        }
        self._attr_options = ["off", "cool", "heat"]

        # Initialize from coordinator state (default to 'cool' if not set)
        self._attr_current_option = getattr(coordinator, "optimization_mode", "cool")

    @property
    def icon(self) -> str:
        """Return the icon based on current mode."""
        if self._attr_current_option == "heat":
            return "mdi:fire"
        elif self._attr_current_option == "cool":
            return "mdi:snowflake"
        else:  # off
            return "mdi:power"

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        return getattr(self.coordinator, "optimization_mode", "cool")

    async def async_select_option(self, option: str) -> None:
        """Change the selected optimization mode."""
        if option not in self._attr_options:
            _LOGGER.error(f"Invalid optimization mode: {option}")
            return

        _LOGGER.info(f"Setting optimization mode to: {option}")

        # Update coordinator state
        self.coordinator.optimization_mode = option

        # Trigger coordinator update to apply new mode
        await self.coordinator.async_request_refresh()

        # Update the entity state
        self._attr_current_option = option
        self.async_write_ha_state()

        # If switching to a mode that requires optimization, trigger it
        if option != "off":
            _LOGGER.info(f"Optimization mode set to {option}, triggering optimization")
            try:
                # Save preferences with the new mode to backend
                await self.coordinator.async_save_preferences_to_backend()
            except Exception as e:
                _LOGGER.error(f"Failed to save optimization mode to backend: {e}")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "mode": self.current_option,
            "description": self._get_mode_description(),
            "active_optimization": self.current_option != "off",
        }

    def _get_mode_description(self) -> str:
        """Return a description of the current mode."""
        if self.current_option == "off":
            return "Manual control - No optimization"
        elif self.current_option == "cool":
            return "Cooling optimization - Uses cooling rate + natural drift"
        elif self.current_option == "heat":
            return "Heating optimization - Uses heating rate + natural drift"
        return "Unknown mode"
