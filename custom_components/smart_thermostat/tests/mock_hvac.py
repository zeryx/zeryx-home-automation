class MockFurnace:
    """Mock Ecobee thermostat entity."""
    
    def __init__(self):
        self.hvac_modes = ["off", "heat", "cool", "heat_cool"]
        self.min_temp = 7
        self.max_temp = 35
        self.min_humidity = 20
        self.max_humidity = 50
        self.fan_modes = ["on", "auto"]
        self._current_temperature = 19.8
        self._temperature = None
        self._target_temp_high = None
        self._target_temp_low = None
        self._current_humidity = 43
        self._humidity = 36
        self._fan_mode = "auto"
        self._hvac_action = "idle"
        self._hvac_mode = "off"
        self.friendly_name = "Mock Furnace"
        self.supported_features = 399
        self.entity_id = "climate.mock_furnace"

    @property
    def state(self):
        return self._hvac_mode

    @property
    def attributes(self):
        return {
            "hvac_modes": self.hvac_modes,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "min_humidity": self.min_humidity,
            "max_humidity": self.max_humidity,
            "fan_modes": self.fan_modes,
            "current_temperature": self._current_temperature,
            "temperature": self._temperature,
            "target_temp_high": self._target_temp_high,
            "target_temp_low": self._target_temp_low,
            "current_humidity": self._current_humidity,
            "humidity": self._humidity,
            "fan_mode": self._fan_mode,
            "hvac_action": self._hvac_action,
            "friendly_name": self.friendly_name,
            "supported_features": self.supported_features
        }

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode in self.hvac_modes:
            self._hvac_mode = hvac_mode
            self._hvac_action = "heating" if hvac_mode == "heat" else "idle"

    async def async_set_temperature(self, **kwargs):
        if "temperature" in kwargs:
            self._temperature = kwargs["temperature"]

class MockHeatPump:
    """Mock Lennox heat pump entity."""
    
    def __init__(self):
        self.hvac_modes = ["off", "heat_cool", "cool", "dry", "heat", "fan_only"]
        self.min_temp = 17
        self.max_temp = 30
        self.target_temp_step = 1
        self.fan_modes = ["low", "mid", "high", "auto"]
        self._current_temperature = 19.8
        self._temperature = 21
        self._current_humidity = 42.24
        self._fan_mode = "high"
        self._last_on_operation = "heat"
        self._hvac_action = "idle"
        self.device_code = "2161"
        self.manufacturer = "Lennox"
        self.supported_models = ["LNMTE026V2"]
        self.supported_controller = "Broadlink"
        self.commands_encoding = "Base64"
        self.friendly_name = "Mock Heat Pump"
        self.supported_features = 393
        self._hvac_mode = "off"
        self.entity_id = "climate.mock_heatpump"

    @property
    def state(self):
        return self._hvac_mode

    @property
    def attributes(self):
        return {
            "hvac_modes": self.hvac_modes,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "target_temp_step": self.target_temp_step,
            "fan_modes": self.fan_modes,
            "current_temperature": self._current_temperature,
            "temperature": self._temperature,
            "current_humidity": self._current_humidity,
            "fan_mode": self._fan_mode,
            "last_on_operation": self._last_on_operation,
            "hvac_action": self._hvac_action,
            "device_code": self.device_code,
            "manufacturer": self.manufacturer,
            "supported_models": self.supported_models,
            "supported_controller": self.supported_controller,
            "commands_encoding": self.commands_encoding,
            "friendly_name": self.friendly_name,
            "supported_features": self.supported_features
        }

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode in self.hvac_modes:
            self._hvac_mode = hvac_mode
            if hvac_mode == "heat":
                self._hvac_action = "heating"
                self._last_on_operation = "heat"
            elif hvac_mode == "cool":
                self._hvac_action = "cooling"
            elif hvac_mode == "dry":
                self._hvac_action = "drying"
            elif hvac_mode == "fan_only":
                self._hvac_action = "fan"
            else:
                self._hvac_action = "idle"

    async def async_set_temperature(self, **kwargs):
        if "temperature" in kwargs:
            self._temperature = kwargs["temperature"]

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode in self.fan_modes:
            self._fan_mode = fan_mode 