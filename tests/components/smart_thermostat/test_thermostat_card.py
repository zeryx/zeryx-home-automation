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
        print(f"\nMock climate service called with service: {call.service}")
        print(f"Call data: {call.data}")
        
        entity_id = call.data.get("entity_id")
        print(f"Looking for entity_id: {entity_id}")
        print(f"Available entities in DOMAIN: {list(hass.data[DOMAIN].keys())}")
        print(f"Heat pump entity stored as: {getattr(list(hass.data[DOMAIN].values())[0], '_heat_pump_entity', None)}")
        
        # Extract entity name from entity_id
        if entity_id:
            entity_name = entity_id.split(".")[-1]
            print(f"Looking up entity with name: {entity_name}")
            
            # Try to find the thermostat
            thermostat = None
            if entity_name in hass.data[DOMAIN]:
                thermostat = hass.data[DOMAIN][entity_name]
                print(f"Found thermostat: {thermostat}")
                print(f"Current thermostat state - hvac_mode: {thermostat.hvac_mode}, system_enabled: {thermostat._system_enabled}")
            else:
                print(f"Entity {entity_name} not found in smart_thermostat data")
                # Check if this is a call to the heat pump
                for t in hass.data[DOMAIN].values():
                    if t._heat_pump_entity == entity_id:
                        print(f"Found matching heat pump entity in thermostat: {t.entity_id}")
                        thermostat = t
                        break
            
            if thermostat:
                if call.service == "set_hvac_mode":
                    hvac_mode = call.data["hvac_mode"]
                    print(f"Setting hvac_mode to: {hvac_mode}")
                    await thermostat.async_set_hvac_mode(hvac_mode)
                    print(f"After async_set_hvac_mode - hvac_mode: {thermostat.hvac_mode}, system_enabled: {thermostat._system_enabled}")
                
                elif call.service == "set_temperature":
                    temp = call.data["temperature"]
                    print(f"Setting temperature to: {temp}")
                    await thermostat.async_set_temperature(temperature=temp)
                    print(f"After set_temperature - target_temp: {thermostat.target_temperature}")
                
                elif call.service == "set_fan_mode":
                    fan_mode = call.data["fan_mode"]
                    print(f"Setting fan_mode to: {fan_mode}")
                    if hasattr(thermostat, '_cycle_status'):
                        print(f"Current cycle_status: {thermostat._cycle_status}")
                    print(f"Current active heat source: {getattr(thermostat, '_active_heat_source', None)}")
    
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
    hass.services.async_register("climate", "set_fan_mode", mock_climate_service)
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
    # Simulate the service call from the Mushroom card
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

@pytest.mark.asyncio
async def test_force_furnace_button(mock_hass, mock_thermostat):
    """Test the force furnace button click."""
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
    
    # Set initial state
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    
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
    
    print("\nAfter HEAT service call:")
    print(f"- hvac_mode: {mock_thermostat.hvac_mode}")
    print(f"- system_enabled: {mock_thermostat._system_enabled}")
    print(f"- active_heat_source: {getattr(mock_thermostat, '_active_heat_source', None)}")
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
    
    # For heat pump, cycle_status should indicate fan speed
    cycle_status = mock_thermostat._cycle_status
    assert cycle_status.startswith("fan speed set to "), f"Expected cycle status to start with 'fan speed set to', got {cycle_status}"
    fan_mode = cycle_status.replace("fan speed set to ", "")
    assert fan_mode in ["low", "mid", "high", "auto"], f"Invalid fan mode: {fan_mode}"
    
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
    assert mock_thermostat._cycle_status in ["ready", "heating"]  # Could be either depending on timing 

@pytest.mark.asyncio
async def test_temperature_based_heat_source_switch(mock_hass, mock_thermostat):
    """Test switching between heat sources when outdoor temperature changes."""
    print("\n=== Starting Temperature-Based Heat Source Switch Test ===")
    
    # Set initial state
    mock_thermostat._hvac_mode = HVACMode.OFF
    mock_thermostat._system_enabled = False
    print(f"\nHeat pump entity configured as: {mock_thermostat._heat_pump_entity}")
    print(f"Furnace entity configured as: {mock_thermostat._hvac_entity}")
    
    # Set initial outdoor temperature to favor heat pump
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
    print(f"- last_heat_pump_mode: {getattr(mock_thermostat, '_last_heat_pump_mode', None)}")
    print(f"- last_heat_pump_temp: {getattr(mock_thermostat, '_last_heat_pump_temp', None)}")
    print(f"- last_heat_pump_fan: {getattr(mock_thermostat, '_last_heat_pump_fan', None)}")
    print(f"- last_furnace_mode: {getattr(mock_thermostat, '_last_furnace_mode', None)}")
    print(f"- last_furnace_temp: {getattr(mock_thermostat, '_last_furnace_temp', None)}")
    
    # Verify heat source switched to furnace
    assert mock_thermostat._active_heat_source == "furnace", "Heat source should switch to furnace when temperature drops below 0°C"
    assert mock_thermostat.hvac_mode == HVACMode.HEAT, "HVAC mode should remain HEAT after source switch"
    assert mock_thermostat._system_enabled is True, "System should remain enabled after source switch"
    assert mock_thermostat._last_heat_pump_temp == 17, "Heat pump should be set to minimum temperature"
    
    # Verify heat pump is set to minimum settings
    assert mock_thermostat._last_heat_pump_temp == 17, "Heat pump should be set to minimum temperature"
    assert mock_thermostat._last_heat_pump_fan == "low", "Heat pump fan should be set to low"
    
    # Verify furnace is properly configured
    assert mock_thermostat._last_furnace_mode == "heat", "Furnace should be set to heat mode"
    assert mock_thermostat._last_furnace_temp == mock_thermostat.target_temperature, "Furnace should be set to target temperature" 