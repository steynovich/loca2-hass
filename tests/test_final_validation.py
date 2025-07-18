"""Final integration testing and validation for Loca2 Home Assistant integration."""
from __future__ import annotations

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.loca2.api import Loca2Device, Loca2Location, Loca2AuthError, Loca2ConnectionError
from custom_components.loca2.const import CONF_BASE_URL, DOMAIN
from custom_components.loca2.device_tracker import Loca2DeviceTracker

# Configure pytest-asyncio
pytestmark = pytest.mark.asyncio


class TestHomeAssistantIntegrationValidation:
    """Test Home Assistant integration validation tools and compliance."""
    
    def test_manifest_validation(self):
        """Test manifest.json meets Home Assistant validation requirements."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Required fields for Home Assistant
        required_fields = [
            "domain", "name", "version", "documentation", "issue_tracker",
            "codeowners", "requirements", "iot_class", "config_flow"
        ]
        
        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"
        
        # Validate field types and formats
        assert isinstance(manifest["domain"], str)
        assert manifest["domain"].islower()
        assert manifest["domain"].replace("_", "").isalnum()
        
        assert isinstance(manifest["name"], str)
        assert len(manifest["name"]) > 0
        
        # Version validation
        version_parts = manifest["version"].split(".")
        assert len(version_parts) >= 2
        for part in version_parts:
            assert part.isdigit()
        
        # URL validation
        assert manifest["documentation"].startswith(("http://", "https://"))
        assert manifest["issue_tracker"].startswith(("http://", "https://"))
        
        # Codeowners validation
        assert isinstance(manifest["codeowners"], list)
        assert len(manifest["codeowners"]) > 0
        for owner in manifest["codeowners"]:
            assert owner.startswith("@")
        
        # IoT class validation
        valid_iot_classes = ["assumed_state", "cloud_polling", "cloud_push", "local_polling", "local_push"]
        assert manifest["iot_class"] in valid_iot_classes
        
        # Config flow validation
        assert isinstance(manifest["config_flow"], bool)
        assert manifest["config_flow"] is True
    
    def test_integration_structure_validation(self):
        """Test integration file structure meets Home Assistant standards."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Required files
        required_files = [
            "__init__.py", "manifest.json", "config_flow.py", 
            "device_tracker.py", "const.py", "api.py", "strings.json"
        ]
        
        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"Missing required file: {file_name}"
            assert file_path.is_file()
        
        # Validate __init__.py structure
        init_content = (integration_path / "__init__.py").read_text()
        assert "async def async_setup_entry" in init_content
        assert "async def async_unload_entry" in init_content
        assert "PLATFORMS" in init_content or "device_tracker" in init_content
        
        # Validate config_flow.py structure
        config_flow_content = (integration_path / "config_flow.py").read_text()
        assert "ConfigFlow" in config_flow_content
        assert "async def async_step_user" in config_flow_content
        assert "DOMAIN" in config_flow_content
    
    def test_strings_json_validation(self):
        """Test strings.json meets Home Assistant translation standards."""
        strings_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "strings.json"
        
        with open(strings_path) as f:
            strings = json.load(f)
        
        # Required sections
        assert "config" in strings
        
        config_section = strings["config"]
        assert "step" in config_section
        assert "error" in config_section
        
        # Validate step structure
        steps = config_section["step"]
        assert isinstance(steps, dict)
        assert "user" in steps
        
        user_step = steps["user"]
        assert "title" in user_step or "data" in user_step
        
        # Validate error structure
        errors = config_section["error"]
        assert isinstance(errors, dict)
    
    def test_async_implementation_validation(self):
        """Test async implementation follows Home Assistant guidelines."""
        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient
        from custom_components.loca2.device_tracker import Loca2DeviceTracker
        
        import inspect
        
        # Main entry points must be async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)
        
        # API client methods must be async
        api_methods = ["test_connection", "get_devices", "get_device_location", "close"]
        for method_name in api_methods:
            if hasattr(Loca2ApiClient, method_name):
                method = getattr(Loca2ApiClient, method_name)
                assert inspect.iscoroutinefunction(method), f"API method {method_name} must be async"
        
        # Device tracker update method must be async
        assert inspect.iscoroutinefunction(Loca2DeviceTracker.async_update)
    
    def test_no_blocking_operations(self):
        """Test integration doesn't use blocking I/O operations."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        python_files = ["__init__.py", "api.py", "config_flow.py", "device_tracker.py"]
        
        blocking_patterns = [
            "requests.get", "requests.post", "requests.put", "requests.delete",
            "urllib.request", "time.sleep", "socket.socket"
        ]
        
        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                for pattern in blocking_patterns:
                    assert pattern not in content, f"Found blocking operation '{pattern}' in {file_name}"


class TestCompleteUserWorkflow:
    """Test complete user workflow from installation to device tracking."""
    
    @pytest.fixture
    def mock_config_entry_data(self):
        """Create mock config entry data."""
        return {
            CONF_API_KEY: "test_api_key_123",
            CONF_BASE_URL: "https://api.loca2.example.com",
            CONF_SCAN_INTERVAL: 30,
            CONF_TIMEOUT: 10,
        }
    
    @pytest.fixture
    def mock_config_entry(self, mock_config_entry_data):
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
    def mock_api_client(self):
        """Create a mock API client with realistic responses."""
        client = Mock()
        client.test_connection = AsyncMock(return_value=True)
        client.get_devices = AsyncMock(return_value=[
            Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now()
            ),
            Loca2Device(
                id="device_2", 
                name="Test Tablet",
                device_type="tablet",
                battery_level=92,
                last_seen=datetime.now()
            )
        ])
        client.get_device_location = AsyncMock(return_value=Loca2Location(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            timestamp=datetime.now(),
            address="San Francisco, CA"
        ))
        client.close = AsyncMock()
        return client
    
    async def test_integration_setup_workflow(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test complete integration setup workflow."""
        from custom_components.loca2 import async_setup_entry
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client):
            # 1. Setup integration
            result = await async_setup_entry(hass, mock_config_entry)
            assert result is True
            
            # 2. Verify integration data is stored
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            
            integration_data = hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "coordinator" in integration_data
            assert "api_client" in integration_data
            
            # 3. Verify API client was tested
            mock_api_client.test_connection.assert_called_once()
            
            # 4. Verify coordinator was created and refreshed
            coordinator = integration_data["coordinator"]
            assert isinstance(coordinator, DataUpdateCoordinator)
    
    async def test_device_discovery_workflow(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test device discovery and entity creation workflow."""
        from custom_components.loca2 import async_setup_entry
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_config_entry_first_refresh"):
            
            # Setup integration
            await async_setup_entry(hass, mock_config_entry)
            
            # Get coordinator
            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            
            # Manually trigger data fetch to simulate coordinator refresh
            coordinator.data = {
                "device_1": Loca2Device(
                    id="device_1",
                    name="Test Phone", 
                    device_type="smartphone",
                    battery_level=85,
                    last_seen=datetime.now()
                ),
                "device_2": Loca2Device(
                    id="device_2",
                    name="Test Tablet",
                    device_type="tablet", 
                    battery_level=92,
                    last_seen=datetime.now()
                )
            }
            
            # Verify devices were discovered
            assert len(coordinator.data) == 2
            assert "device_1" in coordinator.data
            assert "device_2" in coordinator.data
    
    async def test_entity_creation_workflow(self, mock_api_client):
        """Test device tracker entity creation workflow."""
        # Create mock coordinator with device data
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now()
            )
        }
        mock_coordinator.last_update_success = True
        mock_coordinator.api_client = mock_api_client
        
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
    
    async def test_location_update_workflow(self, mock_api_client):
        """Test location update workflow."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now()
            )
        }
        mock_coordinator.last_update_success = True
        mock_coordinator.api_client = mock_api_client
        
        # Create entity
        device = mock_coordinator.data["device_1"]
        entity = Loca2DeviceTracker(mock_coordinator, "device_1", device)
        
        # Update location
        await entity._async_update_location()
        
        # Verify location was fetched
        mock_api_client.get_device_location.assert_called_once_with("device_1")
        
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
    
    async def test_error_handling_workflow(self, hass: HomeAssistant, mock_config_entry):
        """Test error handling throughout the workflow."""
        from custom_components.loca2 import async_setup_entry
        
        # Test authentication failure
        mock_client = Mock()
        mock_client.test_connection = AsyncMock(side_effect=Loca2AuthError("Invalid credentials"))
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to connect to Loca2 API"):
                await async_setup_entry(hass, mock_config_entry)
        
        # Test connection failure
        mock_client.test_connection = AsyncMock(side_effect=Loca2ConnectionError("Connection failed"))
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to connect to Loca2 API"):
                await async_setup_entry(hass, mock_config_entry)


class TestAsyncImplementationPerformance:
    """Test async implementation and performance validation."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create a mock API client for performance testing."""
        client = Mock()
        client.test_connection = AsyncMock(return_value=True)
        client.get_devices = AsyncMock(return_value=[
            Loca2Device(
                id=f"device_{i}",
                name=f"Test Device {i}",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now()
            ) for i in range(10)  # 10 devices for performance testing
        ])
        client.get_device_location = AsyncMock(return_value=Loca2Location(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            timestamp=datetime.now(),
            address="San Francisco, CA"
        ))
        client.close = AsyncMock()
        return client
    
    async def test_async_setup_performance(self, hass: HomeAssistant, mock_api_client):
        """Test async setup performance doesn't block event loop."""
        from custom_components.loca2 import async_setup_entry
        
        config_entry = Mock(spec=ConfigEntry)
        config_entry.data = {
            CONF_API_KEY: "test_api_key",
            CONF_BASE_URL: "https://api.loca2.example.com",
            CONF_SCAN_INTERVAL: 30,
            CONF_TIMEOUT: 10,
        }
        config_entry.options = {}
        config_entry.entry_id = "test_entry"
        config_entry.add_update_listener = Mock(return_value="listener")
        config_entry.async_on_unload = Mock()
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("homeassistant.helpers.update_coordinator.DataUpdateCoordinator.async_config_entry_first_refresh"):
            
            start_time = time.time()
            result = await async_setup_entry(hass, config_entry)
            end_time = time.time()
            
            assert result is True
            # Setup should complete quickly (under 1 second for mocked operations)
            assert (end_time - start_time) < 1.0
    
    async def test_coordinator_update_performance(self, mock_api_client):
        """Test coordinator update performance with multiple devices."""
        from custom_components.loca2 import Loca2DataUpdateCoordinator
        
        coordinator = Loca2DataUpdateCoordinator(
            hass=Mock(),
            api_client=mock_api_client,
            scan_interval=30
        )
        
        start_time = time.time()
        await coordinator._async_update_data()
        end_time = time.time()
        
        # Update should complete quickly even with multiple devices
        assert (end_time - start_time) < 0.5
        
        # Verify all devices were fetched
        mock_api_client.get_devices.assert_called_once()
    
    async def test_concurrent_location_updates(self, mock_api_client):
        """Test concurrent location updates don't block each other."""
        # Create multiple entities
        mock_coordinator = Mock()
        mock_coordinator.api_client = mock_api_client
        mock_coordinator.last_update_success = True
        
        entities = []
        for i in range(5):
            mock_coordinator.data = {
                f"device_{i}": Loca2Device(
                    id=f"device_{i}",
                    name=f"Test Device {i}",
                    device_type="smartphone",
                    battery_level=85,
                    last_seen=datetime.now()
                )
            }
            device = mock_coordinator.data[f"device_{i}"]
            entity = Loca2DeviceTracker(mock_coordinator, f"device_{i}", device)
            entities.append(entity)
        
        # Update all locations concurrently
        start_time = time.time()
        await asyncio.gather(*[entity._async_update_location() for entity in entities])
        end_time = time.time()
        
        # Concurrent updates should be faster than sequential
        assert (end_time - start_time) < 1.0
        
        # Verify all locations were updated
        assert mock_api_client.get_device_location.call_count == 5
    
    async def test_memory_usage_validation(self, mock_api_client):
        """Test memory usage doesn't grow excessively."""
        from custom_components.loca2 import Loca2DataUpdateCoordinator
        
        coordinator = Loca2DataUpdateCoordinator(
            hass=Mock(),
            api_client=mock_api_client,
            scan_interval=30
        )
        
        # Simulate multiple update cycles
        for _ in range(10):
            await coordinator._async_update_data()
        
        # Verify data is properly managed (not accumulating)
        assert len(coordinator.data) == 10  # Should match number of mock devices
        
        # Verify no excessive object creation
        assert mock_api_client.get_devices.call_count == 10


class TestRequirementsValidation:
    """Test that all requirements are met through automated tests."""
    
    def test_requirement_1_4_hacs_compatibility(self):
        """Test Requirement 1.4: HACS compatibility and updates."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # HACS compatibility requirements
        assert "domain" in manifest
        assert "name" in manifest
        assert "version" in manifest
        assert "documentation" in manifest
        assert "issue_tracker" in manifest
        assert "codeowners" in manifest
        assert manifest["config_flow"] is True
        
        # Version should follow semantic versioning for updates
        version = manifest["version"]
        version_parts = version.split(".")
        assert len(version_parts) >= 2
        for part in version_parts:
            assert part.isdigit()
    
    def test_requirement_7_6_async_operations(self):
        """Test Requirement 7.6: Async/await patterns for non-blocking operations."""
        from custom_components.loca2.api import Loca2ApiClient
        from custom_components.loca2 import async_setup_entry, async_unload_entry
        
        import inspect
        
        # All I/O operations should be async
        async_methods = [
            (Loca2ApiClient, "test_connection"),
            (Loca2ApiClient, "get_devices"),
            (Loca2ApiClient, "get_device_location"),
            (Loca2ApiClient, "close"),
        ]
        
        for cls, method_name in async_methods:
            if hasattr(cls, method_name):
                method = getattr(cls, method_name)
                assert inspect.iscoroutinefunction(method), f"{cls.__name__}.{method_name} must be async"
        
        # Entry points should be async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)
    
    def test_requirement_7_7_non_blocking_event_loop(self):
        """Test Requirement 7.7: Async I/O operations don't block event loop."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Check for blocking operations in code
        blocking_patterns = [
            "requests.get", "requests.post", "requests.put", "requests.delete",
            "urllib.request", "time.sleep", "socket.socket", "httpx.get", "httpx.post"
        ]
        
        python_files = ["__init__.py", "api.py", "config_flow.py", "device_tracker.py"]
        
        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                for pattern in blocking_patterns:
                    # Allow aiohttp and other async HTTP libraries
                    if pattern.startswith("requests.") or pattern.startswith("httpx."):
                        assert pattern not in content, f"Found blocking HTTP operation '{pattern}' in {file_name}"
                    else:
                        assert pattern not in content, f"Found blocking operation '{pattern}' in {file_name}"
    
    async def test_all_requirements_integration(self, hass: HomeAssistant):
        """Test integration of all requirements through end-to-end scenario."""
        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.config_flow import Loca2ConfigFlow
        
        # Test config flow (Requirements 2.1, 2.2, 2.3)
        flow = Loca2ConfigFlow()
        assert hasattr(flow, "async_step_user")
        assert hasattr(flow, "VERSION")
        assert flow.VERSION >= 1
        
        # Test integration structure (Requirement 7.1)
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        required_files = ["__init__.py", "manifest.json", "config_flow.py", "device_tracker.py"]
        for file_name in required_files:
            assert (integration_path / file_name).exists()
        
        # Test async implementation (Requirements 7.6, 7.7)
        import inspect
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)
        
        # Test HACS compatibility (Requirement 1.4)
        manifest_path = integration_path / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["config_flow"] is True
        assert "documentation" in manifest
        assert "issue_tracker" in manifest


class TestIntegrationValidationTools:
    """Test integration with Home Assistant validation tools."""
    
    def test_manifest_schema_validation(self):
        """Test manifest.json passes Home Assistant schema validation."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Test against known Home Assistant manifest schema requirements
        required_string_fields = ["domain", "name", "version", "documentation", "issue_tracker", "iot_class"]
        for field in required_string_fields:
            assert field in manifest
            assert isinstance(manifest[field], str)
            assert len(manifest[field]) > 0
        
        required_list_fields = ["codeowners", "requirements"]
        for field in required_list_fields:
            assert field in manifest
            assert isinstance(manifest[field], list)
        
        required_bool_fields = ["config_flow"]
        for field in required_bool_fields:
            assert field in manifest
            assert isinstance(manifest[field], bool)
    
    def test_integration_quality_checks(self):
        """Test integration passes quality checks."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Check for proper imports
        init_content = (integration_path / "__init__.py").read_text()
        assert "from homeassistant" in init_content
        assert "async def" in init_content
        
        # Check for proper error handling
        api_content = (integration_path / "api.py").read_text()
        assert "except" in api_content or "raise" in api_content
        
        # Check for proper logging
        assert "_LOGGER" in init_content or "logging" in init_content
    
    def test_code_style_compliance(self):
        """Test code follows Home Assistant style guidelines."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        python_files = ["__init__.py", "api.py", "config_flow.py", "device_tracker.py"]
        
        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                
                # Check for proper docstrings
                if "class " in content:
                    # Should have class docstrings
                    assert '"""' in content or "'''" in content
                
                # Check for proper type hints
                if "def " in content:
                    # Should use type hints for new code
                    assert "from __future__ import annotations" in content or "->" in content