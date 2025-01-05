# Ecobee Boiler Controller

## Overview
This project extends the functionality of an Ecobee thermostat to better handle boiler/radiator heating systems, which have a significant lag time in delivering heat. By integrating with Home Assistant, this script enables more precise control of the Ecobee thermostat for systems using a single-phase boiler.

## Features
- Monitors multiple temperature sensors to calculate an average temperature.
- Adjusts the setpoint based on occupancy using connected sensors.
- Handles the Ecobee's behavior of waiting before activating heating to avoid unnecessary cycling.
- Ensures a 3-minute delay after heating sessions to account for boiler/radiator lag.
- Provides a curses-based terminal UI for real-time monitoring and control.

## Requirements
### Hardware:
- Ecobee thermostat
- 1-phase boiler with radiator heating

### Software:
- [Home Assistant](https://www.home-assistant.io/)
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
- Thermostat: `climate.thermostat`
- Occupancy sensors:
  - Main floor: `binary_sensor.main_floor_occupancy`
  - Thermostat: `binary_sensor.thermostat_occupancy`
  - Bedroom: `binary_sensor.bedroom_occupancy`
- Temperature sensors:
  - Bedroom: `sensor.bedroom_temperature`
  - Main floor: `sensor.main_floor_temperature`
  - Thermostat: `sensor.thermostat_current_temperature`

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
- `set <value>`: Set a new temperature setpoint. Example: `set 22.0`
- `set`: Clear override and revert to occupancy-based system.
- `q`: Quit the program.

### Logs
The terminal UI displays:
- Current temperature
- Setpoint temperature
- Occupancy status
- HVAC state and action
- Recent events log

## Limitations
- This script assumes a single-phase boiler with significant lag time.
- Relies on the accuracy and availability of Home Assistant sensors.
- Author assumes no responsibility for any damages to your ecobee or furnace, make sure to adjust the settings for your own circumstances.

