import time
import os
from datetime import datetime
from threading import Thread, Event
from homeassistant_api import Client
import curses

# Home Assistant API configuration
HOME_ASSISTANT_URL = os.environ["HOMEKIT_API_ADDRESS"]
ACCESS_TOKEN = os.environ["HOMEKIT_KEY"]

# Thermostat and occupancy entity IDs
THERMOSTAT_ENTITY_ID = "climate.thermostat"
MAIN_FLOOR_OCCUPANCY_SENSOR = "binary_sensor.main_floor_occupancy"
THERMOSTAT_OCCUPANCY_SENSOR = "binary_sensor.thermostat_occupancy"
BEDROOM_OCCUPANCY_SENSOR = "binary_sensor.bedroom_occupancy"

# Temperature sensors
BEDROOM_TEMPERATURE_SENSOR = "sensor.bedroom_temperature"
MAIN_FLOOR_TEMPERATURE_SENSOR = "sensor.main_floor_temperature"
THERMOSTAT_TEMPERATURE_SENSOR = "sensor.thermostat_current_temperature"

# Default setpoint temperatures
DEFAULT_TEMPERATURE_SETPOINT = 21.0  # Celsius
AWAY_TEMPERATURE_SETPOINT = 19.0  # Celsius
MAX_TEMPERATURE_SETPOINT = 22.5  # Celsius
TEMPERATURE_SETPOINT = DEFAULT_TEMPERATURE_SETPOINT  # Initial setpoint
OVERRIDE_SETPOINT = None
MINIMUM_ON_TIME = 5  # Minutes of minimum furnace on cycle time
MAXIMUM_ON_TIME = 15  # Minutes of maximum furnace on cycle time
OFF_TIME = 25  # Minutes of minimum furnace off, after a heating

# Initialize the Home Assistant API client
service_client = Client(HOME_ASSISTANT_URL, ACCESS_TOKEN)
thermostat = service_client.get_entity(entity_id=THERMOSTAT_ENTITY_ID)
service = service_client.get_domain("climate")

# Event to control thread execution
stop_event = Event()
events = []
lock = Event()
hvac_state = "off"
hvac_action_cache = ""
current_temperature_cache = None

# Learning variables
learning_heating_duration = MINIMUM_ON_TIME * 60

def add_event(message):
    """Add an event to the event log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    events.append(f"[{timestamp}] {message}")
    if len(events) > 5:
        events.pop(0)
    lock.set()

def get_current_temperature():
    """Retrieve the average temperature from multiple sensors, considering only fresh data."""
    client = Client(HOME_ASSISTANT_URL, ACCESS_TOKEN)
    temperature_sensors = [
        BEDROOM_TEMPERATURE_SENSOR,
        MAIN_FLOOR_TEMPERATURE_SENSOR,
        THERMOSTAT_TEMPERATURE_SENSOR
    ]

    fresh_temperatures = []
    for sensor_id in temperature_sensors:
        try:
            sensor = client.get_entity(entity_id=sensor_id)
            state = sensor.get_state()
            if isinstance(state.last_updated, str):
                last_updated = datetime.strptime(state.last_updated, "%Y-%m-%dT%H:%M:%S.%fZ")
            else:
                last_updated = state.last_updated
            if (datetime.utcnow().replace(tzinfo=None) - last_updated.replace(tzinfo=None)).total_seconds() <= 300:  # Within 5 minutes
                fresh_temperatures.append(float(state.state))
            else:
                add_event(f"Sensor {sensor_id} data is stale and ignored.")
        except Exception as e:
            add_event(f"Error fetching temperature from {sensor_id}: {e}")

    if fresh_temperatures:
        average_temp = sum(fresh_temperatures) / len(fresh_temperatures)
        add_event(f"Calculated average temperature from fresh data: {average_temp:.2f}°C.")
        return average_temp
    else:
        add_event("No fresh temperature data available. Unable to calculate average temperature.")
        return None

def get_occupancy_status():
    """Check if the house is occupied based on occupancy sensors."""
    client = Client(HOME_ASSISTANT_URL, ACCESS_TOKEN)
    thermo_occupancy_sensor = client.get_entity(entity_id=THERMOSTAT_OCCUPANCY_SENSOR)
    main_floor_occupancy_sensor = client.get_entity(entity_id=MAIN_FLOOR_OCCUPANCY_SENSOR)
    bed_room_occupancy_sensor = client.get_entity(entity_id=BEDROOM_OCCUPANCY_SENSOR)
    try:
        main_floor_state = main_floor_occupancy_sensor.get_state()
        main_floor_state = main_floor_state.state == "on"
        thermostat_occupancy_state = thermo_occupancy_sensor.get_state()
        thermostat_occupancy_state = thermostat_occupancy_state.state == "on"
        bedroom_occupancy_state = bed_room_occupancy_sensor.get_state()
        bedroom_occupancy_state = bedroom_occupancy_state.state == "on"
        occupancy_status = main_floor_state or thermostat_occupancy_state or bedroom_occupancy_state
        return occupancy_status
    except Exception as e:
        add_event(f"Error checking occupancy status: {e}")
        return False

def adjust_setpoint_based_on_occupancy():
    """Adjust the temperature setpoint based on occupancy, unless overridden."""
    global TEMPERATURE_SETPOINT, OVERRIDE_SETPOINT
    if OVERRIDE_SETPOINT is not None:
        add_event(f"Override setpoint active: {OVERRIDE_SETPOINT}°C. No occupancy adjustment.")
    else:
        if get_occupancy_status():
            TEMPERATURE_SETPOINT = DEFAULT_TEMPERATURE_SETPOINT
            add_event("House occupied. Maintaining current setpoint.")
        else:
            TEMPERATURE_SETPOINT = AWAY_TEMPERATURE_SETPOINT
            add_event("House unoccupied. Using away setpoint.")

def set_hvac_mode(mode):
    """Set the HVAC mode of the thermostat."""
    global hvac_state
    try:
        service.set_hvac_mode(hvac_mode=mode, entity_id=THERMOSTAT_ENTITY_ID)
        service.set_temperature(temperature=MAX_TEMPERATURE_SETPOINT, entity_id=THERMOSTAT_ENTITY_ID)
        hvac_state = mode
        add_event(f"Set HVAC mode to {mode} with setpoint {TEMPERATURE_SETPOINT}°C.")
    except Exception as e:
        add_event(f"Error setting HVAC mode: {e}")

def control_loop():
    global current_temperature_cache, hvac_action_cache, learning_heating_duration

    while not stop_event.is_set():
        adjust_setpoint_based_on_occupancy()
        current_temperature_cache = get_current_temperature()

        if current_temperature_cache is None:
            add_event("Unable to retrieve temperature. Retrying in 1 minute.")
            stop_event.wait(10)
            continue

        if current_temperature_cache < TEMPERATURE_SETPOINT:
            add_event("Temperature below setpoint. Turning on heat.")
            set_hvac_mode("heat")

            initial_temperature = current_temperature_cache
            heating_start_time = time.time()

            # Keep heating for the learned duration
            while time.time() - heating_start_time < learning_heating_duration:
                stop_event.wait(10)
                current_temperature_cache = get_current_temperature()
                if current_temperature_cache is None:
                    add_event("Error reading temperature during heating cycle. Continuing...")
                    continue

                elapsed_time = int(time.time() - heating_start_time)
                add_event(f"Heating active for {elapsed_time} seconds. Current temperature: {current_temperature_cache}°C.")

            # Turn off heat and wait minimum off time
            add_event("Turning off heat after heating session.")
            set_hvac_mode("off")
            stop_event.wait(OFF_TIME * 60)

            # Measure temperature increase and adjust heating duration
            if post_off_temperature is not None:
                temperature_difference = post_off_temperature - TEMPERATURE_SETPOINT
                if temperature_difference > 0:
                    adjustment_factor = max(0.1, min(1.0, temperature_difference / TEMPERATURE_SETPOINT))
                    learning_heating_duration = max(
                        MINIMUM_ON_TIME * 60,
                        learning_heating_duration * (1 - adjustment_factor)
                    )
                    add_event(f"Overshot setpoint. Adjusted heating duration to {learning_heating_duration / 60:.2f} minutes.")
                elif temperature_difference < 0:
                    time_to_heat = time.time() - heating_start_time
                    adjustment_factor = abs(temperature_difference) / TEMPERATURE_SETPOINT
                    learning_heating_duration = min(
                        MAXIMUM_ON_TIME * 60,
                        learning_heating_duration + (adjustment_factor * time_to_heat)
                    )
                    add_event(f"Undershot setpoint. Increased heating duration to {learning_heating_duration / 60:.2f} minutes.")

        else:
            add_event("Temperature is at or above setpoint. No heating needed.")

        lock.set()
        stop_event.wait(10)  # Run the control loop every 10 seconds

def curses_ui(stdscr):
    global TEMPERATURE_SETPOINT, OVERRIDE_SETPOINT

    curses.curs_set(1)
    stdscr.nodelay(True)

    control_thread = Thread(target=control_loop, daemon=True)
    control_thread.start()

    input_buffer = ""
    last_update_time = 0

    while True:
        current_time = time.time()

        if current_time - last_update_time >= 1:  # Refresh UI every second
            stdscr.clear()

            # Display the current status
            stdscr.addstr(0, 0, f"Current Temperature: {current_temperature_cache if current_temperature_cache is not None else 'N/A'}°C")
            stdscr.addstr(1, 0, f"Setpoint Temperature: {TEMPERATURE_SETPOINT}°C")
            stdscr.addstr(2, 0, f"Learned Cycle Time: {learning_heating_duration / 60:.2f} minutes")
            stdscr.addstr(3, 0, f"Occupancy Status: {'Occupied' if get_occupancy_status() else 'Unoccupied'}")
            stdscr.addstr(4, 0, f"State: {hvac_state}")

            # Display the event log
            stdscr.addstr(6, 0, "Event Log:")
            for i, event in enumerate(events[-5:]):
                stdscr.addstr(7 + i, 0, event)

            # Display the input prompt
            stdscr.addstr(13, 0, "Commands:")
            stdscr.addstr(14, 0, "  - 'set <value>': Set a new temperature setpoint (e.g., 'set 22.0').")
            stdscr.addstr(15, 0, "  - 'set': Clear override and use occupancy system.")
            stdscr.addstr(16, 0, "  - 'q': Quit the program.")
            stdscr.addstr(18, 0, "Enter command: ")
            stdscr.addstr(18, 15, input_buffer)
            stdscr.refresh()

            last_update_time = current_time

        try:
            key = stdscr.getch()
            if key != -1:
                if key in (10, 13):  # Enter key
                    command = input_buffer.strip()
                    input_buffer = ""
                    if command == "q":
                        add_event("Exiting thermostat control.")
                        set_hvac_mode("off")
                        stop_event.set()
                        control_thread.join()
                        break
                    elif command.startswith("set"):
                        parts = command.split()
                        if len(parts) == 2:
                            try:
                                OVERRIDE_SETPOINT = float(parts[1])
                                TEMPERATURE_SETPOINT = OVERRIDE_SETPOINT
                                add_event(f"Setpoint override activated: {OVERRIDE_SETPOINT}°C.")
                            except ValueError:
                                add_event("Invalid command. Use 'set <value>' to set a new temperature.")
                        elif len(parts) == 1:
                            OVERRIDE_SETPOINT = None
                            add_event("Setpoint override cleared. Using occupancy system.")
                        else:
                            add_event("Invalid command. Use 'set <value>' or 'set' to manage setpoints.")
                    else:
                        add_event("Invalid command. Please try again.")
                elif key == 127:  # Backspace
                    input_buffer = input_buffer[:-1]
                else:
                    input_buffer += chr(key)
        except Exception:
            pass

        time.sleep(0.05)  # Small sleep to reduce CPU usage


if __name__ == "__main__":
    curses.wrapper(curses_ui)
