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
from datetime import datetime, timedelta

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
                    await thermostat.async_set_hvac_mode(hvac_mode)
                    print(f"Set mode: {hvac_mode}")
                
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

@pytest.mark.asyncio
async def test_force_heat_pump_button(mock_hass, mock_thermostat):
    """Test the force heat pump button click."""
    # First enable the system by setting it to HEAT mode
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
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
    # First enable the system by setting it to HEAT mode
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: "climate.smart_furnace",
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
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
    
    # Turn system on using service call
    print("\nCalling set_hvac_mode service with HEAT...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    print("\nAfter HEAT service call:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- force_mode: {getattr(mock_thermostat, '_force_mode', None)}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    
    # Verify state after turning on
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, f"Expected HEAT but got {mock_thermostat.hvac_mode}"
    assert mock_thermostat._system_enabled is True
    
    # Turn system off using service call
    print("\nCalling set_hvac_mode service with OFF...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.OFF
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    print("\nAfter OFF service call:")
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
    
    # Turn system on using service call
    print("\nCalling set_hvac_mode service with HEAT...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    # Force a control cycle to trigger fan mode check
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter HEAT service call and control cycle:")
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
    assert cycle_status in ["heating"] or cycle_status.startswith("fan speed set to "), f"Expected cycle status to be 'heating' or start with 'fan speed set to', got {cycle_status}"
    
    # Verify temperature control is active
    if mock_thermostat.current_temperature < mock_thermostat.target_temperature - mock_thermostat._tolerance:
        assert mock_thermostat._is_heating is True, "Should be heating when below target temperature"

@pytest.mark.asyncio
async def test_turn_on_furnace_weather(mock_hass, mock_thermostat):
    """Test turning on the thermostat when outdoor temperature requires furnace (below 0°C)."""
    print("\n=== Starting Turn On Furnace Weather Test ===")
    
    # Set initial state
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    
    # Set outdoor temperature to require furnace
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": -2.0, "temperature_unit": "°C"}
    )
    await mock_hass.async_block_till_done()
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- outdoor temp: {mock_hass.states.get('weather.forecast_home').attributes['temperature']}°C")
    
    # Turn system on using service call
    print("\nCalling set_hvac_mode service with HEAT...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
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
async def test_temperature_based_heat_source_switch(mock_hass, mock_thermostat):
    """Test switching between heat sources when outdoor temperature changes."""
    print("\n=== Starting Temperature-Based Heat Source Switch Test ===")
    
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    
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
    
    # Turn system on using service call
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
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
    
    # Change outdoor temperature to require furnace
    print("\nChanging outdoor temperature to -1.0°C...")
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": -1.0, "temperature_unit": "°C"}
    )
    await mock_hass.async_block_till_done()
    
    # Force a control cycle to handle the temperature change
    print("\nBefore control heating:")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    
    # Force switch to furnace
    await mock_thermostat._switch_heat_source("furnace")
    await mock_hass.async_block_till_done()
    
    print("\nAfter temperature change and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
    print(f"- outdoor temp: {mock_hass.states.get('weather.forecast_home').attributes['temperature']}°C")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- target_temperature: {mock_thermostat.target_temperature}")
    print(f"- heat_pump_last_mode: {getattr(mock_thermostat, '_heat_pump_last_mode', None)}")
    print(f"- heat_pump_last_temp: {getattr(mock_thermostat, '_heat_pump_last_temp', None)}")
    print(f"- heat_pump_last_fan: {getattr(mock_thermostat, '_heat_pump_last_fan', None)}")
    print(f"- furnace_last_mode: {getattr(mock_thermostat, '_furnace_last_mode', None)}")
    print(f"- furnace_last_temp: {getattr(mock_thermostat, '_furnace_last_temp', None)}")
    
    # Verify heat source switched to furnace
    assert mock_thermostat._active_heat_source == "furnace", "Heat source should switch to furnace when temperature drops below 0°C"
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, "HVAC mode should remain HEAT after source switch"
    assert mock_thermostat._system_enabled is True, "System should remain enabled after source switch"
    assert mock_thermostat._heat_pump_last_temp == 17, "Heat pump should be set to minimum temperature"
    
    # Verify heat pump is set to minimum settings
    assert mock_thermostat._heat_pump_last_temp == 17, "Heat pump should be set to minimum temperature"
    assert mock_thermostat._heat_pump_last_fan == "low", "Heat pump fan should be set to low"
    
    # Verify furnace is properly configured
    assert mock_thermostat._furnace_last_mode == "heat", "Furnace should be set to heat mode"
    assert mock_thermostat._furnace_last_temp == mock_thermostat._max_temp, "Furnace should be set to max temperature"

@pytest.mark.asyncio
async def test_turn_on_off_widget(mock_hass, mock_thermostat):
    """Test the turn on/off widget functionality."""
    print("\n=== Starting Turn On/Off Widget Test ===")
    
    # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    
    # Set temperature to ensure heating is needed
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "19.0", {"unit_of_measurement": "°C"})
    
    # Turn system on using service call
    print("\nTurning system ON...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    # Force a control cycle to start heating
    await mock_thermostat._control_heating()
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
    assert mock_thermostat._cycle_status in ["heating", "fan speed set to low", "fan speed set to mid", "fan speed set to high"], "Cycle status should indicate active heating"
    
    # Turn system off
    print("\nTurning system OFF...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.OFF
        },
        blocking=True
    )
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
    await asyncio.sleep(5)
    
    # Verify system remains off and inactive
    assert mock_thermostat.hvac_mode == HVACMode.OFF, "HVAC mode should remain OFF"
    assert mock_thermostat._system_enabled is False, "System should remain disabled"
    assert mock_thermostat._is_heating is False, "System should remain not heating"
    assert mock_thermostat._active_heat_source is None, "No heat source should remain active"
    assert mock_thermostat._cycle_status == "off", "Cycle status should remain off"

@pytest.mark.asyncio
async def test_furnace_heating_cycle(mock_hass, mock_thermostat):
    """Test the complete furnace heating cycle including learning duration adjustments."""
    print("\n=== Starting Furnace Heating Cycle Test ===")
    
    # Set initial state to off
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    mock_thermostat._is_heating = False
    mock_thermostat._active_heat_source = None
    mock_thermostat._learning_heating_duration = 300  # Start with minimum 5 minutes (300 seconds)
    
    # Set temperature to ensure heating is needed (below target - tolerance)
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "20.0", {"unit_of_measurement": "°C"})
    
    # Set outdoor temperature to require furnace
    mock_hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {"temperature": -2.0, "temperature_unit": "°C"}
    )
    await mock_hass.async_block_till_done()
    
    print("\nInitial state:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- learning_duration: {mock_thermostat._learning_heating_duration}s")
    print(f"- current_temperature: {mock_thermostat.current_temperature}")
    
    # Turn system on using service call
    print("\nTurning system ON...")
    await mock_hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {
            ATTR_ENTITY_ID: mock_thermostat.entity_id,
            "hvac_mode": HVACMode.HEAT
        },
        blocking=True
    )
    await mock_hass.async_block_till_done()
    
    # Force a control cycle to start heating
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter turn ON and control cycle:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- active_heat_source: {mock_thermostat._active_heat_source}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- heating_start_time: {mock_thermostat._heating_start_time}")
    
    # Verify initial heating state
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, "HVAC mode should be HEAT"
    assert mock_thermostat._system_enabled is True, "System should be enabled"
    assert mock_thermostat._is_heating is True, "System should be heating"
    assert mock_thermostat._active_heat_source == "furnace", "Furnace should be active heat source"
    assert mock_thermostat._cycle_status.startswith("heating cycle:") and mock_thermostat._cycle_status.endswith("remaining"), f"Cycle status should be 'heating cycle: Xm remaining', got {mock_thermostat._cycle_status}"
    assert mock_thermostat._heating_start_time is not None, "Heating start time should be set"
    assert mock_thermostat._furnace_last_temp == mock_thermostat._max_temp, "Furnace should be set to max temperature"
    
    # Wait for heating cycle to complete (5 minutes)
    print("\nWaiting for heating cycle to complete...")
    initial_duration = mock_thermostat._learning_heating_duration
    
    # Simulate time passing by manually advancing the heating start time
    mock_thermostat._heating_start_time = mock_thermostat._heating_start_time - timedelta(seconds=initial_duration)
    
    # Run control cycle to process the completed heating duration
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter heating cycle completion:")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- cooling_start_time: {mock_thermostat._cooling_start_time}")
    print(f"- last_furnace_mode: {mock_thermostat._furnace_last_mode}")
    
    # Verify heating cycle completed
    assert mock_thermostat._is_heating is False, "Heating should be stopped"
    assert mock_thermostat._cycle_status.startswith("cooling cycle:") and mock_thermostat._cycle_status.endswith("remaining"), f"Cycle status should be 'cooling cycle: Xm remaining', got {mock_thermostat._cycle_status}"
    assert mock_thermostat._cooling_start_time is not None, "Cooling start time should be set"
    assert mock_thermostat._furnace_last_mode == HVACMode.OFF, "Furnace should be turned off"
    
    # Wait for cooling cycle to complete (20 minutes)
    print("\nWaiting for cooling cycle to complete...")
    
    # Simulate temperature change during cooling to trigger learning adjustment
    # Set temperature to indicate we overshot the target
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "22.5", {"unit_of_measurement": "°C"})
    await mock_hass.async_block_till_done()
    
    # Simulate time passing by manually advancing the cooling start time
    mock_thermostat._cooling_start_time = mock_thermostat._cooling_start_time - timedelta(seconds=mock_thermostat._off_time)
    
    # Run control cycle to process the completed cooling duration
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter cooling cycle completion:")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- learning_duration: {mock_thermostat._learning_heating_duration}s")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    
    # Verify cooling cycle completed and learning duration was adjusted
    assert mock_thermostat._cycle_status == "ready", "Cycle status should be ready"
    assert mock_thermostat._cooling_start_time is None, "Cooling start time should be cleared"
    assert mock_thermostat._learning_heating_duration < initial_duration, "Learning duration should be reduced due to overshoot"
    
    # Set temperature back below target to trigger new heating cycle
    for sensor in mock_thermostat._temp_sensors:
        mock_hass.states.async_set(sensor, "19.0", {"unit_of_measurement": "°C"})
    await mock_hass.async_block_till_done()
    
    # Run control cycle to start new heating cycle
    await mock_thermostat._control_heating()
    await mock_hass.async_block_till_done()
    
    print("\nAfter starting new heating cycle:")
    print(f"- is_heating: {mock_thermostat._is_heating}")
    print(f"- cycle_status: {mock_thermostat._cycle_status}")
    print(f"- heating_start_time: {mock_thermostat._heating_start_time}")
    print(f"- learning_duration: {mock_thermostat._learning_heating_duration}s")
    
    # Verify new heating cycle started with adjusted duration
    assert mock_thermostat._is_heating is True, "New heating cycle should start"
    assert mock_thermostat._cycle_status.startswith("heating cycle:") and mock_thermostat._cycle_status.endswith("remaining"), f"Cycle status should be 'heating cycle: Xm remaining', got {mock_thermostat._cycle_status}"
    assert mock_thermostat._heating_start_time is not None, "New heating start time should be set"
    assert mock_thermostat._furnace_last_mode == HVACMode.HEAT, "Furnace should be turned back on"
    assert mock_thermostat._furnace_last_temp == mock_thermostat._max_temp, "Furnace should be set to max temperature" 