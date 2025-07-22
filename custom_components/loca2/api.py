"""Loca2 API client for Home Assistant integration."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

# API endpoints
AUTH_ENDPOINT = "/apilogin"
DEVICES_ENDPOINT = "/devices"
ASSET_STATUS_ENDPOINT = "/assetstatuslist"

# Default timeout for API requests
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
RETRY_DELAY = 1.0


class Loca2ApiError(Exception):
    """Base exception for Loca2 API errors."""


class Loca2AuthError(Loca2ApiError):
    """Authentication error."""


class Loca2ConnectionError(Loca2ApiError):
    """Connection error."""


class Loca2RateLimitError(Loca2ApiError):
    """Rate limit exceeded error."""


@dataclass
class Loca2Device:
    """Represents a Loca2 device with asset, spot, and history information."""

    # Asset information
    id: str
    name: str
    device_type: str
    serial: str | None = None
    brand: str | None = None
    model: str | None = None
    group: int | None = None
    asset_type_id: int | None = None

    # Device information
    device_id: int | None = None
    device_type_id: int | None = None
    device_version: int | None = None

    # Location information (from Spot)
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    zipcode: str | None = None
    location_time: datetime | None = None

    # Status information (from History)
    battery_level: int | None = None
    last_seen: datetime | None = None
    speed: float | None = None
    motion: int | None = None
    signal_strength: int | None = None
    gps_accuracy: float | None = None
    satellites: int | None = None

    def __post_init__(self) -> None:
        """Validate data after initialization."""
        self._validate_data()

    def _validate_data(self) -> None:
        """Validate device data."""
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Device ID must be a non-empty string")

        if not self.name or not isinstance(self.name, str):
            raise ValueError("Device name must be a non-empty string")

        if not isinstance(self.device_type, str):
            raise ValueError("Device type must be a string")

        if self.battery_level is not None:
            if not isinstance(self.battery_level, int) or not (
                0 <= self.battery_level <= 100
            ):
                raise ValueError("Battery level must be an integer between 0 and 100")

        if self.last_seen is not None and not isinstance(self.last_seen, datetime):
            raise ValueError("Last seen must be a datetime object")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Loca2Device:
        """Create Loca2Device from asset status API response data with validation."""
        if not isinstance(data, dict):
            raise ValueError("Device data must be a dictionary")

        # Extract main sections
        asset_data = data.get("Asset", {})
        device_data = data.get("Device", {})
        spot_data = data.get("Spot", {})
        history_data = data.get("History", {})

        if not asset_data:
            raise ValueError("Asset data is required")

        # Asset information
        asset_id = str(asset_data.get("id", "unknown"))
        name = asset_data.get("label", f"Asset {asset_id}")
        device_type = cls._get_device_type_from_id(asset_data.get("type"))

        # Device information
        device_id = device_data.get("id") if device_data else None
        device_type_id = device_data.get("type") if device_data else None
        device_version = device_data.get("version") if device_data else None

        # Location information from Spot
        latitude = spot_data.get("latitude") if spot_data else None
        longitude = spot_data.get("longitude") if spot_data else None
        location_time = (
            cls._convert_timestamp(spot_data.get("time")) if spot_data else None
        )

        # Address information
        address_parts = []
        if spot_data:
            if spot_data.get("street"):
                address_parts.append(spot_data["street"])
            if spot_data.get("number"):
                address_parts.append(spot_data["number"])
        address = " ".join(address_parts) if address_parts else None

        city = spot_data.get("city") if spot_data else None
        state = spot_data.get("state") if spot_data else None
        country = spot_data.get("country") if spot_data else None
        zipcode = spot_data.get("zipcode") if spot_data else None

        # Status information from History
        battery_level = cls._convert_battery_level(history_data.get("charge")) if history_data else None
        last_seen = (
            cls._convert_timestamp(history_data.get("time")) if history_data else None
        )
        speed = history_data.get("speed") if history_data else None
        motion = history_data.get("motion") if history_data else None
        signal_strength = history_data.get("strength") if history_data else None
        gps_accuracy = history_data.get("HDOP") if history_data else None
        satellites = history_data.get("SATU") if history_data else None

        return cls(
            id=asset_id,
            name=name,
            device_type=device_type,
            serial=asset_data.get("serial"),
            brand=asset_data.get("brand"),
            model=asset_data.get("model"),
            group=asset_data.get("group"),
            asset_type_id=asset_data.get("type"),
            device_id=device_id,
            device_type_id=device_type_id,
            device_version=device_version,
            latitude=latitude,
            longitude=longitude,
            address=address,
            city=city,
            state=state,
            country=country,
            zipcode=zipcode,
            location_time=location_time,
            battery_level=battery_level,
            last_seen=last_seen,
            speed=speed,
            motion=motion,
            signal_strength=signal_strength,
            gps_accuracy=gps_accuracy,
            satellites=satellites,
        )

    @staticmethod
    def _convert_to_string(value: Any, field_name: str) -> str:
        """Convert value to string with validation."""
        if value is None:
            raise ValueError(f"{field_name} cannot be None")

        try:
            str_value = str(value).strip()
            if not str_value:
                raise ValueError(f"{field_name} cannot be empty")
            return str_value
        except Exception as err:
            raise ValueError(f"Cannot convert {field_name} to string: {err}") from err

    @staticmethod
    def _convert_battery_level(value: Any) -> int | None:
        """Convert and validate battery level."""
        if value is None:
            return None

        try:
            if isinstance(value, str):
                # Handle string representations
                value = value.strip()
                if not value:
                    return None
                # Remove percentage sign if present
                if value.endswith("%"):
                    value = value[:-1]
                battery_int = int(float(value))
            elif isinstance(value, int | float):
                battery_int = int(value)
            else:
                raise ValueError(f"Invalid battery level type: {type(value)}")

            if not (0 <= battery_int <= 100):
                _LOGGER.warning(
                    "Battery level %d is outside valid range (0-100), clamping",
                    battery_int,
                )
                battery_int = max(0, min(100, battery_int))

            return battery_int

        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid battery level format: %s - %s", value, err)
            return None

    @staticmethod
    def _convert_datetime(value: Any, field_name: str) -> datetime | None:
        """Convert various datetime formats to datetime object."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            _LOGGER.warning(
                "Invalid %s format (not string): %s", field_name, type(value)
            )
            return None

        value = value.strip()
        if not value:
            return None

        # Try various datetime formats
        formats_to_try = [
            # ISO format with Z
            lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
            # ISO format without timezone
            lambda x: datetime.fromisoformat(x),
            # Common formats
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"),
            lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"),
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%f"),
            lambda x: datetime.strptime(x, "%Y-%m-%d"),
        ]

        for format_func in formats_to_try:
            try:
                return format_func(value)
            except (ValueError, TypeError):
                continue

        _LOGGER.warning("Could not parse %s datetime: %s", field_name, value)
        return None

    def to_dict(self) -> dict[str, Any]:
        """Convert device to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.device_type,
            "battery_level": self.battery_level,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }

    def is_online(self, timeout_minutes: int = 30) -> bool:
        """Check if device is considered online based on last seen time."""
        if self.last_seen is None:
            return False

        from datetime import timedelta

        timeout = timedelta(minutes=timeout_minutes)
        return (datetime.now(self.last_seen.tzinfo) - self.last_seen) <= timeout

    @staticmethod
    def _convert_timestamp(timestamp: Any) -> datetime | None:
        """Convert Unix timestamp to datetime object."""
        if timestamp is None:
            return None

        try:
            if isinstance(timestamp, int | float):
                # Handle both seconds and milliseconds timestamps
                if timestamp > 1e10:  # Likely milliseconds
                    timestamp = timestamp / 1000
                return datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                timestamp_float = float(timestamp)
                if timestamp_float > 1e10:  # Likely milliseconds
                    timestamp_float = timestamp_float / 1000
                return datetime.fromtimestamp(timestamp_float)
        except (ValueError, TypeError, OSError) as err:
            _LOGGER.warning("Could not parse timestamp %s: %s", timestamp, err)

        return None

    @staticmethod
    def _get_device_type_from_id(type_id: int | None) -> str:
        """Map Loca2 asset type ID to readable device type."""
        if type_id is None:
            return "unknown"

        # Map based on common Loca2 asset types
        type_mapping = {
            0: "unknown",
            1: "gps_tracker",
            2: "marine_tracker",
            3: "vehicle_tracker",
            4: "personal_tracker",
            5: "asset_tracker",
        }

        return type_mapping.get(type_id, f"tracker_type_{type_id}")


@dataclass
class Loca2Location:
    """Represents a device location."""

    latitude: float
    longitude: float
    accuracy: float | None = None
    timestamp: datetime | None = None
    address: str | None = None

    def __post_init__(self) -> None:
        """Validate data after initialization."""
        self._validate_data()

    def _validate_data(self) -> None:
        """Validate location data."""
        if not isinstance(self.latitude, int | float):
            raise ValueError("Latitude must be a number")

        if not isinstance(self.longitude, int | float):
            raise ValueError("Longitude must be a number")

        if not (-90 <= self.latitude <= 90):
            raise ValueError("Latitude must be between -90 and 90 degrees")

        if not (-180 <= self.longitude <= 180):
            raise ValueError("Longitude must be between -180 and 180 degrees")

        if self.accuracy is not None:
            if not isinstance(self.accuracy, int | float) or self.accuracy < 0:
                raise ValueError("Accuracy must be a non-negative number")

        if self.timestamp is not None and not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")

        if self.address is not None and not isinstance(self.address, str):
            raise ValueError("Address must be a string")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Loca2Location:
        """Create Loca2Location from API response data with validation."""
        if not isinstance(data, dict):
            raise ValueError("Location data must be a dictionary")

        if "latitude" not in data or "longitude" not in data:
            raise ValueError(
                "Location data must contain 'latitude' and 'longitude' fields"
            )

        # Convert and validate coordinates
        latitude = cls._convert_coordinate(data["latitude"], "latitude", -90, 90)
        longitude = cls._convert_coordinate(data["longitude"], "longitude", -180, 180)

        # Convert and validate accuracy
        accuracy = cls._convert_accuracy(data.get("accuracy"))

        # Convert and validate timestamp
        timestamp = cls._convert_datetime(data.get("timestamp"), "timestamp")

        # Convert and validate address
        address = cls._convert_address(data.get("address"))

        return cls(
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            timestamp=timestamp,
            address=address,
        )

    @staticmethod
    def _convert_coordinate(
        value: Any, coord_name: str, min_val: float, max_val: float
    ) -> float:
        """Convert and validate coordinate values."""
        if value is None:
            raise ValueError(f"{coord_name} cannot be None")

        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    raise ValueError(f"{coord_name} cannot be empty")
                coord_float = float(value)
            elif isinstance(value, int | float):
                coord_float = float(value)
            else:
                raise ValueError(f"Invalid {coord_name} type: {type(value)}")

            if not (min_val <= coord_float <= max_val):
                raise ValueError(
                    f"{coord_name} {coord_float} is outside valid range ({min_val} to {max_val})"
                )

            return coord_float

        except (ValueError, TypeError) as err:
            if "outside valid range" in str(err):
                raise
            raise ValueError(f"Cannot convert {coord_name} to float: {err}") from err

    @staticmethod
    def _convert_accuracy(value: Any) -> float | None:
        """Convert and validate accuracy value."""
        if value is None:
            return None

        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return None
                accuracy_float = float(value)
            elif isinstance(value, int | float):
                accuracy_float = float(value)
            else:
                raise ValueError(f"Invalid accuracy type: {type(value)}")

            if accuracy_float < 0:
                _LOGGER.warning(
                    "Negative accuracy value %f, setting to 0", accuracy_float
                )
                accuracy_float = 0.0

            return accuracy_float

        except (ValueError, TypeError) as err:
            _LOGGER.warning("Invalid accuracy format: %s - %s", value, err)
            return None

    @staticmethod
    def _convert_datetime(value: Any, field_name: str) -> datetime | None:
        """Convert various datetime formats to datetime object."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            _LOGGER.warning(
                "Invalid %s format (not string): %s", field_name, type(value)
            )
            return None

        value = value.strip()
        if not value:
            return None

        # Try various datetime formats
        formats_to_try = [
            # ISO format with Z
            lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
            # ISO format without timezone
            lambda x: datetime.fromisoformat(x),
            # Common formats
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S"),
            lambda x: datetime.strptime(x, "%Y-%m-%d %H:%M:%S"),
            lambda x: datetime.strptime(x, "%Y-%m-%dT%H:%M:%S.%f"),
            lambda x: datetime.strptime(x, "%Y-%m-%d"),
        ]

        for format_func in formats_to_try:
            try:
                return format_func(value)
            except (ValueError, TypeError):
                continue

        _LOGGER.warning("Could not parse %s datetime: %s", field_name, value)
        return None

    @staticmethod
    def _convert_address(value: Any) -> str | None:
        """Convert and validate address value."""
        if value is None:
            return None

        try:
            if isinstance(value, str):
                address = value.strip()
                return address if address else None
            else:
                # Convert other types to string
                address = str(value).strip()
                return address if address else None
        except Exception as err:
            _LOGGER.warning("Cannot convert address to string: %s - %s", value, err)
            return None

    def to_dict(self) -> dict[str, Any]:
        """Convert location to dictionary representation."""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "address": self.address,
        }

    def distance_to(self, other: Loca2Location) -> float:
        """Calculate distance to another location using Haversine formula (in meters)."""
        import math

        # Convert latitude and longitude from degrees to radians
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Radius of earth in meters
        r = 6371000

        return c * r

    def is_valid_coordinates(self) -> bool:
        """Check if coordinates are valid (not 0,0 which often indicates no GPS fix)."""
        return not (self.latitude == 0.0 and self.longitude == 0.0)


class Loca2ApiClient:
    """Client for interacting with the Loca2 API."""

    def __init__(
        self,
        account: str,
        password: str,
        base_url: str = "https://www.mijnloca.nl",
        timeout: int = DEFAULT_TIMEOUT,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._account = account
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = session
        self._close_session = session is None
        self._sid_cookie: str | None = None

        # Diagnostic information
        self._last_error: str | None = None
        self._error_count = 0
        self._last_success: datetime | None = None
        self._total_requests = 0
        self._successful_requests = 0
        self._connection_status = "unknown"
        self._last_response_time: float | None = None

    async def __aenter__(self) -> Loca2ApiClient:
        """Async context manager entry."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._close_session and self._session:
            await self._session.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make an HTTP request to the API with retry logic and comprehensive error handling."""
        url = f"{self._base_url}{endpoint}"

        # Ensure we have a valid session cookie
        if endpoint != AUTH_ENDPOINT and not self._sid_cookie:
            await self._authenticate()

        headers = {
            "Content-Type": "application/json",
            **kwargs.pop("headers", {}),
        }

        # Add session cookie if we have one
        cookies = {}
        if self._sid_cookie:
            cookies["sid"] = self._sid_cookie

        session = await self._get_session()
        start_time = time.time()
        self._total_requests += 1

        _LOGGER.debug(
            "Making %s request to %s (attempt 1/%d)", method, endpoint, DEFAULT_RETRIES
        )

        # Enhanced structured logging for request initiation
        # request_context = {
        #     "method": method,
        #     "endpoint": endpoint,
        #     "url": url,
        #     "timeout": self._timeout,
        #     "total_requests": self._total_requests,
        # }

        for attempt in range(DEFAULT_RETRIES):
            attempt_start = time.time()

            try:
                async with async_timeout.timeout(self._timeout):
                    async with session.request(
                        method, url, headers=headers, cookies=cookies, **kwargs
                    ) as response:
                        response_time = time.time() - attempt_start
                        self._last_response_time = response_time

                        # Log performance metrics with structured format
                        if response_time > 5.0:  # Slow response threshold
                            _LOGGER.warning(
                                "Slow API response: %s %s took %.2fs (status: %d, attempt: %d/%d)",
                                method,
                                endpoint,
                                response_time,
                                response.status,
                                attempt + 1,
                                DEFAULT_RETRIES,
                            )
                        else:
                            _LOGGER.debug(
                                "%s %s completed in %.2fs with status %d (attempt: %d/%d)",
                                method,
                                endpoint,
                                response_time,
                                response.status,
                                attempt + 1,
                                DEFAULT_RETRIES,
                            )

                        if response.status == 401:
                            self._connection_status = "auth_failed"
                            self._last_error = "Authentication failed"
                            self._error_count += 1
                            _LOGGER.error(
                                "Authentication failed for %s %s", method, endpoint
                            )
                            raise Loca2AuthError("Invalid API key or unauthorized")
                        elif response.status == 429:
                            self._connection_status = "rate_limited"
                            self._last_error = "Rate limit exceeded"
                            self._error_count += 1
                            retry_after = response.headers.get("Retry-After", "unknown")
                            _LOGGER.warning(
                                "Rate limit exceeded for %s %s (retry after: %s)",
                                method,
                                endpoint,
                                retry_after,
                            )
                            raise Loca2RateLimitError(
                                f"Rate limit exceeded (retry after: {retry_after})"
                            )
                        elif response.status >= 400:
                            self._connection_status = "api_error"
                            error_text = await response.text()
                            self._last_error = f"HTTP {response.status}: {error_text}"
                            self._error_count += 1
                            _LOGGER.error(
                                "API error for %s %s: status=%d, response=%s",
                                method,
                                endpoint,
                                response.status,
                                error_text,
                            )
                            raise Loca2ApiError(
                                f"API request failed with status {response.status}: {error_text}"
                            )

                        # Success case
                        self._connection_status = "connected"
                        self._last_success = datetime.now()
                        self._successful_requests += 1
                        self._last_error = None

                        try:
                            response_data = await response.json()
                            _LOGGER.debug(
                                "Successfully parsed JSON response for %s %s",
                                method,
                                endpoint,
                            )
                            return response_data
                        except Exception as json_err:
                            self._last_error = f"JSON parsing error: {json_err}"
                            self._error_count += 1
                            _LOGGER.error(
                                "Failed to parse JSON response for %s %s: %s",
                                method,
                                endpoint,
                                json_err,
                            )
                            raise Loca2ApiError(
                                f"Failed to parse JSON response: {json_err}"
                            ) from json_err

            except TimeoutError as err:
                response_time = time.time() - attempt_start
                self._connection_status = "timeout"
                self._last_error = f"Request timeout after {response_time:.1f}s"
                self._error_count += 1

                _LOGGER.warning(
                    "Request timeout for %s %s (attempt %d/%d, %.1fs)",
                    method,
                    endpoint,
                    attempt + 1,
                    DEFAULT_RETRIES,
                    response_time,
                )

                if attempt == DEFAULT_RETRIES - 1:
                    total_time = time.time() - start_time
                    _LOGGER.error(
                        "All retry attempts failed for %s %s due to timeout (total time: %.1fs)",
                        method,
                        endpoint,
                        total_time,
                    )
                    raise Loca2ConnectionError(
                        f"Request timeout after {total_time:.1f}s"
                    ) from err

            except aiohttp.ClientError as err:
                response_time = time.time() - attempt_start
                self._connection_status = "connection_error"
                self._last_error = f"Connection error: {err}"
                self._error_count += 1

                _LOGGER.warning(
                    "Connection error for %s %s (attempt %d/%d): %s",
                    method,
                    endpoint,
                    attempt + 1,
                    DEFAULT_RETRIES,
                    str(err),
                )

                if attempt == DEFAULT_RETRIES - 1:
                    total_time = time.time() - start_time
                    _LOGGER.error(
                        "All retry attempts failed for %s %s due to connection error (total time: %.1fs): %s",
                        method,
                        endpoint,
                        total_time,
                        str(err),
                    )
                    raise Loca2ConnectionError(f"Connection failed: {err}") from err

            except Exception as err:
                response_time = time.time() - attempt_start
                self._connection_status = "unknown_error"
                self._last_error = f"Unexpected error: {err}"
                self._error_count += 1

                _LOGGER.error(
                    "Unexpected error for %s %s (attempt %d/%d): %s",
                    method,
                    endpoint,
                    attempt + 1,
                    DEFAULT_RETRIES,
                    str(err),
                )

                if attempt == DEFAULT_RETRIES - 1:
                    total_time = time.time() - start_time
                    _LOGGER.error(
                        "All retry attempts failed for %s %s due to unexpected error (total time: %.1fs): %s",
                        method,
                        endpoint,
                        total_time,
                        str(err),
                    )
                    raise Loca2ApiError(f"Unexpected error: {err}") from err

            # Wait before retry with exponential backoff
            if attempt < DEFAULT_RETRIES - 1:
                retry_delay = RETRY_DELAY * (2**attempt)
                _LOGGER.debug(
                    "Retrying %s %s in %.1fs (attempt %d/%d)",
                    method,
                    endpoint,
                    retry_delay,
                    attempt + 2,
                    DEFAULT_RETRIES,
                )
                await asyncio.sleep(retry_delay)

        # This should never be reached due to the exception handling above
        total_time = time.time() - start_time
        self._connection_status = "max_retries_exceeded"
        self._last_error = f"Max retries exceeded after {total_time:.1f}s"
        _LOGGER.error(
            "Max retries exceeded for %s %s (total time: %.1fs)",
            method,
            endpoint,
            total_time,
        )
        raise Loca2ConnectionError(f"Max retries exceeded after {total_time:.1f}s")

    async def _authenticate(self) -> None:
        """Authenticate with the Loca2 API and get session cookie."""
        try:
            session = await self._get_session()

            # Prepare authentication data
            auth_data = {
                "account": self._account,
                "password": self._password,
            }

            url = f"{self._base_url}{AUTH_ENDPOINT}"

            async with async_timeout.timeout(self._timeout):
                async with session.post(url, data=auth_data) as response:
                    if response.status == 401:
                        raise Loca2AuthError("Invalid account or password")
                    elif response.status != 200:
                        error_text = await response.text()
                        raise Loca2ApiError(
                            f"Authentication failed with status {response.status}: {error_text}"
                        )

                    # Extract session cookie
                    if "sid" in response.cookies:
                        self._sid_cookie = response.cookies["sid"].value
                        _LOGGER.debug(
                            "Successfully authenticated and received session cookie"
                        )
                    else:
                        raise Loca2AuthError(
                            "No session cookie received after authentication"
                        )

        except (TimeoutError, aiohttp.ClientError) as err:
            raise Loca2ConnectionError(f"Authentication failed: {err}") from err

    async def authenticate(self) -> bool:
        """Test API authentication."""
        try:
            await self._authenticate()
            return True
        except Loca2AuthError:
            return False
        except Loca2ApiError as err:
            _LOGGER.error("Authentication test failed: %s", err)
            return False

    async def get_devices(self) -> list[Loca2Device]:
        """Get all devices with status from the asset status API."""
        try:
            response = await self._make_request("GET", ASSET_STATUS_ENDPOINT)

            # The response should be a list of asset status objects
            if not isinstance(response, list):
                _LOGGER.warning(
                    "Expected list response from asset status API, got: %s",
                    type(response),
                )
                return []

            devices = []
            for asset_status in response:
                try:
                    device = Loca2Device.from_dict(asset_status)
                    devices.append(device)
                except (KeyError, ValueError, TypeError) as err:
                    _LOGGER.warning(
                        "Invalid asset status data: %s - %s", asset_status, err
                    )
                    continue

            _LOGGER.debug("Retrieved %d devices with status", len(devices))
            return devices

        except Loca2ApiError:
            raise
        except Exception as err:
            raise Loca2ApiError(f"Failed to get devices: {err}") from err

    async def get_device_location(self, device_id: str) -> Loca2Location:
        """Get location for a specific device from asset status."""
        try:
            # Get all devices with status (includes location data)
            devices = await self.get_devices()

            # Find the specific device
            for device in devices:
                if device.id == device_id:
                    if device.latitude is not None and device.longitude is not None:
                        # Build address string
                        address_parts = []
                        if device.address:
                            address_parts.append(device.address)
                        if device.city:
                            address_parts.append(device.city)
                        if device.state:
                            address_parts.append(device.state)
                        if device.country:
                            address_parts.append(device.country)

                        full_address = (
                            ", ".join(address_parts) if address_parts else None
                        )

                        return Loca2Location(
                            latitude=device.latitude,
                            longitude=device.longitude,
                            accuracy=device.gps_accuracy,
                            timestamp=device.location_time or device.last_seen,
                            address=full_address,
                        )
                    else:
                        raise Loca2ApiError(
                            f"No location data available for device {device_id}"
                        )

            raise Loca2ApiError(f"Device {device_id} not found")

        except Loca2ApiError:
            raise
        except Exception as err:
            raise Loca2ApiError(
                f"Failed to get location for device {device_id}: {err}"
            ) from err

    async def test_connection(self) -> bool:
        """Test the API connection and authentication."""
        try:
            return await self.authenticate()
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._close_session and self._session:
            await self._session.close()
            self._session = None

    def get_diagnostic_info(self) -> dict[str, Any]:
        """Get comprehensive diagnostic information for troubleshooting."""
        success_rate = 0.0
        if self._total_requests > 0:
            success_rate = (self._successful_requests / self._total_requests) * 100

        # Calculate health status
        health_status = self._calculate_health_status(success_rate)

        # Get performance metrics
        avg_response_time = self._calculate_average_response_time()

        return {
            "connection_status": self._connection_status,
            "health_status": health_status,
            "last_error": self._last_error,
            "error_count": self._error_count,
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "success_rate": f"{success_rate:.1f}%",
            "last_success": (
                self._last_success.isoformat() if self._last_success else None
            ),
            "last_response_time": (
                f"{self._last_response_time:.3f}s" if self._last_response_time else None
            ),
            "average_response_time": (
                f"{avg_response_time:.3f}s" if avg_response_time else None
            ),
            "api_endpoint": self._base_url,
            "timeout": self._timeout,
            "session_active": self._session is not None,
            "diagnostic_timestamp": datetime.now().isoformat(),
        }

    def _calculate_health_status(self, success_rate: float) -> str:
        """Calculate health status based on success rate and recent errors."""
        from .const import (
            HEALTH_STATUS_DEGRADED,
            HEALTH_STATUS_HEALTHY,
            HEALTH_STATUS_UNHEALTHY,
        )

        if success_rate >= 95.0 and self._connection_status == "connected":
            return HEALTH_STATUS_HEALTHY
        elif success_rate >= 80.0 and self._connection_status in [
            "connected",
            "api_error",
        ]:
            return HEALTH_STATUS_DEGRADED
        else:
            return HEALTH_STATUS_UNHEALTHY

    def _calculate_average_response_time(self) -> float | None:
        """Calculate average response time from recent requests."""
        # For now, return the last response time
        # In a full implementation, you might maintain a rolling average
        return self._last_response_time

    def reset_diagnostic_counters(self) -> None:
        """Reset diagnostic counters (useful for testing or after maintenance)."""
        _LOGGER.info("Resetting API client diagnostic counters")
        self._error_count = 0
        self._total_requests = 0
        self._successful_requests = 0
        self._last_error = None
        self._connection_status = "reset"
