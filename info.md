# Loca2 Device Tracker

Track your Loca2 devices directly in Home Assistant with this comprehensive integration.

## What is Loca2 Device Tracker?

The Loca2 Device Tracker integration connects your Home Assistant instance to the Loca2 API, allowing you to monitor and track your Loca2 devices as native device tracker entities. This enables powerful location-based automations and monitoring within your smart home ecosystem.

## Key Features

🎯 **Native Device Tracking**
- Each Loca2 device appears as a device tracker entity
- Real-time location updates with configurable polling intervals
- Automatic state management (home/not_home/unavailable)

🔧 **Easy Configuration**
- Simple setup through Home Assistant's configuration flow
- No manual YAML configuration required
- Secure credential storage and validation

📊 **Rich Device Information**
- GPS coordinates with accuracy information
- Battery level monitoring and alerts
- Last seen timestamps
- Device type and metadata

🛡️ **Robust Error Handling**
- Automatic retry with exponential backoff
- Rate limiting detection and adjustment
- Graceful handling of network issues
- Comprehensive logging and diagnostics

⚙️ **Flexible Configuration**
- Configurable polling intervals (default: 30 seconds)
- Custom API timeout settings
- Per-device enable/disable options
- Runtime configuration changes without restart

## Perfect For

- **Family Tracking**: Monitor family members' locations
- **Asset Tracking**: Keep tabs on valuable items or vehicles
- **Pet Monitoring**: Track pets with Loca2-enabled collars
- **Security Systems**: Integrate with home security automations
- **Presence Detection**: Trigger automations based on location

## Automation Examples

**Welcome Home Automation**
```yaml
- alias: "Welcome home"
  trigger:
    platform: state
    entity_id: device_tracker.loca2_phone
    to: "home"
  action:
    - service: light.turn_on
      entity_id: light.entrance
    - service: climate.set_temperature
      data:
        temperature: 22
```

**Low Battery Alert**
```yaml
- alias: "Device low battery"
  trigger:
    platform: numeric_state
    entity_id: device_tracker.loca2_tracker
    attribute: battery_level
    below: 20
  action:
    service: notify.mobile_app
    data:
      message: "Loca2 device battery low: {{ states.device_tracker.loca2_tracker.attributes.battery_level }}%"
```

## Requirements

- Home Assistant 2023.1.0 or later
- Valid Loca2 API credentials
- Active Loca2 devices in your account
- Network connectivity to Loca2 API endpoints

## Installation

1. Install via HACS (this repository)
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services
4. Enter your Loca2 API credentials
5. Configure polling interval and other options
6. Start tracking your devices!

## Technical Highlights

- **Async Implementation**: Non-blocking operations following Home Assistant best practices
- **Modern Integration Pattern**: Uses DataUpdateCoordinator for efficient data management
- **Comprehensive Testing**: Full test suite with mocked API responses
- **Security First**: Encrypted credential storage and secure API communication
- **Performance Optimized**: Smart polling with rate limit awareness
- **HACS Compatible**: Easy installation, updates, and management

## Support & Documentation

- 📖 **Full Documentation**: Available in the repository README
- 🐛 **Issue Tracking**: GitHub Issues for bug reports and feature requests
- 💬 **Community Support**: Home Assistant Community forums
- 🔧 **Debug Logging**: Comprehensive logging for troubleshooting

## About Loca2

This integration works with Loca2 devices and services. You'll need an active Loca2 account and API access to use this integration. Visit the Loca2 website for more information about their tracking devices and services.

---

*This integration is not officially affiliated with Loca2. It's a community-developed integration that uses the Loca2 public API.*