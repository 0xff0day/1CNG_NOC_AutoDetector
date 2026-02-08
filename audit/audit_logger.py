from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AuditLogger:
    """Comprehensive audit logging for compliance and security."""
    
    AUDIT_EVENTS = {
        # Authentication events
        "auth.login": {"severity": "info", "category": "authentication"},
        "auth.logout": {"severity": "info", "category": "authentication"},
        "auth.failed": {"severity": "warning", "category": "authentication"},
        "auth.token_refresh": {"severity": "info", "category": "authentication"},
        
        # Authorization events
        "access.denied": {"severity": "warning", "category": "authorization"},
        "access.granted": {"severity": "info", "category": "authorization"},
        "permission.changed": {"severity": "info", "category": "authorization"},
        
        # Device management
        "device.created": {"severity": "info", "category": "device"},
        "device.updated": {"severity": "info", "category": "device"},
        "device.deleted": {"severity": "warning", "category": "device"},
        "device.scanned": {"severity": "info", "category": "device"},
        "device.discovered": {"severity": "info", "category": "device"},
        
        # Alert management
        "alert.created": {"severity": "info", "category": "alert"},
        "alert.acknowledged": {"severity": "info", "category": "alert"},
        "alert.resolved": {"severity": "info", "category": "alert"},
        "alert.suppressed": {"severity": "warning", "category": "alert"},
        "alert.escalated": {"severity": "warning", "category": "alert"},
        
        # Configuration changes
        "config.changed": {"severity": "warning", "category": "configuration"},
        "config.migrated": {"severity": "info", "category": "configuration"},
        "config.backup": {"severity": "info", "category": "configuration"},
        "config.restore": {"severity": "warning", "category": "configuration"},
        
        # User management
        "user.created": {"severity": "info", "category": "user"},
        "user.updated": {"severity": "info", "category": "user"},
        "user.deleted": {"severity": "warning", "category": "user"},
        "user.password_changed": {"severity": "info", "category": "user"},
        
        # System events
        "system.startup": {"severity": "info", "category": "system"},
        "system.shutdown": {"severity": "info", "category": "system"},
        "system.error": {"severity": "error", "category": "system"},
        "system.maintenance": {"severity": "info", "category": "system"},
        
        # Plugin events
        "plugin.installed": {"severity": "info", "category": "plugin"},
        "plugin.updated": {"severity": "info", "category": "plugin"},
        "plugin.removed": {"severity": "warning", "category": "plugin"},
        "plugin.validated": {"severity": "info", "category": "plugin"},
    }
    
    def __init__(self, storage=None, tamper_protection: bool = True):
        self.storage = storage
        self.tamper_protection = tamper_protection
        self.event_buffer: List[Dict[str, Any]] = []
        self.buffer_size = 1000
    
    def log(
        self,
        event_type: str,
        actor: str,
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log an audit event."""
        event_def = self.AUDIT_EVENTS.get(event_type, {"severity": "info", "category": "unknown"})
        
        event = {
            "event_id": self._generate_event_id(),
            "event_type": event_type,
            "category": event_def["category"],
            "severity": event_def["severity"],
            "actor": actor,
            "resource": resource,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add integrity hash if tamper protection enabled
        if self.tamper_protection:
            event["integrity_hash"] = self._compute_integrity_hash(event)
        
        # Buffer or write immediately
        self.event_buffer.append(event)
        
        if len(self.event_buffer) >= self.buffer_size:
            self.flush()
        
        return event
    
    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid
        return f"AUDIT-{uuid.uuid4().hex[:16].upper()}"
    
    def _compute_integrity_hash(self, event: Dict[str, Any]) -> str:
        """Compute integrity hash for tamper detection."""
        # Hash everything except the hash itself
        data = {k: v for k, v in event.items() if k != "integrity_hash"}
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:32]
    
    def verify_integrity(self, event: Dict[str, Any]) -> bool:
        """Verify event integrity."""
        if not self.tamper_protection:
            return True
        
        stored_hash = event.get("integrity_hash")
        if not stored_hash:
            return False
        
        computed_hash = self._compute_integrity_hash(event)
        return hmac.compare_digest(stored_hash, computed_hash)
    
    def flush(self):
        """Flush buffered events to storage."""
        if not self.storage or not self.event_buffer:
            return
        
        # Write to storage
        for event in self.event_buffer:
            self.storage.store_audit_event(event)
        
        self.event_buffer = []
    
    def query(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        event_types: Optional[List[str]] = None,
        categories: Optional[List[str]] = None,
        severities: Optional[List[str]] = None,
        actors: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Query audit log."""
        if not self.storage:
            return []
        
        return self.storage.query_audit_events(
            start_time=start_time,
            end_time=end_time,
            event_types=event_types,
            categories=categories,
            severities=severities,
            actors=actors,
            resources=resources,
            limit=limit,
        )
    
    def get_summary(
        self,
        time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """Get audit log summary."""
        from datetime import timedelta
        
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=time_range_hours)
        
        events = self.query(
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            limit=10000
        )
        
        # Calculate statistics
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_actor: Dict[str, int] = {}
        
        for event in events:
            cat = event.get("category", "unknown")
            sev = event.get("severity", "info")
            actor = event.get("actor", "unknown")
            
            by_category[cat] = by_category.get(cat, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            by_actor[actor] = by_actor.get(actor, 0) + 1
        
        return {
            "time_range_hours": time_range_hours,
            "total_events": len(events),
            "by_category": by_category,
            "by_severity": by_severity,
            "top_actors": sorted(by_actor.items(), key=lambda x: x[1], reverse=True)[:10],
            "integrity_verified": all(self.verify_integrity(e) for e in events) if self.tamper_protection else None,
        }
    
    def export(
        self,
        format: str = "json",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> str:
        """Export audit log in various formats."""
        events = self.query(
            start_time=start_time,
            end_time=end_time,
            limit=50000
        )
        
        if format == "json":
            return json.dumps(events, indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=["event_id", "timestamp", "event_type", "category", "severity", "actor", "resource"]
            )
            writer.writeheader()
            
            for event in events:
                writer.writerow({k: event.get(k, "") for k in ["event_id", "timestamp", "event_type", "category", "severity", "actor", "resource"]})
            
            return output.getvalue()
        
        elif format == "syslog":
            lines = []
            for event in events:
                line = (
                    f"<{event['severity']}> {event['timestamp']} "
                    f"noc-audit[{event['event_id']}]: "
                    f"{event['event_type']} actor={event['actor']} "
                    f"resource={event.get('resource', 'none')}"
                )
                lines.append(line)
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unknown format: {format}")


class AuditLogRetention:
    """Manage audit log retention and archival."""
    
    def __init__(self, storage, retention_days: int = 365):
        self.storage = storage
        self.retention_days = retention_days
    
    def archive_old_events(self, archive_before_days: int = 90) -> Dict[str, Any]:
        """Archive events older than specified days."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=archive_before_days)
        
        # Find events to archive
        old_events = self.storage.query_audit_events(
            end_time=cutoff.isoformat(),
            limit=100000
        )
        
        # Archive to file
        archive_path = f"./archive/audit_{cutoff.strftime('%Y%m%d')}.json"
        import os
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        
        with open(archive_path, 'w') as f:
            json.dump(old_events, f)
        
        # Delete from storage
        for event in old_events:
            self.storage.delete_audit_event(event["event_id"])
        
        return {
            "archived_count": len(old_events),
            "archive_path": archive_path,
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "cutoff_date": cutoff.isoformat(),
        }
    
    def purge_expired(self) -> Dict[str, Any]:
        """Delete events older than retention period."""
        from datetime import timedelta
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        
        old_events = self.storage.query_audit_events(
            end_time=cutoff.isoformat(),
            limit=100000
        )
        
        for event in old_events:
            self.storage.delete_audit_event(event["event_id"])
        
        return {
            "purged_count": len(old_events),
            "retention_days": self.retention_days,
            "cutoff_date": cutoff.isoformat(),
            "purged_at": datetime.now(timezone.utc).isoformat(),
        }
