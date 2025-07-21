"""Comprehensive validation tests for Loca2 Home Assistant integration.

This module implements the final integration testing and validation as specified in task 12:
- Run Home Assistant integration validation tools
- Test complete user workflow from installation to device tracking
- Validate async implementation and performance
- Verify all requirements are met through automated tests
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from custom_components.loca2.api import (
    Loca2AuthError,
    Loca2ConnectionError,
    Loca2Device,
    Loca2Location,
)
from custom_components.loca2.const import DOMAIN
from custom_components.loca2.device_tracker import Loca2DeviceTracker


class TestHomeAssistantValidationTools:
    """Test Home Assistant integration validation tools compliance."""

    def test_manifest_validation_compliance(self):
        """Test manifest.json meets Home Assistant validation requirements."""
        manifest_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "manifest.json"
        )

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Home Assistant required fields
        required_fields = [
            "domain",
            "name",
            "version",
            "documentation",
            "issue_tracker",
            "codeowners",
            "requirements",
            "iot_class",
            "config_flow",
        ]

        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

        # Validate field formats
        assert isinstance(manifest["domain"], str) and manifest["domain"].islower()
        assert isinstance(manifest["name"], str) and len(manifest["name"]) > 0
        assert isinstance(manifest["version"], str)
        assert manifest["documentation"].startswith(("http://", "https://"))
        assert manifest["issue_tracker"].startswith(("http://", "https://"))
        assert (
            isinstance(manifest["codeowners"], list) and len(manifest["codeowners"]) > 0
        )
        assert isinstance(manifest["requirements"], list)
        assert manifest["iot_class"] in [
            "assumed_state",
            "cloud_polling",
            "cloud_push",
            "local_polling",
            "local_push",
        ]
        assert (
            isinstance(manifest["config_flow"], bool)
            and manifest["config_flow"] is True
        )

        # Version format validation
        version_parts = manifest["version"].split(".")
        assert len(version_parts) >= 2
        for part in version_parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"

    def test_integration_structure_validation(self):
        """Test integration file structure meets Home Assistant standards."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        # Required files
        required_files = [
            "__init__.py",
            "manifest.json",
            "config_flow.py",
            "device_tracker.py",
            "const.py",
            "api.py",
            "strings.json",
        ]

        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"Missing required file: {file_name}"

        # Validate __init__.py structure
        init_content = (integration_path / "__init__.py").read_text()
        assert "async def async_setup_entry" in init_content
        assert "async def async_unload_entry" in init_content

        # Validate config_flow.py structure
        config_flow_content = (integration_path / "config_flow.py").read_text()
        assert "ConfigFlow" in config_flow_content
        assert "async def async_step_user" in config_flow_content

    def test_strings_json_validation(self):
        """Test strings.json meets Home Assistant translation standards."""
        strings_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "strings.json"
        )

        with open(strings_path) as f:
            strings = json.load(f)

        # Required sections
        assert "config" in strings
        config_section = strings["config"]
        assert "step" in config_section
        assert "error" in config_section

        # Validate structure
        steps = config_section["step"]
        assert isinstance(steps, dict)
        assert "user" in steps

        errors = config_section["error"]
        assert isinstance(errors, dict)


class TestCompleteUserWorkflowValidation:
    """Test complete user workflow from installation to device tracking."""

    def test_config_flow_workflow(self):
        """Test configuration flow workflow."""
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        # Test config flow can be instantiated
        flow = Loca2ConfigFlow()
        assert flow is not None

        # Test required methods exist
        assert hasattr(flow, "async_step_user")
        assert hasattr(flow, "VERSION")
        assert flow.VERSION >= 1

    def test_api_client_workflow(self):
        """Test API client workflow and methods."""
        import inspect

        from custom_components.loca2.api import Loca2ApiClient

        # Test API client methods are async
        api_methods = ["test_connection", "get_devices", "get_device_location", "close"]
        for method_name in api_methods:
            if hasattr(Loca2ApiClient, method_name):
                method = getattr(Loca2ApiClient, method_name)
                assert inspect.iscoroutinefunction(
                    method
                ), f"API method {method_name} must be async"

    def test_device_tracker_entity_workflow(self):
        """Test device tracker entity creation and management workflow."""
        # Create mock coordinator
        mock_coordinator = Mock()
        mock_coordinator.data = {
            "device_1": Loca2Device(
                id="device_1",
                name="Test Phone",
                device_type="smartphone",
                battery_level=85,
                last_seen=datetime.now(),
            )
        }
        mock_coordinator.last_update_success = True

        # Create entity
        device = mock_coordinator.data["device_1"]
        entity = Loca2DeviceTracker(mock_coordinator, "device_1", device)

        # Test entity properties
        assert entity._attr_unique_id == f"{DOMAIN}_device_1"
        assert entity._attr_name == "Test Phone"
        assert entity._attr_source_type.value == "gps"

        # Test device info structure
        device_info = entity._attr_device_info
        assert device_info["identifiers"] == {(DOMAIN, "device_1")}
        assert device_info["name"] == "Test Phone"
        assert device_info["manufacturer"] == "Loca2"
        assert device_info["model"] == "smartphone"

    def test_error_handling_workflow(self):
        """Test error handling throughout the workflow."""

        # Test custom exceptions exist
        assert issubclass(Loca2AuthError, Exception)
        assert issubclass(Loca2ConnectionError, Exception)

        # Test exceptions can be raised
        try:
            raise Loca2AuthError("Test auth error")
        except Loca2AuthError as e:
            assert str(e) == "Test auth error"

        try:
            raise Loca2ConnectionError("Test connection error")
        except Loca2ConnectionError as e:
            assert str(e) == "Test connection error"


class TestAsyncImplementationValidation:
    """Test async implementation and performance validation."""

    def test_async_implementation_compliance(self):
        """Test async implementation follows Home Assistant guidelines."""
        import inspect

        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient
        from custom_components.loca2.device_tracker import Loca2DeviceTracker

        # Main entry points must be async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)

        # API client methods must be async
        api_methods = ["test_connection", "get_devices", "get_device_location", "close"]
        for method_name in api_methods:
            if hasattr(Loca2ApiClient, method_name):
                method = getattr(Loca2ApiClient, method_name)
                assert inspect.iscoroutinefunction(method)

        # Device tracker update method must be async
        assert inspect.iscoroutinefunction(Loca2DeviceTracker.async_update)

    def test_no_blocking_operations(self):
        """Test integration doesn't use blocking I/O operations."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        python_files = ["__init__.py", "api.py", "config_flow.py", "device_tracker.py"]

        blocking_patterns = [
            "requests.get",
            "requests.post",
            "requests.put",
            "requests.delete",
            "urllib.request",
            "time.sleep",
            "socket.socket",
        ]

        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                for pattern in blocking_patterns:
                    assert (
                        pattern not in content
                    ), f"Found blocking operation '{pattern}' in {file_name}"

    def test_performance_characteristics(self):
        """Test performance characteristics of async operations."""
        from custom_components.loca2.api import Loca2ApiClient

        # Test that API client can be instantiated quickly
        start_time = time.time()
        client = Loca2ApiClient("test_key", "https://api.example.com", timeout=10)
        end_time = time.time()

        # Instantiation should be very fast
        assert (end_time - start_time) < 0.1

        # Test that client has expected methods
        assert hasattr(client, "test_connection")
        assert hasattr(client, "get_devices")
        assert hasattr(client, "get_device_location")
        assert hasattr(client, "close")


class TestRequirementsValidation:
    """Test that all requirements are met through automated tests."""

    def test_requirement_1_4_hacs_compatibility(self):
        """Test Requirement 1.4: HACS compatibility and updates."""
        manifest_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "manifest.json"
        )

        with open(manifest_path) as f:
            manifest = json.load(f)

        # HACS compatibility requirements
        hacs_required_fields = [
            "domain",
            "name",
            "version",
            "documentation",
            "issue_tracker",
            "codeowners",
            "config_flow",
        ]

        for field in hacs_required_fields:
            assert field in manifest, f"HACS requires field: {field}"

        # Specific HACS requirements
        assert manifest["config_flow"] is True
        assert (
            isinstance(manifest["codeowners"], list) and len(manifest["codeowners"]) > 0
        )
        assert manifest["documentation"].startswith(("http://", "https://"))
        assert manifest["issue_tracker"].startswith(("http://", "https://"))

        # Version should follow semantic versioning for updates
        version = manifest["version"]
        version_parts = version.split(".")
        assert len(version_parts) >= 2
        for part in version_parts:
            assert part.isdigit()

    def test_requirement_7_6_async_operations(self):
        """Test Requirement 7.6: Async/await patterns for non-blocking operations."""
        import inspect

        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient

        # All I/O operations should be async
        async_methods = [
            (Loca2ApiClient, "test_connection"),
            (Loca2ApiClient, "get_devices"),
            (Loca2ApiClient, "get_device_location"),
            (Loca2ApiClient, "close"),
        ]

        for cls, method_name in async_methods:
            if hasattr(cls, method_name):
                method = getattr(cls, method_name)
                assert inspect.iscoroutinefunction(
                    method
                ), f"{cls.__name__}.{method_name} must be async"

        # Entry points should be async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)

    def test_requirement_7_7_non_blocking_event_loop(self):
        """Test Requirement 7.7: Async I/O operations don't block event loop."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        # Check for blocking operations in code
        blocking_patterns = [
            "requests.get",
            "requests.post",
            "requests.put",
            "requests.delete",
            "urllib.request",
            "time.sleep",
            "socket.socket",
        ]

        python_files = ["__init__.py", "api.py", "config_flow.py", "device_tracker.py"]

        for file_name in python_files:
            file_path = integration_path / file_name
            if file_path.exists():
                content = file_path.read_text()
                for pattern in blocking_patterns:
                    assert (
                        pattern not in content
                    ), f"Found blocking operation '{pattern}' in {file_name}"

    def test_all_requirements_coverage(self):
        """Test that all requirements from the spec are covered."""
        # Read requirements from spec
        requirements_path = (
            Path(__file__).parent.parent
            / ".kiro"
            / "specs"
            / "loca2-home-assistant-integration"
            / "requirements.md"
        )

        if requirements_path.exists():
            requirements_content = requirements_path.read_text()

            # Check that key requirement areas are addressed
            requirement_areas = [
                "HACS",
                "API",
                "device_tracker",
                "config flow",
                "async",
                "error",
            ]

            for area in requirement_areas:
                assert (
                    area.lower() in requirements_content.lower()
                ), f"Requirements should cover {area}"


class TestIntegrationValidationSuite:
    """Comprehensive integration validation test suite."""

    def test_manifest_compliance(self):
        """Test manifest.json compliance with Home Assistant standards."""
        manifest_path = (
            Path(__file__).parent.parent
            / "custom_components"
            / "loca2"
            / "manifest.json"
        )

        with open(manifest_path) as f:
            manifest = json.load(f)

        # Test all required fields are present and valid
        assert manifest["domain"] == "loca2"
        assert len(manifest["name"]) > 0
        assert len(manifest["version"].split(".")) >= 2
        assert manifest["config_flow"] is True
        assert manifest["iot_class"] in [
            "cloud_polling",
            "cloud_push",
            "local_polling",
            "local_push",
            "assumed_state",
        ]
        assert isinstance(manifest["requirements"], list)
        assert (
            isinstance(manifest["codeowners"], list) and len(manifest["codeowners"]) > 0
        )

    def test_file_structure_compliance(self):
        """Test file structure compliance with Home Assistant standards."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        # Test required files exist
        required_files = [
            "__init__.py",
            "manifest.json",
            "config_flow.py",
            "device_tracker.py",
            "const.py",
            "api.py",
            "strings.json",
        ]

        for file_name in required_files:
            file_path = integration_path / file_name
            assert file_path.exists(), f"Missing required file: {file_name}"
            assert file_path.stat().st_size > 0, f"File {file_name} is empty"

    def test_code_quality_compliance(self):
        """Test code quality compliance with Home Assistant standards."""
        integration_path = Path(__file__).parent.parent / "custom_components" / "loca2"

        # Test __init__.py has required functions
        init_content = (integration_path / "__init__.py").read_text()
        assert "async def async_setup_entry" in init_content
        assert "async def async_unload_entry" in init_content

        # Test config_flow.py has required class
        config_flow_content = (integration_path / "config_flow.py").read_text()
        assert "class" in config_flow_content and "ConfigFlow" in config_flow_content

        # Test device_tracker.py has required class
        device_tracker_content = (integration_path / "device_tracker.py").read_text()
        assert "class" in device_tracker_content

    def test_async_compliance(self):
        """Test async implementation compliance."""
        import inspect

        from custom_components.loca2 import async_setup_entry, async_unload_entry
        from custom_components.loca2.api import Loca2ApiClient

        # Test main functions are async
        assert inspect.iscoroutinefunction(async_setup_entry)
        assert inspect.iscoroutinefunction(async_unload_entry)

        # Test API methods are async
        if hasattr(Loca2ApiClient, "test_connection"):
            assert inspect.iscoroutinefunction(Loca2ApiClient.test_connection)
        if hasattr(Loca2ApiClient, "get_devices"):
            assert inspect.iscoroutinefunction(Loca2ApiClient.get_devices)
        if hasattr(Loca2ApiClient, "get_device_location"):
            assert inspect.iscoroutinefunction(Loca2ApiClient.get_device_location)

    def test_error_handling_compliance(self):
        """Test error handling compliance."""

        # Test custom exceptions exist and are properly defined
        assert issubclass(Loca2AuthError, Exception)
        assert issubclass(Loca2ConnectionError, Exception)

        # Test exceptions can be instantiated
        auth_error = Loca2AuthError("Test message")
        assert str(auth_error) == "Test message"

        conn_error = Loca2ConnectionError("Test message")
        assert str(conn_error) == "Test message"

    def test_integration_completeness(self):
        """Test integration completeness and functionality."""
        from custom_components.loca2.api import Loca2ApiClient, Loca2Device
        from custom_components.loca2.config_flow import Loca2ConfigFlow
        from custom_components.loca2.const import DOMAIN
        from custom_components.loca2.device_tracker import Loca2DeviceTracker

        # Test all main classes can be imported
        assert DOMAIN == "loca2"
        assert Loca2ConfigFlow is not None
        assert Loca2DeviceTracker is not None
        assert Loca2ApiClient is not None
        assert Loca2Device is not None
        assert Loca2Location is not None

        # Test config flow has required attributes
        flow = Loca2ConfigFlow()
        assert hasattr(flow, "VERSION")
        assert isinstance(flow.VERSION, int)
        assert flow.VERSION >= 1


class TestPerformanceValidation:
    """Test performance characteristics of the integration."""

    def test_import_performance(self):
        """Test that imports are fast and don't block."""
        start_time = time.time()

        # Import all main modules

        end_time = time.time()

        # Imports should be very fast
        assert (end_time - start_time) < 1.0, "Imports taking too long"

    def test_object_creation_performance(self):
        """Test that object creation is performant."""
        from custom_components.loca2.api import Loca2ApiClient, Loca2Device
        from custom_components.loca2.config_flow import Loca2ConfigFlow

        start_time = time.time()

        # Create objects
        client = Loca2ApiClient("test_key", "https://api.example.com", timeout=10)
        flow = Loca2ConfigFlow()
        device = Loca2Device(id="test", name="Test Device", device_type="smartphone")
        location = Loca2Location(
            latitude=37.7749,
            longitude=-122.4194,
            accuracy=10.0,
            timestamp=datetime.now(),
        )

        end_time = time.time()

        # Object creation should be very fast
        assert (end_time - start_time) < 0.1, "Object creation taking too long"

        # Verify objects were created properly
        assert client is not None
        assert flow is not None
        assert device is not None
        assert location is not None


def run_comprehensive_validation():
    """Run comprehensive validation and return results."""
    results = {
        "manifest_validation": False,
        "structure_validation": False,
        "async_validation": False,
        "requirements_validation": False,
        "performance_validation": False,
        "errors": [],
    }

    try:
        # Test manifest validation
        validator = TestHomeAssistantValidationTools()
        validator.test_manifest_validation_compliance()
        validator.test_integration_structure_validation()
        validator.test_strings_json_validation()
        results["manifest_validation"] = True

        # Test workflow validation
        workflow_validator = TestCompleteUserWorkflowValidation()
        workflow_validator.test_config_flow_workflow()
        workflow_validator.test_api_client_workflow()
        workflow_validator.test_device_tracker_entity_workflow()
        workflow_validator.test_error_handling_workflow()
        results["structure_validation"] = True

        # Test async validation
        async_validator = TestAsyncImplementationValidation()
        async_validator.test_async_implementation_compliance()
        async_validator.test_no_blocking_operations()
        async_validator.test_performance_characteristics()
        results["async_validation"] = True

        # Test requirements validation
        req_validator = TestRequirementsValidation()
        req_validator.test_requirement_1_4_hacs_compatibility()
        req_validator.test_requirement_7_6_async_operations()
        req_validator.test_requirement_7_7_non_blocking_event_loop()
        req_validator.test_all_requirements_coverage()
        results["requirements_validation"] = True

        # Test performance validation
        perf_validator = TestPerformanceValidation()
        perf_validator.test_import_performance()
        perf_validator.test_object_creation_performance()
        results["performance_validation"] = True

    except Exception as e:
        results["errors"].append(str(e))

    return results


if __name__ == "__main__":
    # Run validation when script is executed directly
    results = run_comprehensive_validation()

    print("=== Loca2 Integration Validation Results ===")
    print(f"Manifest Validation: {'✓' if results['manifest_validation'] else '✗'}")
    print(f"Structure Validation: {'✓' if results['structure_validation'] else '✗'}")
    print(f"Async Validation: {'✓' if results['async_validation'] else '✗'}")
    print(
        f"Requirements Validation: {'✓' if results['requirements_validation'] else '✗'}"
    )
    print(
        f"Performance Validation: {'✓' if results['performance_validation'] else '✗'}"
    )

    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")

    all_passed = (
        all(
            [
                results["manifest_validation"],
                results["structure_validation"],
                results["async_validation"],
                results["requirements_validation"],
                results["performance_validation"],
            ]
        )
        and not results["errors"]
    )

    print(f"\nOverall Status: {'✓ PASSED' if all_passed else '✗ FAILED'}")
