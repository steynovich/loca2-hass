"""Tests for Loca2 API client."""

from datetime import datetime
from unittest.mock import AsyncMock

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.loca2.api import (
    Loca2ApiClient,
    Loca2ApiError,
    Loca2AuthError,
    Loca2ConnectionError,
    Loca2Device,
    Loca2Location,
    Loca2RateLimitError,
)


@pytest.fixture
def api_client():
    """Create API client for testing."""
    return Loca2ApiClient(
        api_key="test_api_key",
        base_url="https://api.loca2.example.com",
        timeout=5,
    )


@pytest.fixture
def mock_device_data():
    """Mock device data from API."""
    return {
        "id": "device123",
        "name": "Test Device",
        "type": "tracker",
        "battery_level": 85,
        "last_seen": "2023-12-01T10:30:00Z",
    }


@pytest.fixture
def mock_location_data():
    """Mock location data from API."""
    return {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "accuracy": 10.5,
        "timestamp": "2023-12-01T10:30:00Z",
        "address": "San Francisco, CA",
    }


class TestLoca2Device:
    """Test Loca2Device data model."""

    def test_from_dict_complete_data(self, mock_device_data):
        """Test creating device from complete data."""
        device = Loca2Device.from_dict(mock_device_data)

        assert device.id == "device123"
        assert device.name == "Test Device"
        assert device.device_type == "tracker"
        assert device.battery_level == 85
        assert device.last_seen is not None
        assert device.last_seen.year == 2023

    def test_from_dict_minimal_data(self):
        """Test creating device from minimal data."""
        data = {"id": "device456"}
        device = Loca2Device.from_dict(data)

        assert device.id == "device456"
        assert device.name == "Device device456"
        assert device.device_type == "unknown"
        assert device.battery_level is None
        assert device.last_seen is None

    def test_from_dict_invalid_date(self):
        """Test handling invalid date format."""
        data = {
            "id": "device789",
            "name": "Test Device",
            "last_seen": "invalid-date",
        }
        device = Loca2Device.from_dict(data)

        assert device.id == "device789"
        assert device.last_seen is None

    def test_validation_missing_id(self):
        """Test validation fails when ID is missing."""
        with pytest.raises(ValueError, match="Device data must contain 'id' field"):
            Loca2Device.from_dict({"name": "Test Device"})

    def test_validation_empty_id(self):
        """Test validation fails when ID is empty."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            Loca2Device.from_dict({"id": ""})

    def test_validation_none_id(self):
        """Test validation fails when ID is None."""
        with pytest.raises(ValueError, match="id cannot be None"):
            Loca2Device.from_dict({"id": None})

    def test_validation_invalid_data_type(self):
        """Test validation fails when data is not a dictionary."""
        with pytest.raises(ValueError, match="Device data must be a dictionary"):
            Loca2Device.from_dict("not a dict")

    def test_battery_level_conversion_string(self):
        """Test battery level conversion from string."""
        data = {"id": "device123", "battery_level": "75"}
        device = Loca2Device.from_dict(data)
        assert device.battery_level == 75

    def test_battery_level_conversion_string_with_percent(self):
        """Test battery level conversion from string with percent sign."""
        data = {"id": "device123", "battery_level": "85%"}
        device = Loca2Device.from_dict(data)
        assert device.battery_level == 85

    def test_battery_level_conversion_float(self):
        """Test battery level conversion from float."""
        data = {"id": "device123", "battery_level": 92.5}
        device = Loca2Device.from_dict(data)
        assert device.battery_level == 92

    def test_battery_level_out_of_range_clamping(self):
        """Test battery level clamping for out of range values."""
        data = {"id": "device123", "battery_level": 150}
        device = Loca2Device.from_dict(data)
        assert device.battery_level == 100

        data = {"id": "device123", "battery_level": -10}
        device = Loca2Device.from_dict(data)
        assert device.battery_level == 0

    def test_battery_level_invalid_format(self):
        """Test battery level with invalid format returns None."""
        data = {"id": "device123", "battery_level": "invalid"}
        device = Loca2Device.from_dict(data)
        assert device.battery_level is None

    def test_datetime_conversion_various_formats(self):
        """Test datetime conversion from various formats."""
        formats = [
            ("2023-12-01T10:30:00Z", 2023),
            ("2023-12-01T10:30:00", 2023),
            ("2023-12-01 10:30:00", 2023),
            ("2023-12-01T10:30:00.123456", 2023),
            ("2023-12-01", 2023),
        ]

        for date_str, expected_year in formats:
            data = {"id": "device123", "last_seen": date_str}
            device = Loca2Device.from_dict(data)
            assert device.last_seen is not None
            assert device.last_seen.year == expected_year

    def test_datetime_conversion_already_datetime(self):
        """Test datetime conversion when value is already datetime."""
        dt = datetime(2023, 12, 1, 10, 30, 0)
        data = {"id": "device123", "last_seen": dt}
        device = Loca2Device.from_dict(data)
        assert device.last_seen == dt

    def test_datetime_conversion_invalid_type(self):
        """Test datetime conversion with invalid type."""
        data = {"id": "device123", "last_seen": 123456}
        device = Loca2Device.from_dict(data)
        assert device.last_seen is None

    def test_string_conversion_numeric_id(self):
        """Test string conversion for numeric ID."""
        data = {"id": 12345}
        device = Loca2Device.from_dict(data)
        assert device.id == "12345"

    def test_to_dict_serialization(self):
        """Test device serialization to dictionary."""
        dt = datetime(2023, 12, 1, 10, 30, 0)
        device = Loca2Device(
            id="device123",
            name="Test Device",
            device_type="tracker",
            battery_level=85,
            last_seen=dt,
        )

        result = device.to_dict()
        expected = {
            "id": "device123",
            "name": "Test Device",
            "type": "tracker",
            "battery_level": 85,
            "last_seen": "2023-12-01T10:30:00",
        }
        assert result == expected

    def test_to_dict_serialization_none_values(self):
        """Test device serialization with None values."""
        device = Loca2Device(id="device123", name="Test Device", device_type="tracker")

        result = device.to_dict()
        expected = {
            "id": "device123",
            "name": "Test Device",
            "type": "tracker",
            "battery_level": None,
            "last_seen": None,
        }
        assert result == expected

    def test_is_online_with_recent_timestamp(self):
        """Test is_online returns True for recent timestamp."""
        recent_time = datetime.now()
        device = Loca2Device(
            id="device123",
            name="Test Device",
            device_type="tracker",
            last_seen=recent_time,
        )
        assert device.is_online() is True

    def test_is_online_with_old_timestamp(self):
        """Test is_online returns False for old timestamp."""
        from datetime import timedelta

        old_time = datetime.now() - timedelta(hours=2)
        device = Loca2Device(
            id="device123",
            name="Test Device",
            device_type="tracker",
            last_seen=old_time,
        )
        assert device.is_online() is False

    def test_is_online_with_none_timestamp(self):
        """Test is_online returns False when last_seen is None."""
        device = Loca2Device(id="device123", name="Test Device", device_type="tracker")
        assert device.is_online() is False

    def test_is_online_custom_timeout(self):
        """Test is_online with custom timeout."""
        from datetime import timedelta

        time_45_min_ago = datetime.now() - timedelta(minutes=45)
        device = Loca2Device(
            id="device123",
            name="Test Device",
            device_type="tracker",
            last_seen=time_45_min_ago,
        )
        assert device.is_online(timeout_minutes=30) is False
        assert device.is_online(timeout_minutes=60) is True

    def test_post_init_validation_invalid_battery(self):
        """Test post-init validation fails for invalid battery level."""
        with pytest.raises(
            ValueError, match="Battery level must be an integer between 0 and 100"
        ):
            Loca2Device(
                id="device123",
                name="Test Device",
                device_type="tracker",
                battery_level=150,
            )

    def test_post_init_validation_empty_name(self):
        """Test post-init validation fails for empty name."""
        with pytest.raises(ValueError, match="Device name must be a non-empty string"):
            Loca2Device(id="device123", name="", device_type="tracker")


class TestLoca2Location:
    """Test Loca2Location data model."""

    def test_from_dict_complete_data(self, mock_location_data):
        """Test creating location from complete data."""
        location = Loca2Location.from_dict(mock_location_data)

        assert location.latitude == 37.7749
        assert location.longitude == -122.4194
        assert location.accuracy == 10.5
        assert location.timestamp is not None
        assert location.address == "San Francisco, CA"

    def test_from_dict_minimal_data(self):
        """Test creating location from minimal data."""
        data = {"latitude": 40.7128, "longitude": -74.0060}
        location = Loca2Location.from_dict(data)

        assert location.latitude == 40.7128
        assert location.longitude == -74.0060
        assert location.accuracy is None
        assert location.timestamp is None
        assert location.address is None

    def test_from_dict_invalid_timestamp(self):
        """Test handling invalid timestamp format."""
        data = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timestamp": "invalid-timestamp",
        }
        location = Loca2Location.from_dict(data)

        assert location.latitude == 40.7128
        assert location.longitude == -74.0060
        assert location.timestamp is None

    def test_validation_missing_coordinates(self):
        """Test validation fails when coordinates are missing."""
        with pytest.raises(
            ValueError,
            match="Location data must contain 'latitude' and 'longitude' fields",
        ):
            Loca2Location.from_dict({"latitude": 40.7128})

        with pytest.raises(
            ValueError,
            match="Location data must contain 'latitude' and 'longitude' fields",
        ):
            Loca2Location.from_dict({"longitude": -74.0060})

    def test_validation_invalid_data_type(self):
        """Test validation fails when data is not a dictionary."""
        with pytest.raises(ValueError, match="Location data must be a dictionary"):
            Loca2Location.from_dict("not a dict")

    def test_coordinate_conversion_string(self):
        """Test coordinate conversion from string."""
        data = {"latitude": "40.7128", "longitude": "-74.0060"}
        location = Loca2Location.from_dict(data)
        assert location.latitude == 40.7128
        assert location.longitude == -74.0060

    def test_coordinate_conversion_integer(self):
        """Test coordinate conversion from integer."""
        data = {"latitude": 40, "longitude": -74}
        location = Loca2Location.from_dict(data)
        assert location.latitude == 40.0
        assert location.longitude == -74.0

    def test_coordinate_validation_out_of_range(self):
        """Test coordinate validation for out of range values."""
        with pytest.raises(ValueError, match="latitude .* is outside valid range"):
            Loca2Location.from_dict({"latitude": 91.0, "longitude": 0.0})

        with pytest.raises(ValueError, match="latitude .* is outside valid range"):
            Loca2Location.from_dict({"latitude": -91.0, "longitude": 0.0})

        with pytest.raises(ValueError, match="longitude .* is outside valid range"):
            Loca2Location.from_dict({"latitude": 0.0, "longitude": 181.0})

        with pytest.raises(ValueError, match="longitude .* is outside valid range"):
            Loca2Location.from_dict({"latitude": 0.0, "longitude": -181.0})

    def test_coordinate_validation_none_values(self):
        """Test coordinate validation fails for None values."""
        with pytest.raises(ValueError, match="latitude cannot be None"):
            Loca2Location.from_dict({"latitude": None, "longitude": 0.0})

        with pytest.raises(ValueError, match="longitude cannot be None"):
            Loca2Location.from_dict({"latitude": 0.0, "longitude": None})

    def test_coordinate_validation_empty_string(self):
        """Test coordinate validation fails for empty strings."""
        with pytest.raises(ValueError, match="latitude cannot be empty"):
            Loca2Location.from_dict({"latitude": "", "longitude": 0.0})

        with pytest.raises(ValueError, match="longitude cannot be empty"):
            Loca2Location.from_dict({"latitude": 0.0, "longitude": ""})

    def test_coordinate_validation_invalid_type(self):
        """Test coordinate validation fails for invalid types."""
        with pytest.raises(ValueError, match="Cannot convert latitude to float"):
            Loca2Location.from_dict({"latitude": "invalid", "longitude": 0.0})

        with pytest.raises(ValueError, match="Cannot convert longitude to float"):
            Loca2Location.from_dict({"latitude": 0.0, "longitude": "invalid"})

    def test_accuracy_conversion_string(self):
        """Test accuracy conversion from string."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "accuracy": "15.5"}
        location = Loca2Location.from_dict(data)
        assert location.accuracy == 15.5

    def test_accuracy_conversion_integer(self):
        """Test accuracy conversion from integer."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "accuracy": 20}
        location = Loca2Location.from_dict(data)
        assert location.accuracy == 20.0

    def test_accuracy_conversion_negative_clamping(self):
        """Test accuracy clamping for negative values."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "accuracy": -5.0}
        location = Loca2Location.from_dict(data)
        assert location.accuracy == 0.0

    def test_accuracy_conversion_invalid_format(self):
        """Test accuracy with invalid format returns None."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "accuracy": "invalid"}
        location = Loca2Location.from_dict(data)
        assert location.accuracy is None

    def test_accuracy_conversion_empty_string(self):
        """Test accuracy with empty string returns None."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "accuracy": ""}
        location = Loca2Location.from_dict(data)
        assert location.accuracy is None

    def test_address_conversion_string(self):
        """Test address conversion from string."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "address": "New York, NY"}
        location = Loca2Location.from_dict(data)
        assert location.address == "New York, NY"

    def test_address_conversion_non_string(self):
        """Test address conversion from non-string types."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "address": 12345}
        location = Loca2Location.from_dict(data)
        assert location.address == "12345"

    def test_address_conversion_empty_string(self):
        """Test address with empty string returns None."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "address": ""}
        location = Loca2Location.from_dict(data)
        assert location.address is None

    def test_address_conversion_whitespace_only(self):
        """Test address with whitespace only returns None."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "address": "   "}
        location = Loca2Location.from_dict(data)
        assert location.address is None

    def test_datetime_conversion_various_formats(self):
        """Test datetime conversion from various formats."""
        formats = [
            ("2023-12-01T10:30:00Z", 2023),
            ("2023-12-01T10:30:00", 2023),
            ("2023-12-01 10:30:00", 2023),
            ("2023-12-01T10:30:00.123456", 2023),
            ("2023-12-01", 2023),
        ]

        for date_str, expected_year in formats:
            data = {"latitude": 40.7128, "longitude": -74.0060, "timestamp": date_str}
            location = Loca2Location.from_dict(data)
            assert location.timestamp is not None
            assert location.timestamp.year == expected_year

    def test_datetime_conversion_already_datetime(self):
        """Test datetime conversion when value is already datetime."""
        dt = datetime(2023, 12, 1, 10, 30, 0)
        data = {"latitude": 40.7128, "longitude": -74.0060, "timestamp": dt}
        location = Loca2Location.from_dict(data)
        assert location.timestamp == dt

    def test_datetime_conversion_invalid_type(self):
        """Test datetime conversion with invalid type."""
        data = {"latitude": 40.7128, "longitude": -74.0060, "timestamp": 123456}
        location = Loca2Location.from_dict(data)
        assert location.timestamp is None

    def test_to_dict_serialization(self):
        """Test location serialization to dictionary."""
        dt = datetime(2023, 12, 1, 10, 30, 0)
        location = Loca2Location(
            latitude=40.7128,
            longitude=-74.0060,
            accuracy=15.5,
            timestamp=dt,
            address="New York, NY",
        )

        result = location.to_dict()
        expected = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy": 15.5,
            "timestamp": "2023-12-01T10:30:00",
            "address": "New York, NY",
        }
        assert result == expected

    def test_to_dict_serialization_none_values(self):
        """Test location serialization with None values."""
        location = Loca2Location(latitude=40.7128, longitude=-74.0060)

        result = location.to_dict()
        expected = {
            "latitude": 40.7128,
            "longitude": -74.0060,
            "accuracy": None,
            "timestamp": None,
            "address": None,
        }
        assert result == expected

    def test_distance_calculation(self):
        """Test distance calculation between two locations."""
        loc1 = Loca2Location(latitude=40.7128, longitude=-74.0060)  # New York
        loc2 = Loca2Location(latitude=34.0522, longitude=-118.2437)  # Los Angeles

        distance = loc1.distance_to(loc2)
        # Distance between NYC and LA is approximately 3944 km
        assert 3900000 < distance < 4000000  # Allow some tolerance

    def test_distance_calculation_same_location(self):
        """Test distance calculation for same location."""
        loc1 = Loca2Location(latitude=40.7128, longitude=-74.0060)
        loc2 = Loca2Location(latitude=40.7128, longitude=-74.0060)

        distance = loc1.distance_to(loc2)
        assert distance == 0.0

    def test_distance_calculation_close_locations(self):
        """Test distance calculation for close locations."""
        loc1 = Loca2Location(latitude=40.7128, longitude=-74.0060)
        loc2 = Loca2Location(latitude=40.7129, longitude=-74.0061)  # Very close

        distance = loc1.distance_to(loc2)
        assert 0 < distance < 20  # Should be less than 20 meters

    def test_is_valid_coordinates_valid(self):
        """Test is_valid_coordinates returns True for valid coordinates."""
        location = Loca2Location(latitude=40.7128, longitude=-74.0060)
        assert location.is_valid_coordinates() is True

    def test_is_valid_coordinates_zero_zero(self):
        """Test is_valid_coordinates returns False for 0,0 coordinates."""
        location = Loca2Location(latitude=0.0, longitude=0.0)
        assert location.is_valid_coordinates() is False

    def test_is_valid_coordinates_near_zero(self):
        """Test is_valid_coordinates returns True for coordinates near but not exactly 0,0."""
        location = Loca2Location(latitude=0.001, longitude=0.001)
        assert location.is_valid_coordinates() is True

    def test_post_init_validation_invalid_latitude(self):
        """Test post-init validation fails for invalid latitude."""
        with pytest.raises(
            ValueError, match="Latitude must be between -90 and 90 degrees"
        ):
            Loca2Location(latitude=91.0, longitude=0.0)

    def test_post_init_validation_invalid_longitude(self):
        """Test post-init validation fails for invalid longitude."""
        with pytest.raises(
            ValueError, match="Longitude must be between -180 and 180 degrees"
        ):
            Loca2Location(latitude=0.0, longitude=181.0)

    def test_post_init_validation_invalid_accuracy(self):
        """Test post-init validation fails for invalid accuracy."""
        with pytest.raises(ValueError, match="Accuracy must be a non-negative number"):
            Loca2Location(latitude=0.0, longitude=0.0, accuracy=-5.0)


class TestLoca2ApiClient:
    """Test Loca2ApiClient functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager."""
        async with Loca2ApiClient("key", "https://api.example.com") as client:
            assert client._session is not None
        # Session should be closed after context exit

    @pytest.mark.asyncio
    async def test_authenticate_success(self, api_client):
        """Test successful authentication."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/auth/validate",
                payload={"status": "ok"},
            )

            result = await api_client.authenticate()
            assert result is True

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, api_client):
        """Test authentication failure."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/auth/validate",
                status=401,
            )

            result = await api_client.authenticate()
            assert result is False

    @pytest.mark.asyncio
    async def test_get_devices_success(self, api_client, mock_device_data):
        """Test successful device retrieval."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                payload={"devices": [mock_device_data]},
            )

            devices = await api_client.get_devices()
            assert len(devices) == 1
            assert devices[0].id == "device123"
            assert devices[0].name == "Test Device"

    @pytest.mark.asyncio
    async def test_get_devices_empty_response(self, api_client):
        """Test handling empty device list."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                payload={"devices": []},
            )

            devices = await api_client.get_devices()
            assert len(devices) == 0

    @pytest.mark.asyncio
    async def test_get_devices_invalid_data(self, api_client):
        """Test handling invalid device data."""
        invalid_device = {"id": "device123"}  # Missing required fields
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                payload={"devices": [invalid_device, {"invalid": "data"}]},
            )

            devices = await api_client.get_devices()
            # Should skip invalid devices and continue
            assert len(devices) == 1
            assert devices[0].id == "device123"

    @pytest.mark.asyncio
    async def test_get_device_location_success(self, api_client, mock_location_data):
        """Test successful location retrieval."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices/device123/location",
                payload={"location": mock_location_data},
            )

            location = await api_client.get_device_location("device123")
            assert location.latitude == 37.7749
            assert location.longitude == -122.4194
            assert location.accuracy == 10.5

    @pytest.mark.asyncio
    async def test_get_device_location_no_data(self, api_client):
        """Test handling missing location data."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices/device123/location",
                payload={},
            )

            with pytest.raises(Loca2ApiError, match="No location data"):
                await api_client.get_device_location("device123")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, api_client):
        """Test rate limit handling."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                status=429,
            )

            with pytest.raises(Loca2RateLimitError):
                await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_auth_error(self, api_client):
        """Test authentication error handling."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                status=401,
            )

            with pytest.raises(Loca2AuthError):
                await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_generic_api_error(self, api_client):
        """Test generic API error handling."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                status=500,
                payload={"error": "Internal server error"},
            )

            with pytest.raises(Loca2ApiError, match="API request failed"):
                await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_connection_timeout(self, api_client):
        """Test connection timeout handling."""
        with aioresponses() as m:
            # Simulate timeout by raising TimeoutError for all attempts
            for _ in range(3):  # DEFAULT_RETRIES
                m.get(
                    "https://api.loca2.example.com/api/devices",
                    exception=TimeoutError(),
                )

            with pytest.raises(Loca2ConnectionError, match="Request timeout"):
                await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_connection_error(self, api_client):
        """Test connection error handling."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                exception=aiohttp.ClientError("Connection failed"),
            )

            with pytest.raises(Loca2ConnectionError, match="Connection failed"):
                await api_client.get_devices()

    @pytest.mark.asyncio
    async def test_retry_logic_success_on_retry(self, api_client, mock_device_data):
        """Test retry logic succeeds on second attempt."""
        with aioresponses() as m:
            # First call fails, second succeeds
            m.get(
                "https://api.loca2.example.com/api/devices",
                exception=aiohttp.ClientError("Temporary failure"),
            )
            m.get(
                "https://api.loca2.example.com/api/devices",
                payload={"devices": [mock_device_data]},
            )

            devices = await api_client.get_devices()
            assert len(devices) == 1
            assert devices[0].id == "device123"

    @pytest.mark.asyncio
    async def test_test_connection(self, api_client):
        """Test connection testing method."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/auth/validate",
                payload={"status": "ok"},
            )

            result = await api_client.test_connection()
            assert result is True

    @pytest.mark.asyncio
    async def test_close_session(self, api_client):
        """Test session cleanup."""
        # Create session
        await api_client._get_session()
        assert api_client._session is not None

        # Close session
        await api_client.close()
        assert api_client._session is None

    @pytest.mark.asyncio
    async def test_custom_session(self):
        """Test using custom session."""
        mock_session = AsyncMock()
        client = Loca2ApiClient("key", "https://api.example.com", session=mock_session)

        # Should not close custom session
        await client.close()
        mock_session.close.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_headers(self, api_client):
        """Test proper request headers are sent."""
        with aioresponses() as m:
            m.get(
                "https://api.loca2.example.com/api/devices",
                payload={"devices": []},
            )

            await api_client.get_devices()
            await api_client.close()  # Clean up session

            # Check that the request was made with proper headers
            # aioresponses uses URL objects as keys, so we need to find the right key
            requests_made = list(m.requests.keys())
            assert len(requests_made) > 0

            # Find the GET request to /api/devices
            device_request_key = None
            for key in requests_made:
                if key[0] == "GET" and "/api/devices" in str(key[1]):
                    device_request_key = key
                    break

            assert device_request_key is not None
            request = m.requests[device_request_key][0]
            assert request.kwargs["headers"]["Authorization"] == "Bearer test_api_key"
            assert request.kwargs["headers"]["Content-Type"] == "application/json"
