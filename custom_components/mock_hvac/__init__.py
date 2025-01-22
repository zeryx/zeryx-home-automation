"""Mock HVAC Integration."""
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_platform, entity_registry as er
from homeassistant.const import ATTR_ENTITY_ID, Platform

DOMAIN = "mock_hvac"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Mock HVAC integration."""
    
    async def async_handle_climate_service(service_call: ServiceCall) -> None:
        """Handle climate services."""
        entity_ids = service_call.data.get(ATTR_ENTITY_ID, [])
        
        # Get entity registry
        ent_reg = er.async_get(hass)
        
        # Get all climate entities for this domain
        entities = [
            entry.entity_id
            for entry in ent_reg.entities.values()
            if entry.domain == Platform.CLIMATE and entry.platform == DOMAIN
        ]
        
        # Filter entities if specific ones were requested
        if entity_ids:
            entities = [entity for entity in entities if entity in entity_ids]
            
        # Get service parameters
        service = service_call.service
        service_data = service_call.data
        
        # Call service for each entity
        for entity_id in entities:
            await hass.services.async_call(
                "climate",
                service,
                {ATTR_ENTITY_ID: entity_id, **service_data},
                blocking=True,
            )

    # Register services
    hass.services.async_register(DOMAIN, "set_temperature", async_handle_climate_service)
    hass.services.async_register(DOMAIN, "set_hvac_mode", async_handle_climate_service)
    hass.services.async_register(DOMAIN, "set_fan_mode", async_handle_climate_service)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mock HVAC from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CLIMATE])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.CLIMATE]) 