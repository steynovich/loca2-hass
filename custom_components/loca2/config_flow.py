"""Config flow for Loca2 integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .api import Loca2ApiClient, Loca2AuthError, Loca2ConnectionError, Loca2ApiError
from .const import (
    DOMAIN,
    CONF_BASE_URL,
    CONF_DISABLED_DEVICES,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    ERROR_AUTH_FAILED,
    ERROR_CANNOT_CONNECT,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
    ERROR_INVALID_SCAN_INTERVAL,
    ERROR_INVALID_TIMEOUT,
    ERROR_INVALID_DEVICE_LIST,
    OPTIONS_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

# Step schemas
STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): cv.url,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    base_url = data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
    timeout = data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
    
    # Test the connection
    client = Loca2ApiClient(account=username, password=password, base_url=base_url, timeout=timeout)
    
    try:
        async with client:
            # Test authentication
            auth_result = await client.authenticate()
            if not auth_result:
                raise Loca2AuthError("Authentication failed")
            
            # Try to get devices to ensure full API access
            devices = await client.get_devices()
            _LOGGER.debug("Successfully connected to Loca2 API, found %d devices", len(devices))
            
    except Loca2AuthError as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise Loca2AuthError("Invalid username or password") from err
    except Loca2ConnectionError as err:
        _LOGGER.error("Connection failed: %s", err)
        raise Loca2ConnectionError("Cannot connect to Loca2 API") from err
    except Exception as err:
        _LOGGER.error("Unexpected error during validation: %s", err)
        raise Loca2ApiError(f"Unexpected error: {err}") from err
    
    # Return info that you want to store in the config entry
    return {
        "title": f"Loca2 ({base_url})",
        "data": data,
    }


class Loca2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Loca2."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except Loca2AuthError:
                errors["base"] = ERROR_AUTH_FAILED
            except Loca2ConnectionError:
                errors["base"] = ERROR_CANNOT_CONNECT
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = ERROR_UNKNOWN
            else:
                # Check if already configured
                await self.async_set_unique_id(user_input[CONF_BASE_URL])
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(title=info["title"], data=info["data"])

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> Loca2OptionsFlowHandler:
        """Create the options flow."""
        return Loca2OptionsFlowHandler(config_entry)


class Loca2OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Loca2 options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry
        self._available_devices: Optional[Dict[str, str]] = None

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Validate the input
            try:
                validated_data = await self._validate_options(user_input)
                return self.async_create_entry(title="", data=validated_data)
            except vol.Invalid as err:
                if "scan_interval" in str(err):
                    errors["scan_interval"] = ERROR_INVALID_SCAN_INTERVAL
                elif "timeout" in str(err):
                    errors["timeout"] = ERROR_INVALID_TIMEOUT
                elif "disabled_devices" in str(err):
                    errors["disabled_devices"] = ERROR_INVALID_DEVICE_LIST
                else:
                    errors["base"] = ERROR_UNKNOWN
                _LOGGER.error("Options validation error: %s", err)
            except Exception as err:
                _LOGGER.exception("Unexpected error in options flow: %s", err)
                errors["base"] = ERROR_UNKNOWN

        # Get available devices for device filtering
        try:
            await self._get_available_devices()
        except Exception as err:
            _LOGGER.warning("Could not fetch devices for options: %s", err)

        # Get current values from config entry
        current_scan_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        current_timeout = self._config_entry.options.get(
            CONF_TIMEOUT,
            self._config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        )
        current_disabled_devices = self._config_entry.options.get(
            CONF_DISABLED_DEVICES, []
        )

        # Build the options schema
        options_schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current_scan_interval
            ): vol.All(
                cv.positive_int, 
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
            vol.Optional(
                CONF_TIMEOUT,
                default=current_timeout
            ): vol.All(cv.positive_int, vol.Range(min=1, max=120)),
        })

        # Add device filtering if we have available devices
        if self._available_devices:
            device_options = {device_id: f"{name} ({device_id})" 
                            for device_id, name in self._available_devices.items()}
            
            options_schema = options_schema.extend({
                vol.Optional(
                    CONF_DISABLED_DEVICES,
                    default=current_disabled_devices
                ): cv.multi_select(device_options),
            })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )

    async def _get_available_devices(self) -> None:
        """Get available devices from the API."""
        try:
            # Get API client configuration
            username = self._config_entry.data[CONF_USERNAME]
            password = self._config_entry.data[CONF_PASSWORD]
            base_url = self._config_entry.data[CONF_BASE_URL]
            timeout = self._config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            
            # Create API client and fetch devices
            client = Loca2ApiClient(account=username, password=password, base_url=base_url, timeout=timeout)
            async with client:
                devices = await client.get_devices()
                self._available_devices = {device.id: device.name for device in devices}
                _LOGGER.debug("Found %d devices for options", len(self._available_devices))
                
        except Exception as err:
            _LOGGER.warning("Failed to fetch devices for options: %s", err)
            self._available_devices = None

    async def _validate_options(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the options input with comprehensive error handling."""
        validation_errors = []
        
        try:
            # Validate scan interval
            scan_interval = user_input.get(CONF_SCAN_INTERVAL)
            if scan_interval is not None:
                if not isinstance(scan_interval, int):
                    validation_errors.append(f"Scan interval must be an integer, got {type(scan_interval).__name__}")
                elif scan_interval < MIN_SCAN_INTERVAL or scan_interval > MAX_SCAN_INTERVAL:
                    validation_errors.append(f"Scan interval must be between {MIN_SCAN_INTERVAL} and {MAX_SCAN_INTERVAL} seconds, got {scan_interval}")
                else:
                    _LOGGER.debug("Scan interval validation passed: %d seconds", scan_interval)

            # Validate timeout
            timeout = user_input.get(CONF_TIMEOUT)
            if timeout is not None:
                if not isinstance(timeout, int):
                    validation_errors.append(f"Timeout must be an integer, got {type(timeout).__name__}")
                elif timeout < 1 or timeout > 120:
                    validation_errors.append(f"Timeout must be between 1 and 120 seconds, got {timeout}")
                else:
                    _LOGGER.debug("Timeout validation passed: %d seconds", timeout)

            # Validate disabled devices
            disabled_devices = user_input.get(CONF_DISABLED_DEVICES, [])
            if disabled_devices:
                if not isinstance(disabled_devices, list):
                    validation_errors.append(f"Disabled devices must be a list, got {type(disabled_devices).__name__}")
                else:
                    # Validate that all disabled devices exist in available devices
                    if self._available_devices:
                        invalid_devices = [device for device in disabled_devices 
                                         if device not in self._available_devices]
                        if invalid_devices:
                            validation_errors.append(f"Unknown devices: {', '.join(invalid_devices)}")
                        else:
                            _LOGGER.debug("Disabled devices validation passed: %s", disabled_devices)
                    else:
                        _LOGGER.warning("Cannot validate disabled devices - available devices list not loaded")
            
            # Log validation summary
            if validation_errors:
                _LOGGER.warning("Options validation failed with %d errors: %s", 
                              len(validation_errors), "; ".join(validation_errors))
                raise vol.Invalid("; ".join(validation_errors))
            else:
                _LOGGER.info("Options validation successful for %d parameters", len(user_input))
                
        except vol.Invalid:
            raise  # Re-raise validation errors
        except Exception as err:
            _LOGGER.error("Unexpected error during options validation: %s", err)
            raise vol.Invalid(f"Validation error: {err}") from err

        return user_input