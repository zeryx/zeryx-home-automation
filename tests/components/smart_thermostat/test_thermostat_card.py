"""Test the Smart Thermostat Mushroom card interactions."""
from unittest.mock import patch, MagicMock
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.climate.const import HVACMode
from homeassistant.setup import async_setup_component
from homeassistant.helpers import entity_registry as er, storage
from homeassistant.config_entries import ConfigEntries
from custom_components.smart_thermostat.climate import DOMAIN, SmartThermostat
import os
import asyncio
from datetime import datetime, timedelta, timezone

@pytest.fixture
async def mock_hass(hass: HomeAssistant):
    """Create a mock Home Assistant instance."""
    # Set up configuration directory
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    os.makedirs(config_dir, exist_ok=True)
    hass.config.config_dir = config_dir

    # Initialize config entries
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()

    # Mock climate platform setup
    async def mock_setup_platform(*args, **kwargs):
        print("\nMock platform setup called with:", args, kwargs)
        return True

    with patch("homeassistant.components.climate.async_setup", side_effect=mock_setup_platform), \
         patch("homeassistant.components.climate.async_setup_entry", side_effect=mock_setup_platform):
        assert await async_setup_component(hass, "climate", {
            "climate": {}
        })
    
    # Initialize domain data
    hass.data[DOMAIN] = {}
    
    # Register climate services
    async def mock_climate_service(call):
        """Mock climate service calls."""
        print(f"\nService: {call.service}")
        print(f"Data: {call.data}")
        
        entity_id = call.data.get("entity_id")
        print(f"Entity: {entity_id}")
        
        # Try to find the thermostat
        thermostat = None
        if entity_id:
            # First check if this is a direct call to the thermostat
            entity_name = entity_id.split(".")[-1]
            if entity_name in hass.data[DOMAIN]:
                thermostat = hass.data[DOMAIN][entity_name]
            else:
                # Check if this is a call to one of the thermostat's entities
                for t in hass.data[DOMAIN].values():
                    if t._heat_pump_entity == entity_id:
                        print("Found via heat pump entity")
                        thermostat = t
                        break
                    elif t._hvac_entity == entity_id:
                        print("Found via furnace entity")
                        thermostat = t
                        break
            
            if thermostat:
                if call.service == "set_hvac_mode":
                    hvac_mode = call.data["hvac_mode"]
                    print(f"Setting mode to {hvac_mode} for {entity_id}")
                    await thermostat.async_set_hvac_mode(hvac_mode)
                    print(f"Mode set to: {hvac_mode}, system_enabled: {thermostat._system_enabled}, active_source: {thermostat._active_heat_source}")
                if call.service == "turn_on":
                    await thermostat.async_turn_on()
                    print(f"Turned on: {entity_id}, system_enabled: {thermostat._system_enabled}, active_source: {thermostat._active_heat_source}")
                elif call.service == "turn_off":
                    await thermostat.async_turn_off()
                    print(f"Turned off: {entity_id}, system_enabled: {thermostat._system_enabled}, active_source: {thermostat._active_heat_source}")
                
                elif call.service == "set_temperature":
                    temp = call.data["temperature"]
                    await thermostat.async_set_temperature(temperature=temp)
                    print(f"Set temp: {temp}")
            else:
                print(f"No thermostat found for {entity_id}")
    
    # Register force mode service
    async def mock_force_mode_service(call):
        """Mock force mode service."""
        entity_id = call.data.get("entity_id")
        force_mode = call.data.get("force_mode")
        
        if entity_id is None:
            raise ValueError("entity_id must be provided")
            
        # Try to find the thermostat
        thermostat = None
        for t in hass.data[DOMAIN].values():
            if t.entity_id == entity_id:
                thermostat = t
                break
                
        if not thermostat:
            raise ValueError(f"Thermostat {entity_id} not found")
            
        await thermostat.async_force_heat_source(force_mode)
    
    hass.services.async_register("climate", "set_hvac_mode", mock_climate_service)
    hass.services.async_register("climate", "set_temperature", mock_climate_service)
    hass.services.async_register(DOMAIN, "force_mode", mock_force_mode_service)
    
    await hass.async_block_till_done()
    return hass

@pytest.fixture
async def entity_registry(mock_hass):
    """Create a mock entity registry."""
    registry = er.EntityRegistry(mock_hass)
    
    # Create initial registry data structure with all required fields
    registry_data = {
        "entities": [],
        "deleted_entities": [],
        "aliases": {},
        "orphaned_timestamps": {},
    }
    
    with patch.object(er, 'async_get', return_value=registry), \
         patch.object(storage.Store, 'async_save'), \
         patch.object(storage.Store, 'async_load', return_value=registry_data):
        await registry.async_load()
        mock_hass.data["entity_registry"] = registry
        yield registry

@pytest.fixture
async def mock_thermostat(mock_hass, entity_registry):
    """Create a mock thermostat instance."""
    config = {
        "name": "Smart Furnace",
        "temperature_sensors": [
            "sensor.bedroom_temperature",
            "sensor.office_temperature",
            "sensor.thermostat_current_temperature",
            "sensor.hvac_controller_temperature"
        ],
        "hvac_entity": "climate.mock_furnace_mock_furnace",
        "heat_pump_entity": "climate.mock_heat_pump_mock_heat_pump",
        "target_temp": 21.5,
        "min_temp": 19.0,
        "max_temp": 22.5,
        "tolerance": 0.5,
        "minimum_on_time": 5,
        "maximum_on_time": 15,
        "off_time": 5,
        "heat_pump_min_temp": 0,
        "heat_pump_max_temp": 30
    }
    
    # Create mock entities for HVAC and heat pump
    mock_hvac = MagicMock()
    mock_hvac.entity_id = config["hvac_entity"]
    mock_hvac.state = "off"
    mock_hass.states.async_set(config["hvac_entity"], "off")
    
    mock_heat_pump = MagicMock()
    mock_heat_pump.entity_id = config["heat_pump_entity"]
    mock_heat_pump.state = "off"
    mock_hass.states.async_set(config["heat_pump_entity"], "off")
    
    # Create thermostat instance
    thermostat = SmartThermostat(
        mock_hass,
        config["name"],
        config["temperature_sensors"],
        config["hvac_entity"],
        config["heat_pump_entity"],
        config["min_temp"],
        config["max_temp"],
        config["target_temp"],
        config["tolerance"],
        config["minimum_on_time"] * 60,
        config["maximum_on_time"] * 60,
        config["off_time"] * 60,
        config["heat_pump_min_temp"],
        config["heat_pump_max_temp"],
        "weather.forecast_home"
    )
    
    # Register the thermostat entity
    entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        "smart_furnace",
        suggested_object_id="smart_furnace",
        config_entry=None,
    )
    
    # Add to Home Assistant
    mock_hass.data[DOMAIN]["smart_furnace"] = thermostat
    thermostat.hass = mock_hass
    thermostat.entity_id = "climate.smart_furnace"
    
    # Register the force_mode service
    async def async_force_mode(call):
        await thermostat.async_force_heat_source(call.data.get("force_mode"))
    
    mock_hass.services.async_register(DOMAIN, "force_mode", async_force_mode)
    
    # Create mock states for temperature sensors
    for sensor in config["temperature_sensors"]:
        mock_hass.states.async_set(sensor, "20.0", {"unit_of_measurement": "°C"})
    
    # Create mock weather entity
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": 1.7, "temperature_unit": "°C"}
    )
    
    await mock_hass.async_block_till_done()
    return thermostat

@pytest.fixture(autouse=True)
async def reset_thermostat(mock_hass, mock_thermostat):
    """Reset thermostat state before each test."""
    # Reset basic system states
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._force_mode = None
    mock_thermostat._heating_start_time = None
    mock_thermostat._cooling_start_time = None
    mock_thermostat._cycle_status = "waiting to activate"
    
    # Reset timing parameters to default test values
    mock_thermostat._learning_heating_duration = 0.1  # 100ms
    mock_thermostat._minimum_heating_duration = 0.1
    mock_thermostat._maximum_heating_duration = 0.2
    mock_thermostat._off_time = 0.1
    
    # Reset last states for heat sources
    mock_thermostat._heat_pump_last_mode = None
    mock_thermostat._heat_pump_last_temp = None
    mock_thermostat._heat_pump_last_fan = None
    mock_thermostat._furnace_last_mode = None
    mock_thermostat._furnace_last_temp = None
    
    # Reset mock states for HVAC entities
    mock_hass.states.async_set(mock_thermostat._hvac_entity, "off")
    mock_hass.states.async_set(mock_thermostat._heat_pump_entity, "off")
    
    # Reset temperature sensors to default value
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "20.0", {"unit_of_measurement": "°C"})
    
    # Reset weather to default value
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": 1.7, "temperature_unit": "°C"}
    )
    
    await mock_hass.async_block_till_done()

@pytest.mark.asyncio
async def test_force_heat_pump_button(mock_hass, mock_thermostat):
    """Test the force heat pump button click."""
    # First enable the system
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    # Now force the heat pump
    await mock_hass.services.async_call(
        DOMAIN,
        "force_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "force_mode": "heat_pump"
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    assert mock_thermostat._force_mode == "heat_pump"
    assert mock_thermostat._active_heat_source == "heat_pump"
    assert mock_thermostat._system_enabled is True

@pytest.mark.asyncio
async def test_force_furnace_button(mock_hass, mock_thermostat):
    """Test the force furnace button click."""
    # First enable the system
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    # Now force the furnace
    await mock_hass.services.async_call(
        DOMAIN,
        "force_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "force_mode": "furnace"
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    assert mock_thermostat._force_mode == "furnace"
    assert mock_thermostat._active_heat_source == "furnace"
    assert mock_thermostat._system_enabled is True

@pytest.mark.asyncio
async def test_auto_mode_button(mock_hass, mock_thermostat):
    """Test the auto mode button click."""
    # First set a force mode
    await mock_hass.services.async_call(
        DOMAIN,
        "force_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "force_mode": "furnace"
        },
        blocking=True
    )
    
    await mock_hass.async_block_till_done()
    
    # Then clear it with auto mode
    await mock_hass.services.async_call(
        DOMAIN,
        "force_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "force_mode": None
        },
        blocking=True
    )
    
    await mock_hass.async_block_till_done()
    assert mock_thermostat._force_mode is None

@pytest.mark.asyncio
async def test_hvac_mode_toggle(mock_hass, mock_thermostat):
    """Test HVAC mode toggle button."""
    print("\n=== Starting HVAC Mode Toggle Test ===")
    
    # Set initial state
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    print(f"\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- entity_id: {mock_thermostat.entity_id}")
    print(f"- name: {mock_thermostat.name}")
    print(f"- available in hass.data[DOMAIN]: {mock_thermostat.name in mock_hass.data[DOMAIN]}")
    
    # Turn system on
    print("\nTurning system ON...")
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn ON:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- force_mode: {getattr(mock_thermostat, '_force_mode', None)}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    
    # Verify state after turning on
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, f"Expected HEAT but got {mock_thermostat.hvac_mode}"
    assert mock_thermostat._system_enabled is True
    
    # Turn system off
    print("\nTurning system OFF...")
    await mock_thermostat.async_turn_off()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn OFF:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- force_mode: {getattr(mock_thermostat, '_force_mode', None)}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    
    # Verify state after turning off
    assert mock_thermostat.hvac_mode == HVACMode.OFF
    assert mock_thermostat._system_enabled is False

@pytest.mark.asyncio
async def test_turn_on_heat_pump_weather(mock_hass, mock_thermostat):
    """Test turning on the thermostat when outdoor temperature favors heat pump (above 0°C)."""
    print("\n=== Starting Turn On Heat Pump Weather Test ===")
    
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._off_time = 0  # Set to 0 to force immediate fan check
    
    # Set temperature to ensure heating is needed
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "19.0", {"unit_of_measurement": "°C"})
    
    # Set outdoor temperature to favor heat pump
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": 5.0, "temperature_unit": "°C"}
    )
    await mock_hass.async_block_till_done()
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- outdoor temp: {mock_hass.states.get('weather.forecast_home').attributes['temperature']}°C")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- current_temperature: {mock_thermostat.current_temperature}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Turn system on
    print("\nTurning system ON...")
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    # Force a control cycle to trigger fan mode check
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn ON and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- current_temperature: {mock_thermostat.current_temperature}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- heating_start_time: {mock_thermostat._heating_start_time}")
    print(f"- cooling_start_time: {mock_thermostat._cooling_start_time}")
    
    # Verify state after turning on
    assert mock_thermostat.hvac_mode == HVACMode.HEAT
    assert mock_thermostat._system_enabled is True
    assert mock_thermostat._active_heat_source == "heat_pump"
    
    # For heat pump, cycle_status should indicate fan speed or heating
    cycle_status = mock_thermostat._cycle_status
    assert cycle_status == "heatpump active"
    
    # Verify temperature control is active
    if mock_thermostat.current_temperature < mock_thermostat.target_temperature - mock_thermostat._tolerance:
        assert mock_thermostat._is_heating is True, "Should be heating when below target temperature"

@pytest.mark.asyncio
async def test_turn_on_furnace_weather(mock_hass, mock_thermostat):
    """Test turning on the thermostat when outdoor temperature requires furnace (below 0°C)."""
    print("\n=== Starting Turn On Furnace Weather Test ===")
    current_time = datetime.now(timezone.utc)  # Use UTC timezone
    # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 5  # 5 seconds
    mock_thermostat._minimum_heating_duration = 5
    mock_thermostat._maximum_heating_duration = 15
    mock_thermostat._off_time = 20

    # Set initial state
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "19.0",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time,  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )
    
    # Set outdoor temperature to require furnace
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": -2.0,
            "temperature_unit": "°C",
            "last_updated": current_time,  # Pass datetime object directly
            "friendly_name": "Weather"
        }
    )
    await mock_hass.async_block_till_done()
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- outdoor temp: {mock_hass.states.get('weather.forecast_home').attributes['temperature']}°C")
    
    # Turn system on using service call
    print("\nCalling set_hvac_mode service with HEAT...")
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    print("\nAfter HEAT service call:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    
    # Verify state after turning on
    assert mock_thermostat.hvac_mode == HVACMode.HEAT
    assert mock_thermostat._system_enabled is True
    assert mock_thermostat._active_heat_source == "furnace"
    assert mock_thermostat._cycle_status.startswith("heating cycle:") and mock_thermostat._cycle_status.endswith("remaining"), f"Cycle status should be 'heating cycle: Xm remaining', got {mock_thermostat._cycle_status}"

@pytest.mark.asyncio
async def test_furnace_heating_cycle(mock_hass, mock_thermostat):
    """Test the complete furnace heating cycle including learning duration adjustments."""
    print("\n=== Starting Furnace Heating Cycle Test ===")
    
    # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 5  # 5 seconds
    mock_thermostat._minimum_heating_duration = 5
    mock_thermostat._maximum_heating_duration = 15
    mock_thermostat._off_time = 20
    
    # Set initial temperatures with proper timezone handling
    print("\nSetting initial temperatures...")
    current_time = datetime.now(timezone.utc)  # Use UTC timezone
    
    # Set temperature sensors
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "19.0",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time,  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )
    
    # Set outdoor temperature to require furnace
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": -2.0,
            "temperature_unit": "°C",
            "last_updated": current_time,  # Pass datetime object directly
            "friendly_name": "Weather"
        }
    )
    await mock_hass.async_block_till_done()
    
    # Mock datetime for the entire test
    with patch('custom_components.smart_thermostat.climate.datetime') as mock_datetime, \
         patch('homeassistant.util.dt.now') as mock_dt_now:  # Mock HA's dt.now instead
        
        # Configure datetime mocks to return timezone-aware datetime
        mock_datetime.now.return_value = current_time
        mock_dt_now.return_value = current_time
        
        print("\nInitial state:")
        print(f"- current_temperature: {mock_thermostat.current_temperature}")
        print(f"- target_temperature: {mock_thermostat.target_temperature}")
        print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
        print(f"- system_enabled: {mock_thermostat._system_enabled}")
        
        # Turn system on
        await mock_thermostat.async_turn_on()
        await mock_hass.async_block_till_done()
        
        # Force initial control cycle
        await mock_thermostat._control_heating()
        await mock_hass.async_block_till_done()
        
        print("\nAfter turn on:")
        print(f"- is_heating: {mock_thermostat._is_heating}")
        print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
        print(f"- cycle_status: {mock_thermostat._cycle_status}")
        print(f"- current_temperature: {mock_thermostat.current_temperature}")
        print(f"- sensor_temperatures: {mock_thermostat._sensor_temperatures}")
        
        # Verify initial heating state
        assert mock_thermostat._is_heating is True, "System should start heating"
        assert mock_thermostat._active_heat_source == "furnace"
        assert mock_thermostat._cycle_status.startswith("heating cycle:")
        
        # Advance time past heating duration
        new_time = current_time + timedelta(seconds=6)  # Past the 5s heating duration
        mock_datetime.now.return_value = new_time
        mock_dt_now.return_value = new_time
        
        # Run control cycle to process the completed heating duration
        await mock_thermostat._control_heating()
        await mock_hass.async_block_till_done()
        
        print("\nAfter heating cycle completion:")
        print(f"- is_heating: {mock_thermostat._is_heating}")
        print(f"- cycle_status: {mock_thermostat._cycle_status}")
        print(f"- cooling_start_time: {mock_thermostat._cooling_start_time}")
        
        # Verify heating cycle completed and cooling started
        assert mock_thermostat._is_heating is False, "Heating should be stopped"
        assert mock_thermostat._cycle_status.startswith("cooling cycle:"), \
            f"Cycle status should start with 'cooling cycle:', got {mock_thermostat._cycle_status}"
        assert mock_thermostat._cooling_start_time is not None, "Cooling start time should be set"

@pytest.mark.asyncio
async def test_turn_on_off_widget(mock_hass, mock_thermostat):
    """Test the turn on/off widget functionality."""
    print("\n=== Starting Turn On/Off Widget Test ===")
    
    # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 5  # 5 seconds
    mock_thermostat._minimum_heating_duration = 5
    mock_thermostat._maximum_heating_duration = 15
    mock_thermostat._off_time = 20
    
    current_time = datetime.now(timezone.utc)  # Use UTC timezone

    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "19.0",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time,  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )
    
    # Set outdoor temperature to require furnace
    print("\nSetting outdoor temperature to -2.0°C (furnace required)...")
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": -2.0,
            "temperature_unit": "°C",
            "last_updated": current_time,  # Pass datetime object directly
            "friendly_name": "Weather"
        }
    )
        # Mock datetime for the entire test
    with patch('custom_components.smart_thermostat.climate.datetime') as mock_datetime, \
         patch('homeassistant.util.dt.now') as mock_dt_now:  # Mock HA's dt.now instead
        
        # Configure datetime mocks to return timezone-aware datetime
        mock_datetime.now.return_value = current_time
        mock_dt_now.return_value = current_time

    await mock_hass.async_block_till_done()
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    
    # Turn system on using service call
    print("\nTurning system ON...")
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn ON and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    
    # Verify system is on and heating
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, "HVAC mode should be HEAT"
    assert mock_thermostat._system_enabled is True, "System should be enabled"
    assert mock_thermostat._is_heating is True, "System should be heating"
    assert mock_thermostat._active_heat_source in ["heat_pump", "furnace"], "An active heat source should be selected"
    assert mock_thermostat._cycle_status.startswith("heating cycle:"), "Cycle status should be heating cycle"
    

    new_time = current_time + timedelta(seconds=6)  # Past the 5s heating duration
    mock_datetime.now.return_value = new_time
    mock_dt_now.return_value = new_time

    # Turn system off
    print("\nTurning system OFF...")
    await mock_thermostat.async_turn_off()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn OFF:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    
    # Verify system is fully off
    assert mock_thermostat.hvac_mode == HVACMode.OFF, "HVAC mode should be OFF"
    assert mock_thermostat._system_enabled is False, "System should be disabled"
    assert mock_thermostat._is_heating is False, "System should not be heating"
    assert mock_thermostat._active_heat_source is None, "No heat source should be active"
    assert mock_thermostat._cycle_status == "off", "Cycle status should be off"
    
    # Wait a bit to ensure no further HVAC interactions
    await asyncio.sleep(0.1)  # Change to 100ms
    
    # Verify system remains off and inactive
    assert mock_thermostat.hvac_mode == HVACMode.OFF, "HVAC mode should remain OFF"
    assert mock_thermostat._system_enabled is False, "System should remain disabled"
    assert mock_thermostat._is_heating is False, "System should remain not heating"
    assert mock_thermostat._active_heat_source is None, "No heat source should remain active"
    assert mock_thermostat._cycle_status == "off", "Cycle status should remain off"

@pytest.mark.asyncio
async def test_temperature_based_heat_source_switch(mock_hass, mock_thermostat):
    """Test switching between heat sources when outdoor temperature changes."""
    print("\n=== Starting Temperature-Based Heat Source Switch Test ===")


    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 5  # 5 seconds
    mock_thermostat._minimum_heating_duration = 5
    mock_thermostat._maximum_heating_duration = 15
    mock_thermostat._off_time = 20
    
    
    current_time = datetime.now(timezone.utc)  # Use UTC timezone

            # Mock datetime for the entire test
    with patch('custom_components.smart_thermostat.climate.datetime') as mock_datetime, \
         patch('homeassistant.util.dt.now') as mock_dt_now:  # Mock HA's dt.now instead
        
        # Configure datetime mocks to return timezone-aware datetime
        mock_datetime.now.return_value = current_time
        mock_dt_now.return_value = current_time
    
    
    print("\nSetting temperature sensors below setpoint (19.0°C)...")
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "19.0",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time,  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )
    
    # Set outdoor temperature to require heat pump
    print("\nSetting outdoor temperature to 2.0°C (heat pump required)...")
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": 2.0,
            "temperature_unit": "°C",
            "last_updated": current_time,  # Pass datetime object directly
            "friendly_name": "Weather"
        }
    )
    await mock_hass.async_block_till_done()
    
    # Turn system on using service call
    await mock_thermostat.async_turn_on()
    
    # Force a control cycle to ensure heat pump is active
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter HEAT service call:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Verify initial state with heat pump
    assert mock_thermostat.hvac_mode == HVACMode.HEAT
    assert mock_thermostat._system_enabled is True
    assert mock_thermostat._active_heat_source == "heat_pump"
    assert mock_thermostat._cycle_status == "heatpump active"
    # Change outdoor temperature to require furnace
    print("\nChanging outdoor temperature to -1.0°C...")
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": -1.0, "temperature_unit": "°C"}
    )

    new_time = current_time + timedelta(seconds=6)  # Past the 5s heating duration
    mock_datetime.now.return_value = new_time
    mock_dt_now.return_value = new_time

    await mock_hass.async_block_till_done()
    
    # Force a control cycle to handle the temperature change
    print("\nBefore control heating:")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Force switch to furnace
    await mock_thermostat._check_outdoor_temperature()

    new_time = new_time + timedelta(seconds=20)  # Past the 5s heating duration
    mock_datetime.now.return_value = new_time
    mock_dt_now.return_value = new_time
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter temperature change and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- outdoor temp: {mock_hass.states.get('weather.forecast_home').attributes['temperature']}°C")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Verify heat source switched to furnace
    assert mock_thermostat._active_heat_source == "furnace", "Heat source should switch to furnace when temperature drops below 0°C"
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, "HVAC mode should remain HEAT after source switch"
    assert mock_thermostat._system_enabled is True, "System should remain enabled after source switch"
    assert mock_thermostat._cycle_status.startswith("heating cycle:"), "Cycle status should be heating cycle"
    
    # Verify furnace is properly configured
    assert mock_thermostat._furnace_last_mode == "heat", "Furnace should be set to heat mode"
    assert mock_thermostat._furnace_last_temp == mock_thermostat._max_temp, "Furnace should be set to max temperature"

@pytest.mark.asyncio
async def test_turn_on_above_setpoint(mock_hass, mock_thermostat):
    """Test turning on when temperature is above setpoint."""
    print("\n=== Starting Turn On Above Setpoint Test ===")

        # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 5  # 5 seconds
    mock_thermostat._minimum_heating_duration = 5
    mock_thermostat._maximum_heating_duration = 15
    mock_thermostat._off_time = 20
    
    
    current_time = datetime.now(timezone.utc)  # Use UTC timezone

            # Mock datetime for the entire test
    with patch('custom_components.smart_thermostat.climate.datetime') as mock_datetime, \
         patch('homeassistant.util.dt.now') as mock_dt_now:  # Mock HA's dt.now instead
        
        # Configure datetime mocks to return timezone-aware datetime
        mock_datetime.now.return_value = current_time
        mock_dt_now.return_value = current_time
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Set temperature sensors above setpoint
    print("\nSetting temperature sensors above setpoint (23.0°C)...")
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "23.0",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time,  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )
    
    # Set outdoor temperature to require furnace
    print("\nSetting outdoor temperature to -2.0°C (furnace required)...")
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": -2.0,
            "temperature_unit": "°C",
            "last_updated": current_time,  # Pass datetime object directly
            "friendly_name": "Weather"
        }
    )
    
    print("\nTurning system ON...")
    await mock_thermostat.async_turn_on()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn ON with temperature above setpoint:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- current_temperature: {mock_thermostat.current_temperature}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    assert mock_thermostat.hvac_mode == HVACMode.HEAT
    assert mock_thermostat._system_enabled is True
    assert mock_thermostat._is_heating is False
    assert mock_thermostat._cycle_status == "waiting to activate"
    
    # Now lower temperature and verify heating starts
    print("\nLowering temperature to 19.0°C (below setpoint)...")
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(
            sensor, 
            "19",
            {
                "unit_of_measurement": "°C",
                "last_updated": current_time+timedelta(seconds=1),  # Pass datetime object directly
                "friendly_name": f"Temperature Sensor {sensor}"
            }
        )

    new_time = current_time + timedelta(seconds=6)  # Past the 5s heating duration
    mock_datetime.now.return_value = new_time
    mock_dt_now.return_value = new_time

    await mock_hass.async_block_till_done()
    
    # Force a control cycle to ensure heating starts
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter temperature drop and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- current_temperature: {mock_thermostat.current_temperature}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    print(f"- heating_start_time: {mock_thermostat._heating_start_time}")
    print(f"- learning_duration: {mock_thermostat._learning_heating_duration/60:.1f}min")
    
    assert mock_thermostat._is_heating is True
    assert mock_thermostat._cycle_status.startswith("heating cycle:")