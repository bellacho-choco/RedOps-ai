"""
====================================================================
PROJECT REDOPS-AI - COMPREHENSIVE MONITORING & LOGGING SYSTEM
Real-time performance monitoring, structured logging, and health checks
====================================================================
"""

import asyncio
import time
import logging
import json
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
from datetime import datetime, timedelta
import psutil


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


@dataclass
class Metric:
    """Represents a single metric data point."""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "metadata": self.metadata
        }


@dataclass
class LogEntry:
    """Structured log entry with context."""
    level: LogLevel
    message: str
    timestamp: float
    component: str
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "component": self.component,
            "context": self.context
        }


class MetricsCollector:
    """
    High-performance metrics collection with aggregation and time-series storage.
    """
    def __init__(self, max_points: int = 10000):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def record_metric(self, name: str, value: float, 
                     tags: Optional[Dict[str, str]] = None,
                     metadata: Optional[Dict[str, Any]] = None):
        """Record a metric data point."""
        metric = Metric(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
            metadata=metadata or {}
        )
        
        with self._lock:
            self.metrics[name].append(metric)
    
    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        with self._lock:
            self.counters[name] += value
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge metric value."""
        with self._lock:
            self.gauges[name] = value
    
    def get_metric_history(self, name: str, 
                          since: Optional[float] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get historical data for a metric."""
        with self._lock:
            if name not in self.metrics:
                return []
            
            history = list(self.metrics[name])
            if since:
                history = [m for m in history if m.timestamp >= since]
            
            return [m.to_dict() for m in history[-limit:]]
    
    def get_metric_stats(self, name: str, 
                        since: Optional[float] = None) -> Dict[str, Any]:
        """Get statistical summary for a metric."""
        history = self.get_metric_history(name, since)
        
        if not history:
            return {"count": 0}
        
        values = [m["value"] for m in history]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest": values[-1] if values else None
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metric values."""
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "metric_names": list(self.metrics.keys())
            }


class StructuredLogger:
    """
    Structured logging with JSON formatting and context support.
    """
    def __init__(self, component: str, level: LogLevel = LogLevel.INFO):
        self.component = component
        self.level = level
        self.log_entries: deque = deque(maxlen=1000)
        self._lock = threading.Lock()
        
        # Setup Python logging
        self.logger = logging.getLogger(f"redops.{component}")
        self.logger.setLevel(getattr(logging, level.value))
        
        # Console handler
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(handler)
    
    def _log(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None):
        """Internal logging method."""
        entry = LogEntry(
            level=level,
            message=message,
            timestamp=time.time(),
            component=self.component,
            context=context or {}
        )
        
        with self._lock:
            self.log_entries.append(entry)
        
        # Also log to Python logger
        log_method = getattr(self.logger, level.value.lower())
        log_method(message, extra={"context": context or {}})
    
    def debug(self, message: str, **context):
        if self.level.value <= LogLevel.DEBUG.value:
            self._log(LogLevel.DEBUG, message, context)
    
    def info(self, message: str, **context):
        if self.level.value <= LogLevel.INFO.value:
            self._log(LogLevel.INFO, message, context)
    
    def warning(self, message: str, **context):
        if self.level.value <= LogLevel.WARNING.value:
            self._log(LogLevel.WARNING, message, context)
    
    def error(self, message: str, **context):
        if self.level.value <= LogLevel.ERROR.value:
            self._log(LogLevel.ERROR, message, context)
    
    def critical(self, message: str, **context):
        if self.level.value <= LogLevel.CRITICAL.value:
            self._log(LogLevel.CRITICAL, message, context)
    
    def get_recent_logs(self, limit: int = 50, 
                       level: Optional[LogLevel] = None) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        with self._lock:
            logs = list(self.log_entries)
            if level:
                logs = [l for l in logs if l.level == level]
            return [l.to_dict() for l in logs[-limit:]]


class HealthChecker:
    """
    System health monitoring with configurable checks and thresholds.
    """
    def __init__(self):
        self.health_checks: Dict[str, Callable] = {}
        self.health_status: Dict[str, HealthStatus] = {}
        self.last_check_time: float = 0.0
        self._lock = threading.Lock()
        
        # Default health checks
        self._setup_default_checks()
    
    def _setup_default_checks(self):
        """Setup default system health checks."""
        self.register_check("memory", self._check_memory)
        self.register_check("cpu", self._check_cpu)
        self.register_check("disk", self._check_disk)
    
    def register_check(self, name: str, check_func: Callable[[], HealthStatus]):
        """Register a custom health check."""
        self.health_checks[name] = check_func
    
    def _check_memory(self) -> HealthStatus:
        """Check system memory usage."""
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                return HealthStatus.CRITICAL
            elif mem.percent > 75:
                return HealthStatus.UNHEALTHY
            elif mem.percent > 60:
                return HealthStatus.DEGRADED
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY
    
    def _check_cpu(self) -> HealthStatus:
        """Check CPU usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > 90:
                return HealthStatus.CRITICAL
            elif cpu_percent > 75:
                return HealthStatus.UNHEALTHY
            elif cpu_percent > 60:
                return HealthStatus.DEGRADED
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY
    
    def _check_disk(self) -> HealthStatus:
        """Check disk usage."""
        try:
            import sys
            path = '/' if sys.platform != 'win32' else 'C:\\'
            disk = psutil.disk_usage(path)
            if disk.percent > 90:
                return HealthStatus.CRITICAL
            elif disk.percent > 80:
                return HealthStatus.UNHEALTHY
            elif disk.percent > 70:
                return HealthStatus.DEGRADED
            return HealthStatus.HEALTHY
        except Exception:
            return HealthStatus.UNHEALTHY
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_status = HealthStatus.HEALTHY
        
        for name, check_func in self.health_checks.items():
            try:
                status = check_func() if not asyncio.iscoroutinefunction(check_func) else await check_func()
                self.health_status[name] = status
                results[name] = status.value
                
                # Determine overall status (worst status wins)
                if status.value in ["critical", "unhealthy", "degraded"]:
                    overall_status = status
            except Exception as e:
                results[name] = f"error: {str(e)}"
                overall_status = HealthStatus.UNHEALTHY
        
        self.last_check_time = time.time()
        
        return {
            "overall_status": overall_status.value,
            "checks": results,
            "timestamp": self.last_check_time
        }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get detailed system information."""
        import sys
        import socket
        return {
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "hostname": socket.gethostname(),
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "disk_total_gb": psutil.disk_usage('/').total / (1024**3) if sys.platform != 'win32' else psutil.disk_usage('C:\\').total / (1024**3)
        }


class MonitoringSystem:
    """
    Central monitoring system integrating metrics, logging, and health checks.
    """
    def __init__(self):
        self.metrics = MetricsCollector()
        self.loggers: Dict[str, StructuredLogger] = {}
        self.health_checker = HealthChecker()
        self.performance_traces: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()
        
        # Setup main logger
        self.get_logger("main")
    
    def get_logger(self, component: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
        """Get or create a logger for a component."""
        if component not in self.loggers:
            self.loggers[component] = StructuredLogger(component, level)
        return self.loggers[component]
    
    def record_performance(self, operation: str, duration_ms: float):
        """Record performance timing for an operation."""
        with self._lock:
            self.performance_traces[operation].append(duration_ms)
            # Keep only last 1000 traces
            if len(self.performance_traces[operation]) > 1000:
                self.performance_traces[operation] = self.performance_traces[operation][-1000:]
        
        self.metrics.record_metric(f"perf.{operation}", duration_ms)
    
    def get_performance_stats(self, operation: str) -> Dict[str, Any]:
        """Get performance statistics for an operation."""
        with self._lock:
            traces = self.performance_traces.get(operation, [])
        
        if not traces:
            return {"count": 0}
        
        return {
            "count": len(traces),
            "min_ms": min(traces),
            "max_ms": max(traces),
            "avg_ms": sum(traces) / len(traces),
            "p50_ms": self._percentile(traces, 50),
            "p95_ms": self._percentile(traces, 95),
            "p99_ms": self._percentile(traces, 99)
        }
    
    def _percentile(self, data: List[float], p: int) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        health_status = await self.health_checker.run_health_checks()
        
        return {
            "timestamp": time.time(),
            "health": health_status,
            "system_info": self.health_checker.get_system_info(),
            "metrics": self.metrics.get_all_metrics(),
            "performance": {
                op: self.get_performance_stats(op)
                for op in list(self.performance_traces.keys())[:10]  # Limit to top 10
            },
            "recent_logs": {
                component: logger.get_recent_logs(limit=10)
                for component, logger in list(self.loggers.items())[:5]  # Limit to top 5
            }
        }
    
    def start_background_monitoring(self, interval: float = 30.0):
        """Start background monitoring loop."""
        async def monitor_loop():
            while True:
                try:
                    # Record system metrics
                    self.metrics.set_gauge("memory_usage_gb", psutil.virtual_memory().used / (1024**3))
                    self.metrics.set_gauge("cpu_usage_percent", psutil.cpu_percent())
                    
                    import sys
                    path = '/' if sys.platform != 'win32' else 'C:\\'
                    self.metrics.set_gauge("disk_usage_percent", psutil.disk_usage(path).percent)
                    
                    # Run health checks
                    await self.health_checker.run_health_checks()
                    
                except Exception as e:
                    self.get_logger("monitoring").error(f"Background monitoring error: {e}")
                
                await asyncio.sleep(interval)
        
        asyncio.create_task(monitor_loop())


# Global monitoring system instance
monitoring_system = MonitoringSystem()


def get_monitoring() -> MonitoringSystem:
    """Get the global monitoring system instance."""
    return monitoring_system


def get_logger(component: str, level: LogLevel = LogLevel.INFO) -> StructuredLogger:
    """Get a logger for a specific component."""
    return monitoring_system.get_logger(component, level)


def record_performance(operation: str, duration_ms: float):
    """Record performance timing for an operation."""
    monitoring_system.record_performance(operation, duration_ms)


async def get_health_status() -> Dict[str, Any]:
    """Get current system health status."""
    return await monitoring_system.health_checker.run_health_checks()