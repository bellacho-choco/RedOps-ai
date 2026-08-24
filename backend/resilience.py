"""
====================================================================
PROJECT REDOPS-AI - RESILIENCE & ERROR HANDLING LAYER
Comprehensive error handling with circuit breakers, retry policies, and fallback mechanisms
====================================================================
"""

import asyncio
import time
import logging
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import traceback


class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit tripped, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class ErrorContext:
    """Context information about an error."""
    error_type: str
    error_message: str
    severity: ErrorSeverity
    timestamp: float
    component: str
    stack_trace: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "component": self.component,
            "stack_trace": self.stack_trace,
            "metadata": self.metadata
        }


class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.
    """
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker protection."""
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker is OPEN. Last failure: {self.last_failure_time}"
                    )
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.success_count += 1
                    if self.success_count >= 2:  # Need 2 successes to close
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0
                elif self.state == CircuitState.CLOSED:
                    self.failure_count = 0  # Reset on success
            
            return result
            
        except self.expected_exception as e:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.success_count = 0
            
            raise
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }
    
    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0


class RetryPolicy:
    """
    Configurable retry policy with exponential backoff.
    """
    def __init__(self,
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 backoff_multiplier: float = 2.0,
                 retryable_exceptions: Optional[List[Type[Exception]]] = None):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.retryable_exceptions = retryable_exceptions or [Exception]
    
    def should_retry(self, exception: Exception) -> bool:
        """Determine if exception is retryable."""
        return any(isinstance(exception, exc_type) for exc_type in self.retryable_exceptions)
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = min(self.base_delay * (self.backoff_multiplier ** attempt), self.max_delay)
        return delay
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if not self.should_retry(e) or attempt == self.max_attempts - 1:
                    raise
                
                delay = self.get_delay(attempt)
                await asyncio.sleep(delay)
        
        raise last_exception


class FallbackHandler:
    """
    Fallback mechanism for when primary operations fail.
    """
    def __init__(self):
        self.fallbacks: Dict[str, Callable] = {}
    
    def register(self, operation: str, fallback: Callable):
        """Register a fallback function for an operation."""
        self.fallbacks[operation] = fallback
    
    async def execute(self, operation: str, *args, **kwargs) -> Any:
        """Execute fallback for operation if available."""
        fallback = self.fallbacks.get(operation)
        if fallback:
            return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
        raise FallbackNotAvailableError(f"No fallback registered for operation: {operation}")


class ErrorHandler:
    """
    Centralized error handling with logging, context capture, and recovery strategies.
    """
    def __init__(self):
        self.error_log: List[ErrorContext] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_policies: Dict[str, RetryPolicy] = {}
        self.fallback_handler = FallbackHandler()
        self.logger = logging.getLogger("redops.error_handler")
        
        # Default configurations
        self._setup_defaults()
    
    def _setup_defaults(self):
        """Setup default error handling configurations."""
        # Circuit breaker for external API calls
        self.circuit_breakers["external_api"] = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0
        )
        
        # Retry policy for network operations
        self.retry_policies["network"] = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            backoff_multiplier=2.0
        )
    
    def capture_error(self, error: Exception, component: str, 
                     severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                     metadata: Optional[Dict[str, Any]] = None) -> ErrorContext:
        """Capture error context for logging and analysis."""
        context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            timestamp=time.time(),
            component=component,
            stack_trace=traceback.format_exc(),
            metadata=metadata or {}
        )
        
        self.error_log.append(context)
        
        # Log based on severity
        log_method = {
            ErrorSeverity.LOW: self.logger.info,
            ErrorSeverity.MEDIUM: self.logger.warning,
            ErrorSeverity.HIGH: self.logger.error,
            ErrorSeverity.CRITICAL: self.logger.critical
        }.get(severity, self.logger.error)
        
        log_method(f"[{component}] {context.error_type}: {context.error_message}")
        
        return context
    
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker for component."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker()
        return self.circuit_breakers[name]
    
    def get_retry_policy(self, name: str) -> RetryPolicy:
        """Get or create retry policy for operation type."""
        if name not in self.retry_policies:
            self.retry_policies[name] = RetryPolicy()
        return self.retry_policies[name]
    
    def register_fallback(self, operation: str, fallback: Callable):
        """Register fallback for an operation."""
        self.fallback_handler.register(operation, fallback)
    
    async def execute_with_resilience(self,
                                     func: Callable,
                                     component: str,
                                     operation_type: str = "default",
                                     circuit_breaker: Optional[str] = None,
                                     retry_policy: Optional[str] = None,
                                     fallback_operation: Optional[str] = None,
                                     *args,
                                     **kwargs) -> Any:
        """
        Execute function with comprehensive resilience patterns.
        """
        circuit_breaker_name = circuit_breaker or component
        retry_policy_name = retry_policy or operation_type
        
        try:
            # Apply circuit breaker if configured
            if circuit_breaker_name in self.circuit_breakers:
                cb = self.circuit_breakers[circuit_breaker_name]
                return await cb.call(func, *args, **kwargs)
            
            # Apply retry policy if configured
            if retry_policy_name in self.retry_policies:
                policy = self.retry_policies[retry_policy_name]
                return await policy.execute(func, *args, **kwargs)
            
            # Direct execution
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
        except Exception as e:
            # Capture error context
            self.capture_error(e, component)
            
            # Try fallback if available
            if fallback_operation:
                try:
                    return await self.fallback_handler.execute(fallback_operation, *args, **kwargs)
                except Exception as fallback_error:
                    self.capture_error(fallback_error, f"{component}_fallback", ErrorSeverity.HIGH)
            
            raise
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors and system state."""
        if not self.error_log:
            return {"total_errors": 0, "by_severity": {}, "by_component": {}}
        
        by_severity = {}
        by_component = {}
        
        for error in self.error_log:
            severity = error.severity.value
            component = error.component
            
            by_severity[severity] = by_severity.get(severity, 0) + 1
            by_component[component] = by_component.get(component, 0) + 1
        
        return {
            "total_errors": len(self.error_log),
            "by_severity": by_severity,
            "by_component": by_component,
            "recent_errors": [e.to_dict() for e in self.error_log[-10:]],
            "circuit_breakers": {name: cb.get_state() for name, cb in self.circuit_breakers.items()}
        }
    
    def clear_errors(self):
        """Clear error log."""
        self.error_log.clear()


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class FallbackNotAvailableError(Exception):
    """Raised when no fallback is available."""
    pass


# Global error handler instance
error_handler = ErrorHandler()


def with_resilience(component: str,
                   operation_type: str = "default",
                   circuit_breaker: Optional[str] = None,
                   retry_policy: Optional[str] = None,
                   fallback_operation: Optional[str] = None):
    """
    Decorator for adding resilience patterns to functions.
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await error_handler.execute_with_resilience(
                func, component, operation_type, circuit_breaker,
                retry_policy, fallback_operation, *args, **kwargs
            )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return asyncio.run(error_handler.execute_with_resilience(
                func, component, operation_type, circuit_breaker,
                retry_policy, fallback_operation, *args, **kwargs
            ))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator