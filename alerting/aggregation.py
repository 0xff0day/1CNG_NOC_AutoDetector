from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass(frozen=True)
class AlertGroup:
    group_id: str
    alert_ids: List[str]
    common_device_id: Optional[str]
    common_variable: Optional[str]
    severity: str
    first_seen: str
    last_seen: str
    message_summary: str
    count: int


class AlertAggregator:
    """Aggregate related alerts into groups for noise reduction."""
    
    def __init__(self, time_window_sec: int = 300):
        self.time_window_sec = time_window_sec
        self.groups: Dict[str, AlertGroup] = {}
        self.alert_to_group: Dict[str, str] = {}
    
    def _generate_group_key(
        self,
        device_id: str,
        variable: str,
        severity: str
    ) -> str:
        """Generate a grouping key for similar alerts."""
        key_str = f"{device_id}:{variable}:{severity}"
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
    
    def add_alert(self, alert: Dict[str, Any]) -> Optional[AlertGroup]:
        """Add an alert to aggregation. Returns group if created/updated."""
        alert_id = alert.get("id", alert.get("dedupe_key", ""))
        device_id = alert.get("device_id", "")
        variable = alert.get("variable", "")
        severity = alert.get("severity", "info")
        ts = alert.get("ts", datetime.now(timezone.utc).isoformat())
        
        # Check if alert already in a group
        if alert_id in self.alert_to_group:
            return None
        
        # Find or create group
        group_key = self._generate_group_key(device_id, variable, severity)
        
        if group_key in self.groups:
            # Add to existing group
            existing = self.groups[group_key]
            
            # Check time window
            last_seen = datetime.fromisoformat(existing.last_seen)
            current = datetime.fromisoformat(ts)
            time_diff = (current - last_seen).total_seconds()
            
            if time_diff <= self.time_window_sec:
                # Update group
                new_alert_ids = list(existing.alert_ids) + [alert_id]
                updated = AlertGroup(
                    group_id=existing.group_id,
                    alert_ids=new_alert_ids,
                    common_device_id=existing.common_device_id,
                    common_variable=existing.common_variable,
                    severity=existing.severity,
                    first_seen=existing.first_seen,
                    last_seen=ts,
                    message_summary=existing.message_summary,
                    count=len(new_alert_ids)
                )
                self.groups[group_key] = updated
                self.alert_to_group[alert_id] = group_key
                return updated
        
        # Create new group
        new_group = AlertGroup(
            group_id=f"GRP-{group_key}-{int(datetime.now().timestamp())}",
            alert_ids=[alert_id],
            common_device_id=device_id if device_id else None,
            common_variable=variable if variable else None,
            severity=severity,
            first_seen=ts,
            last_seen=ts,
            message_summary=alert.get("message", "")[:100],
            count=1
        )
        
        self.groups[group_key] = new_group
        self.alert_to_group[alert_id] = group_key
        return new_group
    
    def get_group(self, alert_id: str) -> Optional[AlertGroup]:
        """Get the group an alert belongs to."""
        group_key = self.alert_to_group.get(alert_id)
        if group_key:
            return self.groups.get(group_key)
        return None
    
    def flush_expired_groups(self, max_age_sec: int = 600) -> List[AlertGroup]:
        """Flush and return groups older than max_age_sec."""
        now = datetime.now(timezone.utc)
        expired = []
        keys_to_remove = []
        
        for key, group in self.groups.items():
            last_seen = datetime.fromisoformat(group.last_seen)
            age = (now - last_seen).total_seconds()
            
            if age > max_age_sec:
                expired.append(group)
                keys_to_remove.append(key)
        
        # Remove expired groups
        for key in keys_to_remove:
            del self.groups[key]
            # Clean up alert mappings
            self.alert_to_group = {
                k: v for k, v in self.alert_to_group.items() 
                if v != key
            }
        
        return expired
    
    def get_all_active_groups(self) -> List[AlertGroup]:
        """Get all currently active (non-expired) groups."""
        return sorted(
            list(self.groups.values()),
            key=lambda g: g.last_seen,
            reverse=True
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get aggregation summary."""
        severity_counts: Dict[str, int] = {}
        for group in self.groups.values():
            severity_counts[group.severity] = severity_counts.get(group.severity, 0) + 1
        
        total_alerts = sum(g.count for g in self.groups.values())
        
        return {
            "total_groups": len(self.groups),
            "total_alerts_aggregated": total_alerts,
            "severity_distribution": severity_counts,
            "aggregation_window_sec": self.time_window_sec,
        }


class AlertSuppressor:
    """Suppress alerts based on patterns and conditions."""
    
    def __init__(self):
        self.suppression_rules: List[Dict[str, Any]] = []
        self.suppressed_alerts: List[Dict[str, Any]] = []
    
    def add_suppression_rule(
        self,
        name: str,
        pattern: Dict[str, Any],
        duration_sec: int,
        reason: str
    ):
        """Add a suppression rule."""
        rule = {
            "name": name,
            "pattern": pattern,  # e.g., {"device_id": "srv1", "variable": "CPU_USAGE"}
            "duration_sec": duration_sec,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": None,
            "reason": reason,
            "hit_count": 0,
        }
        self.suppression_rules.append(rule)
    
    def should_suppress(self, alert: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if an alert should be suppressed."""
        for rule in self.suppression_rules:
            if self._matches_pattern(alert, rule["pattern"]):
                rule["hit_count"] += 1
                self.suppressed_alerts.append({
                    "alert": alert,
                    "suppressed_at": datetime.now(timezone.utc).isoformat(),
                    "rule_name": rule["name"],
                    "reason": rule["reason"],
                })
                return True, rule["reason"]
        
        return False, None
    
    def _matches_pattern(self, alert: Dict[str, Any], pattern: Dict[str, Any]) -> bool:
        """Check if alert matches suppression pattern."""
        for key, value in pattern.items():
            if alert.get(key) != value:
                return False
        return True
    
    def get_suppression_stats(self) -> Dict[str, Any]:
        """Get suppression statistics."""
        return {
            "active_rules": len(self.suppression_rules),
            "total_suppressed": len(self.suppressed_alerts),
            "rules": [
                {
                    "name": r["name"],
                    "hits": r["hit_count"],
                    "pattern": r["pattern"],
                }
                for r in self.suppression_rules
            ],
        }
