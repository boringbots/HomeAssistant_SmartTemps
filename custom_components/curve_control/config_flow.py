"""Config flow for Curve Control integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN,
    CONF_BACKEND_URL,
    CONF_SUPABASE_URL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_EMAIL,
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
    DEFAULT_HOME_SIZE,
    DEFAULT_TARGET_TEMP,
    DEFAULT_LOCATION,
    DEFAULT_TIME_AWAY,
    DEFAULT_TIME_HOME,
    DEFAULT_SAVINGS_LEVEL,
    LOCATIONS,
    SAVINGS_LEVELS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_auth(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate authentication credentials with Supabase."""
    session = async_get_clientsession(hass)
    supabase_url = data.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL)

    try:
        # Determine if this is login or register
        action = "register" if data.get(CONF_EMAIL) else "login"

        auth_payload = {
            "username": data[CONF_USERNAME],
            "password": data[CONF_PASSWORD],
            "action": action,
        }

        if action == "register":
            auth_payload["email"] = data.get(CONF_EMAIL, "")

        _LOGGER.info(f"Attempting {action} for user: {data[CONF_USERNAME]}")

        async with session.post(
            f"{supabase_url}/functions/v1/authenticate",
            json=auth_payload,
            headers={"Authorization": f"Bearer {DEFAULT_SUPABASE_ANON_KEY}"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                error_data = await response.json()
                error_msg = error_data.get("error", f"Authentication failed with status {response.status}")
                raise InvalidAuth(error_msg)

            result = await response.json()

            if result.get("status") != "success":
                raise InvalidAuth(result.get("error", "Authentication failed"))

            _LOGGER.info(f"Authentication successful for user: {data[CONF_USERNAME]}")

            # Return authentication data
            return {
                "user_id": result["user_id"],
                "username": result["username"],
                "auth_token": result["token"],
                "title": f"Curve Control - {result['username']}",
            }

    except aiohttp.ClientError as err:
        raise CannotConnect(f"Failed to connect to authentication server: {err}")
    except InvalidAuth:
        raise
    except Exception as err:
        _LOGGER.exception("Unexpected authentication exception")
        raise InvalidAuth(f"Unexpected error: {err}")


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    
    # Test connection to backend
    backend_url = data.get(CONF_BACKEND_URL, DEFAULT_BACKEND_URL)
    
    try:
        # Debug logging
        _LOGGER.info(f"Config validation data types: homeSize={type(data[CONF_HOME_SIZE])}, targetTemp={type(data[CONF_TARGET_TEMP])}, location={type(data[CONF_LOCATION])}, timeAway={type(data[CONF_TIME_AWAY])}, timeHome={type(data[CONF_TIME_HOME])}, savingsLevel={type(data[CONF_SAVINGS_LEVEL])}")
        _LOGGER.info(f"Raw time values: timeAway='{data[CONF_TIME_AWAY]}', timeHome='{data[CONF_TIME_HOME]}'")
        
        # Prepare test request
        test_data = {
            "homeSize": int(data[CONF_HOME_SIZE]),
            "homeTemperature": float(data[CONF_TARGET_TEMP]),
            "location": int(data[CONF_LOCATION]),
            "timeAway": str(data[CONF_TIME_AWAY])[:5],  # Ensure HH:MM format
            "timeHome": str(data[CONF_TIME_HOME])[:5],  # Ensure HH:MM format
            "savingsLevel": int(data[CONF_SAVINGS_LEVEL]),
        }
        
        _LOGGER.info(f"Sending test data to backend: {test_data}")
        
        async with session.post(
            f"{backend_url}/generate_schedule",
            json=test_data,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            if response.status != 200:
                raise CannotConnect(f"Backend returned status {response.status}")
            
            result = await response.json()
            if "HourlyTemperature" not in result:
                raise InvalidResponse("Backend response missing required data")
    
    except aiohttp.ClientError as err:
        raise CannotConnect(f"Failed to connect to backend: {err}")
    except Exception as err:
        _LOGGER.exception("Unexpected exception")
        raise InvalidResponse(f"Unexpected error: {err}")
    
    # Return info that you want to store in the config entry
    # Convert location to int since form sends it as string
    location_key = int(data[CONF_LOCATION])
    return {"title": f"Curve Control - {LOCATIONS[location_key]}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Curve Control."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._auth_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the authentication step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate authentication
                auth_info = await validate_auth(self.hass, user_input)

                # Store auth data for next step
                self._auth_data = {
                    CONF_USER_ID: auth_info["user_id"],
                    CONF_USERNAME: auth_info["username"],
                    CONF_AUTH_TOKEN: auth_info["auth_token"],
                    CONF_SUPABASE_URL: user_input.get(CONF_SUPABASE_URL, DEFAULT_SUPABASE_URL),
                }

                # Move to preferences step
                return await self.async_step_preferences()

            except InvalidAuth as err:
                _LOGGER.error(f"Authentication error: {err}")
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during authentication")
                errors["base"] = "unknown"

        # Show authentication form
        auth_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_EMAIL): str,  # If provided, will register new user
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=auth_schema,
            errors=errors,
            description_placeholders={
                "note": "Enter your credentials. Provide an email address to create a new account."
            },
        )

    async def async_step_preferences(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the preferences configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Merge auth data with preferences
                full_data = {**self._auth_data, **user_input}

                info = await validate_input(self.hass, full_data)

                # Create unique ID based on user_id
                unique_id = full_data[CONF_USER_ID]
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates=full_data)

                # Show progress message to user
                self.async_show_progress(
                    step_id="preferences",
                    progress_action="calculating",
                    progress_task="Calculating optimal temperature schedule..."
                )

                return self.async_create_entry(
                    title=f"Curve Control - {full_data[CONF_USERNAME]}",
                    data=full_data
                )
            
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidResponse:
                errors["base"] = "invalid_response"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
        
        # Get list of climate entities for thermostat selection
        climate_entities = [
            state.entity_id
            for state in self.hass.states.async_all("climate")
        ]
        
        # Get list of weather entities
        weather_entities = [
            state.entity_id
            for state in self.hass.states.async_all("weather")
        ]
        
        # Build location options
        location_options = [
            selector.SelectOptionDict(value=str(k), label=v)
            for k, v in LOCATIONS.items()
        ]
        
        # Build savings level options
        savings_options = [
            selector.SelectOptionDict(value=str(k), label=v)
            for k, v in SAVINGS_LEVELS.items()
        ]
        
        # Create the form schema
        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_THERMOSTAT_ENTITY,
                    default=climate_entities[0] if climate_entities else None,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(
                    CONF_HOME_SIZE,
                    default=DEFAULT_HOME_SIZE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=500,
                        max=10000,
                        step=100,
                        unit_of_measurement="sq ft",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Required(
                    CONF_TARGET_TEMP,
                    default=DEFAULT_TARGET_TEMP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=60,
                        max=85,
                        step=1,
                        unit_of_measurement="°F",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Required(
                    CONF_LOCATION,
                    default=str(DEFAULT_LOCATION),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=location_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_TIME_AWAY,
                    default=DEFAULT_TIME_AWAY,
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_TIME_HOME,
                    default=DEFAULT_TIME_HOME,
                ): selector.TimeSelector(),
                vol.Required(
                    CONF_SAVINGS_LEVEL,
                    default=str(DEFAULT_SAVINGS_LEVEL),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=savings_options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_WEATHER_ENTITY,
                    default=weather_entities[0] if weather_entities else None,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }
        )

        return self.async_show_form(
            step_id="preferences",
            data_schema=data_schema,
            errors=errors,
        )
    
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Update the config entry
                self.hass.config_entries.async_update_entry(
                    entry,
                    data=user_input,
                    title=info["title"],
                )
                
                # Trigger optimization with new preferences
                if DOMAIN in self.hass.data and entry.entry_id in self.hass.data[DOMAIN]:
                    coordinator = self.hass.data[DOMAIN][entry.entry_id]["coordinator"]
                    await coordinator.force_optimization()
                
                # Reload the integration
                await self.hass.config_entries.async_reload(entry.entry_id)
                
                return self.async_abort(reason="reconfigure_successful")
            
            except CannotConnect:
                errors = {"base": "cannot_connect"}
            except InvalidResponse:
                errors = {"base": "invalid_response"}
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors = {"base": "unknown"}
        else:
            user_input = entry.data
            errors = {}
        
        # Use the same schema as initial setup
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidResponse(HomeAssistantError):
    """Error to indicate the response was invalid."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate authentication failed."""