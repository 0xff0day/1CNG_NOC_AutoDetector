from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json


@dataclass
class NotificationRule:
    """Rule for routing notifications."""
    rule_id: str
    name: str
    priority: int  # Higher number = higher priority
    conditions: Dict[str, Any]  # Match criteria
    actions: List[Dict[str, Any]]  # What to do when matched
    enabled: bool = True
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class NotificationRouter:
    """Route notifications based on configurable rules."""
    
    def __init__(self):
        self.rules: List[NotificationRule] = []
        self.default_channels = ["telegram"]
    
    def add_rule(self, rule: NotificationRule):
        """Add a notification routing rule."""
        self.rules.append(rule)
        # Sort by priority (highest first)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule by ID."""
        original_count = len(self.rules)
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        return len(self.rules) < original_count
    
    def route_notification(
        self,
        notification: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Route a notification based on rules."""
        matched_actions = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            if self._matches_conditions(notification, rule.conditions):
                matched_actions.extend(rule.actions)
                
                # Stop on first match if rule has 'stop_processing' flag
                if rule.conditions.get("stop_processing", False):
                    break
        
        # If no rules matched, use defaults
        if not matched_actions:
            matched_actions = [
                {"type": "channel", "channel": ch} 
                for ch in self.default_channels
            ]
        
        return matched_actions
    
    def _matches_conditions(
        self,
        notification: Dict[str, Any],
        conditions: Dict[str, Any]
    ) -> bool:
        """Check if notification matches rule conditions."""
        for key, expected in conditions.items():
            if key == "stop_processing":
                continue
            
            actual = notification.get(key)
            
            # Handle different condition types
            if isinstance(expected, list):
                if actual not in expected:
                    return False
            elif isinstance(expected, dict):
                # Comparison operators
                if "eq" in expected and actual != expected["eq"]:
                    return False
                if "ne" in expected and actual == expected["ne"]:
                    return False
                if "gt" in expected and (actual is None or actual <= expected["gt"]):
                    return False
                if "lt" in expected and (actual is None or actual >= expected["lt"]):
                    return False
                if "contains" in expected:
                    if not actual or expected["contains"] not in str(actual):
                        return False
                if "regex" in expected:
                    import re
                    if not actual or not re.search(expected["regex"], str(actual)):
                        return False
            else:
                if actual != expected:
                    return False
        
        return True
    
    def get_matching_rules(
        self,
        notification: Dict[str, Any]
    ) -> List[NotificationRule]:
        """Get all rules that match a notification."""
        return [
            rule for rule in self.rules
            if rule.enabled and self._matches_conditions(notification, rule.conditions)
        ]
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """List all notification rules."""
        return [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "priority": r.priority,
                "enabled": r.enabled,
                "conditions": r.conditions,
                "actions": r.actions,
                "created_at": r.created_at,
            }
            for r in self.rules
        ]


# Common routing rule presets
PRESET_RULES = {
    "critical_to_all": NotificationRule(
        rule_id="preset-critical-all",
        name="Critical alerts to all channels",
        priority=100,
        conditions={"severity": "critical"},
        actions=[
            {"type": "channel", "channel": "telegram"},
            {"type": "channel", "channel": "email"},
            {"type": "channel", "channel": "voice_call"},
        ],
    ),
    
    "core_network_sms": NotificationRule(
        rule_id="preset-core-sms",
        name="Core network alerts via SMS",
        priority=90,
        conditions={
            "tags": {"contains": "core"},
            "severity": ["critical", "warning"],
        },
        actions=[
            {"type": "channel", "channel": "sms"},
            {"type": "channel", "channel": "telegram"},
        ],
    ),
    
    "security_to_security_team": NotificationRule(
        rule_id="preset-security-team",
        name="Security alerts to security team",
        priority=95,
        conditions={
            "variable": {"regex": "(firewall|acl|vpn|auth)"},
        },
        actions=[
            {"type": "channel", "channel": "telegram"},
            {"type": "contact_group", "group": "security_team"},
        ],
    ),
    
    "maintenance_suppress": NotificationRule(
        rule_id="preset-maintenance-suppress",
        name="Suppress alerts during maintenance",
        priority=200,
        conditions={
            "maintenance_mode": True,
        },
        actions=[
            {"type": "suppress", "reason": "maintenance_window"},
        ],
    ),
    
    "flapping_alerts_escalate": NotificationRule(
        rule_id="preset-flapping-escalate",
        name="Escalate flapping alerts",
        priority=85,
        conditions={
            "flapping": True,
            "flap_count": {"gt": 5},
        },
        actions=[
            {"type": "escalate", "level": "noc_manager"},
            {"type": "channel", "channel": "telegram"},
        ],
    ),
}
