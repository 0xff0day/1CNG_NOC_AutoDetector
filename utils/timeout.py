"""
Timeout Handler Module

Manages timeout operations for device connections and commands.
"""

from __future__ import annotations

import signal
import threading
from typing import Optional, Callable, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when operation times out."""
    pass


class TimeoutHandler:
    """Handles timeouts for operations."""
    
    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
    
    @contextmanager
    def timeout(self, seconds: Optional[float] = None):
        """Context manager for timeouts (Unix only)."""
        seconds = seconds or self.default_timeout
        
        def handler(signum, frame):
            raise TimeoutError(f"Operation timed out after {seconds} seconds")
        
        # Set up signal handler
        old_handler = signal.signal(signal.SIGALRM, handler)
        signal.alarm(int(seconds))
        
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    
    def run_with_timeout(
        self,
        func: Callable[[], Any],
        timeout: Optional[float] = None
    ) -> Any:
        """
        Run function with timeout (cross-platform).
        
        Uses threading for Windows compatibility.
        """
        timeout = timeout or self.default_timeout
        result = [None]
        exception = [None]
        
        def target():
            try:
                result[0] = func()
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Operation timed out after {timeout} seconds")
        
        if exception[0]:
            raise exception[0]
        
        return result[0]


class ConnectionTimeout:
    """Manages connection timeouts."""
    
    def __init__(
        self,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        command_timeout: float = 30.0
    ):
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.command_timeout = command_timeout
