"""Mock HVAC Platform for testing."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_FAN_MODE,
    ClimateEntityFeature,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the mock climate platform."""
    async_add_entities([
        MockFurnace(),
        MockHeatPump(),
    ])

class MockFurnace(ClimateEntity):
    """Mock Ecobee thermostat entity."""
    
    def __init__(self):
        """Initialize the mock furnace."""
        self._attr_hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT, HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL]
        self._attr_min_temp = 7
        self._attr_max_temp = 35
        self._attr_min_humidity = 20
        self._attr_max_humidity = 50
        self._attr_fan_modes = ["on", "auto"]
        self._attr_current_temperature = 19.8
        self._attr_target_temperature = None
        self._attr_target_temperature_high = None
        self._attr_target_temperature_low = None
        self._attr_current_humidity = 43
        self._attr_humidity = 36
        self._attr_fan_mode = "auto"
        self._attr_hvac_action = "idle"
        self._attr_hvac_mode = HVAC_MODE_OFF
        self._attr_name = "Mock Furnace"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE
        )
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_unique_id = "mock_furnace_001"

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode in self.hvac_modes:
            self._attr_hvac_mode = hvac_mode
            self._attr_hvac_action = "heating" if hvac_mode == HVAC_MODE_HEAT else "idle"
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            self.async_write_ha_state()

class MockHeatPump(ClimateEntity):
    """Mock Lennox heat pump entity."""
    
    def __init__(self):
        """Initialize the mock heat pump."""
        self._attr_hvac_modes = [
            HVAC_MODE_OFF,
            HVAC_MODE_HEAT_COOL,
            HVAC_MODE_COOL,
            HVAC_MODE_DRY,
            HVAC_MODE_HEAT,
            HVAC_MODE_FAN_ONLY
        ]
        self._attr_min_temp = 17
        self._attr_max_temp = 30
        self._attr_target_temperature_step = 1
        self._attr_fan_modes = ["low", "mid", "high", "auto"]
        self._attr_current_temperature = 19.8
        self._attr_target_temperature = 21
        self._attr_current_humidity = 42.24
        self._attr_fan_mode = "high"
        self._attr_last_on_operation = "heat"
        self._attr_device_code = "2161"
        self._attr_manufacturer = "Lennox"
        self._attr_supported_models = ["LNMTE026V2"]
        self._attr_supported_controller = "Broadlink"
        self._attr_commands_encoding = "Base64"
        self._attr_name = "Mock Heat Pump"
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.FAN_MODE
        )
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_unique_id = "mock_heatpump_001"
        self._attr_hvac_mode = HVAC_MODE_OFF

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode in self.hvac_modes:
            self._attr_hvac_mode = hvac_mode
            if hvac_mode == HVAC_MODE_HEAT:
                self._attr_last_on_operation = "heat"
            self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._attr_target_temperature = kwargs[ATTR_TEMPERATURE]
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode in self.fan_modes:
            self._attr_fan_mode = fan_mode
            self.async_write_ha_state() 