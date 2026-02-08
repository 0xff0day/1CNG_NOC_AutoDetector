"""
Offline Detection Module

Detects when devices go offline and tracks connectivity state.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device connectivity state."""
    ONLINE = "online"
    OFFLINE = "offline"
    UNSTABLE = "unstable"
    UNKNOWN = "unknown"


@dataclass
class ConnectivityStatus:
    """Device connectivity status."""
    device_id: str
    state: DeviceState
    last_seen: float
    last_check: float
    consecutive_failures: int
    consecutive_successes: int
    total_checks: int
    offline_since: Optional[float] = None


class OfflineDetector:
    """
    Detects offline devices based on polling results.
    
    Features:
    - Consecutive failure detection
    - Recovery detection
    - State transitions
    - Flapping detection
    """
    
    def __init__(
        self,
        offline_threshold: int = 3,
        recovery_threshold: int = 2
    ):
        self.offline_threshold = offline_threshold
        self.recovery_threshold = recovery_threshold
        self._status: Dict[str, ConnectivityStatus] = {}
    
    def check_device(
        self,
        device_id: str,
        is_reachable: bool
    ) -> ConnectivityStatus:
        """
        Update device connectivity status.
        
        Args:
            device_id: Device identifier
            is_reachable: Whether device responded
        
        Returns:
            Updated connectivity status
        """
        current_time = time.time()
        
        if device_id not in self._status:
            self._status[device_id] = ConnectivityStatus(
                device_id=device_id,
                state=DeviceState.UNKNOWN,
                last_seen=0,
                last_check=current_time,
                consecutive_failures=0,
                consecutive_successes=0,
                total_checks=0
            )
        
        status = self._status[device_id]
        status.last_check = current_time
        status.total_checks += 1
        
        if is_reachable:
            status.consecutive_successes += 1
            status.consecutive_failures = 0
            status.last_seen = current_time
            
            # Check for recovery
            if status.state == DeviceState.OFFLINE:
                if status.consecutive_successes >= self.recovery_threshold:
                    status.state = DeviceState.ONLINE
                    status.offline_since = None
                    logger.info(f"Device {device_id} is back online")
            else:
                status.state = DeviceState.ONLINE
        else:
            status.consecutive_failures += 1
            status.consecutive_successes = 0
            
            # Check for offline
            if status.state != DeviceState.OFFLINE:
                if status.consecutive_failures >= self.offline_threshold:
                    status.state = DeviceState.OFFLINE
                    status.offline_since = current_time
                    logger.warning(f"Device {device_id} is now offline")
            
            # Check for unstable
            elif status.consecutive_failures >= self.offline_threshold * 2:
                status.state = DeviceState.UNSTABLE
        
        return status
    
    def get_status(self, device_id: str) -> Optional[ConnectivityStatus]:
        """Get connectivity status for device."""
        return self._status.get(device_id)
    
    def get_offline_devices(self) -> List[str]:
        """Get list of offline device IDs."""
        return [
            did for did, s in self._status.items()
            if s.state == DeviceState.OFFLINE
        ]
    
    def get_online_devices(self) -> List[str]:
        """Get list of online device IDs."""
        return [
            did for did, s in self._status.items()
            if s.state == DeviceState.ONLINE
        ]
