"""
Summary Command Module

Generates system summary and statistics for CLI display.
"""

from __future__ import annotations

from typing import Dict, List, Any
from datetime import datetime


class SummaryCommand:
    """Handles 'nocctl summary' command."""
    
    def __init__(self, device_db, alert_manager, metric_store):
        self.device_db = device_db
        self.alert_manager = alert_manager
        self.metric_store = metric_store
    
    def execute(self, format: str = "text") -> str:
        """
        Execute summary command.
        
        Args:
            format: Output format (text, json, yaml)
        
        Returns:
            Formatted summary
        """
        summary = self._gather_summary()
        
        if format == "json":
            import json
            return json.dumps(summary, indent=2)
        elif format == "yaml":
            import yaml
            return yaml.dump(summary, default_flow_style=False)
        else:
            return self._format_text(summary)
    
    def _gather_summary(self) -> Dict[str, Any]:
        """Gather summary data."""
        devices = self.device_db.get_all()
        alerts = self.alert_manager.get_active()
        
        return {
            "generated_at": datetime.now().isoformat(),
            "devices": {
                "total": len(devices),
                "online": sum(1 for d in devices if d.get("reachable")),
                "offline": sum(1 for d in devices if not d.get("reachable")),
                "by_type": self._count_by_type(devices),
            },
            "alerts": {
                "total_active": len(alerts),
                "by_severity": self._count_by_severity(alerts),
                "unacknowledged": sum(1 for a in alerts if not a.get("acknowledged")),
            },
            "health": {
                "average_score": self._calculate_avg_health(devices),
                "needs_attention": [
                    d.get("device_id") for d in devices
                    if d.get("health_score", 100) < 70
                ],
            },
            "system": {
                "storage_used_mb": self.metric_store.get_storage_stats().get("db_size_mb", 0),
                "last_poll": self._get_last_poll_time(),
            }
        }
    
    def _count_by_type(self, devices: List[Dict]) -> Dict[str, int]:
        """Count devices by type."""
        counts = {}
        for d in devices:
            dev_type = d.get("device_type", "unknown")
            counts[dev_type] = counts.get(dev_type, 0) + 1
        return counts
    
    def _count_by_severity(self, alerts: List[Dict]) -> Dict[str, int]:
        """Count alerts by severity."""
        counts = {}
        for a in alerts:
            sev = a.get("severity", "unknown")
            counts[sev] = counts.get(sev, 0) + 1
        return counts
    
    def _calculate_avg_health(self, devices: List[Dict]) -> float:
        """Calculate average health score."""
        if not devices:
            return 100.0
        scores = [d.get("health_score", 100) for d in devices]
        return sum(scores) / len(scores)
    
    def _get_last_poll_time(self) -> str:
        """Get timestamp of last polling cycle."""
        return "Just now"  # Would come from scheduler
    
    def _format_text(self, summary: Dict) -> str:
        """Format summary as text."""
        lines = [
            "=" * 60,
            "NOC SYSTEM SUMMARY",
            "=" * 60,
            "",
            f"Generated: {summary['generated_at']}",
            "",
            "DEVICES",
            f"  Total: {summary['devices']['total']}",
            f"  Online: {summary['devices']['online']}",
            f"  Offline: {summary['devices']['offline']}",
            "",
            "ALERTS",
            f"  Active: {summary['alerts']['total_active']}",
            f"  Unacknowledged: {summary['alerts']['unacknowledged']}",
            "",
            "HEALTH",
            f"  Average Score: {summary['health']['average_score']:.1f}/100",
            f"  Need Attention: {len(summary['health']['needs_attention'])}",
            "",
            "STORAGE",
            f"  Database Size: {summary['system']['storage_used_mb']:.1f} MB",
            "",
            "=" * 60,
        ]
        return "\n".join(lines)
