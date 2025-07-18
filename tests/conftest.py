"""Global fixtures for Loca2 integration tests."""
import pytest

# Import the Home Assistant test fixtures
pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return {
        "api_key": "test_api_key_123",
        "base_url": "https://api.loca2.example.com",
        "scan_interval": 60,
        "timeout": 15,
    }