"""The Smart Thermostat integration."""
import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import ServiceNotFound, HomeAssistantError

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Smart Thermostat component."""
    
    async def async_handle_turn_on(call: ServiceCall) -> None:
        """Handle the turn_on service call."""
        entity_id = call.data.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id must be provided for turn_on service")
            
        try:
            await hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": "heat"},
                blocking=True
            )
        except ServiceNotFound:
            _LOGGER.error("Climate service not found. Is the climate integration configured?")
            raise
        except HomeAssistantError as err:
            _LOGGER.error("Failed to turn on thermostat %s: %s", entity_id, str(err))
            raise

    async def async_handle_turn_off(call: ServiceCall) -> None:
        """Handle the turn_off service call."""
        entity_id = call.data.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id must be provided for turn_off service")
            
        try:
            await hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": "off"},
                blocking=True
            )
        except ServiceNotFound:
            _LOGGER.error("Climate service not found. Is the climate integration configured?")
            raise
        except HomeAssistantError as err:
            _LOGGER.error("Failed to turn off thermostat %s: %s", entity_id, str(err))
            raise

    try:
        # Register our services with error handling
        hass.services.async_register(
            DOMAIN, "turn_on", async_handle_turn_on
        )
        hass.services.async_register(
            DOMAIN, "turn_off", async_handle_turn_off
        )
        return True
    except Exception as e:
        _LOGGER.error("Failed to register smart_thermostat services: %s", str(e))
        return False 