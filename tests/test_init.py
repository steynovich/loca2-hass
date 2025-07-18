"""Test the Loca2 integration initialization and lifecycle."""
from unittest.mock import AsyncMock, Mock, patch
import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL, CONF_TIMEOUT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.loca2 import (
    async_setup_entry,
    async_unload_entry,
    async_update_options,
    Loca2DataUpdateCoordinator,
)
from custom_components.loca2.api import Loca2ApiClient
from custom_components.loca2.const import CONF_BASE_URL, DOMAIN, DEFAULT_SCAN_INTERVAL


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return Mock(spec=ConfigEntry, data={
        CONF_API_KEY: "test_api_key",
        CONF_BASE_URL: "https://api.loca2.com",
        CONF_SCAN_INTERVAL: 30,
        CONF_TIMEOUT: 10,
    }, options={}, entry_id="test_entry_id")


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = Mock(spec=Loca2ApiClient)
    client.test_connection = AsyncMock(return_value=True)
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = Mock(spec=Loca2DataUpdateCoordinator)
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


class TestIntegrationLifecycle:
    """Test integration lifecycle management."""

    async def test_async_setup_entry_success(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test successful integration setup."""
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward:
            
            result = await async_setup_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify API client was created and tested
            mock_api_client.test_connection.assert_called_once()
            
            # Verify coordinator was created and refreshed
            mock_coordinator.async_config_entry_first_refresh.assert_called_once()
            
            # Verify platforms were set up
            mock_forward.assert_called_once_with(mock_config_entry, ["device_tracker"])
            
            # Verify data was stored in hass
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert "coordinator" in hass.data[DOMAIN][mock_config_entry.entry_id]
            assert "api_client" in hass.data[DOMAIN][mock_config_entry.entry_id]

    async def test_async_setup_entry_connection_failure(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test setup failure due to connection issues."""
        mock_api_client.test_connection.return_value = False
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to authenticate"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_async_setup_entry_api_exception(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test setup failure due to API exception."""
        mock_api_client.test_connection.side_effect = Exception("Connection error")
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client):
            with pytest.raises(ConfigEntryNotReady, match="Failed to connect to Loca2 API"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_async_setup_entry_with_options(self, hass: HomeAssistant, mock_api_client, mock_coordinator):
        """Test setup with options overriding config data."""
        config_entry = Mock(spec=ConfigEntry, data={
            CONF_API_KEY: "test_api_key",
            CONF_BASE_URL: "https://api.loca2.com",
            CONF_SCAN_INTERVAL: 30,
            CONF_TIMEOUT: 10,
        }, options={
            CONF_SCAN_INTERVAL: 60,
            CONF_TIMEOUT: 15,
        }, entry_id="test_entry_id")
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client) as mock_client_class, \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator) as mock_coord_class, \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, config_entry)
            
            # Verify API client was created with options values
            mock_client_class.assert_called_once_with(
                api_key="test_api_key",
                base_url="https://api.loca2.com",
                timeout=15,  # From options
            )
            
            # Verify coordinator was created with options values
            mock_coord_class.assert_called_once_with(
                hass=hass,
                api_client=mock_api_client,
                scan_interval=60,  # From options
            )

    async def test_async_setup_entry_default_values(self, hass: HomeAssistant, mock_api_client, mock_coordinator):
        """Test setup with default values when not specified."""
        config_entry = Mock(spec=ConfigEntry, data={
            CONF_API_KEY: "test_api_key",
            CONF_BASE_URL: "https://api.loca2.com",
        }, options={}, entry_id="test_entry_id")
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client) as mock_client_class, \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator) as mock_coord_class, \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, config_entry)
            
            # Verify API client was created with default timeout
            mock_client_class.assert_called_once_with(
                api_key="test_api_key",
                base_url="https://api.loca2.com",
                timeout=10,  # Default value
            )
            
            # Verify coordinator was created with default scan interval
            mock_coord_class.assert_called_once_with(
                hass=hass,
                api_client=mock_api_client,
                scan_interval=DEFAULT_SCAN_INTERVAL,  # Default value
            )

    async def test_async_unload_entry_success(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test successful integration unload."""
        # Set up hass data as if integration was loaded
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": Mock(),
                "api_client": mock_api_client,
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True) as mock_unload:
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            
            # Verify platforms were unloaded
            mock_unload.assert_called_once_with(mock_config_entry, ["device_tracker"])
            
            # Verify API client was closed
            mock_api_client.close.assert_called_once()
            
            # Verify data was cleaned up
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_async_unload_entry_platform_failure(self, hass: HomeAssistant, mock_config_entry, mock_api_client):
        """Test unload when platform unload fails."""
        # Set up hass data as if integration was loaded
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": Mock(),
                "api_client": mock_api_client,
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=False) as mock_unload:
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is False
            
            # Verify platforms unload was attempted
            mock_unload.assert_called_once_with(mock_config_entry, ["device_tracker"])
            
            # Verify API client was NOT closed since unload failed
            mock_api_client.close.assert_not_called()
            
            # Verify data was NOT cleaned up since unload failed
            assert mock_config_entry.entry_id in hass.data[DOMAIN]

    async def test_async_update_options(self, hass: HomeAssistant, mock_config_entry):
        """Test options update triggers reload."""
        with patch.object(hass.config_entries, "async_reload") as mock_reload:
            await async_update_options(hass, mock_config_entry)
            
            mock_reload.assert_called_once_with(mock_config_entry.entry_id)

    async def test_integration_setup_with_update_listener(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test that update listener is properly set up."""
        mock_config_entry.async_on_unload = Mock()
        mock_config_entry.add_update_listener = Mock(return_value="listener")
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify update listener was added and registered for unload
            mock_config_entry.add_update_listener.assert_called_once_with(async_update_options)
            mock_config_entry.async_on_unload.assert_called_once_with("listener")

    async def test_coordinator_first_refresh_failure(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test handling of coordinator first refresh failure."""
        mock_coordinator.async_config_entry_first_refresh.side_effect = Exception("Refresh failed")
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator):
            
            with pytest.raises(Exception, match="Refresh failed"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_hass_data_initialization(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test that hass.data is properly initialized."""
        # Ensure DOMAIN is not in hass.data initially
        if DOMAIN in hass.data:
            del hass.data[DOMAIN]
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify DOMAIN was created in hass.data
            assert DOMAIN in hass.data
            assert isinstance(hass.data[DOMAIN], dict)

    async def test_multiple_entries_data_isolation(self, hass: HomeAssistant):
        """Test that multiple config entries have isolated data."""
        entry1 = Mock(spec=ConfigEntry, data={
            CONF_API_KEY: "key1",
            CONF_BASE_URL: "https://api1.loca2.com",
        }, options={}, entry_id="entry1")
        
        entry2 = Mock(spec=ConfigEntry, data={
            CONF_API_KEY: "key2", 
            CONF_BASE_URL: "https://api2.loca2.com",
        }, options={}, entry_id="entry2")
        
        # Create separate mock instances for each entry
        mock_api_client1 = Mock(spec=Loca2ApiClient)
        mock_api_client1.test_connection = AsyncMock(return_value=True)
        mock_api_client1.close = AsyncMock()
        
        mock_api_client2 = Mock(spec=Loca2ApiClient)
        mock_api_client2.test_connection = AsyncMock(return_value=True)
        mock_api_client2.close = AsyncMock()
        
        mock_coordinator1 = Mock(spec=Loca2DataUpdateCoordinator)
        mock_coordinator1.async_config_entry_first_refresh = AsyncMock()
        
        mock_coordinator2 = Mock(spec=Loca2DataUpdateCoordinator)
        mock_coordinator2.async_config_entry_first_refresh = AsyncMock()
        
        with patch("custom_components.loca2.Loca2ApiClient", side_effect=[mock_api_client1, mock_api_client2]), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", side_effect=[mock_coordinator1, mock_coordinator2]), \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, entry1)
            await async_setup_entry(hass, entry2)
            
            # Verify both entries have separate data
            assert "entry1" in hass.data[DOMAIN]
            assert "entry2" in hass.data[DOMAIN]
            assert hass.data[DOMAIN]["entry1"]["api_client"] is mock_api_client1
            assert hass.data[DOMAIN]["entry2"]["api_client"] is mock_api_client2
            assert hass.data[DOMAIN]["entry1"]["coordinator"] is mock_coordinator1
            assert hass.data[DOMAIN]["entry2"]["coordinator"] is mock_coordinator2

    async def test_unload_with_missing_data(self, hass: HomeAssistant, mock_config_entry):
        """Test unload behavior when data is missing."""
        # Ensure no data exists for this entry
        hass.data[DOMAIN] = {}
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Should not raise an exception even with missing data
            result = await async_unload_entry(hass, mock_config_entry)
            assert result is True

    async def test_unload_with_missing_domain_data(self, hass: HomeAssistant, mock_config_entry):
        """Test unload behavior when domain data is completely missing."""
        # Ensure DOMAIN is not in hass.data at all
        if DOMAIN in hass.data:
            del hass.data[DOMAIN]
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Should not raise an exception even with missing domain data
            result = await async_unload_entry(hass, mock_config_entry)
            assert result is True

    async def test_unload_with_missing_api_client(self, hass: HomeAssistant, mock_config_entry):
        """Test unload behavior when API client is missing from data."""
        # Set up hass data without api_client
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": Mock(),
                # Missing "api_client" key
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Should not raise an exception even with missing API client
            result = await async_unload_entry(hass, mock_config_entry)
            assert result is True
            
            # Verify data was still cleaned up
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_api_client_close_exception(self, hass: HomeAssistant, mock_config_entry):
        """Test unload behavior when API client close raises an exception."""
        mock_api_client = Mock(spec=Loca2ApiClient)
        mock_api_client.close = AsyncMock(side_effect=Exception("Close failed"))
        
        # Set up hass data
        hass.data[DOMAIN] = {
            mock_config_entry.entry_id: {
                "coordinator": Mock(),
                "api_client": mock_api_client,
            }
        }
        
        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            # Should handle API client close exception gracefully
            with pytest.raises(Exception, match="Close failed"):
                await async_unload_entry(hass, mock_config_entry)

    async def test_setup_entry_stores_correct_data_structure(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test that setup stores the correct data structure."""
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify exact data structure
            entry_data = hass.data[DOMAIN][mock_config_entry.entry_id]
            assert isinstance(entry_data, dict)
            assert len(entry_data) == 2
            assert entry_data["coordinator"] is mock_coordinator
            assert entry_data["api_client"] is mock_api_client

    async def test_setup_entry_platform_forward_failure(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test setup behavior when platform forwarding fails."""
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups", side_effect=Exception("Platform setup failed")):
            
            with pytest.raises(Exception, match="Platform setup failed"):
                await async_setup_entry(hass, mock_config_entry)

    async def test_update_listener_registration(self, hass: HomeAssistant, mock_config_entry, mock_api_client, mock_coordinator):
        """Test that update listener is properly registered and can be unloaded."""
        mock_unload_listener = Mock()
        mock_config_entry.async_on_unload = Mock()
        mock_config_entry.add_update_listener = Mock(return_value=mock_unload_listener)
        
        with patch("custom_components.loca2.Loca2ApiClient", return_value=mock_api_client), \
             patch("custom_components.loca2.Loca2DataUpdateCoordinator", return_value=mock_coordinator), \
             patch.object(hass.config_entries, "async_forward_entry_setups"):
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify listener was registered for unload
            mock_config_entry.async_on_unload.assert_called_once_with(mock_unload_listener)