"""Mock HVAC integration."""
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import entity_platform

DOMAIN = "mock_hvac"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Mock HVAC component."""
    hass.data.setdefault(DOMAIN, {})
    
    # Register services at the component level
    async def async_handle_climate_service(service_call: ServiceCall) -> None:
        """Handle climate services."""
        entity_id = service_call.data.get(ATTR_ENTITY_ID)
        if not entity_id:
            return
            
        # Get all platforms
        platforms = [platform for platform in entity_platform._async_platforms_for_domain(hass, DOMAIN)]
        
        # Find the entity and call the appropriate service
        for platform in platforms:
            for entity in platform.entities.values():
                if entity.entity_id == entity_id:
                    if service_call.service == "set_hvac_mode":
                        await entity.async_set_hvac_mode(service_call.data["hvac_mode"])
                    elif service_call.service == "set_temperature":
                        await entity.async_set_temperature(**{k: v for k, v in service_call.data.items() if k != ATTR_ENTITY_ID})
                    elif service_call.service == "set_fan_mode":
                        await entity.async_set_fan_mode(service_call.data["fan_mode"])
                    return
    
    # Register all required services
    hass.services.async_register(
        "climate", "set_hvac_mode",
        async_handle_climate_service
    )
    
    hass.services.async_register(
        "climate", "set_temperature",
        async_handle_climate_service
    )
    
    hass.services.async_register(
        "climate", "set_fan_mode",
        async_handle_climate_service
    )
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mock HVAC from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, ["climate"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["climate"]) 