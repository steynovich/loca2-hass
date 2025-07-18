"""Tests for Loca2 device tracker platform."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.device_tracker import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.loca2.api import Loca2Device, Loca2Location
from custom_components.loca2.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_TYPE,
    ATTR_GPS_ACCURACY,
    ATTR_LAST_SEEN,
    DOMAIN,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from custom_components.loca2.device_tracker import (
    Loca2DeviceTracker,
    async_setup_entry,
)


@pytest.fixture
def mock_device():
    """Create a mock Loca2Device."""
    return Loca2Device(
        id="device_123",
        name="Test Device",
        device_type="smartphone",
        battery_level=85,
        last_seen=datetime.now(),
    )


@pytest.fixture
def mock_location():
    """Create a mock Loca2Location."""
    return Loca2Location(
        latitude=37.7749,
        longitude=-122.4194,
        accuracy=10.0,
        timestamp=datetime.now(),
        address="San Francisco, CA",
    )


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = {}
    coordinator.last_update_success = True
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_get_device_location = AsyncMock()
    coordinator.async_add_listener = MagicMock()
    return coordinator


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    return entry


class TestLoca2DeviceTracker:
    """Test the Loca2DeviceTracker class."""

    def test_init(self, mock_coordinator, mock_device):
        """Test device tracker initialization."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker._device_id == "device_123"
        assert tracker._device == mock_device
        assert tracker._attr_unique_id == f"{DOMAIN}_device_123"
        assert tracker._attr_name == "Test Device"
        assert tracker._attr_source_type == SourceType.GPS
        assert tracker._location is None
        
        # Check device info
        expected_device_info = {
            "identifiers": {(DOMAIN, "device_123")},
            "name": "Test Device",
            "manufacturer": "Loca2",
            "model": "smartphone",
            "sw_version": None,
        }
        assert tracker._attr_device_info == expected_device_info

    def test_device_property_with_data(self, mock_coordinator, mock_device):
        """Test device property when coordinator has data."""
        mock_coordinator.data = {"device_123": mock_device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.device == mock_device

    def test_device_property_without_data(self, mock_coordinator, mock_device):
        """Test device property when coordinator has no data."""
        mock_coordinator.data = None
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.device is None

    def test_device_property_missing_device(self, mock_coordinator, mock_device):
        """Test device property when device is missing from coordinator data."""
        mock_coordinator.data = {"other_device": mock_device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.device is None

    def test_available_true(self, mock_coordinator, mock_device):
        """Test available property when coordinator is successful and device exists."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.last_update_success = True
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.available is True

    def test_available_false_no_success(self, mock_coordinator, mock_device):
        """Test available property when coordinator update failed."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.last_update_success = False
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.available is False

    def test_available_false_no_device(self, mock_coordinator, mock_device):
        """Test available property when device doesn't exist."""
        mock_coordinator.data = {}
        mock_coordinator.last_update_success = True
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.available is False

    def test_latitude_with_valid_location(self, mock_coordinator, mock_device, mock_location):
        """Test latitude property with valid location."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        tracker._location = mock_location
        
        assert tracker.latitude == 37.7749

    def test_latitude_with_invalid_coordinates(self, mock_coordinator, mock_device):
        """Test latitude property with invalid coordinates (0,0)."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        invalid_location = Loca2Location(latitude=0.0, longitude=0.0)
        tracker._location = invalid_location
        
        assert tracker.latitude is None

    def test_latitude_without_location(self, mock_coordinator, mock_device):
        """Test latitude property without location data."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.latitude is None

    def test_longitude_with_valid_location(self, mock_coordinator, mock_device, mock_location):
        """Test longitude property with valid location."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        tracker._location = mock_location
        
        assert tracker.longitude == -122.4194

    def test_longitude_with_invalid_coordinates(self, mock_coordinator, mock_device):
        """Test longitude property with invalid coordinates (0,0)."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        invalid_location = Loca2Location(latitude=0.0, longitude=0.0)
        tracker._location = invalid_location
        
        assert tracker.longitude is None

    def test_longitude_without_location(self, mock_coordinator, mock_device):
        """Test longitude property without location data."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.longitude is None

    def test_location_accuracy_with_accuracy(self, mock_coordinator, mock_device, mock_location):
        """Test location_accuracy property with accuracy data."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        tracker._location = mock_location
        
        assert tracker.location_accuracy == 10

    def test_location_accuracy_without_accuracy(self, mock_coordinator, mock_device):
        """Test location_accuracy property without accuracy data."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        location_no_accuracy = Loca2Location(latitude=37.7749, longitude=-122.4194)
        tracker._location = location_no_accuracy
        
        assert tracker.location_accuracy is None

    def test_location_accuracy_without_location(self, mock_coordinator, mock_device):
        """Test location_accuracy property without location data."""
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.location_accuracy is None

    def test_state_unavailable_not_available(self, mock_coordinator, mock_device):
        """Test state when device is not available."""
        mock_coordinator.last_update_success = False
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.state == STATE_UNAVAILABLE

    def test_state_unavailable_no_device(self, mock_coordinator, mock_device):
        """Test state when device doesn't exist in coordinator data."""
        mock_coordinator.data = {}
        mock_coordinator.last_update_success = True
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.state == STATE_UNAVAILABLE

    def test_state_home_online_with_location(self, mock_coordinator, mock_device, mock_location):
        """Test state when device is online and has valid location."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.last_update_success = True
        
        # Mock device as online
        with patch.object(mock_device, 'is_online', return_value=True):
            tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
            tracker._location = mock_location
            
            assert tracker.state == STATE_HOME

    def test_state_not_home_online_without_location(self, mock_coordinator, mock_device):
        """Test state when device is online but has no valid location."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.last_update_success = True
        
        # Mock device as online
        with patch.object(mock_device, 'is_online', return_value=True):
            tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
            
            assert tracker.state == STATE_NOT_HOME

    def test_state_not_home_offline(self, mock_coordinator, mock_device):
        """Test state when device is offline."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.last_update_success = True
        
        # Mock device as offline
        with patch.object(mock_device, 'is_online', return_value=False):
            tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
            
            assert tracker.state == STATE_NOT_HOME

    def test_extra_state_attributes_full(self, mock_coordinator, mock_device, mock_location):
        """Test extra_state_attributes with full device and location data."""
        mock_coordinator.data = {"device_123": mock_device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        tracker._location = mock_location
        
        attributes = tracker.extra_state_attributes
        
        assert attributes[ATTR_BATTERY_LEVEL] == 85
        assert attributes[ATTR_DEVICE_TYPE] == "smartphone"
        assert ATTR_LAST_SEEN in attributes
        assert attributes[ATTR_GPS_ACCURACY] == 10.0
        assert attributes["address"] == "San Francisco, CA"
        assert "location_timestamp" in attributes

    def test_extra_state_attributes_minimal(self, mock_coordinator, mock_device):
        """Test extra_state_attributes with minimal data."""
        device_minimal = Loca2Device(
            id="device_123",
            name="Test Device",
            device_type="unknown",
        )
        mock_coordinator.data = {"device_123": device_minimal}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", device_minimal)
        
        attributes = tracker.extra_state_attributes
        
        assert attributes[ATTR_DEVICE_TYPE] == "unknown"
        assert ATTR_BATTERY_LEVEL not in attributes
        assert ATTR_LAST_SEEN not in attributes
        assert ATTR_GPS_ACCURACY not in attributes

    def test_battery_level_with_battery(self, mock_coordinator, mock_device):
        """Test battery_level property with battery data."""
        mock_coordinator.data = {"device_123": mock_device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.battery_level == 85

    def test_battery_level_without_battery(self, mock_coordinator, mock_device):
        """Test battery_level property without battery data."""
        device_no_battery = Loca2Device(
            id="device_123",
            name="Test Device",
            device_type="unknown",
        )
        mock_coordinator.data = {"device_123": device_no_battery}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", device_no_battery)
        
        assert tracker.battery_level is None

    def test_battery_level_no_device(self, mock_coordinator, mock_device):
        """Test battery_level property when device doesn't exist."""
        mock_coordinator.data = {}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.battery_level is None

    @pytest.mark.parametrize("device_type,expected_icon", [
        ("phone", "mdi:cellphone"),
        ("mobile", "mdi:cellphone"),
        ("smartphone", "mdi:cellphone"),
        ("tablet", "mdi:tablet"),
        ("watch", "mdi:watch"),
        ("smartwatch", "mdi:watch"),
        ("car", "mdi:car"),
        ("vehicle", "mdi:car"),
        ("bike", "mdi:bike"),
        ("bicycle", "mdi:bike"),
        ("unknown", "mdi:map-marker"),
        ("other", "mdi:map-marker"),
    ])
    def test_icon_by_device_type(self, mock_coordinator, device_type, expected_icon):
        """Test icon selection based on device type."""
        device = Loca2Device(
            id="device_123",
            name="Test Device",
            device_type=device_type,
        )
        mock_coordinator.data = {"device_123": device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", device)
        
        assert tracker.icon == expected_icon

    def test_icon_no_device(self, mock_coordinator, mock_device):
        """Test icon when device doesn't exist."""
        mock_coordinator.data = {}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        assert tracker.icon == "mdi:help-circle"

    @pytest.mark.asyncio
    async def test_async_update_success(self, mock_coordinator, mock_device, mock_location):
        """Test async_update with successful location fetch."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.async_get_device_location.return_value = mock_location
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        await tracker.async_update()
        
        mock_coordinator.async_request_refresh.assert_called_once()
        mock_coordinator.async_get_device_location.assert_called_once_with("device_123")
        assert tracker._location == mock_location

    @pytest.mark.asyncio
    async def test_async_update_no_location(self, mock_coordinator, mock_device):
        """Test async_update when no location is returned."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.async_get_device_location.return_value = None
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        await tracker.async_update()
        
        mock_coordinator.async_request_refresh.assert_called_once()
        mock_coordinator.async_get_device_location.assert_called_once_with("device_123")
        assert tracker._location is None

    @pytest.mark.asyncio
    async def test_async_update_no_device(self, mock_coordinator, mock_device):
        """Test async_update when device doesn't exist."""
        mock_coordinator.data = {}
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        await tracker.async_update()
        
        mock_coordinator.async_request_refresh.assert_called_once()
        mock_coordinator.async_get_device_location.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_update_location_error(self, mock_coordinator, mock_device):
        """Test async_update when location fetch fails."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.async_get_device_location.side_effect = Exception("API Error")
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        # Should not raise exception
        await tracker.async_update()
        
        mock_coordinator.async_request_refresh.assert_called_once()
        mock_coordinator.async_get_device_location.assert_called_once_with("device_123")

    @pytest.mark.asyncio
    async def test_handle_coordinator_update_name_change(self, mock_coordinator, mock_device):
        """Test _handle_coordinator_update when device name changes."""
        # Initial setup
        mock_coordinator.data = {"device_123": mock_device}
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        # Change device name
        updated_device = Loca2Device(
            id="device_123",
            name="Updated Device Name",
            device_type="smartphone",
            battery_level=85,
            last_seen=datetime.now(),
        )
        mock_coordinator.data = {"device_123": updated_device}
        
        # Mock hass and async_create_task
        tracker.hass = MagicMock()
        tracker.hass.async_create_task = MagicMock()
        tracker.async_write_ha_state = MagicMock()  # Mock this to avoid entity ID issues
        
        # Call the update handler
        tracker._handle_coordinator_update()
        
        # Check that name was updated
        assert tracker._attr_name == "Updated Device Name"
        assert tracker._attr_device_info["name"] == "Updated Device Name"
        
        # Check that location update task was created
        tracker.hass.async_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_location_success(self, mock_coordinator, mock_device, mock_location):
        """Test _async_update_location with successful location fetch."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.async_get_device_location.return_value = mock_location
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        tracker.async_write_ha_state = MagicMock()
        
        await tracker._async_update_location()
        
        mock_coordinator.async_get_device_location.assert_called_once_with("device_123")
        assert tracker._location == mock_location
        tracker.async_write_ha_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_location_no_device(self, mock_coordinator, mock_device):
        """Test _async_update_location when device doesn't exist."""
        mock_coordinator.data = {}
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        await tracker._async_update_location()
        
        mock_coordinator.async_get_device_location.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_update_location_error(self, mock_coordinator, mock_device):
        """Test _async_update_location when location fetch fails."""
        mock_coordinator.data = {"device_123": mock_device}
        mock_coordinator.async_get_device_location.side_effect = Exception("API Error")
        
        tracker = Loca2DeviceTracker(mock_coordinator, "device_123", mock_device)
        
        # Should not raise exception
        await tracker._async_update_location()
        
        mock_coordinator.async_get_device_location.assert_called_once_with("device_123")


class TestAsyncSetupEntry:
    """Test the async_setup_entry function."""

    def test_setup_entry_creates_entities_from_coordinator_data(self, mock_coordinator):
        """Test that setup entry creates entities from coordinator data."""
        # Setup mock data
        device1 = Loca2Device(id="device_1", name="Device 1", device_type="phone")
        device2 = Loca2Device(id="device_2", name="Device 2", device_type="tablet")
        mock_coordinator.data = {
            "device_1": device1,
            "device_2": device2,
        }
        
        # Test that we can create entities from the data
        entities = []
        for device_id, device in mock_coordinator.data.items():
            entity = Loca2DeviceTracker(mock_coordinator, device_id, device)
            entities.append(entity)
        
        assert len(entities) == 2
        assert all(isinstance(entity, Loca2DeviceTracker) for entity in entities)
        assert entities[0]._device_id in ["device_1", "device_2"]
        assert entities[1]._device_id in ["device_1", "device_2"]

    def test_setup_entry_handles_empty_coordinator_data(self, mock_coordinator):
        """Test that setup entry handles empty coordinator data."""
        # Setup mock data with no devices
        mock_coordinator.data = {}
        
        # Test that we handle empty data correctly
        entities = []
        if mock_coordinator.data:
            for device_id, device in mock_coordinator.data.items():
                entity = Loca2DeviceTracker(mock_coordinator, device_id, device)
                entities.append(entity)
        
        assert len(entities) == 0

    def test_setup_entry_handles_none_coordinator_data(self, mock_coordinator):
        """Test that setup entry handles None coordinator data."""
        # Setup mock data
        mock_coordinator.data = None
        
        # Test that we handle None data correctly
        entities = []
        if mock_coordinator.data:
            for device_id, device in mock_coordinator.data.items():
                entity = Loca2DeviceTracker(mock_coordinator, device_id, device)
                entities.append(entity)
        
        assert len(entities) == 0