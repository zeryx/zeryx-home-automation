import time
import os
from datetime import datetime
from threading import Thread, Event
from homeassistant_api import Client
import curses

# Home Assistant API configuration
HOME_ASSISTANT_URL = "http://192.168.8.249:8123/api"
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
TEMPERATURE_SETPOINT = DEFAULT_TEMPERATURE_SETPOINT  # Initial setpoint
OVERRIDE_SETPOINT = None

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

def add_event(message):
    """Add an event to the event log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    events.append(f"[{timestamp}] {message}")
    if len(events) > 5:
        events.pop(0)
    lock.set()

def get_current_temperature():
    """Retrieve the average temperature from multiple sensors."""
    client = Client(HOME_ASSISTANT_URL, ACCESS_TOKEN)
    bedroom_temperature_sensor = client.get_entity(entity_id=BEDROOM_TEMPERATURE_SENSOR)
    main_floor_temperature_sensor = client.get_entity(entity_id=MAIN_FLOOR_TEMPERATURE_SENSOR)
    thermostat_temperature_sensor = client.get_entity(entity_id=THERMOSTAT_TEMPERATURE_SENSOR)
    try:
        bed_state = bedroom_temperature_sensor.get_state()
        main_floor_state = main_floor_temperature_sensor.get_state()
        thermostat_state = thermostat_temperature_sensor.get_state()
        bedroom_temp = float(bed_state.state)
        main_floor_temp = float(main_floor_state.state)
        thermostat_temp = float(thermostat_state.state)
        average_temp = (bedroom_temp + main_floor_temp + thermostat_temp) / 3
        add_event(f"last updated thermostat: {thermostat_state.last_updated}")
        return average_temp
    except Exception as e:
        add_event(f"Error fetching temperatures: {e}")
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

def get_hvac_action():
  client = Client(HOME_ASSISTANT_URL, ACCESS_TOKEN)
  thermostat_entity = client.get_entity(entity_id=THERMOSTAT_ENTITY_ID)
  thermostat_state = thermostat_entity.get_state()
  hvac_action = thermostat_state.attributes["hvac_action"]
  return hvac_action

def set_hvac_mode(mode):
    """Set the HVAC mode of the thermostat."""
    global hvac_state
    try:
        service.set_hvac_mode(hvac_mode=mode, entity_id=THERMOSTAT_ENTITY_ID)
        service.set_temperature(temperature=TEMPERATURE_SETPOINT, entity_id=THERMOSTAT_ENTITY_ID)
        hvac_state = mode
        add_event(f"Set HVAC mode to {mode} with setpoint {TEMPERATURE_SETPOINT}°C.")
    except Exception as e:
        add_event(f"Error setting HVAC mode: {e}")

def control_loop():
    global current_temperature_cache, hvac_action_cache
    while not stop_event.is_set():
        adjust_setpoint_based_on_occupancy()
        current_temperature_cache = get_current_temperature()
        hvac_action_cache = get_hvac_action()

        if current_temperature_cache is None:
            add_event("Unable to retrieve temperature. Retrying in 1 minute.")
            stop_event.wait(10)
            continue

        if current_temperature_cache < TEMPERATURE_SETPOINT:
            add_event("Temperature below setpoint. Turning on heat.")
            set_hvac_mode("heat")

            # Trap to wait for thermostat to actually trigger as it has a setpoint histeresis
            while hvac_action_cache == "idle":
               hvac_action_cache = get_hvac_action()
               current_temperature_cache = get_current_temperature()
               add_event("Thermostat is still idle after heat started, probably waiting on setpoint to dip.")
               time.sleep(10)
            add_event("Thermostat is heating, exiting idle catch loop.")
             # Monitor temperature for at least 2 minutes
            initial_temperature = get_current_temperature()
            heating_start_time = time.time()
            while time.time() - heating_start_time < 180 or (current_temperature_cache is not None and current_temperature_cache <= initial_temperature):
                stop_event.wait(10)  # Check every 10 seconds
                current_temperature_cache = get_current_temperature()

                if current_temperature_cache is None:
                    add_event("Error reading temperature during heating cycle. Continuing...")
                    continue

                elapsed_time = int(time.time() - heating_start_time)
                add_event(f"Heating active for {elapsed_time} seconds. Current temperature: {current_temperature_cache}°C, Initial temperature: {initial_temperature}°C.")

                if current_temperature_cache > initial_temperature and time.time() - heating_start_time >= 180:
                    add_event("Temperature has increased sufficiently. Turning off heat.")
                    set_hvac_mode("off")
                    break

            # Wait for 3 minutes after heating is turned off
            add_event("Heating session complete. Waiting for 3 minutes before next control cycle.")
            stop_event.wait(180)
        elif current_temperature_cache < TEMPERATURE_SETPOINT:
            add_event("Temperature is at or above setpoint or HVAC not heating. Turning off heat.")
            set_hvac_mode("off")

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
            stdscr.addstr(2, 0, f"Occupancy Status: {'Occupied' if get_occupancy_status() else 'Unoccupied'}")
            stdscr.addstr(3, 0, f"State: {hvac_state}")
            stdscr.addstr(4, 0, f"Hvac Action: {hvac_action_cache}")

            # Display the event log
            stdscr.addstr(5, 0, "Event Log:")
            for i, event in enumerate(events[-5:]):
                stdscr.addstr(6 + i, 0, event)

            # Display the input prompt
            stdscr.addstr(12, 0, "Commands:")
            stdscr.addstr(13, 0, "  - 'set <value>': Set a new temperature setpoint (e.g., 'set 22.0').")
            stdscr.addstr(14, 0, "  - 'set': Clear override and use occupancy system.")
            stdscr.addstr(15, 0, "  - 'q': Quit the program.")
            stdscr.addstr(17, 0, "Enter command: ")
            stdscr.addstr(17, 15, input_buffer)
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
