"""
Health Dashboard CLI

Command-line health dashboard visualization.
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
import shutil


class HealthDashboard:
    """
    CLI-based health dashboard.
    Displays device health in a visual format.
    """
    
    def __init__(self):
        self.term_width = shutil.get_terminal_size().columns
    
    def render(self, devices: List[Dict[str, Any]]) -> str:
        """
        Render health dashboard.
        
        Args:
            devices: List of device health data
        
        Returns:
            Formatted dashboard string
        """
        lines = []
        
        # Header
        lines.append("=" * self.term_width)
        lines.append("NOC HEALTH DASHBOARD".center(self.term_width))
        lines.append("=" * self.term_width)
        lines.append("")
        
        # Summary
        total = len(devices)
        healthy = sum(1 for d in devices if d.get("status") == "healthy")
        warning = sum(1 for d in devices if d.get("status") == "warning")
        critical = sum(1 for d in devices if d.get("status") == "critical")
        
        lines.append(f"Total Devices: {total} | Healthy: {healthy} | Warning: {warning} | Critical: {critical}")
        lines.append("")
        
        # Health bars
        if total > 0:
            healthy_pct = healthy / total * 100
            warning_pct = warning / total * 100
            critical_pct = critical / total * 100
            
            bar_width = min(50, self.term_width - 20)
            
            healthy_len = int(bar_width * healthy_pct / 100)
            warning_len = int(bar_width * warning_pct / 100)
            critical_len = int(bar_width * critical_pct / 100)
            
            health_bar = (
                "🟢" * healthy_len +
                "🟡" * warning_len +
                "🔴" * critical_len
            )
            
            lines.append(f"Health Distribution: [{health_bar}]")
            lines.append("")
        
        # Device list
        lines.append(f"{'Device':<20} {'Status':<10} {'Health':<8} {'CPU':<6} {'Mem':<6} {'Issues'}")
        lines.append("-" * self.term_width)
        
        # Sort by severity
        sorted_devices = sorted(
            devices,
            key=lambda d: {"critical": 0, "warning": 1, "healthy": 2}.get(d.get("status"), 3)
        )
        
        for device in sorted_devices[:20]:  # Show top 20
            device_id = device.get("device_id", "unknown")[:18]
            status = device.get("status", "unknown")
            health = device.get("health_score", 0)
            cpu = device.get("cpu_usage", 0)
            mem = device.get("memory_usage", 0)
            issues = device.get("issue_count", 0)
            
            # Color coding
            status_icon = {
                "healthy": "🟢",
                "warning": "🟡",
                "critical": "🔴"
            }.get(status, "⚪")
            
            lines.append(
                f"{device_id:<20} {status_icon} {status:<8} {health:>6.1f}  {cpu:>4.1f}  {mem:>4.1f}  {issues}"
            )
        
        if len(sorted_devices) > 20:
            lines.append(f"... and {len(sorted_devices) - 20} more devices")
        
        lines.append("")
        lines.append("=" * self.term_width)
        
        return "\n".join(lines)
    
    def render_compact(self, devices: List[Dict[str, Any]]) -> str:
        """Render compact dashboard view."""
        total = len(devices)
        healthy = sum(1 for d in devices if d.get("status") == "healthy")
        warning = sum(1 for d in devices if d.get("status") == "warning")
        critical = sum(1 for d in devices if d.get("status") == "critical")
        
        return (
            f"Devices: {total} | 🟢{healthy} 🟡{warning} 🔴{critical} | "
            f"Health: {healthy/total*100:.1f}%" if total > 0 else "No devices"
        )
