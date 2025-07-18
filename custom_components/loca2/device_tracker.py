"""Device tracker platform for Loca2 integration."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Loca2Device, Loca2Location
from .const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_TYPE,
    ATTR_GPS_ACCURACY,
    ATTR_LAST_SEEN,
    DOMAIN,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    ERROR_CATEGORY_API,
    ERROR_CATEGORY_UNKNOWN,
    ERROR_SEVERITY_LOW,
    ERROR_SEVERITY_MEDIUM,
    PERFORMANCE_SLOW_UPDATE_THRESHOLD,
)
from .logging_utils import get_structured_logger

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Loca2 device tracker entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    # Create device tracker entities for all discovered devices
    entities = []
    if coordinator.data:
        for device_id, device in coordinator.data.items():
            entity = Loca2DeviceTracker(coordinator, device_id, device)
            entities.append(entity)
    
    async_add_entities(entities, True)
    
    # Set up listener for new devices
    @callback
    def _async_add_new_devices():
        """Add new devices that appear in coordinator data."""
        if not coordinator.data:
            return
            
        current_entities = {entity.unique_id for entity in entities}
        new_entities = []
        
        for device_id, device in coordinator.data.items():
            unique_id = f"{DOMAIN}_{device_id}"
            if unique_id not in current_entities:
                entity = Loca2DeviceTracker(coordinator, device_id, device)
                new_entities.append(entity)
                entities.append(entity)
        
        if new_entities:
            _LOGGER.info("Adding %d new Loca2 device tracker entities", len(new_entities))
            async_add_entities(new_entities, True)
    
    # Listen for coordinator updates to detect new devices
    coordinator.async_add_listener(_async_add_new_devices)


class Loca2DeviceTracker(CoordinatorEntity, TrackerEntity):
    """Representation of a Loca2 device tracker."""

    def __init__(
        self,
        coordinator,
        device_id: str,
        device: Loca2Device,
    ) -> None:
        """Initialize the device tracker."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._device = device
        self._location: Optional[Loca2Location] = None
        self._attr_unique_id = f"{DOMAIN}_{device_id}"
        self._attr_name = device.name
        self._attr_source_type = SourceType.GPS
        
        # Initialize structured logging
        self._structured_logger = get_structured_logger(f"device_tracker.{device_id}")
        
        # Error tracking
        self._consecutive_location_errors = 0
        self._last_successful_location_update = None
        
        # Set initial device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device.name,
            "manufacturer": "Loca2",
            "model": device.device_type,
            "sw_version": None,
        }

    @property
    def device(self) -> Optional[Loca2Device]:
        """Return the current device data."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._device_id)
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.device is not None
        )

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of the device."""
        device = self.device
        if device and device.latitude is not None:
            return device.latitude
        if self._location and self._location.is_valid_coordinates():
            return self._location.latitude
        return None

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of the device."""
        device = self.device
        if device and device.longitude is not None:
            return device.longitude
        if self._location and self._location.is_valid_coordinates():
            return self._location.longitude
        return None

    @property
    def location_accuracy(self) -> Optional[int]:
        """Return the location accuracy of the device."""
        device = self.device
        if device and device.gps_accuracy is not None:
            return int(device.gps_accuracy)
        if self._location and self._location.accuracy is not None:
            return int(self._location.accuracy)
        return None

    @property
    def state(self) -> str:
        """Return the state of the device tracker."""
        if not self.available:
            return STATE_UNAVAILABLE
        
        device = self.device
        if not device:
            return STATE_UNAVAILABLE
        
        # Check if device is online based on last seen time
        if device.is_online():
            # If we have valid location coordinates, consider it "home"
            # In a real implementation, you might want to check against home zones
            if self._location and self._location.is_valid_coordinates():
                return STATE_HOME
            else:
                return STATE_NOT_HOME
        else:
            return STATE_NOT_HOME

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the device tracker."""
        attributes = {}
        
        device = self.device
        if device:
            # Basic attributes
            if device.battery_level is not None:
                attributes[ATTR_BATTERY_LEVEL] = device.battery_level
            
            if device.last_seen is not None:
                attributes[ATTR_LAST_SEEN] = device.last_seen.isoformat()
            
            attributes[ATTR_DEVICE_TYPE] = device.device_type
            
            # Asset information
            if device.serial:
                attributes["serial"] = device.serial
            if device.brand:
                attributes["brand"] = device.brand
            if device.model:
                attributes["model"] = device.model
            if device.group is not None:
                attributes["group"] = device.group
            if device.asset_type_id is not None:
                attributes["asset_type_id"] = device.asset_type_id
            
            # Device information
            if device.device_id is not None:
                attributes["device_id"] = device.device_id
            if device.device_type_id is not None:
                attributes["device_type_id"] = device.device_type_id
            if device.device_version is not None:
                attributes["device_version"] = device.device_version
            
            # Location information
            if device.address:
                attributes["address"] = device.address
            if device.city:
                attributes["city"] = device.city
            if device.state:
                attributes["state"] = device.state
            if device.country:
                attributes["country"] = device.country
            if device.zipcode:
                attributes["zipcode"] = device.zipcode
            if device.location_time:
                attributes["location_time"] = device.location_time.isoformat()
            
            # Status information
            if device.speed is not None:
                attributes["speed"] = device.speed
            if device.motion is not None:
                attributes["motion"] = device.motion
            if device.signal_strength is not None:
                attributes["signal_strength"] = device.signal_strength
            if device.gps_accuracy is not None:
                attributes[ATTR_GPS_ACCURACY] = device.gps_accuracy
            if device.satellites is not None:
                attributes["satellites"] = device.satellites
        
        if self._location:
            if self._location.accuracy is not None:
                attributes[ATTR_GPS_ACCURACY] = self._location.accuracy
            
            if self._location.address:
                attributes["address"] = self._location.address
            
            if self._location.timestamp:
                attributes["location_timestamp"] = self._location.timestamp.isoformat()
        
        return attributes

    @property
    def battery_level(self) -> Optional[int]:
        """Return the battery level of the device."""
        device = self.device
        if device and device.battery_level is not None:
            return device.battery_level
        return None

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        device = self.device
        if not device:
            return "mdi:help-circle"
        
        # Choose icon based on device type and brand/model
        device_type = device.device_type.lower()
        brand = (device.brand or "").lower()
        model = (device.model or "").lower()
        
        # Marine/boat trackers
        if "marine" in device_type or "boat" in brand or "interboat" in brand:
            return "mdi:ferry"
        # Vehicle trackers
        elif "vehicle" in device_type or "car" in device_type:
            return "mdi:car"
        # Personal trackers
        elif "personal" in device_type:
            return "mdi:account-circle"
        # Asset trackers
        elif "asset" in device_type:
            return "mdi:package-variant"
        # Phone/mobile devices
        elif "phone" in device_type or "mobile" in device_type:
            return "mdi:cellphone"
        elif "tablet" in device_type:
            return "mdi:tablet"
        elif "watch" in device_type:
            return "mdi:watch"
        # Generic GPS tracker
        elif "gps" in device_type or "tracker" in device_type:
            return "mdi:crosshairs-gps"
        elif "bike" in device_type or "bicycle" in device_type:
            return "mdi:bike"
        else:
            return "mdi:map-marker"

    async def async_update(self) -> None:
        """Update the device tracker with comprehensive error handling and structured logging."""
        with self._structured_logger.operation_timer("device_update"):
            try:
                await self.coordinator.async_request_refresh()
                
                # Fetch location data for this specific device
                if self.device:
                    await self._update_device_location()
                else:
                    self._structured_logger.log_diagnostic(
                        f"Device {self._device_id} not found in coordinator data, skipping location update",
                        data={
                            "coordinator_success": self.coordinator.last_update_success,
                            "data_available": self.coordinator.data is not None,
                        }
                    )
                    
            except Exception as err:
                # Use structured logger for comprehensive error logging
                self._structured_logger.log_error(
                    category=ERROR_CATEGORY_UNKNOWN,
                    error_type="device_update_failed",
                    message=str(err),
                    severity=ERROR_SEVERITY_MEDIUM,
                    exception=err,
                    extra_data={
                        "device_id": self._device_id,
                        "coordinator_status": {
                            "last_update_success": self.coordinator.last_update_success,
                            "last_exception": str(self.coordinator.last_exception) if self.coordinator.last_exception else None,
                            "data_available": self.coordinator.data is not None,
                        },
                        "entity_status": {
                            "available": self.available,
                            "has_location": self._location is not None,
                            "device_available": self.device is not None,
                        }
                    }
                )

    async def _update_device_location(self) -> None:
        """Update location data for the device with enhanced error handling."""
        location_start_time = time.time()
        
        try:
            with self._structured_logger.operation_timer("location_fetch"):
                location = await self.coordinator.async_get_device_location(self._device_id)
                
                if location:
                    # Validate location quality
                    location_quality = self._assess_location_quality(location)
                    
                    self._location = location
                    self._consecutive_location_errors = 0
                    self._last_successful_location_update = time.time()
                    
                    # Log successful location update with quality assessment
                    self._structured_logger.log_diagnostic(
                        f"Location updated for device {self._device_id}",
                        data={
                            "device_name": self.device.name,
                            "coordinates": f"{location.latitude:.6f}, {location.longitude:.6f}",
                            "accuracy": f"{location.accuracy}m" if location.accuracy else "unknown",
                            "valid_coordinates": location.is_valid_coordinates(),
                            "location_quality": location_quality,
                            "update_duration": time.time() - location_start_time,
                        }
                    )
                    
                    # Warn about poor location quality
                    if location_quality == "poor":
                        self._structured_logger.log_error(
                            category="location_quality",
                            error_type="poor_accuracy",
                            message=f"Poor location accuracy for device {self._device_id}",
                            severity=ERROR_SEVERITY_LOW,
                            extra_data={
                                "device_name": self.device.name,
                                "accuracy": location.accuracy,
                                "coordinates_valid": location.is_valid_coordinates(),
                            }
                        )
                else:
                    self._consecutive_location_errors += 1
                    self._structured_logger.log_diagnostic(
                        f"No location data available for device {self._device_id}",
                        data={
                            "device_name": self.device.name,
                            "consecutive_errors": self._consecutive_location_errors,
                            "coordinator_status": self.coordinator.last_update_success,
                        }
                    )
                    
        except Exception as err:
            self._consecutive_location_errors += 1
            location_duration = time.time() - location_start_time
            
            # Determine error severity based on consecutive errors and duration
            severity = ERROR_SEVERITY_LOW
            if self._consecutive_location_errors >= 10:
                severity = ERROR_SEVERITY_HIGH
            elif self._consecutive_location_errors >= 5 or location_duration > 30:
                severity = ERROR_SEVERITY_MEDIUM
            
            # Use structured logger for location fetch errors
            self._structured_logger.log_error(
                category=ERROR_CATEGORY_API,
                error_type="location_fetch_failed",
                message=str(err),
                duration=location_duration,
                consecutive=self._consecutive_location_errors,
                context=f"device_{self._device_id}",
                severity=severity,
                exception=err,
                extra_data={
                    "device_name": self.device.name if self.device else "unknown",
                    "coordinator_available": self.coordinator.last_update_success,
                    "last_successful_update": self._last_successful_location_update,
                    "coordinator_error_count": getattr(self.coordinator, '_consecutive_errors', 0),
                }
            )
            
            # Clear stale location data on persistent errors
            if self._consecutive_location_errors >= 5:
                if self._location is not None:
                    self._structured_logger.log_diagnostic(
                        f"Clearing stale location data for device {self._device_id} due to persistent errors",
                        data={
                            "consecutive_errors": self._consecutive_location_errors,
                            "last_successful_update": self._last_successful_location_update,
                        }
                    )
                    self._location = None
    
    def _assess_location_quality(self, location: Loca2Location) -> str:
        """Assess the quality of location data."""
        if not location.is_valid_coordinates():
            return "invalid"
        
        if location.accuracy is None:
            return "unknown"
        
        if location.accuracy <= 10:
            return "excellent"
        elif location.accuracy <= 50:
            return "good"
        elif location.accuracy <= 100:
            return "fair"
        else:
            return "poor"
    
    def get_device_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostic information for this device tracker."""
        return {
            "device_id": self._device_id,
            "device_name": self.device.name if self.device else "unknown",
            "available": self.available,
            "state": self.state,
            "location_info": {
                "has_location": self._location is not None,
                "location_quality": self._assess_location_quality(self._location) if self._location else None,
                "coordinates_valid": self._location.is_valid_coordinates() if self._location else False,
                "accuracy": self._location.accuracy if self._location else None,
                "last_update": self._last_successful_location_update,
            },
            "error_tracking": {
                "consecutive_location_errors": self._consecutive_location_errors,
                "last_successful_update": self._last_successful_location_update,
            },
            "device_info": {
                "battery_level": self.device.battery_level if self.device else None,
                "device_type": self.device.device_type if self.device else None,
                "last_seen": self.device.last_seen.isoformat() if self.device and self.device.last_seen else None,
                "is_online": self.device.is_online() if self.device else False,
            },
            "coordinator_status": {
                "last_update_success": self.coordinator.last_update_success,
                "data_available": self.coordinator.data is not None,
            },
            "timestamp": datetime.now().isoformat(),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update device info if it has changed
        device = self.device
        if device and device.name != self._attr_name:
            self._attr_name = device.name
            self._attr_device_info["name"] = device.name
        
        # Schedule async update to fetch location
        self.hass.async_create_task(self._async_update_location())
        
        super()._handle_coordinator_update()

    async def _async_update_location(self) -> None:
        """Update location data asynchronously."""
        if not self.device:
            return
        
        try:
            location = await self.coordinator.async_get_device_location(self._device_id)
            if location:
                self._location = location
                # Trigger state update
                self.async_write_ha_state()
        except Exception as err:
            _LOGGER.debug(
                "Could not fetch location for device %s: %s",
                self._device_id,
                err,
            )