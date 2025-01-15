from datetime import datetime, timedelta
import pytest
from unittest.mock import Mock, patch
import random
import math

from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.components.climate import HVACMode
from custom_components.smart_thermostat.climate import SmartThermostat

class ThermalModel:
    """Simulates thermal behavior of a house."""
    
    def __init__(self, initial_temp=20.0):
        self.temperature = initial_temp
        self.outdoor_temp = 20.0
        self.heater_on = False
        self.thermal_mass = 2000  # kJ/°C (typical for a medium-sized room)
        self.heat_loss_coefficient = 100  # W/°C
        self.heater_power = 2000  # W
        
    def update(self, minutes):
        """Update temperature based on heating/cooling over time."""
        hours = minutes / 60
        
        # Calculate heat transfer
        heat_loss = self.heat_loss_coefficient * (self.temperature - self.outdoor_temp)
        heat_gain = self.heater_power if self.heater_on else 0
        
        # Net temperature change (°C)
        delta_t = ((heat_gain - heat_loss) * hours * 3600) / (self.thermal_mass * 1000)
        self.temperature += delta_t

    def set_season(self, month):
        """Simulate seasonal outdoor temperatures."""
        # Simple sinusoidal model for outdoor temperature
        self.outdoor_temp = 15 + 15 * math.sin((month - 3) * math.pi / 6)

class MockSensor:
    """Simulates a temperature sensor with realistic behavior."""
    
    def __init__(self, thermal_model, update_interval=10):
        self.thermal_model = thermal_model
        self.last_update = datetime.now()
        self.last_reading = thermal_model.temperature
        self.update_interval = update_interval
        self.failure_rate = 0.05  # 5% chance of reading failure
        
    def get_reading(self, current_time):
        """Get sensor reading with realistic behaviors."""
        minutes_elapsed = (current_time - self.last_update).total_seconds() / 60
        
        if minutes_elapsed < self.update_interval:
            return self.last_reading
            
        if random.random() < self.failure_rate:
            return None
            
        self.last_reading = self.thermal_model.temperature + random.gauss(0, 0.2)
        self.last_update = current_time
        return self.last_reading

@pytest.fixture
def hass_mock():
    """Mock Home Assistant instance."""
    return Mock()

@pytest.fixture
def thermal_model():
    """Create thermal model instance."""
    return ThermalModel()

@pytest.fixture
def mock_sensor(thermal_model):
    """Create mock temperature sensor."""
    return MockSensor(thermal_model)

@pytest.fixture
def thermostat(hass_mock):
    """Create smart thermostat instance."""
    return SmartThermostat(
        hass_mock,
        "Test Thermostat",
        "sensor.test_temperature",
        "switch.test_heater",
        16, 25, 20, 0.5
    )

async def test_seasonal_behavior(hass_mock, thermostat, thermal_model, mock_sensor):
    """Test thermostat behavior across seasons."""
    
    async def simulate_day(month, target_temp):
        thermal_model.set_season(month)
        thermostat._target_temperature = target_temp
        thermostat._hvac_mode = HVACMode.HEAT
        
        # Simulate 24 hours in 10-minute increments
        current_time = datetime.now()
        for _ in range(144):  # 24 hours * 6 (10-minute intervals)
            # Update thermal model
            thermal_model.update(10)
            current_time += timedelta(minutes=10)
            
            # Get sensor reading
            reading = mock_sensor.get_reading(current_time)
            if reading is not None:
                with patch.object(thermostat, 'current_temperature', reading):
                    await thermostat.async_update()
                    
            # Update heater state in thermal model
            thermal_model.heater_on = thermostat._is_heating
            
        return thermal_model.temperature
    
    # Test winter behavior
    winter_temp = await simulate_day(1, 21.0)  # January
    assert 20.5 <= winter_temp <= 21.5, "Winter temperature out of range"
    
    # Test summer behavior
    summer_temp = await simulate_day(7, 21.0)  # July
    assert 20.5 <= summer_temp <= 21.5, "Summer temperature out of range"

async def test_sensor_failures(hass_mock, thermostat, thermal_model, mock_sensor):
    """Test thermostat behavior with sensor failures."""
    mock_sensor.failure_rate = 0.5  # Increase failure rate for testing
    
    current_time = datetime.now()
    temperatures = []
    
    # Simulate 2 hours with frequent sensor failures
    for _ in range(12):  # 12 10-minute intervals
        thermal_model.update(10)
        current_time += timedelta(minutes=10)
        
        reading = mock_sensor.get_reading(current_time)
        if reading is not None:
            with patch.object(thermostat, 'current_temperature', reading):
                await thermostat.async_update()
                temperatures.append(reading)
    
    # Verify thermostat maintained reasonable control despite failures
    assert len(temperatures) > 0, "No valid temperature readings"
    assert max(temperatures) - min(temperatures) < 2.0, "Temperature variance too high"

async def test_user_interaction(hass_mock, thermostat, thermal_model, mock_sensor):
    """Test thermostat response to user changes."""
    current_time = datetime.now()
    
    # Simulate user changing target temperature
    await thermostat.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})
    assert thermostat.target_temperature == 22.0
    
    # Simulate temperature response
    for _ in range(6):  # 1 hour
        thermal_model.update(10)
        current_time += timedelta(minutes=10)
        
        reading = mock_sensor.get_reading(current_time)
        if reading is not None:
            with patch.object(thermostat, 'current_temperature', reading):
                await thermostat.async_update()
                thermal_model.heater_on = thermostat._is_heating
    
    # Verify system responded to user change
    assert abs(thermal_model.temperature - 22.0) < 1.0, "Failed to reach new target temperature" 