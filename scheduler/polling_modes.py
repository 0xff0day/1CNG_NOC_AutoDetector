"""
Polling Modes Module

Different polling strategies for various device types and requirements.
Supports adaptive, on-demand, and event-driven polling.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class PollingMode(Enum):
    """Polling mode types."""
    FIXED = "fixed"           # Fixed interval
    ADAPTIVE = "adaptive"     # Adjust based on activity
    ON_DEMAND = "ondemand"    # Only when requested
    EVENT_DRIVEN = "event"    # Triggered by events
    SMART = "smart"          # AI-optimized


@dataclass
class PollingConfig:
    """Polling configuration."""
    mode: PollingMode
    base_interval: int  # seconds
    min_interval: int = 10
    max_interval: int = 3600
    backoff_multiplier: float = 2.0
    activity_threshold: float = 0.5
    current_interval: int = 300


class AdaptivePolling:
    """
    Adaptive polling that adjusts frequency based on device activity.
    
    - Increases frequency during issues
    - Decreases when stable
    - Respects min/max bounds
    """
    
    def __init__(self, config: PollingConfig):
        self.config = config
        self._stability_score = 1.0  # 0-1, higher = more stable
        self._consecutive_issues = 0
        self._last_poll_time = 0
    
    def calculate_next_interval(
        self,
        has_issues: bool,
        metrics_changed: bool
    ) -> int:
        """
        Calculate next polling interval.
        
        Args:
            has_issues: Device has active issues
            metrics_changed: Significant metric changes detected
        
        Returns:
            New interval in seconds
        """
        current = self.config.current_interval
        
        if has_issues:
            # Increase polling frequency
            self._consecutive_issues += 1
            self._stability_score = max(0, self._stability_score - 0.2)
            
            # More issues = faster polling
            factor = min(self._consecutive_issues, 3)
            new_interval = max(
                self.config.min_interval,
                int(current / (self.config.backoff_multiplier * factor))
            )
        
        elif metrics_changed:
            # Moderate increase for changes
            new_interval = max(
                self.config.min_interval,
                int(current / 1.5)
            )
            self._consecutive_issues = max(0, self._consecutive_issues - 1)
        
        else:
            # Stable - can decrease frequency
            self._consecutive_issues = 0
            self._stability_score = min(1.0, self._stability_score + 0.1)
            
            if self._stability_score > 0.8:
                # Slowly increase interval
                new_interval = min(
                    self.config.max_interval,
                    int(current * 1.1)
                )
            else:
                new_interval = current
        
        self.config.current_interval = new_interval
        return new_interval
    
    def get_current_interval(self) -> int:
        """Get current polling interval."""
        return self.config.current_interval


class SmartPollingManager:
    """
    Manages different polling modes for devices.
    
    Assigns appropriate polling strategy based on:
    - Device criticality
    - Historical stability
    - Time of day
    """
    
    def __init__(self):
        self._configs: Dict[str, PollingConfig] = {}
        self._adaptive_engines: Dict[str, AdaptivePolling] = {}
        self._last_poll: Dict[str, float] = {}
    
    def configure_device(
        self,
        device_id: str,
        mode: PollingMode,
        base_interval: int = 300
    ) -> PollingConfig:
        """
        Configure polling for a device.
        
        Args:
            device_id: Device identifier
            mode: Polling mode
            base_interval: Base polling interval
        
        Returns:
            PollingConfig
        """
        config = PollingConfig(
            mode=mode,
            base_interval=base_interval,
            current_interval=base_interval
        )
        
        self._configs[device_id] = config
        
        if mode == PollingMode.ADAPTIVE:
            self._adaptive_engines[device_id] = AdaptivePolling(config)
        
        logger.info(f"Configured {mode.value} polling for {device_id} ({base_interval}s)")
        return config
    
    def should_poll(self, device_id: str) -> bool:
        """Check if device should be polled now."""
        if device_id not in self._configs:
            return True
        
        config = self._configs[device_id]
        
        if config.mode == PollingMode.ON_DEMAND:
            return False  # Only poll when explicitly requested
        
        if device_id not in self._last_poll:
            return True
        
        elapsed = time.time() - self._last_poll[device_id]
        return elapsed >= config.current_interval
    
    def record_poll(
        self,
        device_id: str,
        has_issues: bool = False,
        metrics_changed: bool = False
    ) -> int:
        """
        Record a poll and get next interval.
        
        Args:
            device_id: Device polled
            has_issues: Issues detected
            metrics_changed: Metrics changed significantly
        
        Returns:
            Next recommended interval
        """
        self._last_poll[device_id] = time.time()
        
        config = self._configs.get(device_id)
        if not config:
            return 300
        
        if config.mode == PollingMode.ADAPTIVE:
            engine = self._adaptive_engines.get(device_id)
            if engine:
                return engine.calculate_next_interval(has_issues, metrics_changed)
        
        return config.current_interval
    
    def get_polling_interval(self, device_id: str) -> int:
        """Get current polling interval for device."""
        config = self._configs.get(device_id)
        if not config:
            return 300
        
        if config.mode == PollingMode.ADAPTIVE:
            engine = self._adaptive_engines.get(device_id)
            if engine:
                return engine.get_current_interval()
        
        return config.current_interval
    
    def force_poll(self, device_id: str) -> None:
        """Force immediate poll on next check."""
        self._last_poll[device_id] = 0
    
    def set_maintenance_mode(
        self,
        device_id: str,
        enabled: bool = True
    ) -> None:
        """
        Set maintenance mode (reduces polling frequency).
        
        Args:
            device_id: Device to configure
            enabled: True to enable maintenance mode
        """
        config = self._configs.get(device_id)
        if not config:
            return
        
        if enabled:
            # Reduce polling during maintenance
            config.current_interval = min(config.max_interval, config.base_interval * 2)
            logger.info(f"Maintenance mode enabled for {device_id}")
        else:
            # Restore normal polling
            config.current_interval = config.base_interval
            logger.info(f"Maintenance mode disabled for {device_id}")
    
    def get_device_polling_stats(self, device_id: str) -> Dict:
        """Get polling statistics for device."""
        config = self._configs.get(device_id)
        if not config:
            return {}
        
        last_poll = self._last_poll.get(device_id, 0)
        
        return {
            "mode": config.mode.value,
            "base_interval": config.base_interval,
            "current_interval": config.current_interval,
            "min_interval": config.min_interval,
            "max_interval": config.max_interval,
            "last_poll": last_poll,
            "next_poll_due": last_poll + config.current_interval,
        }


class BatchPoller:
    """
    Efficient batch polling for multiple devices.
    
    Groups devices by polling interval and batches requests.
    """
    
    def __init__(self, smart_manager: SmartPollingManager):
        self.manager = smart_manager
        self._batch_callbacks: Dict[str, Callable] = {}
    
    def register_batch_callback(
        self,
        interval_bucket: str,
        callback: Callable[[List[str]], None]
    ) -> None:
        """
        Register callback for batch polling.
        
        Args:
            interval_bucket: Interval category (e.g., "fast", "normal", "slow")
            callback: Function to call with list of device IDs
        """
        self._batch_callbacks[interval_bucket] = callback
    
    def get_poll_batch(self) -> Dict[str, List[str]]:
        """
        Get devices ready for polling, grouped by interval.
        
        Returns:
            Dict mapping interval bucket to device IDs
        """
        batches: Dict[str, List[str]] = {
            "fast": [],      # < 60s
            "normal": [],    # 60-300s
            "slow": [],      # > 300s
        }
        
        for device_id in self.manager._configs:
            if self.manager.should_poll(device_id):
                interval = self.manager.get_polling_interval(device_id)
                
                if interval < 60:
                    batches["fast"].append(device_id)
                elif interval <= 300:
                    batches["normal"].append(device_id)
                else:
                    batches["slow"].append(device_id)
        
        return batches
    
    def execute_batch_poll(self) -> Dict[str, int]:
        """
        Execute polling for all due devices.
        
        Returns:
            Dict with poll counts per bucket
        """
        batches = self.get_poll_batch()
        results = {}
        
        for bucket, device_ids in batches.items():
            if device_ids and bucket in self._batch_callbacks:
                try:
                    self._batch_callbacks[bucket](device_ids)
                    results[bucket] = len(device_ids)
                except Exception as e:
                    logger.error(f"Batch poll failed for {bucket}: {e}")
                    results[bucket] = 0
            else:
                results[bucket] = 0
        
        return results
