# Ecobee for Radiators

## Overview
This project extends the functionality of an Ecobee thermostat to better handle boiler/radiator heating systems, which have a significant lag time in delivering heat. By integrating with Home Assistant, this script enables more precise control of the Ecobee thermostat for systems using a single-phase boiler.

## Features
- Monitors multiple temperature sensors to calculate an average temperature.
- Adjusts the setpoint based on occupancy using connected sensors.
- Implements a learning algorithm to optimize heating cycles:
  - Dynamically adjusts the heating duration based on the temperature difference between the setpoint and the observed temperature after a cooling period.
  - Ensures efficient heating by increasing the heating time if the temperature does not reach the setpoint.
- Configurable minimum and maximum heating cycle durations.
- Adjustable minimum off time between heating cycles to allow for boiler recovery.
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

## Disclaimer
The author does not assume any responsibility for damages to your furnace, Ecobee, or any other equipment resulting from the use of this software.

