"""The Smart Thermostat integration."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Smart Thermostat component."""
    
    async def async_handle_turn_on(call):
        """Handle the service call."""
        entity_id = call.data.get("entity_id")
        if entity_id:
            await hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": "heat"}
            )

    async def async_handle_turn_off(call):
        """Handle the service call."""
        entity_id = call.data.get("entity_id")
        if entity_id:
            await hass.services.async_call(
                "climate", "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": "off"}
            )

    # Register our services
    hass.services.async_register(
        DOMAIN, "turn_on", async_handle_turn_on
    )
    hass.services.async_register(
        DOMAIN, "turn_off", async_handle_turn_off
    )

    return True 