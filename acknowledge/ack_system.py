"""
Alert Acknowledge System

Manages alert acknowledgment workflow.
Tracks who acknowledged, when, and notes.
"""

from __future__ import annotations

import time
import uuid
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AckStatus(Enum):
    """Acknowledgment status."""
    UNACKNOWLEDGED = "unacknowledged"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    SUPPRESSED = "suppressed"


@dataclass
class Acknowledgment:
    """Alert acknowledgment record."""
    alert_id: str
    acknowledged_by: str
    acknowledged_at: float
    notes: str = ""
    status: AckStatus = AckStatus.ACKNOWLEDGED
    resolution_notes: str = ""
    resolved_at: Optional[float] = None
    escalated_to: Optional[str] = None


class AlertAcknowledgeSystem:
    """
    Manages alert acknowledgment workflow.
    
    Features:
    - Acknowledge with notes
    - Bulk acknowledge
    - Resolve alerts
    - Escalate instead of acknowledge
    - History tracking
    """
    
    def __init__(self):
        self._acks: Dict[str, Acknowledgment] = {}
        self._active_alerts: Dict[str, Dict] = {}
        self._ack_history: List[Acknowledgment] = []
    
    def acknowledge(
        self,
        alert_id: str,
        acknowledged_by: str,
        notes: str = "",
        alert_data: Optional[Dict] = None
    ) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert to acknowledge
            acknowledged_by: Person acknowledging
            notes: Acknowledgment notes
            alert_data: Original alert data for history
        
        Returns:
            True if acknowledged
        """
        if alert_id in self._acks:
            logger.warning(f"Alert {alert_id} already acknowledged")
            return False
        
        ack = Acknowledgment(
            alert_id=alert_id,
            acknowledged_by=acknowledged_by,
            acknowledged_at=time.time(),
            notes=notes,
            status=AckStatus.ACKNOWLEDGED
        )
        
        self._acks[alert_id] = ack
        self._ack_history.append(ack)
        
        # Store alert data if provided
        if alert_data:
            self._active_alerts[alert_id] = alert_data
        
        logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
        return True
    
    def bulk_acknowledge(
        self,
        alert_ids: List[str],
        acknowledged_by: str,
        notes: str = ""
    ) -> Dict[str, bool]:
        """
        Acknowledge multiple alerts at once.
        
        Returns:
            Dict mapping alert_id to success
        """
        results = {}
        for alert_id in alert_ids:
            results[alert_id] = self.acknowledge(alert_id, acknowledged_by, notes)
        
        return results
    
    def resolve(
        self,
        alert_id: str,
        resolved_by: str,
        resolution_notes: str = ""
    ) -> bool:
        """
        Mark an acknowledged alert as resolved.
        
        Args:
            alert_id: Alert to resolve
            resolved_by: Person resolving
            resolution_notes: How the issue was resolved
        
        Returns:
            True if resolved
        """
        if alert_id not in self._acks:
            logger.warning(f"Cannot resolve unacknowledged alert {alert_id}")
            return False
        
        ack = self._acks[alert_id]
        ack.status = AckStatus.RESOLVED
        ack.resolved_at = time.time()
        ack.resolution_notes = resolution_notes
        
        # Remove from active
        if alert_id in self._active_alerts:
            del self._active_alerts[alert_id]
        
        # Keep in acks but mark resolved
        logger.info(f"Alert {alert_id} resolved by {resolved_by}")
        return True
    
    def escalate_instead(
        self,
        alert_id: str,
        escalated_by: str,
        escalate_to: str,
        reason: str = ""
    ) -> bool:
        """
        Escalate instead of acknowledging.
        
        Args:
            alert_id: Alert to escalate
            escalated_by: Person escalating
            escalate_to: Who to escalate to
            reason: Escalation reason
        
        Returns:
            True if escalated
        """
        ack = Acknowledgment(
            alert_id=alert_id,
            acknowledged_by=escalated_by,
            acknowledged_at=time.time(),
            notes=f"Escalated to {escalate_to}: {reason}",
            status=AckStatus.ESCALATED,
            escalated_to=escalate_to
        )
        
        self._acks[alert_id] = ack
        self._ack_history.append(ack)
        
        logger.info(f"Alert {alert_id} escalated by {escalated_by} to {escalate_to}")
        return True
    
    def unacknowledge(self, alert_id: str, reason: str = "") -> bool:
        """
        Remove acknowledgment (reopen alert).
        
        Args:
            alert_id: Alert to unacknowledge
            reason: Reason for unacknowledging
        
        Returns:
            True if unacknowledged
        """
        if alert_id not in self._acks:
            return False
        
        del self._acks[alert_id]
        logger.info(f"Alert {alert_id} unacknowledged: {reason}")
        return True
    
    def get_ack_info(self, alert_id: str) -> Optional[Dict]:
        """Get acknowledgment information for an alert."""
        if alert_id not in self._acks:
            return None
        
        ack = self._acks[alert_id]
        return {
            "alert_id": ack.alert_id,
            "acknowledged_by": ack.acknowledged_by,
            "acknowledged_at": ack.acknowledged_at,
            "acknowledged_at_formatted": datetime.fromtimestamp(ack.acknowledged_at).isoformat(),
            "notes": ack.notes,
            "status": ack.status.value,
            "resolution_notes": ack.resolution_notes,
            "resolved_at": ack.resolved_at,
            "escalated_to": ack.escalated_to,
        }
    
    def is_acknowledged(self, alert_id: str) -> bool:
        """Check if alert is acknowledged."""
        return alert_id in self._acks
    
    def get_unacknowledged_alerts(self) -> List[str]:
        """Get list of unacknowledged alert IDs."""
        # Returns all active alerts that aren't acknowledged
        all_active = set(self._active_alerts.keys())
        acknowledged = set(self._acks.keys())
        return list(all_active - acknowledged)
    
    def get_acknowledged_alerts(
        self,
        status_filter: Optional[AckStatus] = None
    ) -> List[str]:
        """Get acknowledged alert IDs, optionally filtered by status."""
        if status_filter:
            return [
                aid for aid, ack in self._acks.items()
                if ack.status == status_filter
            ]
        return list(self._acks.keys())
    
    def get_ack_stats(self) -> Dict[str, Any]:
        """Get acknowledgment statistics."""
        total_acks = len(self._acks)
        by_status = {}
        
        for ack in self._acks.values():
            status = ack.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        # Calculate average time to acknowledge
        if self._ack_history:
            times_to_ack = []
            for ack in self._ack_history:
                # This would need alert creation time
                # Placeholder calculation
                pass
        
        return {
            "total_acknowledged": total_acks,
            "by_status": by_status,
            "unacknowledged_count": len(self.get_unacknowledged_alerts()),
            "total_history": len(self._ack_history),
        }
    
    def get_user_ack_history(
        self,
        user: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get acknowledgment history for a user."""
        user_acks = [
            self._ack_to_dict(ack)
            for ack in reversed(self._ack_history)
            if ack.acknowledged_by == user
        ]
        return user_acks[:limit]
    
    def _ack_to_dict(self, ack: Acknowledgment) -> Dict:
        """Convert acknowledgment to dict."""
        return {
            "alert_id": ack.alert_id,
            "acknowledged_by": ack.acknowledged_by,
            "acknowledged_at": ack.acknowledged_at,
            "notes": ack.notes,
            "status": ack.status.value,
            "resolution_notes": ack.resolution_notes,
            "resolved_at": ack.resolved_at,
        }
    
    def export_ack_history(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict]:
        """Export acknowledgment history for time range."""
        result = []
        
        for ack in self._ack_history:
            if start_time and ack.acknowledged_at < start_time:
                continue
            if end_time and ack.acknowledged_at > end_time:
                continue
            
            result.append(self._ack_to_dict(ack))
        
        return result
