# Smart HVAC Controller

## Overview
This project provides intelligent control of multi-source heating systems, including boiler/radiator heating and heat pumps. By integrating with Home Assistant, it orchestrates both an Ecobee thermostat for boiler control and SmartIR for heat pump management, optimizing comfort and efficiency across different heating sources.

## Features
- Manages multiple heating sources:
  - Boiler/radiator system via Ecobee thermostat
  - Lennox heat pump via SmartIR
- Intelligent source selection based on:
  - Outside temperature
  - Relative efficiency
  - Current heating demands
- Monitors multiple temperature sensors to calculate average temperatures per zone
- Implements learning algorithms to optimize heating cycles for both systems:
  - Dynamically adjusts heating duration for boiler cycles
  - Optimizes heat pump operation based on external temperature
- Zone-based temperature management
- Occupancy-aware temperature adjustments
- Configurable minimum and maximum cycle durations for each heat source
- Real-time monitoring via curses-based terminal UI

## Requirements
### Hardware:
- Ecobee thermostat
- 1-phase boiler with radiator heating
- Lennox heat pump
- IR controller compatible with SmartIR
- Temperature sensors for each zone

### Software:
- [Home Assistant](https://www.home-assistant.io/)
- [SmartIR Integration](https://github.com/smartHomeHub/SmartIR)
- [Home Assistant API Python Client](https://github.com/Apollon77/pyhomeassistant)

### Dependencies:
- Python 3.8+
- `homeassistant_api`

Install the required Python package:
```bash
pip install homeassistant-api
```

## Configuration
### Environment Variables
Set the following environment variable to enable API access:
- `HOMEKIT_KEY`: Your Home Assistant long-lived access token.

### Home Assistant Entities
Update the script with your specific entity IDs:
- Boiler Control: `climate.thermostat`
- Heat Pump Control: `climate.lennox_heat_pump`
- Outside Temperature: `sensor.outside_temperature`
- Occupancy sensors:
  - Main floor: `binary_sensor.main_floor_occupancy`
  - Thermostat: `binary_sensor.thermostat_occupancy`
  - Bedroom: `binary_sensor.bedroom_occupancy`
- Temperature sensors:
  - Bedroom: `sensor.bedroom_temperature`
  - Main floor: `sensor.main_floor_temperature`
  - Thermostat: `sensor.thermostat_current_temperature`

## How to Create a Long-Lived Access Token
1. Log in to your Home Assistant instance.
2. Go to your profile by clicking on your username or the user icon in the bottom left corner.
3. Scroll down to the **Long-Lived Access Tokens** section.
4. Click on **Create Token**.
5. Provide a name for the token (e.g., `Boiler Controller`) and click **OK**.
6. Copy the generated token and save it securely. You will not be able to view it again.

Set the token as an environment variable:
```bash
export HOMEKIT_KEY=<your-token-here>
```
Add this line to your shell profile file (e.g., `.bashrc` or `.zshrc`) to make it persistent.

## How to Run
1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/ecobee-boiler-controller.git
   cd ecobee-boiler-controller
   ```
2. Update the script with your Home Assistant configuration details.
3. Run the script:
   ```bash
   python thermostat_control_ui.py
   ```

## Usage
### Commands in the UI:
- `set <zone> <value>`: Set temperature for a specific zone. Example: `set bedroom 22.0`
- `mode <auto|boiler|heatpump>`: Select heating source mode
- `set`: Clear override and revert to automatic mode
- `q`: Quit the program

### Logs
The terminal UI displays:
- Current temperatures by zone
- Setpoint temperatures
- Occupancy status
- HVAC states for both heating sources
- System mode (auto/boiler/heat pump)
- Recent events log
- Outside temperature and efficiency metrics

## Installation
### 1. Install as a Custom Component
1. Create a directory for custom components in your Home Assistant configuration directory:
```bash
cd /config  # Your Home Assistant configuration directory
mkdir -p custom_components/smart_thermostat
```

2. Copy the following files into the `custom_components/smart_thermostat` directory:
- `__init__.py`
- `climate.py`
- `manifest.json`

The core component code should look like this:

```python:custom_components/smart_thermostat/climate.py
async def async_setup_platform(hass: HomeAssistant, config: ConfigType, async_add_entities, discovery_info=None):
    """Set up the smart thermostat platform."""
    name = config.get("name", DEFAULT_NAME)
    temp_sensors = config.get("temperature_sensors", [])
    hvac_entity = config.get("hvac_entity")
    min_temp = config.get("min_temp", 16)
    max_temp = config.get("max_temp", 25)
    target_temp = config.get("target_temp", 20)
    tolerance = config.get("tolerance", 0.5)
    minimum_on_time = config.get("minimum_on_time", 5) * 60  # Convert to seconds
    maximum_on_time = config.get("maximum_on_time", 30) * 60  # Convert to seconds
    off_time = config.get("off_time", 20) * 60  # Convert to seconds
```

And ensure your manifest.json is configured:

```json:custom_components/smart_thermostat/manifest.json
{
  "domain": "smart_thermostat",
  "name": "Smart Thermostat",
  "documentation": "https://github.com/your_username/your_repo",
  "dependencies": [],
  "codeowners": [],
  "requirements": [],
  "version": "1.0.0",
  "iot_class": "local_polling"
}
```

### 2. Configure Home Assistant
1. Add the following to your `configuration.yaml`. Here's a complete example showing both SmartIR and Smart Thermostat configuration:

```yaml:configuration.yaml
smartir:
climate:
  - platform: smartir
    name: "Heat pump"
    unique_id: kitchen_heat_pump
    device_code: 2161
    controller_data: remote.hvac_controller
    temperature_sensor: sensor.hvac_controller_temperature
    humidity_sensor: sensor.hvac_controller_humidity
    power_sensor: binary_sensor.ac_power
  - platform: smart_thermostat
    name: "Smart Furnace"
    temperature_sensors:
      - sensor.bedroom_temperature
      - sensor.office_temperature
      - sensor.thermostat_current_temperature
      - sensor.hvac_controller_temperature
    hvac_entity: climate.thermostat
    target_temp: 21.0
    min_temp: 19.0
    max_temp: 22.5
    tolerance: 0.5
    minimum_on_time: 5
    maximum_on_time: 15
    off_time: 25 
```

### Configuration Options
#### Smart Thermostat
| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `name` | string | "Smart Furnace" | Name of the thermostat entity |
| `temperature_sensors` | list | required | List of temperature sensor entities |
| `hvac_entity` | string | required | Entity ID of your main thermostat |
| `target_temp` | float | 20.0 | Default target temperature |
| `min_temp` | float | 16.0 | Minimum settable temperature |
| `max_temp` | float | 25.0 | Maximum settable temperature |
| `tolerance` | float | 0.5 | Temperature variation allowed |
| `minimum_on_time` | int | 5 | Minimum heating cycle (minutes) |
| `maximum_on_time` | int | 30 | Maximum heating cycle (minutes) |
| `off_time` | int | 20 | Minimum off time between cycles (minutes) |

### Entity Naming
The integration creates entities following this pattern:
- Main climate entity: `climate.smart_furnace` (or your chosen name)
- Attributes available:
  - `average_temperature`: Current average from all sensors
  - `sensor_temperatures`: Individual sensor readings
  - `learning_duration`: Current learned cycle duration
  - `cycle_status`: Current cycle state
  - `action_history`: Recent actions log

### Home Assistant UI Integration
The component automatically appears in:
- Climate card
- Thermostat controls
- Developer Tools > States

### Custom Lovelace Card
Add this to your Lovelace dashboard for enhanced control:

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.smart_furnace
  - type: entities
    entities:
      - entity: climate.smart_furnace
        secondary_info: last-changed
        type: custom:multiple-entity-row
        show_state: false
        entities:
          - attribute: average_temperature
            name: Avg Temp
          - attribute: learning_duration
            name: Cycle
          - attribute: cycle_status
            name: Status
```

### Troubleshooting
1. Check Home Assistant logs for errors:
```bash
tail -f /config/home-assistant.log | grep smart_thermostat
```

2. Verify sensor data:
- Go to Developer Tools > States
- Search for your climate.smart_furnace entity
- Check attributes for sensor readings and cycle status

3. Common issues:
- Stale sensor data: Check sensor update frequency
- Incorrect cycling: Adjust min/max times
- Temperature overshooting: Reduce maximum_on_time
- Slow response: Decrease off_time

## Disclaimer
The author does not assume any responsibility for damages to your furnace, Ecobee, or any other equipment resulting from the use of this software.

