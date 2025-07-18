# Loca2 Device Tracker for Home Assistant

[![CI](https://github.com/steynovich/loca2-hass/workflows/CI/badge.svg)](https://github.com/steynovich/loca2-hass/actions/workflows/ci.yml)
[![HACS Validation](https://github.com/steynovich/loca2-hass/workflows/HACS%20Validation/badge.svg)](https://github.com/steynovich/loca2-hass/actions/workflows/hacs.yml)
[![Home Assistant Validation](https://github.com/steynovich/loca2-hass/workflows/Home%20Assistant%20Validation/badge.svg)](https://github.com/steynovich/loca2-hass/actions/workflows/hassfest.yml)
[![Code Quality](https://github.com/steynovich/loca2-hass/workflows/Code%20Quality/badge.svg)](https://github.com/steynovich/loca2-hass/actions/workflows/code-quality.yml)
[![codecov](https://codecov.io/gh/steynovich/loca2-hass/branch/main/graph/badge.svg)](https://codecov.io/gh/steynovich/loca2-hass)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/steynovich/loca2-hass.svg)](https://github.com/steynovich/loca2-hass/releases)
[![License](https://img.shields.io/github/license/steynovich/loca2-hass.svg)](LICENSE)

A Home Assistant integration that tracks the location of Loca2 devices through their RESTful API. This integration provides device tracker entities for each Loca2 device, enabling location-based automations and monitoring within Home Assistant.

## Features

- 🎯 **Device Tracking**: Monitor Loca2 devices as device tracker entities
- 🔄 **Real-time Updates**: Configurable polling intervals for location updates
- 🛡️ **Error Handling**: Robust error handling with automatic retry and recovery
- ⚙️ **Easy Configuration**: Simple setup through Home Assistant's UI
- 📊 **Rich Attributes**: Battery level, accuracy, last seen, and more
- 🏠 **HACS Compatible**: Easy installation and updates through HACS

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/steynovich/loca2-hass`
6. Select "Integration" as the category
7. Click "Add"
8. Find "Loca2 Device Tracker" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/steynovich/loca2-hass/releases)
2. Extract the contents
3. Copy the `custom_components/loca2` folder to your Home Assistant `custom_components` directory
4. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Loca2 Device Tracker"
4. Enter your Loca2 credentials:
   - **Username**: Your Loca2 username
   - **Password**: Your Loca2 password
   - **Base URL**: Your Loca2 API endpoint URL (default: https://www.mijnloca.nl)
5. Click **Submit**

### Configuration Options

After initial setup, you can configure additional options:

1. Go to **Settings** → **Devices & Services**
2. Find the Loca2 integration
3. Click **Configure**
4. Adjust the following settings:
   - **Scan Interval**: How often to poll for location updates (default: 30 seconds)
   - **Request Timeout**: API request timeout (default: 10 seconds)

## Usage

Once configured, the integration will:

1. **Discover Devices**: Automatically find all Loca2 devices associated with your account
2. **Create Entities**: Each device becomes a `device_tracker` entity
3. **Update Locations**: Regularly poll for location updates
4. **Handle Errors**: Gracefully handle network issues and API errors

### Device Tracker Entities

Each Loca2 device will appear as a device tracker entity with the format:
```
device_tracker.loca2_{device_name}
```

#### Entity States
- `home`: Device is at a known location
- `not_home`: Device is away from known locations  
- `unavailable`: Device is offline or unreachable

#### Entity Attributes
- `latitude`: Current latitude coordinate
- `longitude`: Current longitude coordinate
- `gps_accuracy`: Location accuracy in meters
- `battery_level`: Device battery percentage
- `last_seen`: Timestamp of last location update
- `device_type`: Type of Loca2 device
- `source_type`: Always set to `gps`

## Automation Examples

### Location-Based Automation
```yaml
automation:
  - alias: "Notify when device leaves home"
    trigger:
      - platform: state
        entity_id: device_tracker.loca2_my_device
        from: "home"
        to: "not_home"
    action:
      - service: notify.mobile_app
        data:
          message: "Device has left home"
```

### Battery Alert
```yaml
automation:
  - alias: "Low battery alert"
    trigger:
      - platform: numeric_state
        entity_id: device_tracker.loca2_my_device
        attribute: battery_level
        below: 20
    action:
      - service: notify.mobile_app
        data:
          message: "Loca2 device battery is low ({{ state_attr('device_tracker.loca2_my_device', 'battery_level') }}%)"
```

## Troubleshooting

### Common Issues

#### Integration Not Loading
- Check Home Assistant logs for error messages
- Verify username and password are correct
- Ensure Loca2 API endpoint is accessible

#### Devices Not Appearing
- Verify devices are associated with your Loca2 account
- Check if devices are online and reporting locations
- Review integration logs for API errors

#### Location Updates Not Working
- Check scan interval configuration
- Verify network connectivity to Loca2 API
- Monitor for rate limiting messages in logs

### Debug Logging

To enable debug logging, add this to your `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.loca2: debug
```

## API Requirements

This integration requires:
- Valid Loca2 account credentials (username and password)
- Network access to Loca2 API endpoints (https://www.mijnloca.nl)
- Devices registered and active in your Loca2 account

## Development

### Setting up Development Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/steynovich/loca2-hass.git
   cd loca2-hass
   ```

2. Install uv (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. Install development dependencies:
   ```bash
   uv sync --extra dev
   ```

4. Install pre-commit hooks:
   ```bash
   uv run pre-commit install
   ```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=custom_components/loca2

# Run specific test file
uv run pytest tests/test_api.py -v

# Run comprehensive validation
uv run python tests/test_comprehensive_validation.py
```

### Code Quality

The project uses several tools to maintain code quality:

- **Black**: Code formatting
- **Ruff**: Linting and code analysis
- **MyPy**: Type checking
- **Bandit**: Security analysis

Run quality checks:
```bash
# Format code
uv run black custom_components/ tests/

# Lint code
uv run ruff check custom_components/ tests/

# Type check
uv run mypy custom_components/loca2/

# Security scan
uv run bandit -r custom_components/
```

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration:

- **CI Workflow**: Runs tests, linting, and validation on Python 3.11 and 3.12
- **HACS Validation**: Validates HACS compatibility and integration structure
- **Home Assistant Validation**: Runs hassfest and Home Assistant validation
- **Code Quality**: Checks formatting, linting, security, and complexity
- **Release Workflow**: Automated releases with version tagging

All workflows run on push to `main`/`develop` branches and pull requests.

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests if applicable
5. Ensure all CI checks pass
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Submit a pull request

#### Pull Request Guidelines

- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Ensure all GitHub Actions workflows pass
- Fill out the pull request template completely

## Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/steynovich/loca2-hass/issues)
- 💡 **Feature Requests**: [GitHub Issues](https://github.com/steynovich/loca2-hass/issues)
- 📖 **Documentation**: [GitHub Wiki](https://github.com/steynovich/loca2-hass/wiki)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.