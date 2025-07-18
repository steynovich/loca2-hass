"""Enhanced logging utilities for Loca2 integration."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional, Union
from contextlib import contextmanager

from .const import (
    LOG_FORMAT_ERROR,
    LOG_FORMAT_RECOVERY,
    LOG_FORMAT_PERFORMANCE,
    LOG_FORMAT_DIAGNOSTIC,
    ERROR_SEVERITY_LOW,
    ERROR_SEVERITY_MEDIUM,
    ERROR_SEVERITY_HIGH,
    ERROR_SEVERITY_CRITICAL,
    PERFORMANCE_SLOW_API_THRESHOLD,
    PERFORMANCE_VERY_SLOW_API_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


class StructuredLogger:
    """Enhanced structured logging for Loca2 integration."""
    
    def __init__(self, logger: logging.Logger, component: str):
        """Initialize structured logger."""
        self.logger = logger
        self.component = component
        self._operation_start_times: Dict[str, float] = {}
    
    def log_error(
        self,
        category: str,
        error_type: str,
        message: str,
        duration: float = 0.0,
        consecutive: int = 0,
        context: Optional[str] = None,
        severity: str = ERROR_SEVERITY_MEDIUM,
        exception: Optional[Exception] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log structured error information."""
        log_data = {
            "category": category,
            "error_type": error_type,
            "message": message,
            "duration": duration,
            "consecutive": consecutive,
            "context": context or "general",
            "severity": severity,
            "component": self.component,
            "timestamp": datetime.now().isoformat(),
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        # Choose log level based on severity
        log_level = self._get_log_level_for_severity(severity)
        
        # Format message
        formatted_message = LOG_FORMAT_ERROR % log_data
        
        # Log with appropriate level
        if exception:
            self.logger.log(log_level, formatted_message, exc_info=exception)
        else:
            self.logger.log(log_level, formatted_message)
        
        # Log additional context if provided
        if extra_data:
            self.logger.debug(
                "Additional error context for %s: %s",
                error_type,
                extra_data
            )
    
    def log_recovery(
        self,
        message: str,
        downtime: float = 0.0,
        attempts: int = 0,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log recovery information."""
        log_data = {
            "message": message,
            "downtime": downtime,
            "attempts": attempts,
            "component": self.component,
            "timestamp": datetime.now().isoformat(),
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        formatted_message = LOG_FORMAT_RECOVERY % log_data
        self.logger.info(formatted_message)
    
    def log_performance(
        self,
        operation: str,
        duration: float,
        details: str = "",
        threshold_warning: float = PERFORMANCE_SLOW_API_THRESHOLD,
        threshold_error: float = PERFORMANCE_VERY_SLOW_API_THRESHOLD,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log performance information with automatic threshold warnings."""
        log_data = {
            "operation": operation,
            "duration": duration,
            "details": details,
            "component": self.component,
            "timestamp": datetime.now().isoformat(),
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        formatted_message = LOG_FORMAT_PERFORMANCE % log_data
        
        # Choose log level based on performance thresholds
        if duration >= threshold_error:
            self.logger.error(f"VERY SLOW: {formatted_message}")
        elif duration >= threshold_warning:
            self.logger.warning(f"SLOW: {formatted_message}")
        else:
            self.logger.debug(formatted_message)
    
    def log_diagnostic(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        level: int = logging.DEBUG,
    ) -> None:
        """Log diagnostic information."""
        log_data = {
            "component": self.component,
            "message": message,
            "timestamp": datetime.now().isoformat(),
        }
        
        formatted_message = LOG_FORMAT_DIAGNOSTIC % log_data
        self.logger.log(level, formatted_message)
        
        if data:
            self.logger.log(level, "Diagnostic data: %s", data)
    
    @contextmanager
    def operation_timer(self, operation_name: str):
        """Context manager for timing operations."""
        start_time = time.time()
        self._operation_start_times[operation_name] = start_time
        
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.log_performance(operation_name, duration)
            self._operation_start_times.pop(operation_name, None)
    
    def start_operation(self, operation_name: str) -> None:
        """Start timing an operation."""
        self._operation_start_times[operation_name] = time.time()
    
    def end_operation(
        self,
        operation_name: str,
        details: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> float:
        """End timing an operation and log performance."""
        start_time = self._operation_start_times.pop(operation_name, None)
        if start_time is None:
            self.logger.warning(
                "Attempted to end operation '%s' that was not started",
                operation_name
            )
            return 0.0
        
        duration = time.time() - start_time
        self.log_performance(operation_name, duration, details, extra_data=extra_data)
        return duration
    
    def _get_log_level_for_severity(self, severity: str) -> int:
        """Get logging level for error severity."""
        severity_levels = {
            ERROR_SEVERITY_LOW: logging.DEBUG,
            ERROR_SEVERITY_MEDIUM: logging.WARNING,
            ERROR_SEVERITY_HIGH: logging.ERROR,
            ERROR_SEVERITY_CRITICAL: logging.CRITICAL,
        }
        return severity_levels.get(severity, logging.WARNING)


class DiagnosticCollector:
    """Collects and manages diagnostic information."""
    
    def __init__(self, max_history_size: int = 100):
        """Initialize diagnostic collector."""
        self.max_history_size = max_history_size
        self._error_history: list[Dict[str, Any]] = []
        self._performance_history: list[Dict[str, Any]] = []
        self._health_checks: list[Dict[str, Any]] = []
        self._last_diagnostic_summary = None
    
    def add_error(
        self,
        category: str,
        error_type: str,
        message: str,
        duration: float = 0.0,
        context: Optional[str] = None,
        severity: str = ERROR_SEVERITY_MEDIUM,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add error to diagnostic history."""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "error_type": error_type,
            "message": message,
            "duration": duration,
            "context": context,
            "severity": severity,
        }
        
        if extra_data:
            error_record.update(extra_data)
        
        self._error_history.append(error_record)
        self._trim_history(self._error_history)
    
    def add_performance_metric(
        self,
        operation: str,
        duration: float,
        details: str = "",
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add performance metric to diagnostic history."""
        perf_record = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "duration": duration,
            "details": details,
        }
        
        if extra_data:
            perf_record.update(extra_data)
        
        self._performance_history.append(perf_record)
        self._trim_history(self._performance_history)
    
    def add_health_check(
        self,
        status: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add health check result to diagnostic history."""
        health_record = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details or {},
        }
        
        self._health_checks.append(health_record)
        self._trim_history(self._health_checks)
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors."""
        if not self._error_history:
            return {"total_errors": 0, "categories": {}, "recent_errors": []}
        
        # Count errors by category
        categories = {}
        for error in self._error_history:
            category = error.get("category", "unknown")
            categories[category] = categories.get(category, 0) + 1
        
        # Get recent errors (last 10)
        recent_errors = self._error_history[-10:]
        
        return {
            "total_errors": len(self._error_history),
            "categories": categories,
            "recent_errors": recent_errors,
            "last_error": self._error_history[-1] if self._error_history else None,
        }
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of performance metrics."""
        if not self._performance_history:
            return {"total_operations": 0, "average_duration": 0.0, "slow_operations": 0}
        
        durations = [p["duration"] for p in self._performance_history]
        avg_duration = sum(durations) / len(durations)
        slow_operations = len([d for d in durations if d > PERFORMANCE_SLOW_API_THRESHOLD])
        
        return {
            "total_operations": len(self._performance_history),
            "average_duration": avg_duration,
            "slow_operations": slow_operations,
            "recent_operations": self._performance_history[-5:],
        }
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get summary of health checks."""
        if not self._health_checks:
            return {"total_checks": 0, "current_status": "unknown", "status_distribution": {}}
        
        # Count status distribution
        status_dist = {}
        for check in self._health_checks:
            status = check.get("status", "unknown")
            status_dist[status] = status_dist.get(status, 0) + 1
        
        return {
            "total_checks": len(self._health_checks),
            "current_status": self._health_checks[-1].get("status", "unknown"),
            "status_distribution": status_dist,
            "last_check": self._health_checks[-1] if self._health_checks else None,
        }
    
    def get_comprehensive_diagnostic(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information."""
        return {
            "collection_timestamp": datetime.now().isoformat(),
            "errors": self.get_error_summary(),
            "performance": self.get_performance_summary(),
            "health": self.get_health_summary(),
            "history_sizes": {
                "errors": len(self._error_history),
                "performance": len(self._performance_history),
                "health_checks": len(self._health_checks),
            },
        }
    
    def _trim_history(self, history_list: list) -> None:
        """Trim history list to maximum size."""
        while len(history_list) > self.max_history_size:
            history_list.pop(0)
    
    def clear_history(self) -> None:
        """Clear all diagnostic history."""
        self._error_history.clear()
        self._performance_history.clear()
        self._health_checks.clear()
        _LOGGER.info("Diagnostic history cleared")


def get_structured_logger(component: str) -> StructuredLogger:
    """Get a structured logger for a component."""
    logger = logging.getLogger(f"custom_components.loca2.{component}")
    return StructuredLogger(logger, component)


def format_diagnostic_summary(diagnostics: Dict[str, Any]) -> str:
    """Format diagnostic information for human-readable logging."""
    lines = ["=== Loca2 Integration Diagnostic Summary ==="]
    
    # Error summary
    error_info = diagnostics.get("errors", {})
    lines.append(f"Errors: {error_info.get('total_errors', 0)} total")
    if error_info.get("categories"):
        for category, count in error_info["categories"].items():
            lines.append(f"  - {category}: {count}")
    
    # Performance summary
    perf_info = diagnostics.get("performance", {})
    lines.append(f"Performance: {perf_info.get('total_operations', 0)} operations")
    lines.append(f"  - Average duration: {perf_info.get('average_duration', 0):.2f}s")
    lines.append(f"  - Slow operations: {perf_info.get('slow_operations', 0)}")
    
    # Health summary
    health_info = diagnostics.get("health", {})
    lines.append(f"Health: {health_info.get('current_status', 'unknown')}")
    lines.append(f"  - Total checks: {health_info.get('total_checks', 0)}")
    
    lines.append("=" * 45)
    return "\n".join(lines)