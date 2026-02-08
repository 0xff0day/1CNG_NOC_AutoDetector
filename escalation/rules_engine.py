"""
Escalation Rules Engine

Manages alert escalation policies and procedures.
Defines when and how alerts should be escalated.
"""

from __future__ import annotations

import time
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EscalationAction(Enum):
    """Escalation action types."""
    NOTIFY_MANAGER = "notify_manager"
    PAGE_ON_CALL = "page_on_call"
    CREATE_TICKET = "create_ticket"
    EXECUTE_SCRIPT = "execute_script"
    UPDATE_PRIORITY = "update_priority"


@dataclass
class EscalationRule:
    """Single escalation rule."""
    name: str
    condition: str  # time_based, ack_timeout, severity_change
    delay_minutes: int
    action: EscalationAction
    target: str  # who to escalate to
    repeat_count: int = 1
    repeat_interval: int = 30
    enabled: bool = True


class EscalationEngine:
    """
    Manages alert escalation workflows.
    
    Escalation triggers:
    - Time-based (no acknowledgment)
    - Severity change
    - Correlated failures
    - Manual escalation
    """
    
    def __init__(self):
        self.rules: List[EscalationRule] = []
        self._pending_escalations: Dict[str, Dict] = {}  # alert_id -> escalation info
        self._escalation_history: List[Dict] = []
        self._callbacks: Dict[EscalationAction, Callable] = {}
    
    def add_rule(self, rule: EscalationRule) -> None:
        """Add escalation rule."""
        self.rules.append(rule)
        logger.info(f"Added escalation rule: {rule.name}")
    
    def register_callback(
        self,
        action: EscalationAction,
        callback: Callable
    ) -> None:
        """Register callback for escalation action."""
        self._callbacks[action] = callback
    
    def schedule_escalation(
        self,
        alert_id: str,
        severity: str,
        created_at: float
    ) -> List[Dict]:
        """
        Schedule escalations for an alert.
        
        Args:
            alert_id: Alert identifier
            severity: Current severity
            created_at: Alert creation timestamp
        
        Returns:
            List of scheduled escalations
        """
        scheduled = []
        current_time = time.time()
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # Check if rule applies to this severity
            if not self._severity_matches(rule, severity):
                continue
            
            # Calculate escalation time
            escalation_time = created_at + (rule.delay_minutes * 60)
            
            escalation_info = {
                "alert_id": alert_id,
                "rule_name": rule.name,
                "action": rule.action.value,
                "target": rule.target,
                "scheduled_time": escalation_time,
                "executed": False,
                "repeat_count": 0,
                "max_repeats": rule.repeat_count,
            }
            
            self._pending_escalations[f"{alert_id}:{rule.name}"] = escalation_info
            scheduled.append(escalation_info)
        
        return scheduled
    
    def _severity_matches(self, rule: EscalationRule, severity: str) -> bool:
        """Check if rule applies to severity level."""
        # Rules with higher delays typically apply to higher severities
        severity_priority = {
            "info": 1, "low": 2, "medium": 3,
            "high": 4, "critical": 5, "emergency": 6
        }
        
        alert_priority = severity_priority.get(severity.lower(), 3)
        
        # Critical alerts escalate faster
        if rule.delay_minutes <= 5:
            return alert_priority >= 5
        elif rule.delay_minutes <= 15:
            return alert_priority >= 4
        elif rule.delay_minutes <= 60:
            return alert_priority >= 3
        
        return True
    
    def check_and_execute_escalations(self) -> List[Dict]:
        """
        Check for pending escalations and execute if due.
        
        Returns:
            List of executed escalations
        """
        executed = []
        current_time = time.time()
        
        for key, escalation in list(self._pending_escalations.items()):
            if escalation["executed"]:
                continue
            
            if current_time >= escalation["scheduled_time"]:
                # Execute escalation
                result = self._execute_escalation(escalation)
                
                if result:
                    executed.append(escalation)
                    
                    # Handle repeats
                    if escalation["repeat_count"] < escalation["max_repeats"]:
                        escalation["repeat_count"] += 1
                        escalation["scheduled_time"] = current_time + (30 * 60)  # 30 min repeat
                    else:
                        escalation["executed"] = True
                else:
                    escalation["executed"] = True
        
        return executed
    
    def _execute_escalation(self, escalation: Dict) -> bool:
        """Execute single escalation."""
        action_str = escalation["action"]
        
        try:
            action = EscalationAction(action_str)
        except ValueError:
            logger.error(f"Unknown escalation action: {action_str}")
            return False
        
        callback = self._callbacks.get(action)
        if callback:
            try:
                callback(
                    alert_id=escalation["alert_id"],
                    target=escalation["target"]
                )
                
                self._escalation_history.append({
                    **escalation,
                    "executed_at": time.time()
                })
                
                logger.info(f"Executed escalation: {escalation['rule_name']} for {escalation['alert_id']}")
                return True
                
            except Exception as e:
                logger.error(f"Escalation callback failed: {e}")
                return False
        else:
            logger.warning(f"No callback registered for action: {action}")
            return False
    
    def cancel_escalation(self, alert_id: str) -> bool:
        """
        Cancel all pending escalations for an alert.
        Called when alert is acknowledged.
        """
        cancelled = False
        
        for key in list(self._pending_escalations.keys()):
            if key.startswith(f"{alert_id}:"):
                del self._pending_escalations[key]
                cancelled = True
        
        if cancelled:
            logger.info(f"Cancelled escalations for alert: {alert_id}")
        
        return cancelled
    
    def manual_escalate(
        self,
        alert_id: str,
        level: int = 2
    ) -> bool:
        """
        Manually escalate an alert.
        
        Args:
            alert_id: Alert to escalate
            level: Escalation level (2=L2, 3=L3, etc.)
        
        Returns:
            True if escalated
        """
        targets = {
            2: "level2_support",
            3: "level3_support",
            4: "management"
        }
        
        target = targets.get(level, "management")
        
        escalation = {
            "alert_id": alert_id,
            "rule_name": f"manual_escalate_{level}",
            "action": EscalationAction.NOTIFY_MANAGER.value,
            "target": target,
            "scheduled_time": time.time(),
            "executed": False,
            "repeat_count": 0,
            "max_repeats": 1,
        }
        
        return self._execute_escalation(escalation)
    
    def create_default_rules(self) -> None:
        """Create default escalation rules."""
        defaults = [
            EscalationRule(
                name="ack_timeout_15min",
                condition="ack_timeout",
                delay_minutes=15,
                action=EscalationAction.NOTIFY_MANAGER,
                target="team_lead",
                repeat_count=1
            ),
            EscalationRule(
                name="ack_timeout_30min",
                condition="ack_timeout",
                delay_minutes=30,
                action=EscalationAction.PAGE_ON_CALL,
                target="on_call_engineer",
                repeat_count=2,
                repeat_interval=30
            ),
            EscalationRule(
                name="critical_immediate",
                condition="severity_change",
                delay_minutes=5,
                action=EscalationAction.PAGE_ON_CALL,
                target="on_call_engineer"
            ),
            EscalationRule(
                name="emergency_immediate",
                condition="severity_change",
                delay_minutes=0,
                action=EscalationAction.NOTIFY_MANAGER,
                target="noc_manager"
            ),
        ]
        
        for rule in defaults:
            self.add_rule(rule)
    
    def get_pending_escalations(self) -> List[Dict]:
        """Get list of pending escalations."""
        return [
            e for e in self._pending_escalations.values()
            if not e["executed"]
        ]
    
    def get_escalation_history(
        self,
        alert_id: Optional[str] = None
    ) -> List[Dict]:
        """Get escalation history."""
        if alert_id:
            return [
                h for h in self._escalation_history
                if h["alert_id"] == alert_id
            ]
        return self._escalation_history
