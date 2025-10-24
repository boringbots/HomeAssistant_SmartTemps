"""Button platform for Curve Control integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Curve Control button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    buttons = [
        CurveControlOptimizeButton(coordinator, entry),
    ]

    async_add_entities(buttons)


class CurveControlOptimizeButton(CoordinatorEntity, ButtonEntity):
    """Button to optimize schedule and save preferences."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.UPDATE

    def __init__(self, coordinator, entry: ConfigEntry) -> None:
        """Initialize the optimize button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_optimize_button"
        self._attr_name = "Optimize Schedule"
        self._attr_icon = "mdi:chart-line"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": "Curve Control",
            "manufacturer": "Curve Control",
            "model": "Energy Optimizer",
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        return {
            "description": "Optimizes your AC schedule and saves for nightly runs",
            "last_optimization": getattr(self.coordinator, 'last_optimization_time', None),
            "next_optimization": "Tonight at midnight (automatic)",
        }

    async def async_press(self) -> None:
        """Handle the button press - Optimize and save."""
        _LOGGER.info("Optimize button pressed")
        await self.coordinator.async_optimize_and_save(immediate=True)
