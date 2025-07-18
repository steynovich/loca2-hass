"""Constants for the Loca2 integration."""
from datetime import timedelta
import voluptuous as vol
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
)
import homeassistant.helpers.config_validation as cv

# Integration domain
DOMAIN = "loca2"

# Configuration constants  
CONF_BASE_URL = "base_url"
CONF_ENABLED_DEVICES = "enabled_devices"
CONF_DISABLED_DEVICES = "disabled_devices"
DEFAULT_BASE_URL = "https://www.mijnloca.nl"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

# API constants
API_TIMEOUT = 30
API_RETRIES = 3
API_BACKOFF_FACTOR = 2

# Entity constants
DEVICE_TRACKER_PLATFORM = "device_tracker"
ATTR_BATTERY_LEVEL = "battery_level"
ATTR_LAST_SEEN = "last_seen"
ATTR_DEVICE_TYPE = "device_type"
ATTR_GPS_ACCURACY = "gps_accuracy"

# Configuration schema
CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): cv.url,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})

# Options schema for config flow
OPTIONS_SCHEMA = vol.Schema({
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
        cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
    ),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Optional(CONF_DISABLED_DEVICES, default=[]): vol.All(cv.ensure_list, [cv.string]),
})

# Update interval
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

# Error messages
ERROR_AUTH_FAILED = "auth_failed"
ERROR_CANNOT_CONNECT = "cannot_connect"
ERROR_TIMEOUT = "timeout"
ERROR_UNKNOWN = "unknown"
ERROR_INVALID_SCAN_INTERVAL = "invalid_scan_interval"
ERROR_INVALID_TIMEOUT = "invalid_timeout"
ERROR_INVALID_DEVICE_LIST = "invalid_device_list"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_API_ERROR = "api_error"
ERROR_NETWORK_ERROR = "network_error"

# Diagnostic information keys
DIAG_API_RESPONSE_TIME = "api_response_time"
DIAG_LAST_ERROR = "last_error"
DIAG_ERROR_COUNT = "error_count"
DIAG_CONNECTION_STATUS = "connection_status"
DIAG_LAST_SUCCESS = "last_successful_update"
DIAG_RETRY_COUNT = "retry_count"
DIAG_RATE_LIMIT_INFO = "rate_limit_info"

# Logging levels for different scenarios
LOG_LEVEL_API_ERROR = "warning"
LOG_LEVEL_NETWORK_ERROR = "error"
LOG_LEVEL_AUTH_ERROR = "error"
LOG_LEVEL_RATE_LIMIT = "warning"
LOG_LEVEL_RECOVERY = "info"
LOG_LEVEL_DIAGNOSTIC = "debug"
LOG_LEVEL_PERFORMANCE = "info"

# Structured logging format templates
LOG_FORMAT_ERROR = "Loca2 error [%(category)s:%(error_type)s] after %(duration).2fs: %(message)s (consecutive: %(consecutive)d, context: %(context)s)"
LOG_FORMAT_RECOVERY = "Loca2 recovery: %(message)s (downtime: %(downtime).1fs, attempts: %(attempts)d)"
LOG_FORMAT_PERFORMANCE = "Loca2 performance: %(operation)s completed in %(duration).2fs (%(details)s)"
LOG_FORMAT_DIAGNOSTIC = "Loca2 diagnostic [%(component)s]: %(message)s"

# Enhanced diagnostic collection intervals
DIAGNOSTIC_HISTORY_SIZE = 100
DIAGNOSTIC_SUMMARY_INTERVAL = 300  # seconds
ERROR_HISTORY_MAX_SIZE = 50
PERFORMANCE_HISTORY_MAX_SIZE = 20

# User notification rate limiting
NOTIFICATION_RATE_LIMIT_SECONDS = 300  # 5 minutes
NOTIFICATION_RECOVERY_DELAY_SECONDS = 60  # 1 minute

# Health check constants
HEALTH_CHECK_INTERVAL = 120  # seconds
HEALTH_CHECK_TIMEOUT = 30  # seconds
HEALTH_STATUS_HEALTHY = "healthy"
HEALTH_STATUS_DEGRADED = "degraded"
HEALTH_STATUS_UNHEALTHY = "unhealthy"

# Error severity levels
ERROR_SEVERITY_LOW = "low"
ERROR_SEVERITY_MEDIUM = "medium"
ERROR_SEVERITY_HIGH = "high"
ERROR_SEVERITY_CRITICAL = "critical"

# Error recovery strategies
RECOVERY_STRATEGY_RETRY = "retry"
RECOVERY_STRATEGY_BACKOFF = "exponential_backoff"
RECOVERY_STRATEGY_RESET = "reset_connection"
RECOVERY_STRATEGY_NOTIFY = "notify_user"

# Performance monitoring thresholds
PERFORMANCE_SLOW_API_THRESHOLD = 5.0  # seconds
PERFORMANCE_VERY_SLOW_API_THRESHOLD = 10.0  # seconds
PERFORMANCE_SLOW_UPDATE_THRESHOLD = 30.0  # seconds

# Error recovery constants
MAX_CONSECUTIVE_ERRORS = 5
BACKOFF_BASE_DELAY = 1.0
BACKOFF_MAX_DELAY = 300.0
BACKOFF_MULTIPLIER = 2.0
RECOVERY_CHECK_INTERVAL = 60

# Notification constants
NOTIFICATION_ID_AUTH_FAILED = "loca2_auth_failed"
NOTIFICATION_ID_CONNECTION_LOST = "loca2_connection_lost"
NOTIFICATION_ID_RATE_LIMITED = "loca2_rate_limited"
NOTIFICATION_ID_RECOVERY = "loca2_recovery"
NOTIFICATION_ID_API_DEGRADED = "loca2_api_degraded"
NOTIFICATION_ID_HEALTH_CHECK_FAILED = "loca2_health_check_failed"

# Error categories for structured logging
ERROR_CATEGORY_AUTH = "authentication"
ERROR_CATEGORY_NETWORK = "network"
ERROR_CATEGORY_API = "api"
ERROR_CATEGORY_DATA = "data_validation"
ERROR_CATEGORY_CONFIG = "configuration"
ERROR_CATEGORY_LOCATION = "location_quality"
ERROR_CATEGORY_HEALTH_CHECK = "health_check"
ERROR_CATEGORY_NOTIFICATION = "notification"
ERROR_CATEGORY_UNKNOWN = "unknown"

# Device tracker states
STATE_HOME = "home"
STATE_NOT_HOME = "not_home"
STATE_UNAVAILABLE = "unavailable"