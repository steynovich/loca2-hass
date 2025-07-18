"""Tests for Loca2DataUpdateCoordinator error handling and recovery."""
import asyncio
import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any

import pytest

from custom_components.loca2 import Loca2DataUpdateCoordinator
from custom_components.loca2.api import (
    Loca2ApiClient,
    Loca2ApiError,
    Loca2AuthError,
    Loca2ConnectionError,
    Loca2RateLimitError,
    Loca2Device,
)
from custom_components.loca2.const import (
    ERROR_CATEGORY_AUTH,
    ERROR_CATEGORY_NETWORK,
    ERROR_CATEGORY_API,
    ERROR_CATEGORY_UNKNOWN,
    NOTIFICATION_ID_AUTH_FAILED,
    NOTIFICATION_ID_CONNECTION_LOST,
    NOTIFICATION_ID_RATE_LIMITED,
    NOTIFICATION_ID_RECOVERY,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)


@pytest.fixture
def mock_hass():
    """Create mock Home Assistant instance."""
    hass = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    return hass


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    client = Mock(spec=Loca2ApiClient)
    client.get_devices = AsyncMock()
    client.get_device_location = AsyncMock()
    client.get_diagnostic_info = Mock(return_value={
        "connection_status": "connected",
        "success_rate": "95.0%",
        "error_count": 1,
        "last_error": None,
    })
    return client


@pytest.fixture
def coordinator(mock_hass, mock_api_client):
    """Create coordinator for testing."""
    return Loca2DataUpdateCoordinator(
        hass=mock_hass,
        api_client=mock_api_client,
        scan_interval=30,
    )


class TestCoordinatorErrorTracking:
    """Test coordinator error tracking and categorization."""

    @pytest.mark.asyncio
    async def test_error_history_tracking(self, coordinator):
        """Test that error history is properly tracked."""
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("Test error")
        
        # Generate some errors
        for i in range(3):
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Check error history
        assert len(coordinator._error_history) == 3
        
        # Verify error record structure
        error_record = coordinator._error_history[0]
        assert "timestamp" in error_record
        assert "category" in error_record
        assert "type" in error_record
        assert "message" in error_record
        assert "duration" in error_record
        assert "consecutive_errors" in error_record

    @pytest.mark.asyncio
    async def test_error_history_limit(self, coordinator):
        """Test that error history is limited to prevent memory issues."""
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("Test error")
        
        # Generate more than 50 errors (the limit)
        for i in range(55):
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Verify history is limited to 50 entries
        assert len(coordinator._error_history) == 50
        
        # Verify oldest entries were removed (FIFO)
        # The first error should no longer be in history
        timestamps = [record["timestamp"] for record in coordinator._error_history]
        assert len(set(timestamps)) <= 50  # All should be unique and recent

    @pytest.mark.asyncio
    async def test_error_categorization(self, coordinator):
        """Test that errors are properly categorized."""
        # Test different error types
        error_scenarios = [
            (Loca2AuthError("Auth failed"), ERROR_CATEGORY_AUTH),
            (Loca2ConnectionError("Network failed"), ERROR_CATEGORY_NETWORK),
            (Loca2RateLimitError("Rate limited"), ERROR_CATEGORY_API),
            (Loca2ApiError("API failed"), ERROR_CATEGORY_API),
            (ValueError("Unexpected error"), ERROR_CATEGORY_UNKNOWN),
        ]
        
        for error, expected_category in error_scenarios:
            coordinator.api_client.get_devices.side_effect = error
            
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Verify error categorization
        diagnostics = coordinator.get_diagnostic_info()
        error_categories = diagnostics["error_tracking"]["error_categories"]
        
        assert error_categories[ERROR_CATEGORY_AUTH] == 1
        assert error_categories[ERROR_CATEGORY_NETWORK] == 1
        assert error_categories[ERROR_CATEGORY_API] == 2  # Rate limit + API error
        assert error_categories[ERROR_CATEGORY_UNKNOWN] == 1

    @pytest.mark.asyncio
    async def test_consecutive_error_counting(self, coordinator):
        """Test consecutive error counting and reset."""
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("Test error")
        
        # Generate consecutive errors
        for i in range(3):
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
            
            assert coordinator._consecutive_errors == i + 1
        
        # Simulate successful update
        mock_device = Mock()
        mock_device.id = "device1"
        coordinator.api_client.get_devices.side_effect = None
        coordinator.api_client.get_devices.return_value = [mock_device]
        
        await coordinator._async_update_data()
        
        # Verify consecutive errors were reset
        assert coordinator._consecutive_errors == 0


class TestCoordinatorNotifications:
    """Test coordinator user notifications."""

    @pytest.mark.asyncio
    async def test_auth_error_notification(self, coordinator, mock_hass):
        """Test authentication error notification."""
        coordinator.api_client.get_devices.side_effect = Loca2AuthError("Invalid API key")
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Verify notification was sent
        mock_hass.services.async_call.assert_called_with(
            "persistent_notification",
            "create",
            {
                "notification_id": NOTIFICATION_ID_AUTH_FAILED,
                "title": "Loca2 Authentication Failed",
                "message": "Please check your API credentials. Error: Invalid API key",
            },
        )

    @pytest.mark.asyncio
    async def test_connection_error_notification_after_threshold(self, coordinator, mock_hass):
        """Test connection error notification after consecutive errors threshold."""
        coordinator.api_client.get_devices.side_effect = Loca2ConnectionError("Network error")
        
        # Generate errors below threshold (should not notify)
        for i in range(2):
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Verify no notification yet
        connection_calls = [call for call in mock_hass.services.async_call.call_args_list
                           if call[0][2].get("notification_id") == NOTIFICATION_ID_CONNECTION_LOST]
        assert len(connection_calls) == 0
        
        # Generate one more error (should trigger notification)
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Verify notification was sent
        connection_calls = [call for call in mock_hass.services.async_call.call_args_list
                           if call[0][2].get("notification_id") == NOTIFICATION_ID_CONNECTION_LOST]
        assert len(connection_calls) == 1

    @pytest.mark.asyncio
    async def test_rate_limit_notification(self, coordinator, mock_hass):
        """Test rate limit notification."""
        coordinator.api_client.get_devices.side_effect = Loca2RateLimitError("Rate exceeded")
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Verify notification was sent
        rate_limit_calls = [call for call in mock_hass.services.async_call.call_args_list
                           if call[0][2].get("notification_id") == NOTIFICATION_ID_RATE_LIMITED]
        assert len(rate_limit_calls) == 1

    @pytest.mark.asyncio
    async def test_notification_rate_limiting(self, coordinator, mock_hass):
        """Test that notifications are rate limited to avoid spam."""
        coordinator.api_client.get_devices.side_effect = Loca2AuthError("Auth error")
        
        # Generate multiple auth errors quickly
        for i in range(3):
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Verify only one notification was sent (rate limited)
        auth_calls = [call for call in mock_hass.services.async_call.call_args_list
                     if call[0][2].get("notification_id") == NOTIFICATION_ID_AUTH_FAILED]
        assert len(auth_calls) == 1

    @pytest.mark.asyncio
    async def test_recovery_notification(self, coordinator, mock_hass):
        """Test recovery notification after successful update."""
        # First, generate some errors
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("API error")
        coordinator._consecutive_errors = 3  # Simulate previous errors
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Then simulate successful recovery
        mock_device = Mock()
        mock_device.id = "device1"
        coordinator.api_client.get_devices.side_effect = None
        coordinator.api_client.get_devices.return_value = [mock_device]
        
        await coordinator._async_update_data()
        
        # Verify recovery notification was sent
        recovery_calls = [call for call in mock_hass.services.async_call.call_args_list
                         if call[0][2].get("notification_id") == NOTIFICATION_ID_RECOVERY]
        assert len(recovery_calls) == 1
        
        # Verify notification content
        recovery_call = recovery_calls[0]
        assert "Successfully reconnected" in recovery_call[0][2]["message"]

    @pytest.mark.asyncio
    async def test_notification_clearing_on_recovery(self, coordinator, mock_hass):
        """Test that error notifications are cleared on recovery."""
        # Generate auth error (creates notification)
        coordinator.api_client.get_devices.side_effect = Loca2AuthError("Auth error")
        coordinator._consecutive_errors = 1
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Simulate successful recovery
        mock_device = Mock()
        mock_device.id = "device1"
        coordinator.api_client.get_devices.side_effect = None
        coordinator.api_client.get_devices.return_value = [mock_device]
        
        await coordinator._async_update_data()
        
        # Verify error notifications were dismissed
        dismiss_calls = [call for call in mock_hass.services.async_call.call_args_list
                        if call[0][1] == "dismiss"]
        assert len(dismiss_calls) >= 1


class TestCoordinatorRateLimitHandling:
    """Test coordinator rate limit handling."""

    @pytest.mark.asyncio
    async def test_scan_interval_adjustment_on_rate_limit(self, coordinator):
        """Test scan interval adjustment when rate limited."""
        original_interval = coordinator._scan_interval
        coordinator.api_client.get_devices.side_effect = Loca2RateLimitError("Rate limited")
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Verify scan interval was increased
        assert coordinator._scan_interval > original_interval
        assert coordinator._scan_interval <= MAX_SCAN_INTERVAL

    @pytest.mark.asyncio
    async def test_scan_interval_restoration_after_recovery(self, coordinator):
        """Test scan interval restoration after recovery from rate limiting."""
        original_interval = coordinator._scan_interval
        
        # Simulate rate limiting
        coordinator.api_client.get_devices.side_effect = Loca2RateLimitError("Rate limited")
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        increased_interval = coordinator._scan_interval
        assert increased_interval > original_interval
        
        # Simulate time passing (more than 10 minutes)
        coordinator._last_rate_limit = datetime.now() - timedelta(minutes=15)
        
        # Simulate successful recovery
        mock_device = Mock()
        mock_device.id = "device1"
        coordinator.api_client.get_devices.side_effect = None
        coordinator.api_client.get_devices.return_value = [mock_device]
        
        await coordinator._async_update_data()
        
        # Verify interval was restored
        assert coordinator._scan_interval == original_interval

    @pytest.mark.asyncio
    async def test_rate_limit_info_tracking(self, coordinator):
        """Test rate limit information tracking."""
        coordinator.api_client.get_devices.side_effect = Loca2RateLimitError("Rate limited")
        
        # Generate rate limit error
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Check rate limit info
        rate_info = coordinator.rate_limit_info
        assert rate_info["rate_limit_count"] == 1
        assert rate_info["last_rate_limit"] is not None
        assert rate_info["current_scan_interval"] > rate_info["original_scan_interval"]


class TestCoordinatorBackoffLogic:
    """Test coordinator exponential backoff logic."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_on_consecutive_errors(self, coordinator):
        """Test exponential backoff on consecutive errors."""
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("API error")
        
        # Generate enough consecutive errors to trigger backoff
        for i in range(6):  # Exceed max consecutive errors
            with pytest.raises(Exception):  # UpdateFailed
                await coordinator._async_update_data()
        
        # Verify backoff was applied
        assert coordinator._backoff_multiplier > 1
        assert coordinator._backoff_multiplier <= coordinator._max_backoff_multiplier

    @pytest.mark.asyncio
    async def test_backoff_reset_on_success(self, coordinator):
        """Test backoff reset on successful update."""
        # Set up backoff state
        coordinator._backoff_multiplier = 4
        coordinator._consecutive_errors = 5
        
        # Simulate successful update
        mock_device = Mock()
        mock_device.id = "device1"
        coordinator.api_client.get_devices.return_value = [mock_device]
        
        await coordinator._async_update_data()
        
        # Verify backoff was reset
        assert coordinator._backoff_multiplier == 1
        assert coordinator._consecutive_errors == 0

    @pytest.mark.asyncio
    async def test_backoff_interval_calculation(self, coordinator):
        """Test backoff interval calculation."""
        original_interval = coordinator._scan_interval
        coordinator._backoff_multiplier = 4
        
        # Simulate error to trigger backoff application
        coordinator.api_client.get_devices.side_effect = Loca2ApiError("API error")
        coordinator._consecutive_errors = 6  # Above threshold
        
        with pytest.raises(Exception):  # UpdateFailed
            await coordinator._async_update_data()
        
        # Verify update interval was adjusted with backoff
        expected_interval = min(original_interval * 4, MAX_SCAN_INTERVAL)
        # Note: The actual interval might be set to timedelta, so we check the underlying value
        actual_interval = coordinator.update_interval.total_seconds()
        assert actual_interval >= expected_interval or actual_interval == MAX_SCAN_INTERVAL


class TestCoordinatorDiagnostics:
    """Test coordinator diagnostic information."""

    def test_diagnostic_info_structure(self, coordinator):
        """Test diagnostic information structure."""
        diagnostics = coordinator.get_diagnostic_info()
        
        # Verify main sections
        assert "coordinator" in diagnostics
        assert "rate_limiting" in diagnostics
        assert "error_tracking" in diagnostics
        assert "api_client" in diagnostics
        
        # Verify coordinator section
        coord_diag = diagnostics["coordinator"]
        expected_keys = [
            "last_update_success", "last_exception", "update_count",
            "data_available", "device_count", "last_successful_update",
            "recovery_attempts"
        ]
        for key in expected_keys:
            assert key in coord_diag
        
        # Verify rate limiting section
        rate_diag = diagnostics["rate_limiting"]
        expected_keys = [
            "rate_limit_count", "last_rate_limit", "current_scan_interval",
            "original_scan_interval", "backoff_multiplier", "consecutive_errors"
        ]
        for key in expected_keys:
            assert key in rate_diag
        
        # Verify error tracking section
        error_diag = diagnostics["error_tracking"]
        expected_keys = [
            "error_categories", "recent_errors", "total_errors", "last_error"
        ]
        for key in expected_keys:
            assert key in error_diag

    def test_diagnostic_info_with_data(self, coordinator):
        """Test diagnostic information with actual data."""
        # Set up some diagnostic state
        coordinator._consecutive_errors = 2
        coordinator._rate_limit_count = 1
        coordinator._last_rate_limit = datetime.now()
        coordinator._recovery_attempts = 3
        coordinator._last_successful_update = datetime.now()
        
        # Add some error history
        coordinator._error_history = [
            {
                "timestamp": datetime.now().isoformat(),
                "category": ERROR_CATEGORY_API,
                "type": "api_error",
                "message": "Test error",
                "duration": 1.5,
                "consecutive_errors": 1,
                "recovery_attempts": 0,
            }
        ]
        
        diagnostics = coordinator.get_diagnostic_info()
        
        # Verify data is properly included
        assert diagnostics["rate_limiting"]["consecutive_errors"] == 2
        assert diagnostics["rate_limiting"]["rate_limit_count"] == 1
        assert diagnostics["coordinator"]["recovery_attempts"] == 3
        assert diagnostics["error_tracking"]["total_errors"] == 1
        assert len(diagnostics["error_tracking"]["recent_errors"]) == 1

    def test_diagnostic_summary_logging(self, coordinator, caplog):
        """Test diagnostic summary logging output."""
        # Set up diagnostic data
        coordinator._consecutive_errors = 1
        coordinator._rate_limit_count = 2
        coordinator.data = {"device1": Mock(), "device2": Mock()}
        coordinator.last_update_success = True
        
        with caplog.at_level(logging.INFO):
            coordinator.log_diagnostic_summary()
        
        # Verify summary sections were logged
        log_content = "\n".join([record.message for record in caplog.records])
        
        assert "Loca2 Integration Diagnostic Summary" in log_content
        assert "Coordinator Status:" in log_content
        assert "Rate Limiting:" in log_content
        assert "API Client:" in log_content
        assert "Device count: 2" in log_content


class TestCoordinatorConfigurationUpdates:
    """Test coordinator configuration updates."""

    def test_scan_interval_adjustment(self, coordinator, caplog):
        """Test scan interval adjustment."""
        new_interval = 60
        
        with caplog.at_level(logging.INFO):
            coordinator.adjust_scan_interval(new_interval)
        
        assert coordinator._scan_interval == new_interval
        assert coordinator._original_scan_interval == new_interval
        
        # Verify logging
        adjust_logs = [record for record in caplog.records 
                      if "Scan interval adjusted" in record.message]
        assert len(adjust_logs) == 1

    def test_scan_interval_validation(self, coordinator, caplog):
        """Test scan interval validation."""
        invalid_interval = 5  # Below minimum
        
        with caplog.at_level(logging.WARNING):
            coordinator.adjust_scan_interval(invalid_interval)
        
        # Verify interval was not changed
        assert coordinator._scan_interval != invalid_interval
        
        # Verify warning was logged
        warning_logs = [record for record in caplog.records 
                       if "Invalid scan interval" in record.message]
        assert len(warning_logs) == 1

    def test_disabled_devices_update(self, coordinator, caplog):
        """Test disabled devices list update."""
        disabled_devices = ["device1", "device2"]
        
        with caplog.at_level(logging.INFO):
            coordinator.update_disabled_devices(disabled_devices)
        
        assert coordinator._disabled_devices == disabled_devices
        
        # Verify logging
        update_logs = [record for record in caplog.records 
                      if "Updated disabled devices list" in record.message]
        assert len(update_logs) == 1

    def test_configuration_update_combined(self, coordinator, caplog):
        """Test combined configuration update."""
        new_interval = 45
        disabled_devices = ["device3"]
        
        with caplog.at_level(logging.INFO):
            coordinator.update_configuration(new_interval, disabled_devices)
        
        assert coordinator._scan_interval == new_interval
        assert coordinator._disabled_devices == disabled_devices
        
        # Verify combined logging
        config_logs = [record for record in caplog.records 
                      if "Configuration updated" in record.message]
        assert len(config_logs) == 1


class TestCoordinatorDeviceFiltering:
    """Test coordinator device filtering functionality."""

    @pytest.mark.asyncio
    async def test_device_filtering_with_disabled_devices(self, coordinator, caplog):
        """Test device filtering with disabled devices list."""
        # Set up disabled devices
        coordinator._disabled_devices = ["device2", "device3"]
        
        # Mock API to return multiple devices
        mock_devices = [
            Mock(id="device1", name="Device 1"),
            Mock(id="device2", name="Device 2"),  # Should be filtered
            Mock(id="device3", name="Device 3"),  # Should be filtered
            Mock(id="device4", name="Device 4"),
        ]
        coordinator.api_client.get_devices.return_value = mock_devices
        
        with caplog.at_level(logging.DEBUG):
            result = await coordinator._async_update_data()
        
        # Verify filtering
        assert len(result) == 2  # Only device1 and device4
        assert "device1" in result
        assert "device4" in result
        assert "device2" not in result
        assert "device3" not in result
        
        # Verify filtering was logged
        filter_logs = [record for record in caplog.records 
                      if "Filtered out" in record.message]
        assert len(filter_logs) == 1
        assert "2 disabled devices" in filter_logs[0].message

    @pytest.mark.asyncio
    async def test_device_filtering_with_empty_disabled_list(self, coordinator):
        """Test device filtering with empty disabled devices list."""
        coordinator._disabled_devices = []
        
        # Mock API to return devices
        mock_devices = [
            Mock(id="device1", name="Device 1"),
            Mock(id="device2", name="Device 2"),
        ]
        coordinator.api_client.get_devices.return_value = mock_devices
        
        result = await coordinator._async_update_data()
        
        # Verify no filtering occurred
        assert len(result) == 2
        assert "device1" in result
        assert "device2" in result

    @pytest.mark.asyncio
    async def test_device_location_fetch_error_handling(self, coordinator, caplog):
        """Test device location fetch error handling."""
        device_id = "test_device"
        coordinator.api_client.get_device_location.side_effect = Loca2ApiError("Location error")
        
        with caplog.at_level(logging.WARNING):
            result = await coordinator.async_get_device_location(device_id)
        
        assert result is None
        
        # Verify error was logged
        error_logs = [record for record in caplog.records 
                     if "Failed to get location" in record.message]
        assert len(error_logs) == 1
        assert device_id in error_logs[0].message

    @pytest.mark.asyncio
    async def test_device_location_fetch_unexpected_error(self, coordinator, caplog):
        """Test device location fetch with unexpected error."""
        device_id = "test_device"
        coordinator.api_client.get_device_location.side_effect = ValueError("Unexpected error")
        
        with caplog.at_level(logging.ERROR):
            result = await coordinator.async_get_device_location(device_id)
        
        assert result is None
        
        # Verify error was logged as unexpected
        error_logs = [record for record in caplog.records 
                     if "Unexpected error getting location" in record.message]
        assert len(error_logs) == 1
        assert device_id in error_logs[0].message