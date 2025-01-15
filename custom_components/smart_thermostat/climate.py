"""Smart Thermostat Climate Platform"""
from homeassistant.components.climate import (
    ClimateEntity,
    HVACMode,
    ClimateEntityFeature,
    HVACAction,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import logging
from datetime import datetime
from collections import deque

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"
DEFAULT_NAME = "Smart Thermostat"

async def async_setup_platform(hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up the smart thermostat platform."""
    name = config.get("name", DEFAULT_NAME)
    temp_sensor = config.get("temperature_sensor")
    heater_switch = config.get("heater")
    min_temp = config.get("min_temp", 16)
    max_temp = config.get("max_temp", 25)
    target_temp = config.get("target_temp", 20)
    tolerance = config.get("tolerance", 0.5)

    async_add_entities([
        SmartThermostat(
            hass, name, temp_sensor, heater_switch,
            min_temp, max_temp, target_temp, tolerance
        )
    ])

class SmartThermostat(ClimateEntity):
    """Smart Thermostat Climate Entity."""
    
    def __init__(self, hass, name, temp_sensor, heater_switch,
                 min_temp, max_temp, target_temp, tolerance):
        """Initialize the thermostat."""
        self._hass = hass
        self._name = name
        self._temp_sensor = temp_sensor
        self._heater_switch = heater_switch
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temperature = target_temp
        self._tolerance = tolerance
        self._hvac_mode = HVACMode.OFF
        self._current_temperature = None
        self._unit = UnitOfTemperature.CELSIUS
        self._is_heating = False
        self._action_history = deque(maxlen=5)  # Stores last 5 actions
        
    def _add_action(self, action: str):
        """Add an action to the history."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._action_history.appendleft(f"[{timestamp}] {action}")
        
    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._temp_sensor:
            state = self._hass.states.get(self._temp_sensor)
            if state and state.state not in ('unknown', 'unavailable'):
                self._current_temperature = float(state.state)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVACMode.OFF, HVACMode.HEAT]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def hvac_action(self):
        """Return the current running hvac operation."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        elif self._is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        return {
            "action_history": list(self._action_history)
        }

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = temp
            self._add_action(f"Set temperature to {temp}°C")
            await self._control_heating()
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        self._hvac_mode = hvac_mode
        self._add_action(f"Set mode to {hvac_mode}")
        if hvac_mode == HVACMode.OFF:
            # Turn off heater
            if self._heater_switch:
                await self._hass.services.async_call(
                    'switch', 'turn_off',
                    {'entity_id': self._heater_switch}
                )
            self._is_heating = False
        else:
            # Control heating based on temperature
            await self._control_heating()
        self.async_write_ha_state()

    async def _control_heating(self):
        """Control the heating based on temperature."""
        if not self._heater_switch or self._hvac_mode == HVACMode.OFF:
            return

        current_temp = self.current_temperature
        if current_temp is None:
            self._add_action("No temperature reading available")
            return

        if current_temp < (self._target_temperature - self._tolerance):
            if not self._is_heating:
                await self._hass.services.async_call(
                    'switch', 'turn_on',
                    {'entity_id': self._heater_switch}
                )
                self._is_heating = True
                self._add_action(f"Started heating at {current_temp}°C")
        elif current_temp > (self._target_temperature + self._tolerance):
            if self._is_heating:
                await self._hass.services.async_call(
                    'switch', 'turn_off',
                    {'entity_id': self._heater_switch}
                )
                self._is_heating = False
                self._add_action(f"Stopped heating at {current_temp}°C")

    async def async_update(self):
        """Update the current temperature and control heating."""
        await self._control_heating() 