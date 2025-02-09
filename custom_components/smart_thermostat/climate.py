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
from datetime import datetime, timezone, timedelta
from collections import deque
import asyncio
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import callback
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "smart_thermostat"
DEFAULT_NAME = "Smart Thermostat"

# System variables for timing
COMMAND_DELAY_MS = 100  # 100 milliseconds delay between commands

async def async_setup_platform(hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up the smart thermostat platform."""
    name = config.get("name", DEFAULT_NAME)
    temp_sensors = config.get("temperature_sensors", [])
    hvac_entity = config.get("hvac_entity")
    heat_pump_entity = config.get("heat_pump_entity")
    min_temp = config.get("min_temp", 16)
    max_temp = config.get("max_temp", 25)
    target_temp = config.get("target_temp", 20)
    tolerance = config.get("tolerance", 0.5)
    minimum_on_time = config.get("minimum_on_time", 5) * 60
    maximum_on_time = config.get("maximum_on_time", 30) * 60
    off_time = config.get("off_time", 20) * 60
    heat_pump_min_temp = config.get("heat_pump_min_temp", -5)
    heat_pump_max_temp = config.get("heat_pump_max_temp", -3)
    weather_entity = config.get("weather_entity", "weather.forecast_home")

    thermostat = SmartThermostat(
        hass, name, temp_sensors, hvac_entity, heat_pump_entity,
        min_temp, max_temp, target_temp, tolerance,
        minimum_on_time, maximum_on_time, off_time,
        heat_pump_min_temp, heat_pump_max_temp, weather_entity
    )
    
    # Store the thermostat instance in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][name] = thermostat
    
    # Register custom services
    async def handle_turn_on(call):
        """Handle the custom turn_on service."""
        entity_id = call.data.get('entity_id')
        if entity_id and entity_id == thermostat.entity_id:
            await thermostat.async_turn_on()

    async def handle_turn_off(call):
        """Handle the custom turn_off service."""
        entity_id = call.data.get('entity_id')
        if entity_id and entity_id == thermostat.entity_id:
            await thermostat.async_turn_off()

    # Register the services
    hass.services.async_register(
        DOMAIN, 'turn_on', handle_turn_on,
        schema=vol.Schema({
            vol.Required('entity_id'): cv.entity_id
        })
    )
    
    hass.services.async_register(
        DOMAIN, 'turn_off', handle_turn_off,
        schema=vol.Schema({
            vol.Required('entity_id'): cv.entity_id
        })
    )
    
    async_add_entities([thermostat])

class SmartThermostat(ClimateEntity):
    """Smart Thermostat Climate Entity."""
    
    def __init__(self, hass, name, temp_sensors, hvac_entity, heat_pump_entity,
                 min_temp, max_temp, target_temp, tolerance,
                 minimum_on_time, maximum_on_time, off_time,
                 heat_pump_min_temp, heat_pump_max_temp, weather_entity):
        """Initialize the thermostat."""
        # Validate required entities
        if not hvac_entity or not heat_pump_entity:
            raise ValueError("Both hvac_entity (furnace) and heat_pump_entity must be defined")
            
        self._hass = hass
        self._name = name
        self._hvac_entity = hvac_entity
        self._heat_pump_entity = heat_pump_entity
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._target_temperature = target_temp
        self._tolerance = tolerance
        self._temp_sensors = temp_sensors
        self._weather_entity = weather_entity
        
        # HVAC State
        self._hvac_mode = HVACMode.OFF
        self._hvac_action = HVACAction.OFF
        self._is_heating = False
        
        # Command tracking
        self._last_command_time = None
        self._command_delay = COMMAND_DELAY_MS / 1000  # Convert to seconds
        self._heat_pump_last_mode = None
        self._heat_pump_last_temp = None
        self._heat_pump_last_fan = None
        self._furnace_last_mode = None
        self._furnace_last_temp = None
        
        # Add supported features
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        
        # Initialize action history
        self._action_history = deque(maxlen=50)  # Keep last 50 actions
        self._last_update = datetime.now()
        self._sensor_temperatures = {}
        
        # Initialize temperature tracking
        self._current_temperature = None
        self._sensor_temperatures = {}
        
        # Initialize cycle tracking
        self._heating_start_time = None
        self._cooling_start_time = None
        self._learning_heating_duration = minimum_on_time  # Default heating duration
        self._minimum_heating_duration = minimum_on_time
        self._maximum_heating_duration = maximum_on_time
        self._off_time = off_time
        self._cycle_status = "waiting to activate"
        self._time_remaining = 0
        self._outdoor_temp_furnace_threshold = heat_pump_min_temp
        self._outdoor_temp_heat_pump_threshold = heat_pump_max_temp
        self._active_heat_source = None
        self._last_forecast_check = None
        self._system_enabled = False  # New state variable for system operational status
        
        # Add force mode tracking
        self._force_mode = None

    def _add_action(self, action: str):
        """Add an action to the history and log it."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        message = f"[{timestamp}] {action}"
        self._action_history.appendleft(message)
        
        # Add more detailed logging
        # _LOGGER.debug(
        #     "Smart Thermostat Action - Name: %s, Action: %s, Current Temp: %.1f, "
        #     "Target: %.1f, Mode: %s, Status: %s",
        #     self._name,
        #     action,
        #     self._current_temperature if self._current_temperature is not None else -999,
        #     self._target_temperature,
        #     self._hvac_mode,
        #     self._cycle_status
        # )
        
    def _is_sensor_fresh(self, sensor_id: str) -> bool:
        """Check if sensor data is fresh (within last 5 minutes)."""
        state = self._hass.states.get(sensor_id)
        if not state:
            self._add_action(f"Sensor {sensor_id} not found")
            # Remove from sensor_temperatures if not found
            self._sensor_temperatures.pop(sensor_id, None)
            return False
            
        try:
            last_updated = state.last_updated
            if isinstance(last_updated, str):
                last_updated = datetime.strptime(last_updated, "%Y-%m-%dT%H:%M:%S.%f%z")
            
            now = datetime.now(timezone.utc)
            time_diff = (now - last_updated).total_seconds()
            
            if time_diff > 300:  # 5 minutes
                # Remove stale data from sensor_temperatures
                self._sensor_temperatures.pop(sensor_id, None)
                return False
            return True
        except Exception as e:
            self._add_action(f"Error checking freshness for {sensor_id}: {str(e)}")
            self._sensor_temperatures.pop(sensor_id, None)
            return False

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
        """Return the average current temperature from fresh sensors only."""
        fresh_temperatures = {}  # Use dictionary to track both temp and source
        
        for sensor_id in self._temp_sensors:
            try:
                if not self._is_sensor_fresh(sensor_id):
                    continue
                    
                state = self._hass.states.get(sensor_id)
                if state and state.state not in ('unknown', 'unavailable'):
                    try:
                        temp = float(state.state)
                        fresh_temperatures[sensor_id] = temp
                    except ValueError:
                        self._add_action(f"Invalid temperature value from {sensor_id}: {state.state}")
                        continue
                else:
                    self._add_action(f"Invalid state from {sensor_id}: {state.state if state else 'No state'}")
            except Exception as e:
                self._add_action(f"Unexpected error with {sensor_id}: {str(e)}")
                continue

        if fresh_temperatures:
            # Update the sensor_temperatures dictionary
            self._sensor_temperatures = fresh_temperatures.copy()
            avg_temp = sum(fresh_temperatures.values()) / len(fresh_temperatures)
            self._current_temperature = avg_temp
            return avg_temp
        else:
            self._add_action("No fresh temperature data available")
            return None  # Return None instead of self._current_temperature when no data is available

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
    def supported_features(self) -> ClimateEntityFeature:
        """Return the list of supported features."""
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        return features

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        return self._hvac_action

    @property
    def extra_state_attributes(self):
        """Return entity specific state attributes."""
        now = datetime.now()
        
        # Calculate time remaining in current cycle
        if self._heating_start_time and self._is_heating:
            elapsed = (now - self._heating_start_time).total_seconds()
            self._time_remaining = max(0, self._learning_heating_duration - elapsed)
            cycle_type = "heating"
        elif self._cooling_start_time and not self._is_heating:
            elapsed = (now - self._cooling_start_time).total_seconds()
            self._time_remaining = max(0, self._off_time - elapsed)
            cycle_type = "cooling"
        else:
            self._time_remaining = 0
            cycle_type = "idle"

        attributes = {
            "action_history": list(self._action_history),
            "sensor_temperatures": self._sensor_temperatures,
            "average_temperature": self._current_temperature,
            "fresh_sensor_count": len(self._sensor_temperatures),
            "available_sensors": self._temp_sensors,
            "last_update": now.strftime("%H:%M:%S"),
            "learning_duration": round(self._learning_heating_duration / 60, 1),
            "cycle_status": self._cycle_status,
            "time_remaining": round(self._time_remaining / 60, 1),
            "cycle_type": cycle_type,
            "off_time": round(self._off_time / 60, 1),
            "force_mode": self._force_mode,  # Add force mode to attributes
        }

        return attributes

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = temp
            self._add_action(f"Set temperature to {temp}°C")
            await self._control_heating()
            self.async_write_ha_state()
            self._add_action(f"Set temperature to {temp}°C")

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return
            
        # Update mode first
        self._hvac_mode = hvac_mode
        
        # If turning off, update all states and return
        if hvac_mode == HVACMode.OFF and not self._system_enabled:
                        # Turn off furnace
            if self._hvac_entity:
                await self._send_command(
                    self._hvac_entity,
                    'set_hvac_mode',
                    {'hvac_mode': 'off'}
                )
                if self._heat_pump_entity:
                # Turn off heat pump
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_hvac_mode',
                        {'hvac_mode': 'off'}
                )
            self._hvac_action = HVACAction.OFF
            self._is_heating = False
            self._active_heat_source = None
            self._heating_start_time = None
            self._cooling_start_time = None
            self._cycle_status = "off"
        elif hvac_mode == HVACMode.OFF and self._system_enabled:

            
            # Turn off furnace
            if self._hvac_entity:
                await self._send_command(
                    self._hvac_entity,
                    'set_hvac_mode',
                    {'hvac_mode': 'off'}
                )
            
            # Set heat pump to minimum settings but don't turn off
            if self._heat_pump_entity:
                # Ensure heat pump is in heat mode first
                await self._send_command(
                    self._heat_pump_entity,
                    'set_hvac_mode',
                    {'hvac_mode': 'heat'}
                )
                await asyncio.sleep(self._command_delay)
                
                # Set minimum temperature
                await self._send_command(
                    self._heat_pump_entity,
                    'set_temperature',
                    {'temperature': 17}
                )
                await asyncio.sleep(self._command_delay)
                
                # # Set low fan speed - only for heat pump
                # await self._send_command(
                #     self._heat_pump_entity,
                #     'set_fan_mode',
                #     {'fan_mode': 'low'}
                # )
            
            # Disable the smart thermostat system
            self._hvac_action = HVACAction.OFF
            self._is_heating = False
            # Preserve cycle status if in a cooling cycle
            if not self._cycle_status.startswith("cooling cycle:"):
                self._cycle_status = "off"
            self._add_action("Smart thermostat disabled - systems available for manual control")
            self.async_write_ha_state()
            return
        else:
        
            # If turning on, determine appropriate heat source and activate it
            if self._force_mode:
                self._active_heat_source = self._force_mode
                self._add_action(f"Using forced heat source: {self._force_mode}")
                await self._switch_heat_source(self._force_mode)
            else:
                # Only check outdoor temperature if not in force mode
                await self._check_outdoor_temperature()
            
            # Ensure heat source is set and activated immediately
            if self._active_heat_source == "furnace":
                if self._hvac_entity:
                    await self._send_command(
                        self._hvac_entity,
                        'set_hvac_mode',
                        {'hvac_mode': 'heat'}
                    )
                    await self._send_command(
                        self._hvac_entity,
                        'set_temperature',
                        {'temperature': self._max_temp}
                    )
                    self._add_action("Activated furnace heating")
            elif self._active_heat_source == "heat_pump":
                if self._heat_pump_entity:
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_hvac_mode',
                        {'hvac_mode': 'heat'}
                    )
                    await asyncio.sleep(self._command_delay)
                    
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_temperature',
                        {'temperature': self._target_temperature}
                    )
                    self._add_action("Activated heat pump heating")
        

        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        self._system_enabled = True
        self._hvac_mode = HVACMode.HEAT
        await self._check_outdoor_temperature()
        await self._control_heating()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        self._system_enabled = False
        await self.async_set_hvac_mode(HVACMode.OFF)
        self.async_write_ha_state()

    async def _check_outdoor_temperature(self):
        """Check outdoor temperature and select appropriate heat source."""
        # Skip temperature check if force mode is active
        if self._force_mode:
            return
            
        now = datetime.now(timezone.utc)
        
        try:
            forecast = self._hass.states.get(self._weather_entity)
            if not forecast:
                self._add_action(f"Weather entity {self._weather_entity} not found")
                return
                
            if not forecast.attributes.get("temperature"):
                self._add_action(f"Temperature attribute missing from {self._weather_entity}")
                return
                
            outdoor_temp = float(forecast.attributes.get("temperature"))
            self._last_forecast_check = now
            
            # Determine appropriate heat source using inclusive boundaries
            new_source = None
            if outdoor_temp <= self._outdoor_temp_furnace_threshold:
                new_source = "furnace"
                self._add_action(f"Temperature {outdoor_temp}°C is below furnace threshold {self._outdoor_temp_furnace_threshold}°C - using furnace")
            elif outdoor_temp >= self._outdoor_temp_heat_pump_threshold:
                new_source = "heat_pump"
                self._add_action(f"Temperature {outdoor_temp}°C is above heat pump threshold {self._outdoor_temp_heat_pump_threshold}°C - using heat pump")
            else:
                # In transition zone - make an intelligent choice based on current source
                # If no current source, prefer heat pump as it's generally more efficient
                new_source = "heat_pump"
                self._add_action(f"Temperature {outdoor_temp}°C is in transition zone ({self._outdoor_temp_furnace_threshold}°C to {self._outdoor_temp_heat_pump_threshold}°C) - using heat pump")
            
            # Always set active heat source before switching
            self._active_heat_source = new_source
            self._add_action(f"Set active heat source to {new_source}")
            
            # Only switch if needed
            if new_source != self._active_heat_source:
                await self._switch_heat_source(new_source)
                
        except ValueError as e:
            self._add_action(f"Error parsing temperature from {self._weather_entity}: {str(e)}")
        except Exception as e:
            self._add_action(f"Unexpected error checking outdoor temperature: {str(e)}")

    async def _get_current_state(self, entity_id):
        """Get current state of an entity."""
        state = self._hass.states.get(entity_id)
        if not state:
            return None
        return {
            'state': state.state,
            'attributes': state.attributes
        }

    async def _should_send_command(self, entity_id, command_type, new_value):
        """Check if we should send a command based on current state and timing."""
        if self._last_command_time:
            time_since_last = (datetime.now() - self._last_command_time).total_seconds()
            if time_since_last < self._command_delay:
                await asyncio.sleep(self._command_delay - time_since_last)

        current_state = await self._get_current_state(entity_id)
        if not current_state:
            return True  # If we can't get state, default to sending command

        if entity_id == self._heat_pump_entity:
            if command_type == 'mode' and self._heat_pump_last_mode == new_value:
                return False
            elif command_type == 'temperature' and self._heat_pump_last_temp == new_value:
                return False
            elif command_type == 'fan_mode' and self._heat_pump_last_fan == new_value:
                return False
        elif entity_id == self._hvac_entity:
            if command_type == 'mode' and self._furnace_last_mode == new_value:
                return False
            elif command_type == 'temperature' and self._furnace_last_temp == new_value:
                return False

        return True

    async def _send_command(self, entity_id, service, data):
        """Send command with state tracking and delay."""
        # Determine command type and value based on data parameters
        command_type = None
        command_value = None
        
        if 'hvac_mode' in data:
            command_type = 'mode'
            command_value = data['hvac_mode']
        elif 'temperature' in data:
            command_type = 'temperature'
            command_value = data['temperature']
        else:
            command_type = 'other'
            command_value = None

        self._add_action(f"Sending command - Entity: {entity_id}, Service: {service}, Data: {data}")
        
        should_send = True
        if command_type != 'other':
            should_send = await self._should_send_command(entity_id, command_type, command_value)
            self._add_action(f"Command check - Type: {command_type}, Value: {command_value}, Should send: {should_send}")
        
        if not should_send:
            self._add_action(f"Skipping duplicate command to {entity_id}: {service} {data}")
            return

        # Update last command time
        self._last_command_time = datetime.now()

        # Update state tracking before sending command
        if entity_id == self._heat_pump_entity:
            if command_type == 'mode':
                self._heat_pump_last_mode = command_value
            elif command_type == 'temperature':
                self._heat_pump_last_temp = command_value
        elif entity_id == self._hvac_entity:
            if command_type == 'mode':
                self._furnace_last_mode = command_value
            elif command_type == 'temperature':
                self._furnace_last_temp = command_value

        self._add_action(f"State tracking updated - Last heat pump temp: {self._heat_pump_last_temp}, Last furnace temp: {self._furnace_last_temp}")

        domain = 'climate'
        
        # Send the command
        try:
            await self._hass.services.async_call(
                domain, service, {
                    'entity_id': entity_id,
                    **data
                }
            )
            self._add_action(f"Command sent successfully - Domain: {domain}, Service: {service}")
        except Exception as e:
            self._add_action(f"Error sending command: {str(e)}")
            raise

    async def _switch_heat_source(self, source):
        """Switch between heat pump and furnace with state checking and delays."""
        self._add_action(f"Switch heat source called - source: {source}, current: {self._active_heat_source}, force_mode: {self._force_mode}")
        
        if source == self._active_heat_source:
            self._add_action(f"Already using {source} - no switch needed")
            return

        try:
            if source == "furnace":
                # Set heat pump to minimum settings and turn it off
                try:
                    self._add_action("Setting heat pump to minimum settings")
                    
                    # First set mode
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_hvac_mode',
                        {'hvac_mode': 'heat'}
                    )
                    await asyncio.sleep(self._command_delay)

                    # Then set temperature
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_temperature',
                        {'temperature': 17}
                    )
                    self._heat_pump_last_temp = 17  # Explicitly set last temp
                    self._add_action(f"Heat pump temperature set to 17°C (last_temp: {self._heat_pump_last_temp})")

                    if self._force_mode:
                        self._cycle_status = "forced"
                    
                except Exception as e:
                    self._add_action(f"Warning: Failed to set heat pump minimum settings: {str(e)}")

                # Turn on furnace
                self._active_heat_source = "furnace"

            elif source == "heat_pump":
                self._add_action("Starting switch to heat pump")
                # Turn off furnace first
                await self._send_command(self._hvac_entity, "set_hvac_mode", {"hvac_mode": HVACMode.OFF})
                self._furnace_last_mode = HVACMode.OFF  # Explicitly set last mode
                await asyncio.sleep(self._command_delay)
                
                # Turn on heat pump
                await self._send_command(self._heat_pump_entity, "set_hvac_mode", {"hvac_mode": HVACMode.HEAT})
                self._heat_pump_last_mode = HVACMode.HEAT  # Explicitly set last mode
                self._active_heat_source = "heat_pump"
                # Set cycle status based on force mode
                if self._force_mode:
                    self._cycle_status = "forced"
                self._add_action(f"Heat source switch complete - now using heat pump (last_heat_pump_temp: {self._heat_pump_last_temp})")

        except Exception as e:
            self._add_action(f"Error during heat source switch: {str(e)}")
            raise

        # Ensure state is written after switch
        self.async_write_ha_state()
        await self._hass.async_block_till_done()

    async def _control_heating(self):
        """Control the heating based on temperature."""
        # Always update current temperature readings, even when system is disabled
        current_temp = self.current_temperature

        # If system is disabled, ensure all heating systems are off and states are reset
        if not self._system_enabled:
            if self._is_heating:
                # Turn off both heating systems
                if self._hvac_entity:
                    await self._hass.services.async_call(
                        'climate', 'set_hvac_mode',
                        {'entity_id': self._hvac_entity, 'hvac_mode': 'off'}
                    )
                if self._heat_pump_entity:
                    await self._hass.services.async_call(
                        'climate', 'set_hvac_mode',
                        {'entity_id': self._heat_pump_entity, 'hvac_mode': 'off'}
                    )
                
                # Reset heating states
                self._is_heating = False
                self._heating_start_time = None
                self._cooling_start_time = None
                self._hvac_action = HVACAction.OFF
                # Preserve cycle status if in a cooling cycle
                if not self._cycle_status.startswith("cooling cycle:"):
                    self._cycle_status = "disabled"
                self._add_action("System disabled - heating systems turned off")
                self.async_write_ha_state()
            return

        # Dispatch to appropriate control method based on active heat source
        if self._active_heat_source == "heat_pump":
            await self._control_heating_heat_pump(current_temp)
        elif self._active_heat_source == "furnace":
            await self._control_heating_furnace(current_temp)
        else:
            self._add_action("No active heat source selected")

    async def _control_heating_heat_pump(self, current_temp: float):
        """Control heat pump specific heating logic."""
        if self._hvac_mode == HVACMode.HEAT:
            if current_temp is not None:
                # Calculate temperature difference
                temp_diff = self._target_temperature - current_temp
                
                # Set heat pump temperature based on three states
                if temp_diff > 0.5:  # Below setpoint by more than 0.5°C
                    new_temp = self._max_temp
                    status = "max heating"
                elif abs(temp_diff) <= 0.5:  # Within 0.5°C of setpoint
                    new_temp = self._target_temperature
                    status = "maintaining"
                else:  # Above setpoint
                    new_temp = self._min_temp
                    status = "minimum heating"
                
                # Send command only if temperature setting would change
                if self._heat_pump_last_temp != new_temp:
                    await self._send_command(
                        self._heat_pump_entity,
                        'set_temperature',
                        {'temperature': new_temp}
                    )
                    self._add_action(f"Setting heat pump to {new_temp}°C ({status}) - current temp: {current_temp}°C")
                
                self._is_heating = True
                self._hvac_action = HVACAction.HEATING
                self._cycle_status = f"heatpump {status}"

    async def _control_heating_furnace(self, current_temp: float):
        """Control furnace specific heating logic with cycles."""
        if not self._system_enabled or self._hvac_mode == HVACMode.OFF:
            self._cycle_status = "off"
            self._is_heating = False
            self._hvac_action = HVACAction.OFF
            self._add_action("Control skipped: HVAC is off or no entity")
            self.async_write_ha_state()
            return


        now = datetime.now()
        
        # If we're not in any cycle and not cooling, ensure we're in ready state
        if not self._is_heating and not self._cooling_start_time:
            self._cycle_status = "waiting to activate"
            self._add_action(f"Status: ready, Temp: {current_temp:.1f}°C, Target: {self._target_temperature}°C, Heating: {self._is_heating}")
            
        # Start new heating cycle if needed and not in cooling period
        if (current_temp < (self._target_temperature - self._tolerance) and 
            self._hvac_mode == HVACMode.HEAT and
            not self._is_heating and 
            not self._cooling_start_time):
            
            await self._start_heating_cycle(now, current_temp)
            self.async_write_ha_state()
            return

        # Check if heating cycle is complete
        if self._heating_start_time and self._is_heating:
            heating_elapsed = (now - self._heating_start_time).total_seconds()
            remaining_time = max(0, self._learning_heating_duration - heating_elapsed)
            remaining_minutes = int(remaining_time / 60)
            self._cycle_status = f"heating cycle: {remaining_minutes}m remaining"
            
            if heating_elapsed >= self._learning_heating_duration:
                await self._hass.services.async_call(
                    'climate', 'set_hvac_mode',
                    {'entity_id': self._hvac_entity, 'hvac_mode': 'off'}
                )
                self._is_heating = False
                self._hvac_action = HVACAction.OFF
                self._heating_start_time = None
                self._cooling_start_time = now
                self._cycle_status = "cooling cycle: 20m remaining"
                self._add_action(f"Completed heating cycle, starting {self._off_time/60:.1f}min cooling period")
                self.async_write_ha_state()
                return

        # Check if cooling period is complete
        if self._cooling_start_time and not self._is_heating:
            cooling_elapsed = (now - self._cooling_start_time).total_seconds()
            remaining_time = max(0, self._off_time - cooling_elapsed)
            remaining_minutes = int(remaining_time / 60)
            self._cycle_status = f"cooling cycle: {remaining_minutes}m remaining"
            self._add_action(f"Off period: {cooling_elapsed:.1f}s of {self._off_time}s ({cooling_elapsed/60:.1f}min of {self._off_time/60:.1f}min)")
            
            if cooling_elapsed >= self._off_time:
                self._cycle_status = "waiting to activate"
                
                # Adjust learning duration based on temperature difference and cooling time
                temp_diff = self._target_temperature - current_temp
                
                if temp_diff > 0:  # We undershot
                    # Standard adjustment for undershooting
                    adjustment = abs(temp_diff) * 120  # 2 minutes per degree difference
                    new_duration = min(
                        self._learning_heating_duration + adjustment,
                        self._maximum_heating_duration
                    )
                    if new_duration != self._learning_heating_duration:
                        self._add_action(f"Undershot by {temp_diff:.1f}°C - Increasing duration to {new_duration/60:.1f}min (was {self._learning_heating_duration/60:.1f}min)")
                        self._learning_heating_duration = new_duration
                elif temp_diff < 0:  # We overshot
                    # Calculate how much longer than _off_time we needed to wait
                    extra_cooling_time = cooling_elapsed - self._off_time
                    if extra_cooling_time > 0:
                        # Adjust based on both temperature difference and extra cooling time
                        temp_adjustment = abs(temp_diff) * 120  # Base adjustment (2 min per degree)
                        cooling_adjustment = (extra_cooling_time / 60) * 60  # 1 min reduction per minute of extra cooling
                        total_adjustment = max(temp_adjustment, cooling_adjustment)
                        
                        new_duration = max(
                            self._learning_heating_duration - total_adjustment,
                            self._minimum_heating_duration
                        )
                        if new_duration != self._learning_heating_duration:
                            self._add_action(
                                f"Overshot by {abs(temp_diff):.1f}°C and needed {extra_cooling_time/60:.1f}min extra cooling - "
                                f"Decreasing duration to {new_duration/60:.1f}min (was {self._learning_heating_duration/60:.1f}min)"
                            )
                            self._learning_heating_duration = new_duration
                
                self._cooling_start_time = None  # Reset cooling start time
                self._add_action("Off period complete - ready for next cycle")
                
                # Immediately check if heating is needed
                if current_temp < (self._target_temperature - self._tolerance):
                    self._add_action(f"Temperature {current_temp:.1f}°C below target {self._target_temperature}°C - starting new heating cycle")
                    await self._start_heating_cycle(now, current_temp)
                self.async_write_ha_state()
                return

        # When cooling period completes, check for pending heat source change
        if hasattr(self, '_pending_heat_source') and self._pending_heat_source:
            if self._cycle_status == "waiting to activate":
                new_source = self._pending_heat_source
                self._pending_heat_source = None
                self._active_heat_source = new_source
                await self._switch_heat_source(new_source)
                self._add_action(f"Executing queued heat source change to {new_source}")

    async def _start_heating_cycle(self, now, current_temp):
        """Helper method to start a new heating cycle for furnace only."""
        if self._active_heat_source != "furnace":
            return
            
        # Calculate remaining time in minutes
        remaining_minutes = int(self._learning_heating_duration / 60)
        self._cycle_status = f"heating cycle: {remaining_minutes}m remaining"
        await self._hass.services.async_call(
            'climate', 'set_hvac_mode',
            {'entity_id': self._hvac_entity, 'hvac_mode': 'heat'}
        )
        await self._hass.services.async_call(
            'climate', 'set_temperature',
            {'entity_id': self._hvac_entity, 'temperature': self._max_temp}
        )
        self._is_heating = True
        self._heating_start_time = now
        self._add_action(f"Started furnace heating cycle at {current_temp:.1f}°C for {remaining_minutes}m")

    async def async_update(self):
        """Update the current temperature and control heating."""
        # Update temperature before controlling heating
        current_temp = self.current_temperature  # Store the result so it's actually used
        await self._control_heating()
        # Schedule next update with force_refresh=True, but don't await it
        self.async_schedule_update_ha_state(force_refresh=True) 

    async def async_force_heat_source(self, source: str) -> None:
        """Force a specific heat source."""
        self._add_action(f"Force heat source called with source: {source}")
        
        if source not in ["heat_pump", "furnace", None]:
            raise ValueError("Invalid heat source specified")
        
        # Set force mode and update state
        self._force_mode = source
        self._add_action(f"Force mode set to: {self._force_mode}")
        
        # Ensure state is written before proceeding
        self.async_write_ha_state()
        await self._hass.async_block_till_done()
        
        if source:
            self._add_action(f"Forcing heat source to {source}")
            # Immediately switch to forced source if system is enabled
            if self._system_enabled:
                self._add_action("System enabled, switching heat source")
                await self._switch_heat_source(source)
            else:
                self._add_action("System disabled, heat source switch queued")
        else:
            self._add_action("Cleared forced heat source")
            # Return to normal temperature-based selection
            await self._check_outdoor_temperature()
            # Ensure state is written after temperature check
            self.async_write_ha_state()
            await self._hass.async_block_till_done()
        
        self._add_action(f"Force heat source complete - force_mode: {self._force_mode}, active_source: {self._active_heat_source}") 

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Use the new event tracking method
        @callback
        def _async_sensor_changed(event):
            """Handle temperature changes."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._temp_sensors, _async_sensor_changed
            )
        ) 