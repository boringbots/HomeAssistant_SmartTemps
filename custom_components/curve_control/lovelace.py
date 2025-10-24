"""Lovelace dashboard card management for Curve Control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend
from homeassistant.components.lovelace import dashboard
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CURVE_CONTROL_CARD = {
    "type": "vertical-stack",
    "cards": [
        {
            "type": "entities",
            "title": "Curve Control Energy Optimizer",
            "entities": [
                {
                    "entity": "switch.curve_control_use_optimized_temperatures",
                    "name": "Use Optimized Schedule",
                    "icon": "mdi:chart-line"
                },
                {
                    "entity": "sensor.curve_control_status",
                    "name": "Status"
                }
            ]
        },
        {
            "type": "horizontal-stack",
            "cards": [
                {
                    "type": "entity",
                    "entity": "sensor.curve_control_savings",
                    "name": "Savings",
                    "icon": "mdi:currency-usd"
                },
                {
                    "type": "entity",
                    "entity": "sensor.curve_control_co2_avoided",
                    "name": "CO2 Avoided",
                    "icon": "mdi:molecule-co2"
                }
            ]
        },
        {
            "type": "markdown",
            "content": "### 📊 Temperature Schedule\n\nTo see your 24-hour optimized temperature schedule graph:\n\n1. **Install ApexCharts Card** from HACS Frontend section\n2. **Refresh your browser** (Ctrl+F5)\n3. **Add the graph card** from the button below\n\n[➕ Add Temperature Graph Card](/#)"
        },
        {
            "type": "entities",
            "title": "Current Schedule",
            "entities": [
                {
                    "entity": "sensor.curve_control_next_setpoint",
                    "name": "Current Target"
                },
                {
                    "entity": "sensor.curve_control_current_interval",
                    "name": "Time Period"
                },
                {
                    "entity": "climate.curve_control_thermostat",
                    "name": "Thermostat"
                }
            ]
        }
    ]
}

APEX_CHART_CARD = {
    "type": "custom:apexcharts-card",
    "header": {
        "show": True,
        "title": "24-Hour Temperature Schedule vs Electricity Prices",
        "show_states": True,
        "colorize_states": True
    },
    "graph_span": "24h",
    "yaxis": [
        {
            "id": "temp",
            "min": 0,
            "max": 100,
            "decimals": 1,
            "apex_config": {
                "title": {
                    "text": "Temperature (°F)"
                }
            }
        },
        {
            "id": "price",
            "opposite": True,
            "min": 0,
            "max": "~(entity.attributes.location === 8 ? 1.6 : 1.0)",
            "decimals": 2,
            "apex_config": {
                "title": {
                    "text": "Price ($/kWh)"
                }
            }
        }
    ],
    "series": [
        {
            "entity": "sensor.curve_control_temperature_schedule_chart",
            "name": "Target Temp",
            "yaxis_id": "temp",
            "data_generator": """
                const data = entity.attributes.graph_data;
                if (!data || !data.datasets) return [];
                const target = data.datasets[0].data;
                return target.map((temp, i) => {
                    const hour = Math.floor(i / 2);
                    const minute = (i % 2) * 30;
                    const time = new Date();
                    time.setHours(hour, minute, 0, 0);
                    return [time.getTime(), temp];
                });
            """,
            "type": "line",
            "color": "green",
            "stroke_width": 3
        },
        {
            "entity": "sensor.curve_control_temperature_schedule_chart",
            "name": "High Limit",
            "yaxis_id": "temp",
            "data_generator": """
                const data = entity.attributes.graph_data;
                if (!data || !data.datasets) return [];
                const high = data.datasets[1].data;
                return high.map((temp, i) => {
                    const hour = Math.floor(i / 2);
                    const minute = (i % 2) * 30;
                    const time = new Date();
                    time.setHours(hour, minute, 0, 0);
                    return [time.getTime(), temp];
                });
            """,
            "type": "line",
            "color": "red",
            "stroke_width": 1,
            "opacity": 0.4
        },
        {
            "entity": "sensor.curve_control_temperature_schedule_chart",
            "name": "Low Limit",
            "yaxis_id": "temp",
            "data_generator": """
                const data = entity.attributes.graph_data;
                if (!data || !data.datasets) return [];
                const low = data.datasets[2].data;
                return low.map((temp, i) => {
                    const hour = Math.floor(i / 2);
                    const minute = (i % 2) * 30;
                    const time = new Date();
                    time.setHours(hour, minute, 0, 0);
                    return [time.getTime(), temp];
                });
            """,
            "type": "line",
            "color": "blue",
            "stroke_width": 1,
            "opacity": 0.4
        },
        {
            "entity": "sensor.curve_control_temperature_schedule_chart",
            "name": "Electricity Price",
            "yaxis_id": "price",
            "data_generator": """
                const data = entity.attributes.graph_data;
                if (!data || !data.datasets) return [];
                const prices = data.datasets[3].data;
                return prices.map((price, i) => {
                    const hour = Math.floor(i / 2);
                    const minute = (i % 2) * 30;
                    const time = new Date();
                    time.setHours(hour, minute, 0, 0);
                    return [time.getTime(), price];
                });
            """,
            "type": "area",
            "color": "orange",
            "opacity": 0.3
        }
    ]
}


async def async_setup_lovelace_cards(hass: HomeAssistant, entry_id: str) -> None:
    """Set up Lovelace cards for Curve Control."""
    try:
        # Register a service to add the card
        async def add_curve_control_card(call):
            """Service to add Curve Control card to Lovelace."""
            _LOGGER.info("Adding Curve Control card to Lovelace")
            
            # This is a placeholder - actual implementation would need 
            # to interact with Lovelace configuration
            # For now, we'll log the card configuration
            _LOGGER.info(f"Card configuration: {CURVE_CONTROL_CARD}")
        
        hass.services.async_register(
            "curve_control",
            "add_dashboard_card",
            add_curve_control_card,
            schema=None
        )
        
        # Log the card configurations for manual setup
        _LOGGER.info("Curve Control Lovelace cards registered")
        
    except Exception as err:
        _LOGGER.error(f"Failed to set up Lovelace cards: {err}")


def get_card_configuration(card_type: str = "main") -> dict[str, Any]:
    """Get the card configuration for manual setup."""
    if card_type == "apex":
        return APEX_CHART_CARD
    return CURVE_CONTROL_CARD