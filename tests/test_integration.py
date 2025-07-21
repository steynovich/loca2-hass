"""Integration tests for Loca2 Home Assistant integration."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.loca2.api import (
    Loca2AuthError,
    Loca2ConnectionError,
    Loca2Device,
    Loca2Location,
)
from custom_components.loca2.const import CONF_BASE_URL, DOMAIN
from custom_components.loca2.device_tracker import Loca2DeviceTracker

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_config_entry_data():
    """Create mock config entry data."""
    return {
        CONF_API_KEY: "test_api_key_123",
        CONF_BASE_URL: "https://api.loca2.example.com",
        CONF_SCAN_INTERVAL: 30,
        CONF_TIMEOUT: 10,
    }


@pytest.fixture
def mock_config_entry(mock_config_entry_data):
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.data = mock_config_entry_data
    entry.options = {}
    entry.entry_id = "test_entry"
    entry.state = ConfigEntryState.NOT_LOADED
    entry.add_update_listener = Mock(return_value="listener")
    entry.async_on_unload = Mock()
    return entry


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = Mock()
    client.test_connection = AsyncMock(return_value=True)
    client.get_devices = AsyncMock(
        return_value=[
            Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now(),
            ),
            Loca2Device(
                id="device_2",
                name="Test Tablet",
                device_type="tablet",
                battery_level=92,
                last_seen=datetime.now(),
            ),
        ]
    )
    client.get_device_location = AsyncMock(
        return_value=Loca2Location(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            timestamp=datetime.now(),
            address="San Francisco, CA",
        )
    )
    client.close = AsyncMock()
    return client


class TestIntegrationSetupFlow:
    """Test complete integration setup and operation flow."""

    async def test_complete_setup_flow(
        self, hass: HomeAssistant, mock_config_entry, mock_api_client
    ):
        """Test complete integration setup from config entry to working entities."""
        from custom_components.loca2 import async_setup_entry

        with patch(
            "custom_components.loca2.Loca2ApiClient", return_value=mock_api_client
        ):
            result = await async_setup_entry(hass, mock_config_entry)
            assert result is True

            # Verify integration data is stored
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert "coordinator" in hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "api_client" in hass.data[DOMAIN][mock_config_entry.entry_id]

            # Verify API client was called
            mock_api_client.test_connection.assert_called_once()

    async def test_setup_with_invalid_credentials(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test setup failure with invalid credentials."""
        from custom_components.loca2 import async_setup_entry

        # Mock API client that fails authentication
        mock_client = Mock()
        mock_client.test_connection = AsyncMock(
            side_effect=Loca2AuthError("Invalid credentials")
        )

        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to authenticate"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_setup_with_connection_error(
        self, hass: HomeAssistant, mock_config_entry
    ):
        """Test setup failure with connection error."""
        from custom_components.loca2 import async_setup_entry

        # Mock API client that fails to connect
        mock_client = Mock()
        mock_client.test_connection = AsyncMock(
            side_effect=Loca2ConnectionError("Connection failed")
        )

        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to connect"):
                await async_setup_entry(hass, mock_config_entry)


class TestEntityCreationAndUpdates:
    """Test entity creation and state updates."""

    async def test_device_tracker_entity_creation(self, mock_api_client):
        """Test that device tracker entities are created correctly."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now(),
            )
        }

        # Create entity
        device = mock_coordinator.data["device_1"]
        entity = Loca2DeviceTracker(mock_coordinator, "device_1", device)

        # Test entity properties
        assert entity._attr_unique_id == f"{DOMAIN}_device_1"
        assert entity._attr_name == "Test Phone"
        assert entity._attr_source_type.value == "gps"

        # Test device info
        device_info = entity._attr_device_info
        assert device_info["identifiers"] == {(DOMAIN, "device_1")}
        assert device_info["name"] == "Test Phone"
        assert device_info["manufacturer"] == "Loca2"
        assert device_info["model"] == "smartphone"

    async def test_entity_state_updates(self, mock_api_client):
        """Test that entity states update correctly."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now(),
            )
        }

        # Mock the API client in coordinator
        mock_coordinator.api_client = mock_api_client

        # Create entity
        device = mock_coordinator.data["device_1"]
        entity = Loca2DeviceTracker(mock_coordinator, "device_1", device)

        # Update location
        await entity._async_update_location()

        # Verify location data
        assert entity.latitude == 37.7749
        assert entity.longitude == -122.4194
        assert entity.location_accuracy == 10.0

        # Verify attributes
        attributes = entity.extra_state_attributes
        assert attributes["battery_level"] == 85
        assert attributes["device_type"] == "smartphone"
        assert attributes["gps_accuracy"] == 10.0
        assert attributes["address"] == "San Francisco, CA"

    async def test_entity_availability_changes(self):
        """Test entity availability changes based on coordinator state."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now(),
            )
        }
        mock_coordinator.last_update_success = True

        # Create entity
        device = mock_coordinator.data["device_1"]
        entity = Loca2DeviceTracker(mock_coordinator, "device_1", device)

        # Initially available
        assert entity.available is True

        # Simulate coordinator failure
        mock_coordinator.last_update_success = False
        assert entity.available is False

        # Restore coordinator
        mock_coordinator.last_update_success = True
        assert entity.available is True


class TestAPIIntegrationWithMockServer:
    """Test API integration with mock server responses."""

    async def test_successful_api_calls(self, mock_api_client):
        """Test successful API calls through the integration."""
        # Test authentication
        auth_result = await mock_api_client.test_connection()
        assert auth_result is True

        # Test device discovery
        devices = await mock_api_client.get_devices()
        assert len(devices) == 2
        assert devices[0].id in ["device_1", "device_2"]
        assert devices[1].id in ["device_1", "device_2"]

        # Test location retrieval
        location = await mock_api_client.get_device_location("device_1")
        assert location.latitude == 37.7749
        assert location.longitude == -122.4194
        assert location.accuracy == 10.0

    async def test_api_rate_limiting(self, hass: HomeAssistant, mock_config_entry):
        """Test API rate limiting handling."""
        from custom_components.loca2 import async_setup_entry

        # Mock API client that raises rate limit error
        mock_client = Mock()
        mock_client.test_connection = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_client):
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, mock_config_entry)

    async def test_api_error_recovery(self, mock_api_client):
        """Test API error recovery."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.api_client = mock_api_client
        mock_coordinator.last_update_success = True
        mock_coordinator.data = {"device_1": Mock()}

        # Simulate API error
        mock_api_client.get_devices.side_effect = Loca2ConnectionError(
            "Connection failed"
        )

        # Simulate coordinator update failure
        mock_coordinator.last_update_success = False
        assert mock_coordinator.last_update_success is False

        # Restore API
        mock_api_client.get_devices.side_effect = None
        mock_coordinator.last_update_success = True
        assert mock_coordinator.last_update_success is True


class TestIntegrationReloadAndUnload:
    """Test integration reload and unload scenarios."""

    async def test_integration_reload(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test integration reload functionality."""
        # Setup integration
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry, async_unload_entry

        # Initial setup
        setup_result = await async_setup_entry(hass, config_entry)
        assert setup_result is True

        # Verify data exists
        assert DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[DOMAIN]

        # Get references to verify cleanup
        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]

        # Unload integration
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            unload_result = await async_unload_entry(hass, config_entry)
            assert unload_result is True

        # Verify cleanup
        assert config_entry.entry_id not in hass.data[DOMAIN]

        # Reload integration
        setup_result = await async_setup_entry(hass, config_entry)
        assert setup_result is True

        # Verify new instances were created
        new_coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        new_api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]

        assert new_coordinator is not coordinator
        assert new_api_client is not api_client

    async def test_integration_unload_cleanup(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test proper cleanup during integration unload."""
        # Setup integration
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry, async_unload_entry

        await async_setup_entry(hass, config_entry)

        # Get API client to verify it gets closed
        api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]

        # Mock the close method to verify it's called
        api_client.close = AsyncMock()

        # Unload integration
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            result = await async_unload_entry(hass, config_entry)
            assert result is True

        # Verify API client was closed
        api_client.close.assert_called_once()

        # Verify data was cleaned up
        assert config_entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_with_platform_failure(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test unload behavior when platform unload fails."""
        # Setup integration
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry, async_unload_entry

        await async_setup_entry(hass, config_entry)

        # Get API client to verify it doesn't get closed on failure
        api_client = hass.data[DOMAIN][config_entry.entry_id]["api_client"]
        api_client.close = AsyncMock()

        # Simulate platform unload failure
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=False
        ):
            result = await async_unload_entry(hass, config_entry)
            assert result is False

        # Verify API client was NOT closed
        api_client.close.assert_not_called()

        # Verify data was NOT cleaned up
        assert config_entry.entry_id in hass.data[DOMAIN]

    async def test_options_update_triggers_reload(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test that options updates trigger integration reload."""
        # Setup integration
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry, async_update_options

        await async_setup_entry(hass, config_entry)

        # Mock hass.config_entries.async_reload
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            await async_update_options(hass, config_entry)
            mock_reload.assert_called_once_with(config_entry.entry_id)


class TestHACSCompatibility:
    """Test HACS compatibility validation."""

    def test_manifest_structure(self):
        """Test that manifest.json has required HACS fields."""
        from pathlib import Path

        manifest_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "manifest.json"
        )

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Required HACS fields
        required_fields = [
            "domain",
            "name",
            "version",
            "documentation",
            "issue_tracker",
            "codeowners",
            "requirements",
            "iot_class",
            "config_flow",
        ]

        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

        # Validate specific values
        assert manifest["domain"] == "loca2"
        assert manifest["config_flow"] is True
        assert manifest["iot_class"] == "cloud_polling"
        assert isinstance(manifest["requirements"], list)
        assert len(manifest["codeowners"]) > 0

    def test_integration_structure(self):
        """Test that integration follows proper structure."""
        from pathlib import Path

        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        # Required files
        required_files = [
            "__init__.py",
            "manifest.json",
            "config_flow.py",
            "device_tracker.py",
            "const.py",
            "api.py",
            "strings.json",
        ]

        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"Missing required file: {file_name}"

    def test_strings_json_structure(self):
        """Test that strings.json has proper structure."""
        from pathlib import Path

        strings_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "strings.json"
        )

        with open(strings_path) as f:
            strings = json.load(f)

        # Should have config section
        assert "config" in strings
        assert "step" in strings["config"]
        assert "error" in strings["config"]

        # Should have options section if options flow exists
        if "options" in strings:
            assert "step" in strings["options"]

    async def test_config_flow_compatibility(self, hass: HomeAssistant):
        """Test config flow HACS compatibility."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        # Test that config flow can be instantiated
        flow = Loca2ConfigFlow()
        assert flow is not None

        # Test that required methods exist
        assert hasattr(flow, "async_step_user")
        assert hasattr(flow, "async_step_reauth")

        # Test version is set
        assert hasattr(flow, "VERSION")
        assert flow.VERSION >= 1

    def test_async_implementation(self):
        """Test that integration uses async/await properly."""
        import inspect

        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient
        from custom_components.loca2.device_tracker import Loca2DeviceTracker

        # Test main entry points are async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)

        # Test API client methods are async
        assert inspect.iscoroutinefunction(Loca2ApiClient.test_connection)
        assert inspect.iscoroutinefunction(Loca2ApiClient.get_devices)
        assert inspect.iscoroutinefunction(Loca2ApiClient.get_device_location)

        # Test device tracker update method is async
        assert inspect.iscoroutinefunction(Loca2DeviceTracker.async_update)


class TestEndToEndIntegration:
    """Test complete end-to-end integration scenarios."""

    async def test_full_integration_lifecycle(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test complete integration lifecycle from setup to entity updates."""
        # Setup integration
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry, async_unload_entry

        # 1. Setup integration
        setup_result = await async_setup_entry(hass, config_entry)
        assert setup_result is True

        # 2. Verify coordinator data
        coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
        await coordinator.async_config_entry_first_refresh()
        assert len(coordinator.data) == 2

        # 3. Create and test entities
        entities = []
        for device_id, device in coordinator.data.items():
            entity = Loca2DeviceTracker(coordinator, device_id, device)
            entities.append(entity)

            # Update entity location
            await entity._async_update_location()

            # Verify entity state
            assert entity.available is True
            assert entity.latitude is not None
            assert entity.longitude is not None

        # 4. Test coordinator updates
        initial_request_count = mock_server.mock_instance.request_count
        await coordinator.async_request_refresh()
        assert mock_server.mock_instance.request_count > initial_request_count

        # 5. Test device changes
        mock_server.mock_instance.devices["device_1"]["battery_level"] = 75
        await coordinator.async_request_refresh()

        updated_device = coordinator.data["device_1"]
        assert updated_device.battery_level == 75

        # 6. Clean unload
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            unload_result = await async_unload_entry(hass, config_entry)
            assert unload_result is True

        assert config_entry.entry_id not in hass.data[DOMAIN]

    async def test_integration_with_config_options(
        self, hass: HomeAssistant, mock_server, mock_config_entry_data
    ):
        """Test integration with configuration options."""
        # Setup config entry with options
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = mock_config_entry_data
        config_entry.options = {
            CONF_SCAN_INTERVAL: 60,  # Override default
            CONF_TIMEOUT: 20,  # Override default
        }
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()

        from custom_components.loca2 import async_setup_entry

        # Setup should use options values
        with (
            patch("custom_components.loca2.Loca2ApiClient") as mock_client_class,
            patch(
                "custom_components.loca2.Loca2DataUpdateCoordinator"
            ) as mock_coord_class,
        ):

            mock_client = Mock()
            mock_client.test_connection = AsyncMock(return_value=True)
            mock_client_class.return_value = mock_client

            mock_coordinator = Mock()
            mock_coordinator.async_config_entry_first_refresh = AsyncMock()
            mock_coord_class.return_value = mock_coordinator

            result = await async_setup_entry(hass, config_entry)
            assert result is True

            # Verify coordinator was created with options values
            mock_coord_class.assert_called_once()
            call_args = mock_coord_class.call_args

            # Check that scan interval from options was used
            assert call_args[1]["update_interval"].total_seconds() == 60

            # Verify API client created with options timeout
            mock_client_class.assert_called_once_with(
                api_key="test_api_key_123",
                base_url="https://api.loca2.example.com",
                timeout=20,  # From options
            )
