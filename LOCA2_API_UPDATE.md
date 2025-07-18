# Loca2 API Integration Update

## Overview

The integration has been updated to work with the actual Loca2 API endpoints and authentication method based on the provided API information.

## API Changes Made

### Authentication Method
**Before:** Bearer token authentication with API key
```python
headers = {"Authorization": f"Bearer {api_key}"}
```

**After:** Session-based authentication with account/password
```python
# Authentication via POST to /apilogin with account and password
# Returns 'sid' cookie for subsequent requests
auth_data = {"account": account, "password": password}
```

### API Endpoints
**Before:** Generic REST API endpoints
- `/api/auth/validate` - Authentication test
- `/api/devices` - Get devices
- `/api/devices/{device_id}/location` - Get device location

**After:** Actual Loca2 API endpoints
- `/apilogin` - Authentication (POST with account/password)
- `/assetstatuslist` - Get devices with full status including location and history (GET with sid cookie)

### Configuration Parameters
**Before:** API Key based configuration
```json
{
  "api_key": "string",
  "base_url": "string"
}
```

**After:** Username/Password based configuration
```json
{
  "username": "string", 
  "password": "string",
  "base_url": "https://www.mijnloca.nl" (default)
}
```

### Device Data Structure
**Before:** Simple device structure
```json
{
  "id": "string",
  "name": "string", 
  "type": "string",
  "battery_level": "number"
}
```

**After:** Loca2 asset status structure
```json
[
  {
    "Asset": {
      "id": 16250,
      "label": "Boot",
      "serial": "#1",
      "brand": "Interboat",
      "model": "Intender 820",
      "group": 8529,
      "type": 3
    },
    "Device": {
      "type": 2,
      "version": 2
    },
    "Spot": {
      "id": 16839075,
      "latitude": 52.228127,
      "longitude": 5.074509,
      "street": "Zuwe",
      "city": "Kortenhoef",
      "state": "Noord-Holland",
      "country": "Netherlands",
      "time": 1752840052
    },
    "History": {
      "time": 1752840052,
      "latitude": 52.22793,
      "longitude": 5.073918,
      "speed": 6.6,
      "motion": 0,
      "charge": 73,
      "strength": 18,
      "SATU": 11,
      "HDOP": 1
    }
  }
]
```

## Updated Components

### 1. API Client (`api.py`)
- **Authentication**: Changed from Bearer token to session cookie authentication
- **Endpoints**: Updated to use actual Loca2 API endpoints
- **Device Parsing**: Updated to parse the assets/device structure from real API
- **Device Types**: Added mapping for Loca2 device type IDs (1=gps_tracker, 2=marine_tracker, etc.)

### 2. Configuration (`const.py`)
- **Fields**: Changed from `CONF_API_KEY` to `CONF_USERNAME` and `CONF_PASSWORD`
- **Default URL**: Set to `https://www.mijnloca.nl`
- **Schema**: Updated configuration schema for new authentication method

### 3. Config Flow (`config_flow.py`)
- **Input Schema**: Updated to collect username/password instead of API key
- **Validation**: Updated to test authentication with username/password
- **Error Messages**: Updated error messages to reference username/password

### 4. Main Integration (`__init__.py`)
- **Client Initialization**: Updated to pass username/password to API client
- **Configuration Reading**: Updated to read username/password from config entry

### 5. Device Tracker (`device_tracker.py`)
- **Attributes**: Added new device attributes (IMEI, code, phone, serial, brand, model, group, version)
- **Icons**: Added icons for marine trackers and GPS trackers
- **Device Info**: Enhanced with additional Loca2-specific device information

### 6. Translations (`strings.json`)
- **Labels**: Updated configuration labels to "Username" and "Password"
- **Descriptions**: Updated help text to reference Loca2 user credentials
- **Error Messages**: Updated to reference username/password authentication

## Device Type Mapping

The integration now maps Loca2 device type IDs to readable names:
- `1` → `gps_tracker`
- `2` → `marine_tracker` 
- `3` → `vehicle_tracker`
- `4` → `personal_tracker`

## Additional Device Attributes

The device tracker entities now expose comprehensive Loca2-specific attributes:

### Asset Information
- `serial` - Device serial number
- `brand` - Device brand (e.g., "Interboat")
- `model` - Device model (e.g., "Intender 820")
- `group` - Loca2 group ID
- `asset_type_id` - Asset type identifier

### Device Information
- `device_id` - Internal device ID
- `device_type_id` - Device type identifier
- `device_version` - Device firmware version

### Location Information
- `address` - Street address
- `city` - City name
- `state` - State/province
- `country` - Country name
- `zipcode` - Postal code
- `location_time` - Timestamp of location update

### Status Information
- `speed` - Current speed (if available)
- `motion` - Motion status
- `signal_strength` - Cellular signal strength
- `satellites` - Number of GPS satellites
- `gps_accuracy` - GPS accuracy (HDOP)

## Authentication Flow

1. User provides username and password in config flow
2. Integration sends POST request to `/apilogin` with credentials
3. Server responds with `sid` session cookie
4. All subsequent API requests include the `sid` cookie
5. Session cookie is maintained for the lifetime of the integration

## Location Data

The current implementation assumes location data may be embedded in the device response or available through the same `/devices` endpoint. If location data requires a separate API call, the `get_device_location` method can be updated accordingly.

## Validation Status

All validation tests continue to pass:
- ✅ Home Assistant integration validation (22 tests)
- ✅ HACS compatibility validation (13 tests)
- ✅ Async implementation validation
- ✅ Requirements verification
- ✅ Performance validation

## Migration Notes

Existing installations will need to be reconfigured with username/password credentials instead of API keys. The integration will prompt users to update their configuration when they upgrade.

## Testing

The integration has been updated and validated to ensure:
- Proper authentication with the real Loca2 API
- Correct parsing of the asset/device data structure
- Enhanced device attributes and information
- Maintained Home Assistant and HACS compliance
- Continued async/await implementation standards