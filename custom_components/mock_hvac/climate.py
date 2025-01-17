"""Mock HVAC climate entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Mock HVAC climate devices."""
    _LOGGER.debug("Setting up Mock HVAC integration")
    
    furnace = MockFurnace(hass)
    heat_pump = MockHeatPump(hass)
    
    _LOGGER.info("Adding Mock HVAC entities with unique_ids: %s, %s", 
                furnace.unique_id, heat_pump.unique_id)
    
    async_add_entities([furnace, heat_pump], True)  # True for update before adding

class MockFurnace(ClimateEntity):
    """Mock Ecobee thermostat entity."""
    
    _attr_has_entity_name = True
    _attr_name = "Mock Furnace"
    _attr_unique_id = "mock_furnace"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the mock furnace."""
        super().__init__()
        self.hass = hass
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
        self._attr_min_temp = 7
        self._attr_max_temp = 35
        self._attr_current_temperature = 19.8
        self._attr_target_temperature = None
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.IDLE
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE
        )
        self._attr_fan_modes = ["on", "auto"]
        self._attr_fan_mode = "auto"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Mock Manufacturer",
            model="Mock Furnace v1",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode in self.hvac_modes:
            self._attr_hvac_mode = hvac_mode
            self._attr_hvac_action = HVACAction.HEATING if hvac_mode == HVACMode.HEAT else HVACAction.IDLE
            self.async_write_ha_state()
            _LOGGER.info("HVAC mode set to %s", self._attr_hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            self.async_write_ha_state()
            _LOGGER.info("Temperature set to %s", self._attr_target_temperature)

class MockHeatPump(ClimateEntity):
    """Mock Lennox heat pump entity."""
    
    _attr_has_entity_name = True
    _attr_name = "Mock Heat Pump"
    _attr_unique_id = "mock_heatpump"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the mock heat pump."""
        super().__init__()
        self.hass = hass
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT_COOL,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.HEAT,
            HVACMode.FAN_ONLY
        ]
        self._attr_min_temp = 17
        self._attr_max_temp = 30
        self._attr_current_temperature = 19.8
        self._attr_target_temperature = 21
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE
        )
        self._attr_fan_modes = ["low", "medium", "mid", "high", "auto"]
        self._attr_fan_mode = "high"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Lennox",
            model="Mock Heat Pump v1",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode in self.hvac_modes:
            self._attr_hvac_mode = hvac_mode
            self.async_write_ha_state()
            _LOGGER.info("HVAC mode set to %s", self._attr_hvac_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            self.async_write_ha_state()
            _LOGGER.info("Temperature set to %s", self._attr_target_temperature)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode in self.fan_modes:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state()
            _LOGGER.info("Fan mode set to %s", self._attr_fan_mode) 