"""The Loca2 integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    Loca2ApiClient,
    Loca2ApiError,
    Loca2AuthError,
    Loca2ConnectionError,
    Loca2Device,
    Loca2RateLimitError,
)
from .const import (
    CONF_BASE_URL,
    CONF_DISABLED_DEVICES,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ERROR_CATEGORY_API,
    ERROR_CATEGORY_AUTH,
    ERROR_CATEGORY_NETWORK,
    ERROR_CATEGORY_UNKNOWN,
    ERROR_SEVERITY_CRITICAL,
    ERROR_SEVERITY_HIGH,
    ERROR_SEVERITY_LOW,
    ERROR_SEVERITY_MEDIUM,
    HEALTH_STATUS_DEGRADED,
    HEALTH_STATUS_HEALTHY,
    HEALTH_STATUS_UNHEALTHY,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NOTIFICATION_ID_AUTH_FAILED,
    NOTIFICATION_ID_CONNECTION_LOST,
    NOTIFICATION_ID_RATE_LIMITED,
    NOTIFICATION_ID_RECOVERY,
    NOTIFICATION_RATE_LIMIT_SECONDS,
    PERFORMANCE_SLOW_UPDATE_THRESHOLD,
)
from .logging_utils import (
    DiagnosticCollector,
    format_diagnostic_summary,
    get_structured_logger,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["device_tracker"]


class Loca2DataUpdateCoordinator(DataUpdateCoordinator[dict[str, Loca2Device]]):
    """Class to manage fetching data from the Loca2 API."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: Loca2ApiClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        disabled_devices: list[str] | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.api_client = api_client
        self._scan_interval = scan_interval
        self._original_scan_interval = scan_interval
        self._disabled_devices = disabled_devices or []
        self._rate_limit_count = 0
        self._last_rate_limit = None
        self._backoff_multiplier = 1
        self._max_backoff_multiplier = 8
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

        # Enhanced error tracking and logging
        self._error_history: list[dict[str, Any]] = []
        self._last_successful_update = None
        self._recovery_attempts = 0
        self._last_notification_sent = {}
        self._error_categories = {
            ERROR_CATEGORY_AUTH: 0,
            ERROR_CATEGORY_NETWORK: 0,
            ERROR_CATEGORY_API: 0,
            ERROR_CATEGORY_UNKNOWN: 0,
        }

        # Initialize structured logging and diagnostics
        self._structured_logger = get_structured_logger("coordinator")
        self._diagnostic_collector = DiagnosticCollector()
        self._last_diagnostic_log = None

        # Initialize with the configured scan interval
        update_interval = timedelta(seconds=scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Loca2Device]:
        """Fetch data from API endpoint with comprehensive error handling."""
        update_start_time = datetime.now()

        # Initialize performance tracking if not exists
        if not hasattr(self, "_update_durations"):
            self._update_durations = []

        try:
            _LOGGER.debug(
                "Fetching device data from Loca2 API (attempt %d)",
                self._recovery_attempts + 1,
            )

            # Get devices from API
            devices = await self.api_client.get_devices()

            # Filter out disabled devices
            if self._disabled_devices:
                original_count = len(devices)
                devices = [
                    device
                    for device in devices
                    if device.id not in self._disabled_devices
                ]
                filtered_count = original_count - len(devices)
                if filtered_count > 0:
                    _LOGGER.debug("Filtered out %d disabled devices", filtered_count)

            # Convert to dictionary keyed by device ID
            device_dict = {device.id: device for device in devices}

            # Handle successful update
            await self._handle_successful_update(device_dict, update_start_time)

            _LOGGER.debug("Successfully fetched %d devices", len(device_dict))
            return device_dict

        except Loca2RateLimitError as err:
            await self._handle_error(
                err, ERROR_CATEGORY_API, "rate_limit", update_start_time
            )
            await self._handle_rate_limit()
            raise UpdateFailed(f"Rate limit exceeded: {err}") from err

        except Loca2AuthError as err:
            await self._handle_error(
                err, ERROR_CATEGORY_AUTH, "authentication", update_start_time
            )
            raise UpdateFailed(f"Authentication failed: {err}") from err

        except Loca2ConnectionError as err:
            await self._handle_error(
                err, ERROR_CATEGORY_NETWORK, "connection_error", update_start_time
            )
            self._consecutive_errors += 1
            await self._handle_api_error()
            raise UpdateFailed(f"Connection error: {err}") from err

        except Loca2ApiError as err:
            await self._handle_error(
                err, ERROR_CATEGORY_API, "api_error", update_start_time
            )
            self._consecutive_errors += 1
            await self._handle_api_error()
            raise UpdateFailed(f"API error: {err}") from err

        except Exception as err:
            await self._handle_error(
                err, ERROR_CATEGORY_UNKNOWN, "unexpected", update_start_time
            )
            self._consecutive_errors += 1
            await self._handle_api_error()
            raise UpdateFailed(f"Unexpected error: {err}") from err

        finally:
            # Track update duration for performance monitoring
            update_duration = (datetime.now() - update_start_time).total_seconds()
            self._last_update_duration = update_duration

            # Keep only last 20 durations for performance analysis
            self._update_durations.append(update_duration)
            if len(self._update_durations) > 20:
                self._update_durations.pop(0)

            # Log performance metrics
            self._structured_logger.log_performance(
                operation="coordinator_update",
                duration=update_duration,
                details=f"devices_fetched={len(device_dict) if 'device_dict' in locals() else 0}",
                extra_data={
                    "consecutive_errors": self._consecutive_errors,
                    "recovery_attempts": self._recovery_attempts,
                    "backoff_multiplier": self._backoff_multiplier,
                },
            )

    async def async_get_device_location(self, device_id: str) -> Any | None:
        """Get location for a specific device with error handling."""
        try:
            location = await self.api_client.get_device_location(device_id)
            return location
        except Loca2ApiError as err:
            await self._handle_error(
                err, ERROR_CATEGORY_API, "location_fetch", datetime.now(), device_id
            )
            _LOGGER.warning("Failed to get location for device %s: %s", device_id, err)
            return None
        except Exception as err:
            await self._handle_error(
                err,
                ERROR_CATEGORY_UNKNOWN,
                "location_fetch_unexpected",
                datetime.now(),
                device_id,
            )
            _LOGGER.error(
                "Unexpected error getting location for device %s: %s", device_id, err
            )
            return None

    async def _handle_successful_update(
        self, device_dict: dict[str, Loca2Device], start_time: datetime
    ) -> None:
        """Handle successful data update with recovery notifications."""
        update_duration = (datetime.now() - start_time).total_seconds()

        # Check if this is a recovery from previous errors
        was_in_error_state = self._consecutive_errors > 0 or self._recovery_attempts > 0

        # Reset error counters on successful update
        self._consecutive_errors = 0
        self._recovery_attempts = 0
        self._last_successful_update = datetime.now()
        self._reset_backoff()

        # Log recovery if we were in an error state
        if was_in_error_state:
            _LOGGER.info(
                "Successfully recovered from error state - fetched %d devices in %.2fs",
                len(device_dict),
                update_duration,
            )
            await self._send_user_notification(
                NOTIFICATION_ID_RECOVERY,
                "Loca2 Connection Restored",
                f"Successfully reconnected to Loca2 API and fetched {len(device_dict)} devices.",
            )
            # Clear previous error notifications
            await self._clear_error_notifications()

        # Log performance metrics
        if update_duration > 10.0:  # Log slow updates
            _LOGGER.warning(
                "Slow API response: update took %.2fs for %d devices",
                update_duration,
                len(device_dict),
            )

    async def _handle_error(
        self,
        error: Exception,
        category: str,
        error_type: str,
        start_time: datetime,
        context: str | None = None,
    ) -> None:
        """Handle errors with comprehensive structured logging and tracking."""
        error_duration = (datetime.now() - start_time).total_seconds()

        # Determine error severity
        severity = self._determine_error_severity(
            category, error_type, self._consecutive_errors
        )

        # Create structured error record
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "type": error_type,
            "message": str(error),
            "duration": error_duration,
            "context": context,
            "consecutive_errors": self._consecutive_errors,
            "recovery_attempts": self._recovery_attempts,
            "severity": severity,
        }

        # Add to error history (keep last 50 errors)
        self._error_history.append(error_record)
        if len(self._error_history) > 50:
            self._error_history.pop(0)

        # Update error category counters
        if category in self._error_categories:
            self._error_categories[category] += 1

        # Use structured logger for enhanced error logging
        self._structured_logger.log_error(
            category=category,
            error_type=error_type,
            message=str(error),
            duration=error_duration,
            consecutive=self._consecutive_errors,
            context=context,
            severity=severity,
            exception=error,
            extra_data={
                "recovery_attempts": self._recovery_attempts,
                "total_errors": len(self._error_history),
                "error_rate": self._calculate_error_rate(),
            },
        )

        # Add to diagnostic collector
        self._diagnostic_collector.add_error(
            category=category,
            error_type=error_type,
            message=str(error),
            duration=error_duration,
            context=context,
            severity=severity,
            extra_data=error_record,
        )

        # Send notifications for critical errors
        await self._handle_error_notifications(error, category, error_type, severity)

    async def _handle_error_notifications(
        self, error: Exception, category: str, error_type: str, severity: str
    ) -> None:
        """Send user notifications for critical errors with enhanced context."""
        now = datetime.now()

        # Rate limit notifications (don't spam user)
        notification_key = f"{category}:{error_type}"
        last_sent = self._last_notification_sent.get(notification_key)

        if (
            last_sent
            and (now - last_sent).total_seconds() < NOTIFICATION_RATE_LIMIT_SECONDS
        ):
            return

        # Only send notifications for medium severity and above
        if severity not in [
            ERROR_SEVERITY_MEDIUM,
            ERROR_SEVERITY_HIGH,
            ERROR_SEVERITY_CRITICAL,
        ]:
            return

        self._last_notification_sent[notification_key] = now

        # Send appropriate notifications with enhanced context
        if category == ERROR_CATEGORY_AUTH:
            await self._send_user_notification(
                NOTIFICATION_ID_AUTH_FAILED,
                "Loca2 Authentication Failed",
                f"Please check your API credentials in the integration configuration. "
                f"The integration cannot connect to your Loca2 account and device tracking has stopped. "
                f"Go to Settings > Devices & Services > Loca2 to reconfigure. "
                f"Technical details: {error}",
                severity,
            )
        elif category == ERROR_CATEGORY_NETWORK and self._consecutive_errors >= 3:
            downtime_minutes = (
                int((now - self._last_successful_update).total_seconds() / 60)
                if self._last_successful_update
                else 0
            )
            await self._send_user_notification(
                NOTIFICATION_ID_CONNECTION_LOST,
                "Loca2 Connection Issues",
                f"Unable to connect to Loca2 API after {self._consecutive_errors} consecutive attempts "
                f"({downtime_minutes} minutes of downtime). Device tracking may be delayed. "
                f"The integration will continue retrying automatically with exponential backoff. "
                f"If this persists, check your internet connection and Loca2 service status. "
                f"Technical details: {error}",
                severity,
            )
        elif error_type == "rate_limit":
            new_interval = min(self._scan_interval * 2, MAX_SCAN_INTERVAL)
            await self._send_user_notification(
                NOTIFICATION_ID_RATE_LIMITED,
                "Loca2 Rate Limited",
                f"API rate limit exceeded. Polling interval automatically increased from {self._original_scan_interval}s "
                f"to {new_interval}s to reduce API usage. Device updates will be less frequent temporarily. "
                f"The interval will be restored automatically once the rate limit clears. "
                f"Technical details: {error}",
                severity,
            )
        elif category == ERROR_CATEGORY_API and self._consecutive_errors >= 5:
            await self._send_user_notification(
                "loca2_api_degraded",
                "Loca2 API Issues",
                f"Experiencing persistent API issues after {self._consecutive_errors} attempts. "
                f"This may indicate a problem with the Loca2 service. Device tracking may be unreliable. "
                f"The integration will continue retrying. Check Loca2 service status if this persists. "
                f"Technical details: {error}",
                severity,
            )

    async def _send_user_notification(
        self,
        notification_id: str,
        title: str,
        message: str,
        severity: str = ERROR_SEVERITY_MEDIUM,
    ) -> None:
        """Send notification to user via Home Assistant with enhanced logging."""
        try:
            # Add timestamp and action buttons for better UX
            enhanced_message = (
                f"{message}\n\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "notification_id": notification_id,
                    "title": title,
                    "message": enhanced_message,
                },
            )

            # Log notification with structured logging
            self._structured_logger.log_diagnostic(
                f"User notification sent: {title}",
                data={
                    "notification_id": notification_id,
                    "severity": severity,
                    "message_length": len(message),
                    "consecutive_errors": self._consecutive_errors,
                    "error_rate": self._calculate_error_rate(),
                },
                level=logging.INFO,
            )

        except Exception as err:
            self._structured_logger.log_error(
                category="notification",
                error_type="send_failed",
                message=f"Failed to send user notification '{title}': {err}",
                severity=ERROR_SEVERITY_LOW,
                exception=err,
                extra_data={
                    "notification_id": notification_id,
                    "original_title": title,
                    "attempted_severity": severity,
                },
            )

    async def _clear_error_notifications(self) -> None:
        """Clear error notifications when connection is restored."""
        notifications_to_clear = [
            NOTIFICATION_ID_AUTH_FAILED,
            NOTIFICATION_ID_CONNECTION_LOST,
            NOTIFICATION_ID_RATE_LIMITED,
        ]

        for notification_id in notifications_to_clear:
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "dismiss",
                    {"notification_id": notification_id},
                )
            except Exception as err:
                _LOGGER.debug(
                    "Could not clear notification %s: %s", notification_id, err
                )

    async def _handle_rate_limit(self) -> None:
        """Handle rate limiting by adjusting polling interval."""
        self._rate_limit_count += 1
        self._last_rate_limit = datetime.now()

        # Increase scan interval to reduce API calls
        new_interval = min(self._scan_interval * 2, MAX_SCAN_INTERVAL)

        if new_interval != self._scan_interval:
            _LOGGER.info(
                "Adjusting scan interval from %d to %d seconds due to rate limiting",
                self._scan_interval,
                new_interval,
            )
            self._scan_interval = new_interval
            self.update_interval = timedelta(seconds=new_interval)

        # Wait before next attempt
        await asyncio.sleep(60)  # Wait 1 minute before retrying

    async def _handle_api_error(self) -> None:
        """Handle API errors with exponential backoff."""
        if self._consecutive_errors >= self._max_consecutive_errors:
            _LOGGER.warning(
                "Too many consecutive errors (%d), applying exponential backoff",
                self._consecutive_errors,
            )

            # Apply exponential backoff
            self._backoff_multiplier = min(
                self._backoff_multiplier * 2, self._max_backoff_multiplier
            )

            backoff_interval = self._scan_interval * self._backoff_multiplier
            backoff_interval = min(backoff_interval, MAX_SCAN_INTERVAL)

            _LOGGER.info(
                "Applying backoff: increasing interval to %d seconds (multiplier: %d)",
                backoff_interval,
                self._backoff_multiplier,
            )

            self.update_interval = timedelta(seconds=backoff_interval)

            # Wait before next attempt
            await asyncio.sleep(min(30, backoff_interval))

    def _reset_backoff(self) -> None:
        """Reset backoff multiplier and restore normal polling interval."""
        if self._backoff_multiplier > 1:
            _LOGGER.info("Resetting backoff, returning to normal polling interval")
            self._backoff_multiplier = 1

            # Gradually restore normal interval if we were rate limited
            if self._last_rate_limit:
                time_since_rate_limit = datetime.now() - self._last_rate_limit
                if time_since_rate_limit > timedelta(minutes=10):
                    # It's been a while since rate limiting, restore original interval
                    self._scan_interval = self._original_scan_interval
                    _LOGGER.info(
                        "Restoring original scan interval: %d seconds",
                        self._scan_interval,
                    )

            self.update_interval = timedelta(seconds=self._scan_interval)

    def adjust_scan_interval(self, new_interval: int) -> None:
        """Adjust the scan interval."""
        if MIN_SCAN_INTERVAL <= new_interval <= MAX_SCAN_INTERVAL:
            self._scan_interval = new_interval
            self._original_scan_interval = new_interval
            self.update_interval = timedelta(seconds=new_interval)
            _LOGGER.info("Scan interval adjusted to %d seconds", new_interval)
        else:
            _LOGGER.warning(
                "Invalid scan interval %d, must be between %d and %d",
                new_interval,
                MIN_SCAN_INTERVAL,
                MAX_SCAN_INTERVAL,
            )

    def update_disabled_devices(self, disabled_devices: list[str]) -> None:
        """Update the list of disabled devices."""
        self._disabled_devices = disabled_devices or []
        _LOGGER.info("Updated disabled devices list: %s", self._disabled_devices)

    def update_configuration(
        self, scan_interval: int, disabled_devices: list[str]
    ) -> None:
        """Update coordinator configuration."""
        self.adjust_scan_interval(scan_interval)
        self.update_disabled_devices(disabled_devices)
        _LOGGER.info(
            "Configuration updated - scan_interval: %d, disabled_devices: %s",
            scan_interval,
            disabled_devices,
        )

    @property
    def rate_limit_info(self) -> dict[str, Any]:
        """Get rate limiting information for diagnostics."""
        return {
            "rate_limit_count": self._rate_limit_count,
            "last_rate_limit": (
                self._last_rate_limit.isoformat() if self._last_rate_limit else None
            ),
            "current_scan_interval": self._scan_interval,
            "original_scan_interval": self._original_scan_interval,
            "backoff_multiplier": self._backoff_multiplier,
            "consecutive_errors": self._consecutive_errors,
        }

    def get_diagnostic_info(self) -> dict[str, Any]:
        """Get comprehensive diagnostic information for troubleshooting."""
        api_diagnostics = self.api_client.get_diagnostic_info()
        now = datetime.now()

        # Calculate uptime and availability metrics
        uptime_seconds = 0
        availability_percentage = 0.0
        if self._last_successful_update:
            uptime_seconds = (now - self._last_successful_update).total_seconds()

        if self._error_history:
            # Calculate availability over last 24 hours
            one_day_ago = now - timedelta(hours=24)
            recent_errors = [
                error
                for error in self._error_history
                if datetime.fromisoformat(error["timestamp"]) > one_day_ago
            ]
            total_time_seconds = 24 * 3600
            error_time_seconds = len(recent_errors) * self._scan_interval
            availability_percentage = max(
                0, (total_time_seconds - error_time_seconds) / total_time_seconds * 100
            )
        else:
            availability_percentage = 100.0

        # Calculate error rate trends
        error_rate_1h = self._calculate_error_rate_for_period(timedelta(hours=1))
        error_rate_24h = self._calculate_error_rate_for_period(timedelta(hours=24))

        # Determine overall health status
        health_status = self._calculate_overall_health_status(
            availability_percentage, error_rate_1h
        )

        return {
            "coordinator": {
                "last_update_success": self.last_update_success,
                "last_exception": (
                    str(self.last_exception) if self.last_exception else None
                ),
                "update_count": getattr(self, "_update_count", 0),
                "data_available": self.data is not None,
                "device_count": len(self.data) if self.data else 0,
                "last_successful_update": (
                    self._last_successful_update.isoformat()
                    if self._last_successful_update
                    else None
                ),
                "recovery_attempts": self._recovery_attempts,
                "uptime_seconds": uptime_seconds,
                "health_status": health_status,
                "availability_24h": f"{availability_percentage:.1f}%",
            },
            "rate_limiting": self.rate_limit_info,
            "error_tracking": {
                "error_categories": self._error_categories.copy(),
                "recent_errors": (
                    self._error_history[-10:] if self._error_history else []
                ),
                "total_errors": len(self._error_history),
                "last_error": self._error_history[-1] if self._error_history else None,
                "error_rate_1h": error_rate_1h,
                "error_rate_24h": error_rate_24h,
                "error_trends": self._analyze_error_trends(),
            },
            "performance": {
                "average_update_duration": self._calculate_average_update_duration(),
                "slow_updates_count": self._count_slow_updates(),
                "last_update_duration": getattr(self, "_last_update_duration", None),
            },
            "configuration": {
                "scan_interval": self._scan_interval,
                "original_scan_interval": self._original_scan_interval,
                "disabled_devices": len(self._disabled_devices),
                "backoff_multiplier": self._backoff_multiplier,
            },
            "api_client": api_diagnostics,
            "diagnostic_timestamp": now.isoformat(),
        }

    def log_diagnostic_summary(self) -> None:
        """Log a comprehensive diagnostic summary for troubleshooting."""
        diagnostics = self.get_diagnostic_info()

        # Use structured logger for diagnostic summary
        self._structured_logger.log_diagnostic(
            "Generating comprehensive diagnostic summary",
            data={"summary_type": "full", "timestamp": datetime.now().isoformat()},
            level=logging.INFO,
        )

        # Get comprehensive diagnostic from collector
        collector_diagnostics = (
            self._diagnostic_collector.get_comprehensive_diagnostic()
        )

        # Format and log the summary
        summary = format_diagnostic_summary(collector_diagnostics)
        _LOGGER.info(summary)

        # Log additional coordinator-specific diagnostics
        _LOGGER.info("=== Coordinator Specific Diagnostics ===")
        _LOGGER.info("Coordinator Status:")
        _LOGGER.info(
            "  - Last update success: %s",
            diagnostics["coordinator"]["last_update_success"],
        )
        _LOGGER.info("  - Device count: %d", diagnostics["coordinator"]["device_count"])
        _LOGGER.info("  - Update count: %d", diagnostics["coordinator"]["update_count"])

        if diagnostics["coordinator"]["last_exception"]:
            _LOGGER.info(
                "  - Last exception: %s", diagnostics["coordinator"]["last_exception"]
            )

        _LOGGER.info("Rate Limiting:")
        _LOGGER.info(
            "  - Rate limit count: %d", diagnostics["rate_limiting"]["rate_limit_count"]
        )
        _LOGGER.info(
            "  - Current scan interval: %ds",
            diagnostics["rate_limiting"]["current_scan_interval"],
        )
        _LOGGER.info(
            "  - Consecutive errors: %d",
            diagnostics["rate_limiting"]["consecutive_errors"],
        )

        _LOGGER.info("API Client:")
        _LOGGER.info(
            "  - Connection status: %s", diagnostics["api_client"]["connection_status"]
        )
        _LOGGER.info("  - Success rate: %s", diagnostics["api_client"]["success_rate"])
        _LOGGER.info("  - Error count: %d", diagnostics["api_client"]["error_count"])

        if diagnostics["api_client"]["last_error"]:
            _LOGGER.info("  - Last error: %s", diagnostics["api_client"]["last_error"])

        _LOGGER.info("=" * 45)

        # Update last diagnostic log time
        self._last_diagnostic_log = datetime.now()

    def _determine_error_severity(
        self, category: str, error_type: str, consecutive_errors: int
    ) -> str:
        """Determine error severity based on category, type, and frequency."""
        # Critical errors
        if category == ERROR_CATEGORY_AUTH:
            return ERROR_SEVERITY_CRITICAL

        if consecutive_errors >= 10:
            return ERROR_SEVERITY_CRITICAL

        # High severity errors
        if category == ERROR_CATEGORY_NETWORK and consecutive_errors >= 5:
            return ERROR_SEVERITY_HIGH

        if error_type == "rate_limit" and consecutive_errors >= 3:
            return ERROR_SEVERITY_HIGH

        # Medium severity errors
        if category in [ERROR_CATEGORY_API, ERROR_CATEGORY_NETWORK]:
            return ERROR_SEVERITY_MEDIUM

        # Low severity errors
        return ERROR_SEVERITY_LOW

    def _calculate_error_rate(self) -> float:
        """Calculate current error rate (errors per hour)."""
        return self._calculate_error_rate_for_period(timedelta(hours=1))

    def _calculate_error_rate_for_period(self, period: timedelta) -> float:
        """Calculate error rate for a specific time period."""
        if not self._error_history:
            return 0.0

        cutoff_time = datetime.now() - period
        recent_errors = [
            error
            for error in self._error_history
            if datetime.fromisoformat(error["timestamp"]) > cutoff_time
        ]

        return len(recent_errors)

    def _calculate_overall_health_status(
        self, availability: float, error_rate_1h: float
    ) -> str:
        """Calculate overall health status based on multiple metrics."""
        # Critical issues
        if self._consecutive_errors >= 10 or availability < 50.0:
            return HEALTH_STATUS_UNHEALTHY

        # Degraded performance
        if (
            self._consecutive_errors >= 3
            or error_rate_1h >= 10
            or availability < 90.0
            or self._backoff_multiplier > 2
        ):
            return HEALTH_STATUS_DEGRADED

        # Healthy
        return HEALTH_STATUS_HEALTHY

    def _analyze_error_trends(self) -> dict[str, Any]:
        """Analyze error trends over time."""
        if not self._error_history:
            return {"trend": "stable", "recent_increase": False, "pattern": "none"}

        now = datetime.now()

        # Compare last hour vs previous hour
        one_hour_ago = now - timedelta(hours=1)
        two_hours_ago = now - timedelta(hours=2)

        recent_errors = [
            error
            for error in self._error_history
            if datetime.fromisoformat(error["timestamp"]) > one_hour_ago
        ]

        previous_errors = [
            error
            for error in self._error_history
            if two_hours_ago
            < datetime.fromisoformat(error["timestamp"])
            <= one_hour_ago
        ]

        recent_count = len(recent_errors)
        previous_count = len(previous_errors)

        # Determine trend
        if recent_count > previous_count * 1.5:
            trend = "increasing"
            recent_increase = True
        elif recent_count < previous_count * 0.5:
            trend = "decreasing"
            recent_increase = False
        else:
            trend = "stable"
            recent_increase = False

        # Analyze error patterns
        if recent_count >= 5:
            pattern = "frequent"
        elif self._consecutive_errors >= 3:
            pattern = "consecutive"
        elif recent_count > 0:
            pattern = "sporadic"
        else:
            pattern = "none"

        return {
            "trend": trend,
            "recent_increase": recent_increase,
            "pattern": pattern,
            "recent_count": recent_count,
            "previous_count": previous_count,
        }

    def _calculate_average_update_duration(self) -> float | None:
        """Calculate average update duration from recent history."""
        if not hasattr(self, "_update_durations"):
            return None

        durations = getattr(self, "_update_durations", [])
        if not durations:
            return None

        return sum(durations) / len(durations)

    def _count_slow_updates(self) -> int:
        """Count slow updates in recent history."""
        if not hasattr(self, "_update_durations"):
            return 0

        durations = getattr(self, "_update_durations", [])
        return len([d for d in durations if d > PERFORMANCE_SLOW_UPDATE_THRESHOLD])

    def should_log_diagnostic_summary(self) -> bool:
        """Check if diagnostic summary should be logged."""
        if self._last_diagnostic_log is None:
            return True

        # Log summary every 5 minutes if there are errors
        if (
            self._error_history
            and (datetime.now() - self._last_diagnostic_log).total_seconds() > 300
        ):
            return True

        # Log summary every 30 minutes regardless
        if (datetime.now() - self._last_diagnostic_log).total_seconds() > 1800:
            return True

        return False

    async def perform_health_check(self) -> dict[str, Any]:
        """Perform comprehensive health check of the integration."""
        health_check_start = datetime.now()

        try:
            # Test API connectivity
            api_healthy = await self.api_client.test_connection()

            # Check data freshness
            data_fresh = True
            if self._last_successful_update:
                data_age = (
                    datetime.now() - self._last_successful_update
                ).total_seconds()
                data_fresh = data_age < (self._scan_interval * 3)  # Allow 3 intervals

            # Check error rates
            error_rate_1h = self._calculate_error_rate_for_period(timedelta(hours=1))
            error_rate_acceptable = error_rate_1h < 10

            # Check consecutive errors
            consecutive_errors_ok = self._consecutive_errors < 5

            # Overall health assessment
            overall_healthy = (
                api_healthy
                and data_fresh
                and error_rate_acceptable
                and consecutive_errors_ok
            )

            health_status = {
                "overall_healthy": overall_healthy,
                "api_connectivity": api_healthy,
                "data_freshness": data_fresh,
                "error_rate_acceptable": error_rate_acceptable,
                "consecutive_errors_ok": consecutive_errors_ok,
                "checks": {
                    "api_connection": "pass" if api_healthy else "fail",
                    "data_age": "pass" if data_fresh else "fail",
                    "error_rate": "pass" if error_rate_acceptable else "fail",
                    "consecutive_errors": "pass" if consecutive_errors_ok else "fail",
                },
                "metrics": {
                    "error_rate_1h": error_rate_1h,
                    "consecutive_errors": self._consecutive_errors,
                    "data_age_seconds": (
                        (datetime.now() - self._last_successful_update).total_seconds()
                        if self._last_successful_update
                        else None
                    ),
                    "scan_interval": self._scan_interval,
                },
                "timestamp": datetime.now().isoformat(),
                "check_duration": (datetime.now() - health_check_start).total_seconds(),
            }

            # Add to diagnostic collector
            self._diagnostic_collector.add_health_check(
                status="healthy" if overall_healthy else "unhealthy",
                details=health_status,
            )

            # Log health check results
            self._structured_logger.log_diagnostic(
                f"Health check completed: {'HEALTHY' if overall_healthy else 'UNHEALTHY'}",
                data=health_status,
                level=logging.INFO if overall_healthy else logging.WARNING,
            )

            return health_status

        except Exception as err:
            error_status = {
                "overall_healthy": False,
                "error": str(err),
                "timestamp": datetime.now().isoformat(),
                "check_duration": (datetime.now() - health_check_start).total_seconds(),
            }

            self._structured_logger.log_error(
                category="health_check",
                error_type="check_failed",
                message=f"Health check failed: {err}",
                severity=ERROR_SEVERITY_MEDIUM,
                exception=err,
            )

            return error_status

    async def schedule_periodic_health_check(self) -> None:
        """Schedule periodic health checks."""
        try:
            # Perform health check every 5 minutes
            await asyncio.sleep(300)  # 5 minutes
            await self.perform_health_check()

            # Schedule next check
            self.hass.async_create_task(self.schedule_periodic_health_check())

        except Exception as err:
            self._structured_logger.log_error(
                category="health_check",
                error_type="scheduling_failed",
                message=f"Failed to schedule health check: {err}",
                severity=ERROR_SEVERITY_LOW,
                exception=err,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Loca2 from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    base_url = entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)
    scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    timeout = entry.options.get(CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, 10))
    disabled_devices = entry.options.get(CONF_DISABLED_DEVICES, [])

    # Create API client
    api_client = Loca2ApiClient(
        account=username,
        password=password,
        base_url=base_url,
        timeout=timeout,
    )

    # Test the connection
    try:
        if not await api_client.test_connection():
            raise ConfigEntryNotReady("Failed to authenticate with Loca2 API")
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Loca2 API: {err}") from err

    # Create data update coordinator
    coordinator = Loca2DataUpdateCoordinator(
        hass=hass,
        api_client=api_client,
        scan_interval=scan_interval,
        disabled_devices=disabled_devices,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator in hass data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        # Clean up stored data if it exists
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            data = hass.data[DOMAIN].pop(entry.entry_id)

            # Close API client session
            api_client = data.get("api_client")
            if api_client:
                await api_client.close()

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options without requiring a full reload."""
    # Get the coordinator from stored data
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.warning(
            "Coordinator not found for options update, performing full reload"
        )
        await hass.config_entries.async_reload(entry.entry_id)
        return

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api_client = hass.data[DOMAIN][entry.entry_id]["api_client"]

    # Get new configuration values
    new_scan_interval = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
    new_timeout = entry.options.get(CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, 10))
    new_disabled_devices = entry.options.get(CONF_DISABLED_DEVICES, [])

    # Update API client timeout if changed
    current_timeout = getattr(api_client, "_timeout", 10)
    if new_timeout != current_timeout:
        api_client._timeout = new_timeout
        _LOGGER.info("Updated API client timeout to %d seconds", new_timeout)

    # Update coordinator configuration
    coordinator.update_configuration(new_scan_interval, new_disabled_devices)

    # Trigger a data refresh to apply the new configuration
    await coordinator.async_request_refresh()

    _LOGGER.info("Options updated successfully without reload")
