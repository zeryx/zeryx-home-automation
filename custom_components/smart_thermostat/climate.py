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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import logging
from datetime import datetime, timezone, timedelta
from collections import deque
from homeassistant.core import callback
from homeassistant.util import dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"
DEFAULT_NAME = "Smart Thermostat"

async def async_setup_platform(hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up the smart thermostat platform."""
    name = config.get("name", DEFAULT_NAME)
    temp_sensors = config.get("temperature_sensors", [])
    hvac_entity = config.get("hvac_entity")
    min_temp = config.get("min_temp", 16)
    max_temp = config.get("max_temp", 25)
    target_temp = config.get("target_temp", 20)
    tolerance = config.get("tolerance", 0.5)

    async_add_entities([
        SmartThermostat(
            hass, name, temp_sensors, hvac_entity,
            min_temp, max_temp, target_temp, tolerance
        )
    ])

class SmartThermostat(ClimateEntity):
    """Smart Thermostat Climate Entity."""
    
    def __init__(self, hass, name, temp_sensors, hvac_entity,
                 min_temp, max_temp, target_temp, tolerance):
        """Initialize the thermostat."""
        self._hass = hass
        self._name = name
        self._hvac_entity = hvac_entity
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temperature = target_temp
        self._tolerance = tolerance
        self._temp_sensors = temp_sensors
        
        # Temperature state
        self._current_temperature = None
        
        # HVAC State
        self._hvac_mode = HVACMode.OFF
        self._hvac_action = HVACAction.OFF
        self._is_heating = False
        
        # Add supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
        )
        
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        
        # Initialize action history
        self._action_history = deque(maxlen=50)  # Keep last 50 actions
        self._last_update = datetime.now()
        self._sensor_temperatures = {}

        # Add missing initializations
        self._heating_start_time = None
        self._cooling_start_time = None
        self._learning_heating_duration = 300  # 5 minutes default
        self._off_time = 1500  # 25 minutes default
        self._time_remaining = 0
        self._cycle_status = "idle"

    def _add_action(self, action: str) -> None:
        """Add a new action to the action log."""
        timestamp = dt_util.utcnow()
        self._action_history.appendleft((timestamp, action))
        if len(self._action_history) > self.MAX_ACTIONS:
            self._action_history.popleft()
        # Remove the state update from here
        _LOGGER.debug("Action added: %s", action)

    def _is_sensor_fresh(self, sensor_id: str) -> bool:
        """Check if the sensor data is fresh."""
        if sensor_id not in self._sensor_temperatures:
            # Instead of adding an action, just return False
            return False
        return True

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._attr_temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        try:
            # Get valid temperatures from sensors
            valid_temps = []
            for sensor_id in self._temp_sensors:
                state = self.hass.states.get(sensor_id)
                if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    self._add_action(f"Sensor {sensor_id} unavailable")
                    continue
                    
                try:
                    temp = float(state.state)
                    valid_temps.append(temp)
                except ValueError:
                    self._add_action(f"Invalid reading from {sensor_id}: {state.state}")
                    continue

            if not valid_temps:
                self._add_action("No valid temperature readings")
                return None

            # Calculate average of valid temperatures
            avg_temp = sum(valid_temps) / len(valid_temps)
            return round(avg_temp, 1)

        except Exception as ex:
            _LOGGER.error("Error getting temperature: %s", ex)
            return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation ie. heat, cool mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available hvac operation modes."""
        return self._attr_hvac_modes

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
        return self._attr_supported_features

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        return self._hvac_action

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        cycle_type = "heating" if self._is_heating else "cooling" if self._is_cooling else "idle"
        recent_actions = list(self._action_history)
        
        return {
            "action_history": recent_actions,
            "sensor_temperatures": self._sensor_temperatures,
            "average_temperature": self._current_temperature,
            "fresh_sensor_count": len(self._sensor_temperatures),
            "cycle_status": self._cycle_status,
            "time_remaining": round(self._time_remaining / 60, 1),
            "cycle_type": cycle_type
        }

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = temp
            self._add_action(f"Set temperature to {temp}°C")
            await self._control_heating()
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return
            
        self._hvac_mode = hvac_mode
        
        # Control underlying HVAC
        if self._hvac_entity:
            if hvac_mode == HVACMode.OFF:
                await self._hass.services.async_call(
                    'climate', 'set_hvac_mode',
                    {
                        'entity_id': self._hvac_entity,
                        'hvac_mode': 'off'
                    }
                )
                self._hvac_action = HVACAction.OFF
                self._is_heating = False
            else:
                await self._hass.services.async_call(
                    'climate', 'set_hvac_mode',
                    {
                        'entity_id': self._hvac_entity,
                        'hvac_mode': 'heat'
                    }
                )
                # Also set temperature when turning on
                await self._hass.services.async_call(
                    'climate', 'set_temperature',
                    {
                        'entity_id': self._hvac_entity,
                        'temperature': self._target_temperature
                    }
                )
                
        await self.async_update_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def _control_heating(self):
        """Control the heating based on temperature."""
        if not self._hvac_entity or self._hvac_mode == HVACMode.OFF:
            return

        current_temp = self.current_temperature
        if current_temp is None:
            self._add_action("No temperature reading available")
            return

        now = datetime.now()

        # Control the underlying climate entity
        if current_temp < (self._target_temperature - self._tolerance) and not self._is_heating:
            await self._hass.services.async_call(
                'climate', 'set_hvac_mode',
                {
                    'entity_id': self._hvac_entity,
                    'hvac_mode': 'heat'
                }
            )
            await self._hass.services.async_call(
                'climate', 'set_temperature',
                {
                    'entity_id': self._hvac_entity,
                    'temperature': self._target_temperature
                }
            )
            self._is_heating = True
            self._heating_start_time = now
            self._add_action(f"Started heating cycle at {current_temp}°C targeting {self._target_temperature}°C")

    async def async_update(self):
        """Update the current temperature and control heating."""
        # Update temperature before controlling heating
        self.current_temperature
        await self._control_heating() 

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        async def _update_state(*_):
            """Update state."""
            # Get current temperature before updating state
            self.current_temperature
            await self._control_heating()
            # Use force_update=False to prevent recursion
            self.async_write_ha_state()

        # Update every 15 seconds instead of 30
        self.async_on_remove(
            self._hass.helpers.event.async_track_time_interval(
                _update_state, timedelta(seconds=15)
            )
        ) 

    @callback
    def _async_sensor_changed(self, event):
        """Handle temperature changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            self._add_action(f"Sensor update: {event.data['entity_id']} unavailable")
        else:
            try:
                float(new_state.state)
                self._add_action(f"Sensor update: {event.data['entity_id']} = {new_state.state}")
            except ValueError as ex:
                self._add_action(f"Invalid sensor reading: {ex}")
        
        # Update state only once per sensor change
        self.async_write_ha_state() 