# Design Document

## Overview

The Loca2 Home Assistant integration is a custom component that enables tracking of Loca2 devices through their RESTful API. The integration follows Home Assistant's modern integration patterns, implements the config flow for setup, and provides device tracker entities for each Loca2 device. It's designed to be HACS-compatible and follows all Home Assistant development best practices.

## Architecture

### Component Structure
```
custom_components/loca2/
├── __init__.py           # Integration setup and coordinator
├── manifest.json         # Integration metadata
├── config_flow.py        # Configuration flow UI
├── device_tracker.py     # Device tracker platform
├── const.py             # Constants and configuration
├── api.py               # Loca2 API client
└── strings.json         # UI strings and translations
```

### Core Components

1. **Integration Entry Point** (`__init__.py`)
   - Manages integration lifecycle
   - Sets up the data update coordinator
   - Handles integration reload and unload

2. **Data Update Coordinator**
   - Centralized data fetching from Loca2 API
   - Manages polling intervals and error handling
   - Coordinates updates across all device tracker entities

3. **Config Flow** (`config_flow.py`)
   - Handles initial setup and authentication
   - Validates API credentials
   - Manages integration options and reconfiguration

4. **API Client** (`api.py`)
   - Abstracts Loca2 RESTful API interactions
   - Handles authentication and rate limiting
   - Provides typed data models for API responses

5. **Device Tracker Platform** (`device_tracker.py`)
   - Creates device tracker entities for each Loca2 device
   - Updates location data from coordinator
   - Manages device attributes and state

## Components and Interfaces

### API Client Interface
```python
class Loca2ApiClient:
    async def authenticate(self, api_key: str, base_url: str) -> bool
    async def get_devices(self) -> List[Loca2Device]
    async def get_device_location(self, device_id: str) -> Loca2Location
    async def test_connection(self) -> bool
```

### Data Models
```python
@dataclass
class Loca2Device:
    id: str
    name: str
    device_type: str
    battery_level: Optional[int]
    last_seen: datetime

@dataclass
class Loca2Location:
    latitude: float
    longitude: float
    accuracy: Optional[float]
    timestamp: datetime
    address: Optional[str]
```

### Configuration Schema
```python
CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_BASE_URL): cv.url,
    vol.Optional(CONF_SCAN_INTERVAL, default=30): cv.positive_int,
    vol.Optional(CONF_TIMEOUT, default=10): cv.positive_int,
})
```

### Coordinator Interface
```python
class Loca2DataUpdateCoordinator(DataUpdateCoordinator):
    async def _async_update_data(self) -> Dict[str, Loca2Device]
    async def async_get_device_location(self, device_id: str) -> Loca2Location
```

## Data Models

### Device Tracker Entity
- **Entity ID**: `device_tracker.loca2_{device_name}`
- **State**: `home`, `not_home`, `unavailable`
- **Attributes**:
  - `latitude`: Current latitude
  - `longitude`: Current longitude
  - `gps_accuracy`: Location accuracy in meters
  - `battery_level`: Device battery percentage
  - `last_seen`: Last update timestamp
  - `device_type`: Type of Loca2 device
  - `source_type`: Always `gps`

### Configuration Data
- **API Key**: Encrypted storage in Home Assistant's configuration
- **Base URL**: Loca2 API endpoint
- **Scan Interval**: Polling frequency in seconds
- **Timeout**: API request timeout

## Error Handling

### API Error Scenarios
1. **Authentication Failures**
   - Log error and mark integration as failed
   - Trigger reconfiguration flow
   - Show notification to user

2. **Network Connectivity Issues**
   - Implement exponential backoff retry logic
   - Mark entities as unavailable during outages
   - Resume normal operation when connectivity restored

3. **Rate Limiting**
   - Respect API rate limits
   - Automatically adjust polling intervals
   - Log warnings when approaching limits

4. **Invalid Device Data**
   - Skip malformed device records
   - Log warnings for debugging
   - Continue processing other devices

### Error Recovery Strategies
- **Coordinator Level**: Retry failed API calls with exponential backoff
- **Entity Level**: Mark entities unavailable during coordinator failures
- **Integration Level**: Graceful degradation and automatic recovery

## Testing Strategy

### Unit Tests
1. **API Client Tests**
   - Mock HTTP responses for all API endpoints
   - Test authentication success/failure scenarios
   - Verify proper error handling and retries

2. **Coordinator Tests**
   - Test data update cycles
   - Verify error handling and recovery
   - Test polling interval adjustments

3. **Config Flow Tests**
   - Test setup flow with valid/invalid credentials
   - Test options flow for configuration changes
   - Verify error message display

4. **Device Tracker Tests**
   - Test entity creation and updates
   - Verify attribute mapping from API data
   - Test state transitions (home/not_home/unavailable)

### Integration Tests
1. **End-to-End Setup**
   - Test complete integration setup process
   - Verify entity creation and initial data load
   - Test integration reload and unload

2. **API Integration**
   - Test against mock Loca2 API server
   - Verify proper handling of various API responses
   - Test rate limiting and error scenarios

### HACS Compatibility Tests
1. **Manifest Validation**
   - Verify manifest.json meets HACS requirements
   - Test integration discovery and installation
   - Validate version management

2. **Code Quality**
   - Run Home Assistant's integration validation tools
   - Ensure compliance with coding standards
   - Verify proper async/await usage

## HACS Integration Requirements

### Manifest Configuration
```json
{
  "domain": "loca2",
  "name": "Loca2 Device Tracker",
  "version": "1.0.0",
  "documentation": "https://github.com/steynovich/loca2-hass",
  "issue_tracker": "https://github.com/steynovich/loca2-hass/issues",
  "dependencies": [],
  "codeowners": ["@steynovich"],
  "requirements": ["aiohttp>=3.8.0"],
  "iot_class": "cloud_polling",
  "config_flow": true
}
```

### Repository Structure
- README.md with installation and configuration instructions
- CHANGELOG.md for version history
- LICENSE file
- .github/workflows/ for CI/CD
- info.md for HACS store description

### Version Management
- Semantic versioning (MAJOR.MINOR.PATCH)
- Git tags for releases
- Automated release process through GitHub Actions

## Security Considerations

### API Key Storage
- Use Home Assistant's encrypted storage for API keys
- Never log API keys or sensitive authentication data
- Implement secure credential validation

### Network Security
- Use HTTPS for all API communications
- Validate SSL certificates
- Implement request timeouts to prevent hanging connections

### Data Privacy
- Minimize data retention (only current location)
- Respect user privacy settings
- Provide clear data usage documentation

## Performance Optimization

### Efficient Polling
- Configurable polling intervals
- Batch API requests when possible
- Implement smart polling based on device activity

### Memory Management
- Limit cached location history
- Clean up unused device references
- Efficient data structures for device storage

### Network Optimization
- Connection pooling for HTTP requests
- Compression support for API responses
- Minimal payload requests when possible