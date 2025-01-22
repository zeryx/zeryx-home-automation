"""Configure pytest for Home Assistant component testing."""
import asyncio
import pytest
from homeassistant import core
import logging

logging.getLogger("homeassistant.core").setLevel(logging.DEBUG)
logging.getLogger("custom_components.mock_hvac.climate").setLevel(logging.DEBUG)

@pytest.fixture(autouse=True)
async def auto_enable_custom_integrations(hass):
    """Enable custom integrations in Home Assistant."""
    hass.data.pop("custom_components", None)

@pytest.fixture
def event_loop(request):
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop
    
    loop.close()

@pytest.fixture
async def hass(event_loop):
    """Fixture to provide a test instance of Home Assistant."""
    hass = core.HomeAssistant()
    hass.config.components.add("persistent_notification")
    
    # Initialize HA
    await hass.async_start()
    
    yield hass
    
    # Stop HA
    await hass.async_stop() 