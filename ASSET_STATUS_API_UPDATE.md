# Loca2 Asset Status API Integration

## Overview

Updated the Loca2 Home Assistant integration to use the comprehensive `/assetstatuslist` endpoint instead of the basic `/devices` endpoint. This provides much richer device information including real-time location, battery status, and detailed asset information.

## API Endpoint Change

### Before
- **Endpoint**: `/devices`
- **Data**: Basic asset and device information
- **Location**: Separate API call required

### After
- **Endpoint**: `/assetstatuslist`
- **Data**: Complete asset status with embedded location and history
- **Location**: Included in the same response

## Enhanced Data Structure

### Asset Status Response Format
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
      "type": 3,
      "locationupdate": {
        "timeofday": 120000,
        "frequency": 86400,
        "always": 1,
        "begin": 0,
        "end": 0
      }
    },
    "Device": {
      "type": 2,
      "version": 2
    },
    "Spot": {
      "id": 16839075,
      "device": 20618,
      "asset": 16250,
      "user": 7688,
      "origin": 1,
      "time": 1752840052,
      "label": "",
      "latitude": 52.228127,
      "longitude": 5.074509,
      "number": "18 d",
      "street": "Zuwe",
      "city": "Kortenhoef",
      "district": "Wijdemeren",
      "region": "",
      "state": "Noord-Holland",
      "zipcode": "1241NC",
      "country": "Netherlands"
    },
    "History": {
      "time": 1752840052,
      "report": 10201,
      "latitude": 52.22793,
      "longitude": 5.073918,
      "speed": 6.6,
      "motion": 0,
      "charge": 73,
      "HDOP": 1,
      "SATU": 11,
      "strength": 18,
      "quality": 0
    }
  }
]
```

## Updated Device Model

### Enhanced Loca2Device Class
The device model now includes comprehensive information from all API sections:

#### Asset Information
- `id` - Asset ID (primary identifier)
- `name` - Asset label/name
- `device_type` - Mapped device type
- `serial` - Serial number
- `brand` - Manufacturer brand
- `model` - Device model
- `group` - Asset group ID
- `asset_type_id` - Asset type identifier

#### Device Information
- `device_id` - Internal device ID
- `device_type_id` - Device type identifier
- `device_version` - Firmware version

#### Location Information (from Spot)
- `latitude` - Current latitude
- `longitude` - Current longitude
- `address` - Street address
- `city` - City name
- `state` - State/province
- `country` - Country name
- `zipcode` - Postal code
- `location_time` - Location timestamp

#### Status Information (from History)
- `battery_level` - Battery charge percentage
- `last_seen` - Last communication timestamp
- `speed` - Current speed
- `motion` - Motion status
- `signal_strength` - Cellular signal strength
- `gps_accuracy` - GPS accuracy (HDOP)
- `satellites` - Number of GPS satellites

## Device Type Mapping

Enhanced device type mapping based on asset type IDs:
- `1` → `gps_tracker`
- `2` → `marine_tracker`
- `3` → `vehicle_tracker`
- `4` → `personal_tracker`
- `5` → `asset_tracker`

## Icon Selection Logic

Improved icon selection based on device type and brand:
- **Marine/Boat**: `mdi:ferry` (for marine trackers or Interboat brand)
- **Vehicle**: `mdi:car` (for vehicle trackers)
- **Personal**: `mdi:account-circle` (for personal trackers)
- **Asset**: `mdi:package-variant` (for asset trackers)
- **GPS**: `mdi:crosshairs-gps` (for generic GPS trackers)

## Location Integration

### Embedded Location Data
Location information is now embedded in the device response, eliminating the need for separate location API calls:

```python
# Before: Separate API call required
location = await api_client.get_device_location(device_id)

# After: Location included in device data
devices = await api_client.get_devices()  # Includes location
device = devices[0]
latitude = device.latitude
longitude = device.longitude
```

### Address Information
Rich address information is now available:
- Street number and name
- City, state, country
- Postal code
- Full formatted address

## Device Tracker Enhancements

### Enhanced Attributes
Device tracker entities now expose comprehensive attributes:

```yaml
# Basic attributes
battery_level: 73
last_seen: "2025-07-18T10:30:52"
device_type: "vehicle_tracker"

# Asset information
serial: "#1"
brand: "Interboat"
model: "Intender 820"
group: 8529
asset_type_id: 3

# Device information
device_id: 20618
device_type_id: 2
device_version: 2

# Location information
address: "18 d Zuwe"
city: "Kortenhoef"
state: "Noord-Holland"
country: "Netherlands"
zipcode: "1241NC"
location_time: "2025-07-18T10:30:52"

# Status information
speed: 6.6
motion: 0
signal_strength: 18
satellites: 11
gps_accuracy: 1.0
```

### Improved Location Properties
Location properties now prioritize embedded device location data:

```python
@property
def latitude(self) -> Optional[float]:
    # First check embedded device location
    if self.device and self.device.latitude is not None:
        return self.device.latitude
    # Fallback to separate location object
    if self._location:
        return self._location.latitude
    return None
```

## Performance Benefits

### Reduced API Calls
- **Before**: 2 API calls (devices + location per device)
- **After**: 1 API call (asset status with everything)

### Real-time Data
- **Before**: Location data might be stale
- **After**: Real-time location, battery, and status in single call

### Rich Context
- **Before**: Basic device information
- **After**: Complete asset context with history and location

## Timestamp Handling

Enhanced timestamp parsing for Unix timestamps:
```python
@staticmethod
def _convert_timestamp(timestamp: Any) -> Optional[datetime]:
    """Convert Unix timestamp to datetime object."""
    if isinstance(timestamp, (int, float)):
        # Handle both seconds and milliseconds timestamps
        if timestamp > 1e10:  # Likely milliseconds
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp)
```

## Error Handling

Improved error handling for the new data structure:
- Graceful handling of missing sections (Asset, Device, Spot, History)
- Validation of required fields
- Fallback values for optional data
- Detailed logging for parsing errors

## Migration Impact

### For Users
- **Richer Information**: More detailed device information in Home Assistant
- **Better Performance**: Faster updates with fewer API calls
- **Enhanced Automation**: More attributes available for automation rules

### For Developers
- **Simplified API**: Single endpoint for complete device status
- **Better Data Model**: Comprehensive device representation
- **Improved Maintainability**: Cleaner code with embedded location data

## Testing Results

✅ **API Integration**: Successfully parses asset status response
✅ **Device Creation**: Creates devices with all attributes
✅ **Location Data**: Properly extracts and formats location information
✅ **Battery Status**: Correctly maps charge percentage
✅ **Address Formatting**: Builds complete address strings
✅ **Timestamp Conversion**: Handles Unix timestamps correctly

## Future Enhancements

### Potential Improvements
1. **Motion Detection**: Use motion status for presence detection
2. **Speed Monitoring**: Track vehicle speed for automation
3. **Signal Quality**: Monitor connectivity status
4. **Geofencing**: Use rich location data for advanced geofencing
5. **Historical Data**: Potentially access historical location data

This update significantly enhances the Loca2 integration by providing comprehensive real-time device status information in a single API call, improving both performance and functionality.