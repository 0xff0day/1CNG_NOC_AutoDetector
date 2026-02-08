"""
Category Report Splitter

Splits reports by category, severity, or device group.
Generates separate files for different audiences.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ReportSplitter:
    """
    Splits monitoring reports into category-specific files.
    
    Categories:
    - By severity (critical, warning, info)
    - By device type (routers, switches, servers)
    - By location/datacenter
    - By organizational group
    """
    
    def __init__(self, output_dir: str = "reports/split"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def split_by_severity(
        self,
        alerts: List[Dict[str, Any]],
        base_filename: str = "alerts"
    ) -> Dict[str, str]:
        """
        Split alerts by severity level.
        
        Returns:
            Dict mapping severity to filepath
        """
        result = {}
        
        # Group by severity
        by_severity = {}
        for alert in alerts:
            sev = alert.get("severity", "unknown")
            by_severity.setdefault(sev, []).append(alert)
        
        # Export each severity group
        for severity, items in by_severity.items():
            if items:
                filename = f"{base_filename}_{severity}.json"
                filepath = self._export_json(items, filename)
                result[severity] = filepath
        
        return result
    
    def split_by_device_type(
        self,
        devices: List[Dict[str, Any]],
        base_filename: str = "devices"
    ) -> Dict[str, str]:
        """
        Split devices by type.
        
        Returns:
            Dict mapping device type to filepath
        """
        result = {}
        
        by_type = {}
        for device in devices:
            dev_type = device.get("device_type", "unknown")
            by_type.setdefault(dev_type, []).append(device)
        
        for dev_type, items in by_type.items():
            if items:
                filename = f"{base_filename}_{dev_type}.json"
                filepath = self._export_json(items, filename)
                result[dev_type] = filepath
        
        return result
    
    def split_by_group(
        self,
        items: List[Dict[str, Any]],
        group_key: str,
        base_filename: str
    ) -> Dict[str, str]:
        """
        Generic split by any field.
        
        Args:
            items: List of items to split
            group_key: Field to group by
            base_filename: Base name for output files
        
        Returns:
            Dict mapping group value to filepath
        """
        result = {}
        
        by_group = {}
        for item in items:
            group = item.get(group_key, "unknown")
            by_group.setdefault(group, []).append(item)
        
        for group, group_items in by_group.items():
            if group_items:
                safe_group = str(group).replace(" ", "_").lower()
                filename = f"{base_filename}_{safe_group}.json"
                filepath = self._export_json(group_items, filename)
                result[group] = filepath
        
        return result
    
    def split_by_custom_filter(
        self,
        items: List[Dict[str, Any]],
        filters: Dict[str, Callable],
        base_filename: str
    ) -> Dict[str, str]:
        """
        Split using custom filter functions.
        
        Args:
            items: Items to split
            filters: Dict of {name: filter_func}
            base_filename: Base filename
        
        Returns:
            Dict mapping filter name to filepath
        """
        result = {}
        
        for name, filter_func in filters.items():
            filtered = [item for item in items if filter_func(item)]
            if filtered:
                filename = f"{base_filename}_{name}.json"
                filepath = self._export_json(filtered, filename)
                result[name] = filepath
        
        return result
    
    def split_for_escalation(
        self,
        alerts: List[Dict[str, Any]],
        escalation_levels: List[str] = None
    ) -> Dict[str, str]:
        """
        Split alerts by escalation level.
        
        Level 1: Team-level issues
        Level 2: Management notification
        Level 3: Executive summary
        """
        if escalation_levels is None:
            escalation_levels = ["level1_team", "level2_mgmt", "level3_exec"]
        
        filters = {
            "level1_team": lambda a: a.get("severity") in ["high", "critical", "emergency"],
            "level2_mgmt": lambda a: a.get("severity") in ["critical", "emergency"] or a.get("business_impact"),
            "level3_exec": lambda a: a.get("severity") == "emergency" or a.get("customer_facing", False),
        }
        
        return self.split_by_custom_filter(
            alerts,
            {k: filters[k] for k in escalation_levels if k in filters},
            "escalation"
        )
    
    def create_executive_summary(
        self,
        devices: List[Dict],
        alerts: List[Dict],
        filename: str = "executive_summary.json"
    ) -> str:
        """
        Create executive summary report.
        
        High-level metrics only, no technical details.
        """
        summary = {
            "report_type": "executive_summary",
            "total_devices": len(devices),
            "healthy_percentage": sum(1 for d in devices if d.get("status") == "healthy") / len(devices) * 100 if devices else 0,
            "critical_issues": sum(1 for d in devices if d.get("status") == "critical"),
            "open_alerts": len(alerts),
            "requires_attention": any(d.get("status") == "critical" for d in devices),
        }
        
        return self._export_json(summary, filename)
    
    def create_technical_report(
        self,
        devices: List[Dict],
        alerts: List[Dict],
        filename: str = "technical_details.json"
    ) -> str:
        """
        Create detailed technical report.
        
        Full metrics, logs, and diagnostic information.
        """
        report = {
            "report_type": "technical",
            "devices": devices,
            "active_alerts": alerts,
            "diagnostics": self._generate_diagnostics(devices),
        }
        
        return self._export_json(report, filename)
    
    def _generate_diagnostics(self, devices: List[Dict]) -> Dict:
        """Generate diagnostic summary."""
        return {
            "devices_requiring_immediate_attention": [
                d.get("device_id") for d in devices if d.get("status") == "critical"
            ],
            "common_issues": self._find_common_patterns(devices),
            "recommendations": self._generate_recommendations(devices),
        }
    
    def _find_common_patterns(self, devices: List[Dict]) -> List[str]:
        """Find common issues across devices."""
        patterns = []
        
        # Check for high CPU across multiple devices
        high_cpu = sum(1 for d in devices if d.get("cpu_usage", 0) > 80)
        if high_cpu > 1:
            patterns.append(f"High CPU usage on {high_cpu} devices")
        
        # Check for memory issues
        high_mem = sum(1 for d in devices if d.get("memory_usage", 0) > 85)
        if high_mem > 1:
            patterns.append(f"High memory usage on {high_mem} devices")
        
        return patterns
    
    def _generate_recommendations(self, devices: List[Dict]) -> List[str]:
        """Generate recommendations based on issues."""
        recs = []
        
        critical_count = sum(1 for d in devices if d.get("status") == "critical")
        if critical_count > 0:
            recs.append(f"Immediate: Address {critical_count} critical devices")
        
        warning_count = sum(1 for d in devices if d.get("status") == "warning")
        if warning_count > 5:
            recs.append(f"Schedule maintenance for {warning_count} warning-state devices")
        
        return recs
    
    def _export_json(self, data: Any, filename: str) -> str:
        """Export data to JSON file."""
        import json
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        return str(filepath)
