"""
Retry Logic Module

Implements retry strategies with exponential backoff and circuit breaker patterns.
"""

from __future__ import annotations

import time
import random
from typing import Callable, Optional, TypeVar, Tuple
from functools import wraps
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[type, ...] = (Exception,)


class RetryHandler:
    """Handles retry logic with exponential backoff."""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def execute(self, func: Callable[[], T]) -> Tuple[bool, Optional[T], int]:
        """
        Execute function with retry logic.
        
        Returns:
            Tuple of (success, result, attempts_made)
        """
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func()
                return True, result, attempt
            except self.config.retryable_exceptions as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                
                if attempt < self.config.max_attempts:
                    delay = self._calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.config.max_attempts} attempts failed")
        
        return False, None, self.config.max_attempts
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff."""
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))
        delay = min(delay, self.config.max_delay)
        
        if self.config.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        return delay


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    Prevents repeated calls to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self._failures = 0
        self._last_failure_time: Optional[float] = None
        self._state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable[[], T]) -> T:
        """Call function with circuit breaker protection."""
        if self._state == "open":
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = "half-open"
                logger.info("Circuit breaker entering half-open state")
            else:
                raise CircuitBreakerOpen("Circuit breaker is open")
        
        try:
            result = func()
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self) -> None:
        """Handle successful call."""
        if self._state == "half-open":
            self._state = "closed"
            self._failures = 0
            logger.info("Circuit breaker closed")
        else:
            self._failures = max(0, self._failures - 1)
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        self._failures += 1
        self._last_failure_time = time.time()
        
        if self._failures >= self.failure_threshold:
            self._state = "open"
            logger.warning(f"Circuit breaker opened after {self._failures} failures")
    
    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass
