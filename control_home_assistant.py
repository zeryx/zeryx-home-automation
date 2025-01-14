"""
Home Assistant Thermostat Control Integration

This script provides intelligent thermostat control with occupancy-based temperature management
and self-learning heating cycles. It can be integrated into Home Assistant in several ways:

1. As a Python Script component:
   - Place this file in config/python_scripts/
   - Call from automations using 'python_script.thermostat_control'

2. As a custom component:
   - Place in config/custom_components/smart_thermostat/
   - Add to configuration.yaml:
     smart_thermostat:

3. As an AppDaemon app:
   - Place in config/appdaemon/apps/
   - Add configuration to apps.yaml

To monitor the system:
1. Add this to your Lovelace UI configuration:

  type: vertical-stack
  cards:
    - type: entities
      title: Smart Thermostat Control
      entities:
        - entity: sensor.smart_thermo_status
        - entity: sensor.smart_thermo_setpoint 
        - entity: sensor.smart_thermo_current_temp
        - entity: sensor.heating_cycle_time
        - entity: sensor.heating_learning_duration
        - entity: input_number.temp_setpoint
        - entity: input_boolean.temp_override
    - type: history-graph
      title: Temperature History
      entities:
        - entity: sensor.smart_thermo_current_temp
        - entity: sensor.smart_thermo_setpoint
    - type: entities
      title: Smart Thermostat Configuration
      entities:
        - entity: input_number.smart_thermo_default_temp
        - entity: input_number.smart_thermo_away_temp
        - entity: input_number.smart_thermo_max_temp
        - entity: input_number.smart_thermo_min_on_time
        - entity: input_number.smart_thermo_max_on_time
        - entity: input_number.smart_thermo_off_time
"""


import hassapi as hass
import datetime
import time

class SmartThermostatControl(hass.Hass):
    def initialize(self):
        # Constants
        self.THERMOSTAT_ENTITY = "climate.thermostat"
        self.OCCUPANCY_SENSORS = [
            "binary_sensor.main_floor_occupancy",
            "binary_sensor.thermostat_occupancy", 
            "binary_sensor.bedroom_occupancy"
        ]
        self.TEMP_SENSORS = [
            "sensor.bedroom_temperature",
            "sensor.main_floor_temperature",
            "sensor.thermostat_current_temperature"
        ]
        
        # Create configurable settings
        self.create_config_controls()
        
        # Initialize state
        self.hvac_state = "off"
        self.current_temp = None
        
        # Set up UI sensors
        self.setup_ui_sensors()
        
        # Set up listeners
        for sensor in self.TEMP_SENSORS + self.OCCUPANCY_SENSORS:
            self.listen_state(self.state_change_handler, sensor)
            
        # Run control loop every minute
        self.run_every(self.control_cycle, "now", 60)
        
        # Create input controls
        self.create_input_controls()

    def setup_ui_sensors(self):
        """Create sensors to display system status in HA frontend"""
        # Status sensor
        attrs = {
            "friendly_name": "Smart Thermostat Status",
            "icon": "mdi:thermostat"
        }
        self.set_state("sensor.smart_thermo_status", state="Initializing", attributes=attrs)
        
        # Learning duration sensor
        attrs = {
            "friendly_name": "Learning Duration", 
            "icon": "mdi:timer",
            "unit_of_measurement": "minutes"
        }
        self.set_state("sensor.heating_learning_duration", 
                       state=round(self.learning_duration/60, 1),
                       attributes=attrs)

        # Current cycle time sensor
        attrs = {
            "friendly_name": "Current Heating Cycle Time",
            "icon": "mdi:timer-sand",
            "unit_of_measurement": "minutes"
        }
        self.set_state("sensor.heating_cycle_time", state="0", attributes=attrs)

        # Setpoint display sensor
        attrs = {
            "friendly_name": "Current Setpoint",
            "icon": "mdi:thermometer",
            "unit_of_measurement": "°C"
        }
        self.set_state("sensor.smart_thermo_setpoint", 
                       state=self.current_setpoint,
                       attributes=attrs)

        # Current temperature sensor
        attrs = {
            "friendly_name": "Current Temperature",
            "icon": "mdi:thermometer",
            "unit_of_measurement": "°C"
        }
        self.set_state("sensor.smart_thermo_current_temp", 
                       state=0,
                       attributes=attrs)

    def create_input_controls(self):
        """Create input controls for user interaction"""
        input_number = {
            "min": 15,
            "max": 25,
            "step": 0.5,
            "mode": "slider",
            "icon": "mdi:thermometer"
        }
        self.set_state("input_number.temp_setpoint", state=self.current_setpoint, 
                       attributes=input_number)
        
        input_boolean = {
            "icon": "mdi:auto-fix"
        }
        self.set_state("input_boolean.temp_override", state="off",
                       attributes=input_boolean)

    def update_cycle_time(self):
        """Update the current heating cycle time display"""
        if self.cycle_start_time and self.hvac_state == "heat":
            elapsed = (time.time() - self.cycle_start_time) / 60  # Convert to minutes
            self.set_state("sensor.heating_cycle_time", 
                          state=round(elapsed, 1))
        else:
            self.set_state("sensor.heating_cycle_time", state="0")

    def get_average_temp(self):
        """Get average temperature from sensors"""
        valid_temps = []
        for sensor in self.TEMP_SENSORS:
            temp = float(self.get_state(sensor))
            if temp is not None:
                valid_temps.append(temp)
                
        if valid_temps:
            avg_temp = sum(valid_temps) / len(valid_temps)
            self.set_state("sensor.smart_thermo_current_temp", state=round(avg_temp, 1))
            return avg_temp
        return None

    def adjust_setpoint(self):
        """Adjust temperature setpoint based on occupancy"""
        override = self.get_state("input_boolean.temp_override") == "on"
        
        if override:
            self.current_setpoint = float(self.get_state("input_number.temp_setpoint"))
        else:
            self.current_setpoint = (self.DEFAULT_TEMP if self.check_occupancy() 
                                   else self.AWAY_TEMP)
            
        self.set_state("sensor.smart_thermo_setpoint", state=round(self.current_setpoint, 1))
        self.log(f"Current setpoint: {self.current_setpoint}°C")

    def set_hvac(self, mode):
        """Control HVAC system with error handling"""
        try:
            self.call_service("climate/set_hvac_mode",
                            entity_id=self.THERMOSTAT_ENTITY,
                            hvac_mode=mode)
            if mode == "heat" and self.hvac_state != "heat":
                self.cycle_start_time = time.time()
            elif mode == "off":
                self.cycle_start_time = None
                
            if mode == "heat":
                self.call_service("climate/set_temperature",
                                entity_id=self.THERMOSTAT_ENTITY,
                                temperature=self.MAX_TEMP)
            self.hvac_state = mode
            self.update_cycle_time()
            return True
        except Exception as e:
            self.log(f"Failed to set HVAC mode: {str(e)}", level="ERROR")
            self.set_state("sensor.smart_thermo_status", 
                          state=f"Error: Failed to control HVAC")
            return False

    def control_cycle(self, kwargs):
        """Main control loop with enhanced logging"""
        self.log(f"Starting control cycle:")
        self.log(f"Current temp: {self.current_temp}°C")
        self.log(f"Target temp: {self.current_setpoint}°C")
        self.log(f"HVAC state: {self.hvac_state}")
        
        self.current_temp = self.get_average_temp()
        self.adjust_setpoint()
        self.update_cycle_time()
        
        if self.current_temp is None:
            self.log("Unable to get temperature readings")
            return
            
        if self.current_temp < self.current_setpoint:
            # Start heating cycle
            initial_temp = self.current_temp
            self.set_hvac("heat")
            self.set_state("sensor.smart_thermo_status", 
                          state=f"Heating - Target: {self.current_setpoint}°C")
            
            # Schedule end of heating cycle
            self.run_in(self.end_heating_cycle, 
                       self.learning_duration,
                       initial_temp=initial_temp)
        else:
            self.set_hvac("off")
            self.set_state("sensor.smart_thermo_status",
                          state=f"Idle - At temperature {self.current_temp}°C")

    def end_heating_cycle(self, kwargs):
        """End heating cycle and adjust learning duration"""
        initial_temp = kwargs["initial_temp"]
        final_temp = self.get_average_temp()
        
        if final_temp is not None:
            temp_diff = final_temp - self.current_setpoint
            
            # Adjust learning duration based on results
            if temp_diff > 0:  # Overshot
                adjustment = max(0.1, min(1.0, temp_diff / self.current_setpoint))
                self.learning_duration *= (1 - adjustment)
                self.learning_duration = max(self.MIN_ON_TIME, self.learning_duration)
            elif temp_diff < 0:  # Undershot
                adjustment = abs(temp_diff) / self.current_setpoint
                self.learning_duration *= (1 + adjustment)
                self.learning_duration = min(self.MAX_ON_TIME, self.learning_duration)
                
            self.set_state("sensor.heating_learning_duration",
                          state=round(self.learning_duration/60, 1))
        
        self.set_hvac("off")
        
    def state_change_handler(self, entity, attribute, old, new, kwargs):
        """Handle state changes of monitored entities with debouncing"""
        if entity.startswith("input_number.smart_thermo_"):
            # Cancel any pending control cycles
            if hasattr(self, '_pending_control'):
                self.cancel_timer(self._pending_control)
            # Schedule new control cycle with 2-second delay
            self._pending_control = self.run_in(
                lambda x: self.control_cycle(kwargs={}), 
                2
            )

    def create_config_controls(self):
        """Create input controls for configuration"""
        # Check if controls already exist
        if self.get_state("input_number.smart_thermo_default_temp") is None:
            # Temperature controls
            temp_controls = {
                "default_temp": {
                    "name": "Default Temperature",
                    "min": 15,
                    "max": 25,
                    "step": 0.5,
                    "initial": 21.0
                },
                "away_temp": {
                    "name": "Away Temperature",
                    "min": 15,
                    "max": 25,
                    "step": 0.5,
                    "initial": 19.0
                },
                "max_temp": {
                    "name": "Maximum Temperature",
                    "min": 15,
                    "max": 30,
                    "step": 0.5,
                    "initial": 22.5
                }
            }
            
            # Timing controls (in minutes)
            time_controls = {
                "min_on_time": {
                    "name": "Minimum Heating Time",
                    "min": 1,
                    "max": 30,
                    "step": 1,
                    "initial": 5
                },
                "max_on_time": {
                    "name": "Maximum Heating Time",
                    "min": 5,
                    "max": 60,
                    "step": 1,
                    "initial": 15
                },
                "off_time": {
                    "name": "Minimum Off Time",
                    "min": 5,
                    "max": 60,
                    "step": 1,
                    "initial": 25
                }
            }
            
            # Create temperature controls
            for key, config in temp_controls.items():
                input_number = {
                    "min": config["min"],
                    "max": config["max"],
                    "step": config["step"],
                    "mode": "slider",
                    "icon": "mdi:thermometer",
                    "friendly_name": config["name"],
                    "unit_of_measurement": "°C"
                }
                self.set_state(f"input_number.smart_thermo_{key}", 
                              state=config["initial"],
                              attributes=input_number)
                
            # Create timing controls
            for key, config in time_controls.items():
                input_number = {
                    "min": config["min"],
                    "max": config["max"],
                    "step": config["step"],
                    "mode": "slider",
                    "icon": "mdi:timer",
                    "friendly_name": config["name"],
                    "unit_of_measurement": "minutes"
                }
                self.set_state(f"input_number.smart_thermo_{key}", 
                              state=config["initial"],
                              attributes=input_number)

    def get_temp_setting(self, setting):
        """Get temperature setting from HA input_number with fallback values"""
        fallback_values = {
            "default_temp": 21.0,
            "away_temp": 19.0,
            "max_temp": 22.5
        }
        try:
            value = float(self.get_state(f"input_number.smart_thermo_{setting}"))
            return value if value is not None else fallback_values[setting]
        except (ValueError, TypeError):
            self.log(f"Error getting {setting}, using fallback value")
            return fallback_values[setting]

    def validate_settings(self):
        """Validate temperature and timing settings"""
        # Get temperature settings
        max_temp = self.get_temp_setting("max_temp")
        default_temp = self.get_temp_setting("default_temp")
        away_temp = self.get_temp_setting("away_temp")
        
        # Validate temperature hierarchy
        errors = []
        if default_temp > max_temp:
            errors.append(
                f"Default temperature ({default_temp}°C) cannot exceed maximum temperature ({max_temp}°C)"
            )
        if away_temp > default_temp:
            errors.append(
                f"Away temperature ({away_temp}°C) cannot exceed default temperature ({default_temp}°C)"
            )
            
        # Validate timing settings
        min_on = self.get_time_setting("min_on_time")
        max_on = self.get_time_setting("max_on_time")
        if min_on > max_on:
            errors.append(
                f"Minimum on time ({min_on/60}min) cannot exceed maximum on time ({max_on/60}min)"
            )
            
        # If any validation errors occurred, log them and update status
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(errors)
            self.log(error_msg, level="ERROR")
            self.set_state("sensor.smart_thermo_status", 
                          state="Error: Invalid Configuration")
            raise ValueError(error_msg)


