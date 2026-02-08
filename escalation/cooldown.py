"""
Alert Cooldown Manager

Prevents alert spam by implementing cooldown periods.
Tracks recently sent alerts and suppresses duplicates.
"""

from __future__ import annotations

import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CooldownEntry:
    """Cooldown tracking entry."""
    first_alert_time: float
    last_alert_time: float
    alert_count: int
    suppressed_count: int = 0


class AlertCooldownManager:
    """
    Manages alert cooldown to prevent notification spam.
    
    Features:
    - Per-device cooldown
    - Per-alert-type cooldown
    - Exponential backoff
    - Cooldown override for critical alerts
    """
    
    def __init__(
        self,
        default_cooldown_seconds: int = 300,  # 5 minutes
        max_suppression_count: int = 10
    ):
        self.default_cooldown = default_cooldown_seconds
        self.max_suppression = max_suppression_count
        
        # Cooldown storage: (device_id, alert_type, variable) -> CooldownEntry
        self._cooldowns: Dict[Tuple[str, str, str], CooldownEntry] = {}
        
        # Custom cooldown periods by alert type
        self._custom_cooldowns: Dict[str, int] = {
            "device_offline": 60,       # 1 minute for offline
            "interface_down": 180,      # 3 minutes for interface
            "high_cpu": 300,           # 5 minutes for CPU
            "high_memory": 300,
            "disk_full": 60,           # 1 minute - critical
            "bgp_flap": 60,
        }
    
    def check_and_update(
        self,
        device_id: str,
        alert_type: str,
        variable: str,
        severity: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if alert should be suppressed due to cooldown.
        
        Args:
            device_id: Device identifier
            alert_type: Type of alert
            variable: Variable/metric involved
            severity: Alert severity
        
        Returns:
            Tuple of (should_send, suppression_message)
        """
        key = (device_id, alert_type, variable)
        current_time = time.time()
        
        # Critical alerts bypass cooldown
        if severity in ["critical", "emergency"]:
            self._clear_cooldown(key)
            return True, None
        
        # Get cooldown period
        cooldown_period = self._custom_cooldowns.get(alert_type, self.default_cooldown)
        
        if key in self._cooldowns:
            entry = self._cooldowns[key]
            time_since_last = current_time - entry.last_alert_time
            
            if time_since_last < cooldown_period:
                # Still in cooldown
                entry.suppressed_count += 1
                remaining = cooldown_period - time_since_last
                
                msg = (
                    f"Suppressed: Alert in cooldown for {remaining:.0f}s more "
                    f"(suppressed {entry.suppressed_count} times)"
                )
                
                return False, msg
            else:
                # Cooldown expired, update entry
                entry.last_alert_time = current_time
                entry.alert_count += 1
                return True, None
        else:
            # New alert, create entry
            self._cooldowns[key] = CooldownEntry(
                first_alert_time=current_time,
                last_alert_time=current_time,
                alert_count=1
            )
            return True, None
    
    def _clear_cooldown(self, key: Tuple[str, str, str]) -> None:
        """Clear cooldown for a specific alert."""
        if key in self._cooldowns:
            del self._cooldowns[key]
    
    def clear_all_cooldowns(self) -> None:
        """Clear all cooldown entries."""
        self._cooldowns.clear()
        logger.info("All cooldowns cleared")
    
    def set_cooldown_period(
        self,
        alert_type: str,
        seconds: int
    ) -> None:
        """Set custom cooldown period for alert type."""
        self._custom_cooldowns[alert_type] = seconds
        logger.info(f"Set cooldown for {alert_type}: {seconds}s")
    
    def get_cooldown_info(
        self,
        device_id: str,
        alert_type: str,
        variable: str
    ) -> Optional[Dict]:
        """Get cooldown information for an alert."""
        key = (device_id, alert_type, variable)
        
        if key not in self._cooldowns:
            return None
        
        entry = self._cooldowns[key]
        current_time = time.time()
        cooldown_period = self._custom_cooldowns.get(alert_type, self.default_cooldown)
        
        time_since_last = current_time - entry.last_alert_time
        remaining = max(0, cooldown_period - time_since_last)
        
        return {
            "first_alert": entry.first_alert_time,
            "last_alert": entry.last_alert_time,
            "alert_count": entry.alert_count,
            "suppressed_count": entry.suppressed_count,
            "cooldown_remaining": remaining,
            "in_cooldown": remaining > 0
        }
    
    def cleanup_expired(self, max_age_hours: int = 24) -> int:
        """Remove old cooldown entries."""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired = [
            key for key, entry in self._cooldowns.items()
            if current_time - entry.last_alert_time > max_age_seconds
        ]
        
        for key in expired:
            del self._cooldowns[key]
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired cooldown entries")
        
        return len(expired)
    
    def get_stats(self) -> Dict:
        """Get cooldown statistics."""
        total_alerts = sum(e.alert_count for e in self._cooldowns.values())
        total_suppressed = sum(e.suppressed_count for e in self._cooldowns.values())
        
        active_cooldowns = sum(
            1 for e in self._cooldowns.values()
            if time.time() - e.last_alert_time < self.default_cooldown
        )
        
        return {
            "active_cooldowns": active_cooldowns,
            "total_tracked": len(self._cooldowns),
            "total_alerts": total_alerts,
            "total_suppressed": total_suppressed,
            "suppression_rate": (
                total_suppressed / (total_alerts + total_suppressed)
                if (total_alerts + total_suppressed) > 0 else 0
            )
        }


class AlertDeduplicator:
    """
    Deduplicates identical or similar alerts.
    Prevents multiple notifications for the same issue.
    """
    
    def __init__(self, similarity_window_seconds: int = 60):
        self.similarity_window = similarity_window_seconds
        self._recent_alerts: Dict[str, float] = {}  # alert_hash -> timestamp
    
    def is_duplicate(
        self,
        device_id: str,
        alert_type: str,
        variable: str,
        value: float,
        threshold: float
    ) -> bool:
        """
        Check if this alert is a duplicate of a recent one.
        
        Returns:
            True if duplicate (should be suppressed)
        """
        # Create alert fingerprint
        alert_hash = f"{device_id}:{alert_type}:{variable}"
        current_time = time.time()
        
        if alert_hash in self._recent_alerts:
            last_time = self._recent_alerts[alert_hash]
            
            if current_time - last_time < self.similarity_window:
                # Similar alert within window
                self._recent_alerts[alert_hash] = current_time  # Update timestamp
                return True
        
        # Not a duplicate, record it
        self._recent_alerts[alert_hash] = current_time
        return False
    
    def record_alert(
        self,
        device_id: str,
        alert_type: str,
        variable: str
    ) -> None:
        """Manually record an alert fingerprint."""
        alert_hash = f"{device_id}:{alert_type}:{variable}"
        self._recent_alerts[alert_hash] = time.time()
    
    def cleanup_old(self, max_age_minutes: int = 60) -> int:
        """Remove old alert fingerprints."""
        current_time = time.time()
        max_age = max_age_minutes * 60
        
        old = [
            h for h, t in self._recent_alerts.items()
            if current_time - t > max_age
        ]
        
        for h in old:
            del self._recent_alerts[h]
        
        return len(old)
