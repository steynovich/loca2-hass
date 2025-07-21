"""Test the Loca2 config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.loca2.api import (
    Loca2ApiError,
    Loca2AuthError,
    Loca2ConnectionError,
)
from custom_components.loca2.config_flow import validate_input
from custom_components.loca2.const import (
    CONF_BASE_URL,
    ERROR_AUTH_FAILED,
    ERROR_CANNOT_CONNECT,
    ERROR_UNKNOWN,
)

# Test data
TEST_API_KEY = "test_api_key_123"
TEST_BASE_URL = "https://api.loca2.example.com"
TEST_SCAN_INTERVAL = 60
TEST_TIMEOUT = 15

VALID_CONFIG = {
    CONF_API_KEY: TEST_API_KEY,
    CONF_BASE_URL: TEST_BASE_URL,
    CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
    CONF_TIMEOUT: TEST_TIMEOUT,
}


class TestValidateInput:
    """Test the validate_input function."""

    @pytest.mark.asyncio
    async def test_validate_input_success(self, hass: HomeAssistant):
        """Test successful validation."""
        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.authenticate.return_value = True
            mock_client.get_devices.return_value = []

            # Test validation
            result = await validate_input(hass, VALID_CONFIG)

            # Verify result
            assert result["title"] == f"Loca2 ({TEST_BASE_URL})"
            assert result["data"] == VALID_CONFIG

            # Verify API client was called correctly
            mock_client_class.assert_called_once_with(
                api_key=TEST_API_KEY, base_url=TEST_BASE_URL, timeout=TEST_TIMEOUT
            )
            mock_client.authenticate.assert_called_once()
            mock_client.get_devices.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_input_auth_error(self, hass: HomeAssistant):
        """Test validation with authentication error."""
        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            # Setup mock client to raise auth error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.authenticate.side_effect = Loca2AuthError("Invalid API key")

            # Test validation should raise auth error
            with pytest.raises(Loca2AuthError):
                await validate_input(hass, VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_validate_input_connection_error(self, hass: HomeAssistant):
        """Test validation with connection error."""
        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            # Setup mock client to raise connection error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.authenticate.side_effect = Loca2ConnectionError(
                "Cannot connect"
            )

            # Test validation should raise connection error
            with pytest.raises(Loca2ConnectionError):
                await validate_input(hass, VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_validate_input_auth_failed_false(self, hass: HomeAssistant):
        """Test validation when authentication returns False."""
        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            # Setup mock client to return False for authentication
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.authenticate.return_value = False

            # Test validation should raise auth error
            with pytest.raises(Loca2AuthError):
                await validate_input(hass, VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_validate_input_unexpected_error(self, hass: HomeAssistant):
        """Test validation with unexpected error."""
        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            # Setup mock client to raise unexpected error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.authenticate.side_effect = ValueError("Unexpected error")

            # Test validation should raise API error
            with pytest.raises(Loca2ApiError):
                await validate_input(hass, VALID_CONFIG)


class TestLoca2ConfigFlow:
    """Test the Loca2 config flow."""

    @pytest.mark.asyncio
    async def test_form_display(self):
        """Test that the form is served with no input."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        flow = Loca2ConfigFlow()
        flow.hass = AsyncMock()

        result = await flow.async_step_user()

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "user"

    @pytest.mark.asyncio
    async def test_form_success(self):
        """Test successful form submission."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        with patch(
            "custom_components.loca2.config_flow.validate_input"
        ) as mock_validate:
            mock_validate.return_value = {
                "title": f"Loca2 ({TEST_BASE_URL})",
                "data": VALID_CONFIG,
            }

            flow = Loca2ConfigFlow()
            flow.hass = AsyncMock()

            # Mock the unique ID methods
            flow.async_set_unique_id = AsyncMock()
            flow._abort_if_unique_id_configured = AsyncMock()
            flow.async_create_entry = AsyncMock(
                return_value={"type": FlowResultType.CREATE_ENTRY}
            )

            result = await flow.async_step_user(VALID_CONFIG)

            assert flow.async_create_entry.called
            mock_validate.assert_called_once_with(flow.hass, VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_form_auth_error(self):
        """Test form with authentication error."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        with patch(
            "custom_components.loca2.config_flow.validate_input"
        ) as mock_validate:
            mock_validate.side_effect = Loca2AuthError("Invalid API key")

            flow = Loca2ConfigFlow()
            flow.hass = AsyncMock()
            flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})

            result = await flow.async_step_user(VALID_CONFIG)

            # Check that async_show_form was called with the right error
            flow.async_show_form.assert_called_once()
            call_args = flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": ERROR_AUTH_FAILED}

    @pytest.mark.asyncio
    async def test_form_connection_error(self):
        """Test form with connection error."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        with patch(
            "custom_components.loca2.config_flow.validate_input"
        ) as mock_validate:
            mock_validate.side_effect = Loca2ConnectionError("Cannot connect")

            flow = Loca2ConfigFlow()
            flow.hass = AsyncMock()
            flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})

            result = await flow.async_step_user(VALID_CONFIG)

            # Check that async_show_form was called with the right error
            flow.async_show_form.assert_called_once()
            call_args = flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": ERROR_CANNOT_CONNECT}

    @pytest.mark.asyncio
    async def test_form_unknown_error(self):
        """Test form with unknown error."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        with patch(
            "custom_components.loca2.config_flow.validate_input"
        ) as mock_validate:
            mock_validate.side_effect = ValueError("Unexpected error")

            flow = Loca2ConfigFlow()
            flow.hass = AsyncMock()
            flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})

            result = await flow.async_step_user(VALID_CONFIG)

            # Check that async_show_form was called with the right error
            flow.async_show_form.assert_called_once()
            call_args = flow.async_show_form.call_args
            assert call_args[1]["errors"] == {"base": ERROR_UNKNOWN}

    @pytest.mark.asyncio
    async def test_form_already_configured(self):
        """Test form when already configured."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        with patch(
            "custom_components.loca2.config_flow.validate_input"
        ) as mock_validate:
            mock_validate.return_value = {
                "title": f"Loca2 ({TEST_BASE_URL})",
                "data": VALID_CONFIG,
            }

            flow = Loca2ConfigFlow()
            flow.hass = AsyncMock()
            flow.async_set_unique_id = AsyncMock()
            flow._abort_if_unique_id_configured = AsyncMock(
                side_effect=Exception("already_configured")
            )

            # The flow should handle the abort internally
            try:
                result = await flow.async_step_user(VALID_CONFIG)
            except Exception as e:
                assert str(e) == "already_configured"

            flow.async_set_unique_id.assert_called_once_with(TEST_BASE_URL)


class TestLoca2OptionsFlow:
    """Test the Loca2 options flow."""

    def test_options_flow_class_exists(self):
        """Test that the options flow handler class exists and can be imported."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Test that the class exists and has the expected methods
        assert hasattr(Loca2OptionsFlowHandler, "__init__")
        assert hasattr(Loca2OptionsFlowHandler, "async_step_init")

        # Test that it's a proper subclass
        from homeassistant.config_entries import OptionsFlow

        assert issubclass(Loca2OptionsFlowHandler, OptionsFlow)

    @pytest.mark.asyncio
    async def test_options_form_display(self):
        """Test that the options form is served with no input."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})

        # Mock the device fetching to avoid API calls
        flow._get_available_devices = AsyncMock()

        result = await flow.async_step_init()

        # Verify form is displayed
        flow.async_show_form.assert_called_once()
        call_args = flow.async_show_form.call_args
        assert call_args[1]["step_id"] == "init"
        assert call_args[1]["errors"] == {}

    @pytest.mark.asyncio
    async def test_options_form_success(self):
        """Test successful options form submission."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler
        from custom_components.loca2.const import CONF_DISABLED_DEVICES

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow.async_create_entry = AsyncMock(
            return_value={"type": FlowResultType.CREATE_ENTRY}
        )
        flow._validate_options = AsyncMock(
            return_value={
                CONF_SCAN_INTERVAL: 45,
                CONF_TIMEOUT: 20,
                CONF_DISABLED_DEVICES: ["device1"],
            }
        )

        # Test options submission
        options_input = {
            CONF_SCAN_INTERVAL: 45,
            CONF_TIMEOUT: 20,
            CONF_DISABLED_DEVICES: ["device1"],
        }

        result = await flow.async_step_init(options_input)

        # Verify entry creation
        flow.async_create_entry.assert_called_once()
        flow._validate_options.assert_called_once_with(options_input)

    @pytest.mark.asyncio
    async def test_options_validation_error(self):
        """Test options form with validation error."""
        import voluptuous as vol

        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler
        from custom_components.loca2.const import ERROR_INVALID_SCAN_INTERVAL

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})
        flow._get_available_devices = AsyncMock()
        flow._validate_options = AsyncMock(
            side_effect=vol.Invalid("scan_interval error")
        )

        # Test options submission with invalid data
        options_input = {
            CONF_SCAN_INTERVAL: 5,  # Too low
        }

        result = await flow.async_step_init(options_input)

        # Verify error handling
        flow.async_show_form.assert_called_once()
        call_args = flow.async_show_form.call_args
        assert call_args[1]["errors"]["scan_interval"] == ERROR_INVALID_SCAN_INTERVAL

    @pytest.mark.asyncio
    async def test_options_get_available_devices_success(self):
        """Test successful device fetching for options."""
        from datetime import datetime

        from custom_components.loca2.api import Loca2Device
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create mock devices
        mock_devices = [
            Loca2Device(
                id="device1",
                name="Device 1",
                device_type="tracker",
                battery_level=80,
                last_seen=datetime.now(),
            ),
            Loca2Device(
                id="device2",
                name="Device 2",
                device_type="tracker",
                battery_level=60,
                last_seen=datetime.now(),
            ),
        ]

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)

        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.get_devices.return_value = mock_devices

            await flow._get_available_devices()

            # Verify devices were fetched and stored
            assert flow._available_devices == {
                "device1": "Device 1",
                "device2": "Device 2",
            }

    @pytest.mark.asyncio
    async def test_options_get_available_devices_error(self):
        """Test device fetching error handling."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)

        with patch(
            "custom_components.loca2.config_flow.Loca2ApiClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.get_devices.side_effect = Exception("API Error")

            await flow._get_available_devices()

            # Verify error was handled gracefully
            assert flow._available_devices is None

    @pytest.mark.asyncio
    async def test_options_validate_scan_interval(self):
        """Test scan interval validation."""
        import voluptuous as vol

        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler
        from custom_components.loca2.const import MAX_SCAN_INTERVAL, MIN_SCAN_INTERVAL

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)

        # Test valid scan interval
        valid_input = {CONF_SCAN_INTERVAL: 30}
        result = await flow._validate_options(valid_input)
        assert result == valid_input

        # Test invalid scan interval (too low)
        with pytest.raises(vol.Invalid):
            await flow._validate_options({CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL - 1})

        # Test invalid scan interval (too high)
        with pytest.raises(vol.Invalid):
            await flow._validate_options({CONF_SCAN_INTERVAL: MAX_SCAN_INTERVAL + 1})

    @pytest.mark.asyncio
    async def test_options_validate_timeout(self):
        """Test timeout validation."""
        import voluptuous as vol

        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)

        # Test valid timeout
        valid_input = {CONF_TIMEOUT: 30}
        result = await flow._validate_options(valid_input)
        assert result == valid_input

        # Test invalid timeout (too low)
        with pytest.raises(vol.Invalid):
            await flow._validate_options({CONF_TIMEOUT: 0})

        # Test invalid timeout (too high)
        with pytest.raises(vol.Invalid):
            await flow._validate_options({CONF_TIMEOUT: 121})

    @pytest.mark.asyncio
    async def test_options_validate_disabled_devices(self):
        """Test disabled devices validation."""
        import voluptuous as vol

        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler
        from custom_components.loca2.const import CONF_DISABLED_DEVICES

        # Create mock config entry
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow._available_devices = {"device1": "Device 1", "device2": "Device 2"}

        # Test valid disabled devices
        valid_input = {CONF_DISABLED_DEVICES: ["device1"]}
        result = await flow._validate_options(valid_input)
        assert result == valid_input

        # Test invalid disabled devices (unknown device)
        with pytest.raises(vol.Invalid):
            await flow._validate_options({CONF_DISABLED_DEVICES: ["unknown_device"]})

        # Test empty disabled devices list
        valid_input = {CONF_DISABLED_DEVICES: []}
        result = await flow._validate_options(valid_input)
        assert result == valid_input

    @pytest.mark.asyncio
    async def test_options_current_values_from_options(self):
        """Test that current values are loaded from options."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler
        from custom_components.loca2.const import CONF_DISABLED_DEVICES

        # Create mock config entry with existing options
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {
            CONF_SCAN_INTERVAL: 45,
            CONF_TIMEOUT: 25,
            CONF_DISABLED_DEVICES: ["device1"],
        }

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})
        flow._get_available_devices = AsyncMock()

        result = await flow.async_step_init()

        # Verify that the form was called (indicating current values were processed)
        flow.async_show_form.assert_called_once()

    @pytest.mark.asyncio
    async def test_options_current_values_from_data(self):
        """Test that current values fall back to config data when options are empty."""
        from custom_components.loca2.config_flow import Loca2OptionsFlowHandler

        # Create mock config entry with no options
        mock_entry = AsyncMock()
        mock_entry.data = VALID_CONFIG
        mock_entry.options = {}

        # Create options flow handler
        flow = Loca2OptionsFlowHandler(mock_entry)
        flow.async_show_form = AsyncMock(return_value={"type": FlowResultType.FORM})
        flow._get_available_devices = AsyncMock()

        result = await flow.async_step_init()

        # Verify that the form was called (indicating fallback values were used)
        flow.async_show_form.assert_called_once()
