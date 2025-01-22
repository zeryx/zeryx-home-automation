"""The Smart Thermostat integration."""
import logging
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry
from homeassistant.const import Platform
from datetime import timedelta
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"
SCAN_INTERVAL = timedelta(seconds=30)  # Update every 30 seconds

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Smart Thermostat integration."""
    if DOMAIN not in config:
        return True

    platform = Platform.CLIMATE
    hass.async_create_task(
        hass.helpers.discovery.async_load_platform(
            platform, DOMAIN, config[DOMAIN], config
        )
    )

    # Set up periodic updates
    async def periodic_update(now):
        """Update all smart thermostats."""
        if DOMAIN in hass.data:
            for thermostat in hass.data[DOMAIN].values():
                await thermostat.async_update()

    hass.async_create_task(
        async_track_time_interval(
            hass, periodic_update, SCAN_INTERVAL
        )
    )

    async def async_handle_turn_on(call: ServiceCall) -> None:
        """Handle the turn_on service call."""
        entity_id = call.data.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id must be provided for turn_on service")

        ent_reg = entity_registry.async_get(hass)
        entity = ent_reg.async_get(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        try:
            thermostat = hass.data[DOMAIN][entity.unique_id]
            await thermostat.async_turn_on()
        except KeyError:
            _LOGGER.error("Thermostat %s not found in smart_thermostat component", entity_id)
            raise
        except HomeAssistantError as err:
            _LOGGER.error("Failed to turn on thermostat %s: %s", entity_id, str(err))
            raise

    async def async_handle_turn_off(call: ServiceCall) -> None:
        """Handle the turn_off service call."""
        entity_id = call.data.get("entity_id")
        if entity_id is None:
            raise ValueError("entity_id must be provided for turn_off service")

        ent_reg = entity_registry.async_get(hass)
        entity = ent_reg.async_get(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        try:
            thermostat = hass.data[DOMAIN][entity.unique_id]
            await thermostat.async_turn_off()
        except KeyError:
            _LOGGER.error("Thermostat %s not found in smart_thermostat component", entity_id)
            raise
        except HomeAssistantError as err:
            _LOGGER.error("Failed to turn off thermostat %s: %s", entity_id, str(err))
            raise

    async def async_handle_force_mode(call: ServiceCall) -> None:
        """Handle forcing a specific heat source."""
        entity_id = call.data.get("entity_id")
        force_mode = call.data.get("force_mode")
        
        if entity_id is None:
            raise ValueError("entity_id must be provided")

        # Get the entity registry entry
        ent_reg = entity_registry.async_get(hass)
        entity = ent_reg.async_get(entity_id)
        
        if not entity:
            # Try getting the state directly if no registry entry
            state = hass.states.get(entity_id)
            if not state:
                raise ValueError(f"Entity {entity_id} not found")
        
        # Initialize domain data if it doesn't exist
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {}
        
        # Try to find the thermostat instance
        thermostat = None
        
        # First try by unique_id if available
        if entity and entity.unique_id and entity.unique_id in hass.data[DOMAIN]:
            thermostat = hass.data[DOMAIN][entity.unique_id]
        else:
            # Fall back to searching by entity_id
            for t in hass.data[DOMAIN].values():
                if getattr(t, 'entity_id', None) == entity_id:
                    thermostat = t
                    break
        
        if not thermostat:
            raise ValueError(f"Thermostat {entity_id} not found in component")

        await thermostat.async_force_heat_source(force_mode)

    try:
        # Register our services with error handling
        hass.services.async_register(
            DOMAIN, "turn_on", async_handle_turn_on
        )
        hass.services.async_register(
            DOMAIN, "turn_off", async_handle_turn_off
        )
        hass.services.async_register(
            DOMAIN, "force_mode", async_handle_force_mode
        )
        return True
    except Exception as e:
        _LOGGER.error("Failed to register smart_thermostat services: %s", str(e))
        return False

async def async_setup_entry(hass: HomeAssistant, entry: dict) -> bool:
    """Set up Smart Thermostat from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CLIMATE])
    return True 