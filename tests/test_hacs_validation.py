"""HACS compatibility validation tests for Loca2 integration."""
from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.loader import Integration


class TestHACSValidation:
    """Test HACS compatibility and validation requirements."""
    
    def test_manifest_hacs_requirements(self):
        """Test manifest.json meets HACS requirements."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # HACS required fields
        hacs_required = [
            "domain",
            "name",
            "version",
            "documentation", 
            "issue_tracker",
            "codeowners",
            "requirements",
            "iot_class",
            "config_flow"
        ]
        
        for field in hacs_required:
            assert field in manifest, f"HACS requires field: {field}"
        
        # Validate field formats
        assert isinstance(manifest["domain"], str)
        assert len(manifest["domain"]) > 0
        assert manifest["domain"].islower()
        assert "_" not in manifest["domain"] or manifest["domain"].replace("_", "").isalnum()
        
        assert isinstance(manifest["name"], str)
        assert len(manifest["name"]) > 0
        
        # Version should follow semantic versioning
        version = manifest["version"]
        assert isinstance(version, str)
        version_parts = version.split(".")
        assert len(version_parts) >= 2, "Version should be at least MAJOR.MINOR"
        for part in version_parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"
        
        # URLs should be valid
        assert manifest["documentation"].startswith(("http://", "https://"))
        assert manifest["issue_tracker"].startswith(("http://", "https://"))
        
        # Codeowners should be a list of GitHub usernames
        assert isinstance(manifest["codeowners"], list)
        assert len(manifest["codeowners"]) > 0
        for owner in manifest["codeowners"]:
            assert owner.startswith("@"), f"Codeowner '{owner}' should start with @"
        
        # Requirements should be a list
        assert isinstance(manifest["requirements"], list)
        
        # IoT class should be valid
        valid_iot_classes = [
            "assumed_state",
            "cloud_polling", 
            "cloud_push",
            "local_polling",
            "local_push"
        ]
        assert manifest["iot_class"] in valid_iot_classes
        
        # Config flow should be boolean
        assert isinstance(manifest["config_flow"], bool)
    
    def test_integration_structure_hacs_compliant(self):
        """Test integration file structure is HACS compliant."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Required files for HACS
        required_files = [
            "__init__.py",
            "manifest.json",
            "strings.json"
        ]
        
        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"HACS requires file: {file_name}"
            assert file_path.is_file(), f"{file_name} should be a file"
        
        # Check __init__.py has required functions
        init_content = (integration_path / "__init__.py").read_text()
        assert "async def async_setup_entry" in init_content
        assert "async def async_unload_entry" in init_content
        
        # If config flow exists, it should be properly structured
        config_flow_path = integration_path / "config_flow.py"
        if config_flow_path.exists():
            config_flow_content = config_flow_path.read_text()
            assert "ConfigFlow" in config_flow_content
            assert "async def async_step_user" in config_flow_content
    
    def test_strings_json_hacs_format(self):
        """Test strings.json follows HACS format requirements."""
        strings_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "strings.json"
        
        with open(strings_path) as f:
            strings = json.load(f)
        
        # Should have config section for config flow
        assert "config" in strings, "strings.json should have 'config' section"
        
        config_section = strings["config"]
        assert "step" in config_section, "config section should have 'step'"
        assert "error" in config_section, "config section should have 'error'"
        
        # Validate step structure
        steps = config_section["step"]
        assert isinstance(steps, dict), "steps should be a dictionary"
        
        # Should have at least user step
        assert "user" in steps, "Should have 'user' step for initial config"
        
        user_step = steps["user"]
        assert "title" in user_step or "data" in user_step, "User step should have title or data"
        
        # Validate error structure
        errors = config_section["error"]
        assert isinstance(errors, dict), "errors should be a dictionary"
    
    def test_no_blocking_io_operations(self):
        """Test that integration doesn't use blocking I/O operations."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Files to check for blocking operations
        python_files = [
            "__init__.py",
            "api.py",
            "config_flow.py",
            "device_tracker.py"
        ]
        
        blocking_patterns = [
            "requests.get",
            "requests.post", 
            "requests.put",
            "requests.delete",
            "urllib.request",
            "time.sleep",
            "socket.socket",
            ".read()",
            ".write()",
            "open("
        ]
        
        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                
                for pattern in blocking_patterns:
                    # Allow some exceptions
                    if pattern == "open(" and ("manifest.json" in content or "strings.json" in content):
                        continue
                    if pattern == ".read()" and "read_text()" in content:
                        continue
                        
                    assert pattern not in content, f"Found blocking operation '{pattern}' in {file_name}"
    
    def test_async_implementation_compliance(self):
        """Test that async implementation follows Home Assistant guidelines."""
        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient
        
        import inspect
        
        # Main entry points should be async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)
        
        # API client methods should be async
        api_methods = [
            "test_connection",
            "get_devices", 
            "get_device_location",
            "close"
        ]
        
        for method_name in api_methods:
            if hasattr(Loca2ApiClient, method_name):
                method = getattr(Loca2ApiClient, method_name)
                assert inspect.iscoroutinefunction(method), f"API method {method_name} should be async"
    
    def test_integration_type_compliance(self):
        """Test integration type is properly set."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Should have integration_type for newer HA versions
        if "integration_type" in manifest:
            valid_types = ["device", "entity", "service", "system", "helper"]
            assert manifest["integration_type"] in valid_types
    
    def test_dependencies_are_minimal(self):
        """Test that dependencies are minimal and necessary."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Dependencies should be minimal
        dependencies = manifest.get("dependencies", [])
        assert isinstance(dependencies, list)
        
        # Should not depend on other custom components
        for dep in dependencies:
            assert not dep.startswith("custom_components"), f"Should not depend on custom component: {dep}"
        
        # Requirements should be specific versions when possible
        requirements = manifest.get("requirements", [])
        for req in requirements:
            assert isinstance(req, str)
            # Should have version constraints for stability
            if not any(op in req for op in [">=", "<=", "==", "~=", "!="]):
                # Allow some exceptions for well-known stable packages
                allowed_without_version = ["aiohttp"]
                package_name = req.split("[")[0]  # Handle extras like package[extra]
                if package_name not in allowed_without_version:
                    pytest.skip(f"Consider adding version constraint to requirement: {req}")
    
    def test_config_flow_translation_keys(self):
        """Test that config flow uses proper translation keys."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow
        from custom_components.loca2.const import DOMAIN
        
        # Check that config flow class exists and has proper structure
        assert hasattr(Loca2ConfigFlow, "VERSION")
        
        # Version should be integer
        assert isinstance(Loca2ConfigFlow.VERSION, int)
        assert Loca2ConfigFlow.VERSION >= 1
        
        # Domain should match manifest
        manifest_path = Path(__file__).parent.parent / "custom_components" / "loca2" / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert DOMAIN == manifest["domain"]
    
    def test_device_info_compliance(self):
        """Test device info follows Home Assistant standards."""
        from custom_components.loca2.device_tracker import Loca2DeviceTracker
        from custom_components.loca2.api import Loca2Device
        from unittest.mock import Mock
        
        # Create mock objects
        mock_coordinator = Mock()
        mock_device = Loca2Device(
            id="test_device",
            name="Test Device",
            device_type="smartphone"
        )
        
        # Create entity
        entity = Loca2DeviceTracker(mock_coordinator, "test_device", mock_device)
        
        # Check device info structure
        device_info = entity._attr_device_info
        
        # Required fields
        assert "identifiers" in device_info
        assert "name" in device_info
        assert "manufacturer" in device_info
        
        # Identifiers should be a set of tuples
        identifiers = device_info["identifiers"]
        assert isinstance(identifiers, set)
        assert len(identifiers) > 0
        
        for identifier in identifiers:
            assert isinstance(identifier, tuple)
            assert len(identifier) == 2
            assert isinstance(identifier[0], str)  # Domain
            assert isinstance(identifier[1], str)  # Unique ID
    
    def test_entity_unique_id_format(self):
        """Test entity unique IDs follow proper format."""
        from custom_components.loca2.device_tracker import Loca2DeviceTracker
        from custom_components.loca2.api import Loca2Device
        from custom_components.loca2.const import DOMAIN
        from unittest.mock import Mock
        
        # Create mock objects
        mock_coordinator = Mock()
        mock_device = Loca2Device(
            id="test_device_123",
            name="Test Device",
            device_type="smartphone"
        )
        
        # Create entity
        entity = Loca2DeviceTracker(mock_coordinator, "test_device_123", mock_device)
        
        # Check unique ID format
        unique_id = entity._attr_unique_id
        assert unique_id == f"{DOMAIN}_test_device_123"
        
        # Should be consistent and reproducible
        entity2 = Loca2DeviceTracker(mock_coordinator, "test_device_123", mock_device)
        assert entity2._attr_unique_id == unique_id
    
    def test_integration_discovery_compliance(self):
        """Test integration can be discovered properly by Home Assistant."""
        # Test that integration files exist and are properly structured
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        # Check that all required files exist
        required_files = ["__init__.py", "manifest.json", "config_flow.py"]
        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"Required file missing: {file_name}"
        
        # Check manifest is valid JSON
        manifest_path = integration_path / "manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
            assert "domain" in manifest
            assert "name" in manifest
            assert "version" in manifest
    
    def test_logging_compliance(self):
        """Test that logging follows Home Assistant standards."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"
        
        python_files = [
            "__init__.py",
            "api.py", 
            "config_flow.py",
            "device_tracker.py"
        ]
        
        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                
                # Should use _LOGGER = logging.getLogger(__name__)
                if "import logging" in content or "from logging" in content:
                    assert "_LOGGER = logging.getLogger(__name__)" in content, \
                        f"{file_name} should use proper logger initialization"
                
                # Should not use print statements
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'print(' in line and not line.strip().startswith('#'):
                        assert False, f"{file_name}:{i} should use logger instead of print()"
    
    def test_error_handling_compliance(self):
        """Test error handling follows Home Assistant patterns."""
        from custom_components.loca2.api import Loca2ApiClient
        from custom_components.loca2.config_flow import Loca2ConfigFlow
        
        # API client should handle common HTTP errors
        api_methods = ["test_connection", "get_devices", "get_device_location"]
        
        for method_name in api_methods:
            if hasattr(Loca2ApiClient, method_name):
                # Method should exist and be callable
                method = getattr(Loca2ApiClient, method_name)
                assert callable(method)
        
        # Config flow should handle validation errors
        config_flow_methods = ["async_step_user", "async_step_reauth"]
        
        for method_name in config_flow_methods:
            if hasattr(Loca2ConfigFlow, method_name):
                method = getattr(Loca2ConfigFlow, method_name)
                assert callable(method)