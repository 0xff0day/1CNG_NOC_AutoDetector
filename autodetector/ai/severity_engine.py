"""
Alert Severity Engine

Determines alert severity based on metric thresholds,
impact scope, and escalation policies.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """Standard severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SeverityResult:
    """Severity determination result."""
    level: SeverityLevel
    score: int  # 0-100
    reasons: List[str]
    escalated: bool
    notification_channels: List[str]
    sla_minutes: Optional[int]


@dataclass
class SeverityRule:
    """Rule for severity calculation."""
    name: str
    condition: str
    severity: SeverityLevel
    weight: int
    auto_escalate: bool = False
    channels: List[str] = None
    sla_minutes: Optional[int] = None


class AlertSeverityEngine:
    """
    Determines alert severity with customizable rules.
    
    Factors considered:
    - Metric thresholds (warn/crit)
    - Device criticality
    - Time of day
    - Concurrent issues
    - Historical patterns
    """
    
    SEVERITY_SCORES = {
        SeverityLevel.INFO: 10,
        SeverityLevel.LOW: 25,
        SeverityLevel.MEDIUM: 50,
        SeverityLevel.HIGH: 75,
        SeverityLevel.CRITICAL: 90,
        SeverityLevel.EMERGENCY: 100,
    }
    
    def __init__(self):
        self.rules: List[SeverityRule] = []
        self.device_criticality: Dict[str, int] = {}  # 1-10
        self._load_default_rules()
    
    def _load_default_rules(self) -> None:
        """Load default severity rules."""
        self.rules = [
            SeverityRule(
                name="cpu_critical",
                condition="cpu_usage > 90",
                severity=SeverityLevel.HIGH,
                weight=30,
                channels=["telegram", "email"]
            ),
            SeverityRule(
                name="memory_critical",
                condition="memory_usage > 95",
                severity=SeverityLevel.CRITICAL,
                weight=40,
                auto_escalate=True,
                channels=["telegram", "voice"],
                sla_minutes=15
            ),
            SeverityRule(
                name="disk_full",
                condition="disk_usage > 98",
                severity=SeverityLevel.CRITICAL,
                weight=50,
                auto_escalate=True,
                channels=["telegram", "voice", "email"],
                sla_minutes=10
            ),
            SeverityRule(
                name="interface_down",
                condition="interface_down > 0",
                severity=SeverityLevel.HIGH,
                weight=35,
                channels=["telegram"]
            ),
            SeverityRule(
                name="device_offline",
                condition="device_reachable == false",
                severity=SeverityLevel.CRITICAL,
                weight=60,
                auto_escalate=True,
                channels=["telegram", "voice"],
                sla_minutes=5
            ),
            SeverityRule(
                name="hardware_failure",
                condition="power_ok == false or fan_ok == false",
                severity=SeverityLevel.EMERGENCY,
                weight=80,
                auto_escalate=True,
                channels=["telegram", "voice", "sms"],
                sla_minutes=5
            ),
            SeverityRule(
                name="routing_instability",
                condition="bgp_flap_count > 3",
                severity=SeverityLevel.HIGH,
                weight=40,
                channels=["telegram"]
            ),
            SeverityRule(
                name="temperature_high",
                condition="temperature > 80",
                severity=SeverityLevel.HIGH,
                weight=35,
                channels=["telegram"]
            ),
        ]
    
    def calculate_severity(
        self,
        alert_type: str,
        metrics: Dict[str, float],
        device_id: str,
        device_criticality: Optional[int] = None
    ) -> SeverityResult:
        """
        Calculate alert severity.
        
        Args:
            alert_type: Type of alert
            metrics: Current metric values
            device_id: Device identifier
            device_criticality: Device criticality level (1-10)
        
        Returns:
            SeverityResult with determination
        """
        matching_rules = []
        reasons = []
        
        # Check each rule
        for rule in self.rules:
            if self._evaluate_condition(rule.condition, metrics):
                matching_rules.append(rule)
                reasons.append(f"Rule '{rule.name}' matched: {rule.condition}")
        
        # Determine base severity
        if matching_rules:
            # Use highest severity
            base_severity = max(matching_rules, key=lambda r: self.SEVERITY_SCORES[r.severity]).severity
            base_score = max(self.SEVERITY_SCORES[r.severity] for r in matching_rules)
        else:
            base_severity = SeverityLevel.INFO
            base_score = 10
        
        # Adjust for device criticality
        criticality = device_criticality or self.device_criticality.get(device_id, 5)
        criticality_boost = (criticality - 5) * 3  # -15 to +15
        
        # Calculate final score
        final_score = min(100, base_score + criticality_boost)
        
        # Determine final severity level
        final_severity = self._score_to_severity(final_score)
        
        # Determine if escalated
        escalated = any(r.auto_escalate for r in matching_rules)
        
        # Collect notification channels
        channels = set()
        sla = None
        for rule in matching_rules:
            if rule.channels:
                channels.update(rule.channels)
            if rule.sla_minutes and (sla is None or rule.sla_minutes < sla):
                sla = rule.sla_minutes
        
        return SeverityResult(
            level=final_severity,
            score=final_score,
            reasons=reasons,
            escalated=escalated,
            notification_channels=list(channels) if channels else ["telegram"],
            sla_minutes=sla
        )
    
    def _evaluate_condition(self, condition: str, metrics: Dict[str, float]) -> bool:
        """Evaluate a condition string against metrics."""
        try:
            # Simple condition parser
            # Supports: metric > value, metric < value, metric == value, metric >= value, metric <= value
            
            condition = condition.strip()
            
            # Handle == false/true
            if " == false" in condition:
                metric = condition.split(" == false")[0].strip()
                return not metrics.get(metric, True)
            elif " == true" in condition:
                metric = condition.split(" == true")[0].strip()
                return metrics.get(metric, False)
            
            # Parse comparison operators
            for op in [">=", "<=", ">", "<", "=="]:
                if op in condition:
                    parts = condition.split(op)
                    if len(parts) == 2:
                        metric = parts[0].strip()
                        value = float(parts[1].strip())
                        metric_value = metrics.get(metric, 0)
                        
                        if op == ">=":
                            return metric_value >= value
                        elif op == "<=":
                            return metric_value <= value
                        elif op == ">":
                            return metric_value > value
                        elif op == "<":
                            return metric_value < value
                        elif op == "==":
                            return metric_value == value
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to evaluate condition '{condition}': {e}")
            return False
    
    def _score_to_severity(self, score: int) -> SeverityLevel:
        """Convert score to severity level."""
        if score >= 95:
            return SeverityLevel.EMERGENCY
        elif score >= 80:
            return SeverityLevel.CRITICAL
        elif score >= 65:
            return SeverityLevel.HIGH
        elif score >= 40:
            return SeverityLevel.MEDIUM
        elif score >= 20:
            return SeverityLevel.LOW
        else:
            return SeverityLevel.INFO
    
    def add_custom_rule(
        self,
        name: str,
        condition: str,
        severity: str,
        weight: int = 30,
        auto_escalate: bool = False,
        channels: Optional[List[str]] = None,
        sla_minutes: Optional[int] = None
    ) -> None:
        """Add a custom severity rule."""
        rule = SeverityRule(
            name=name,
            condition=condition,
            severity=SeverityLevel(severity),
            weight=weight,
            auto_escalate=auto_escalate,
            channels=channels or ["telegram"],
            sla_minutes=sla_minutes
        )
        self.rules.append(rule)
        logger.info(f"Added custom severity rule: {name}")
    
    def set_device_criticality(self, device_id: str, level: int) -> None:
        """Set criticality level for a device (1-10)."""
        self.device_criticality[device_id] = max(1, min(10, level))
    
    def should_page_on_call(
        self,
        severity: SeverityResult,
        business_hours: bool = True
    ) -> bool:
        """Determine if on-call should be paged."""
        if severity.level in (SeverityLevel.EMERGENCY, SeverityLevel.CRITICAL):
            return True
        
        if severity.level == SeverityLevel.HIGH and not business_hours:
            return True
        
        return False
    
    def get_severity_color(self, level: SeverityLevel) -> str:
        """Get display color for severity level."""
        colors = {
            SeverityLevel.INFO: "blue",
            SeverityLevel.LOW: "green",
            SeverityLevel.MEDIUM: "yellow",
            SeverityLevel.HIGH: "orange",
            SeverityLevel.CRITICAL: "red",
            SeverityLevel.EMERGENCY: "purple",
        }
        return colors.get(level, "white")
