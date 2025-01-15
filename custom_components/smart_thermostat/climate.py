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
from datetime import datetime, timezone
from collections import deque

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"
DEFAULT_NAME = "Smart Thermostat"

async def async_setup_platform(hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up the smart thermostat platform."""
    name = config.get("name", DEFAULT_NAME)
    temp_sensors = config.get("temperature_sensors", [])  # Get list of sensors
    heater_switch = config.get("heater")
    min_temp = config.get("min_temp", 16)
    max_temp = config.get("max_temp", 25)
    target_temp = config.get("target_temp", 20)
    tolerance = config.get("tolerance", 0.5)

    async_add_entities([
        SmartThermostat(
            hass, name, temp_sensors, heater_switch,
            min_temp, max_temp, target_temp, tolerance
        )
    ])

class SmartThermostat(ClimateEntity):
    """Smart Thermostat Climate Entity."""
    
    def __init__(self, hass, name, temp_sensors, heater_switch,
                 min_temp, max_temp, target_temp, tolerance):
        """Initialize the thermostat."""
        self._hass = hass
        self._name = name
        self._temp_sensors = temp_sensors
        self._heater_switch = heater_switch
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temperature = target_temp
        self._tolerance = tolerance
        self._hvac_mode = HVACMode.OFF
        self._current_temperature = None
        self._unit = UnitOfTemperature.CELSIUS
        self._is_heating = False
        self._action_history = deque(maxlen=5)
        self._sensor_temperatures = {}
        self._sensor_last_update = {}
        
    def _add_action(self, action: str):
        """Add an action to the history."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._action_history.appendleft(f"[{timestamp}] {action}")
        
    def _is_sensor_fresh(self, sensor_id: str) -> bool:
        """Check if sensor data is fresh (within last 5 minutes)."""
        state = self._hass.states.get(sensor_id)
        if not state:
            self._add_action(f"Sensor {sensor_id} not found")
            return False
            
        try:
            last_updated = state.last_updated
            if isinstance(last_updated, str):
                last_updated = datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%S.%f%z")
            
            # Convert to UTC for comparison
            now = datetime.now(timezone.utc)
            time_diff = (now - last_updated).total_seconds()
            
            if time_diff > 300:  # 5 minutes
                self._add_action(f"Sensor {sensor_id} data is stale: {time_diff:.1f}s old")
                return False
            return True
        except Exception as e:
            self._add_action(f"Error checking freshness for {sensor_id}: {str(e)}")
            return False

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
        """Return the average current temperature from fresh sensors only."""
        fresh_temperatures = []
        
        for sensor_id in self._temp_sensors:
            try:
                if not self._is_sensor_fresh(sensor_id):
                    continue
                    
                state = self._hass.states.get(sensor_id)
                if state and state.state not in ('unknown', 'unavailable'):
                    temp = float(state.state)
                    fresh_temperatures.append(temp)
                    self._sensor_temperatures[sensor_id] = temp
                    self._add_action(f"Got fresh reading from {sensor_id}: {temp}°C")
                else:
                    self._add_action(f"Invalid state from {sensor_id}: {state.state if state else 'No state'}")
            except ValueError as e:
                self._add_action(f"Error reading {sensor_id}: {str(e)}")
                continue
            except Exception as e:
                self._add_action(f"Unexpected error with {sensor_id}: {str(e)}")
                continue

        if fresh_temperatures:
            avg_temp = sum(fresh_temperatures) / len(fresh_temperatures)
            self._current_temperature = avg_temp
            self._add_action(f"Calculated average temperature: {avg_temp:.1f}°C from {len(fresh_temperatures)} sensors")
            return avg_temp
        else:
            self._add_action("No fresh temperature data available")
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
            "action_history": list(self._action_history),
            "sensor_temperatures": self._sensor_temperatures,
            "average_temperature": self._current_temperature,
            "fresh_sensor_count": len([s for s in self._temp_sensors if self._is_sensor_fresh(s)])
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