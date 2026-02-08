"""
TXT Report Exporter

Generates plain text reports for simple viewing and sharing.
Supports formatting, alignment, and basic styling.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TXTReporter:
    """
    Plain text report generator.
    
    Features:
    - Simple table formatting
    - ASCII borders
    - Summary sections
    - Append mode for logs
    """
    
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_device_report(
        self,
        devices: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> str:
        """
        Generate device status report as text.
        
        Args:
            devices: List of device dicts
            filename: Output filename
        
        Returns:
            Path to generated file
        """
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("DEVICE STATUS REPORT".center(80))
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(80))
        lines.append("=" * 80)
        lines.append("")
        
        # Summary
        total = len(devices)
        healthy = sum(1 for d in devices if d.get("status") == "healthy")
        warning = sum(1 for d in devices if d.get("status") == "warning")
        critical = sum(1 for d in devices if d.get("status") == "critical")
        
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"  Total Devices:    {total}")
        lines.append(f"  Healthy:          {healthy}")
        lines.append(f"  Warning:          {warning}")
        lines.append(f"  Critical:         {critical}")
        lines.append("")
        
        # Device details
        lines.append("DEVICE DETAILS")
        lines.append("-" * 80)
        lines.append(f"{'Device ID':<20} {'Status':<10} {'Health':<8} {'CPU%':<6} {'MEM%':<6} {'Last Seen'}")
        lines.append("-" * 80)
        
        for device in devices:
            device_id = device.get("device_id", "N/A")[:18]
            status = device.get("status", "unknown")[:8]
            health = device.get("health_score", 0)
            cpu = device.get("cpu_usage", 0)
            mem = device.get("memory_usage", 0)
            last_seen = device.get("last_seen", "N/A")
            
            lines.append(f"{device_id:<20} {status:<10} {health:>6.1f}  {cpu:>4.1f}  {mem:>4.1f}  {last_seen}")
        
        lines.append("-" * 80)
        lines.append("")
        
        # Critical devices section
        critical_devices = [d for d in devices if d.get("status") == "critical"]
        if critical_devices:
            lines.append("CRITICAL DEVICES - IMMEDIATE ATTENTION REQUIRED")
            lines.append("-" * 80)
            for device in critical_devices:
                lines.append(f"  • {device.get('device_id')}: {device.get('alerts', 'No details')}")
            lines.append("")
        
        lines.append("=" * 80)
        lines.append("End of Report".center(80))
        lines.append("=" * 80)
        
        # Write to file
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"device_report_{timestamp}.txt"
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"TXT report saved: {filepath}")
        return str(filepath)
    
    def generate_alert_report(
        self,
        alerts: List[Dict[str, Any]],
        filename: Optional[str] = None
    ) -> str:
        """Generate alert report as text."""
        lines = []
        
        lines.append("=" * 80)
        lines.append("ALERT REPORT".center(80))
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(80))
        lines.append("=" * 80)
        lines.append("")
        
        lines.append(f"Total Alerts: {len(alerts)}")
        lines.append("")
        
        # Group by severity
        by_severity = {}
        for alert in alerts:
            sev = alert.get("severity", "unknown")
            by_severity.setdefault(sev, []).append(alert)
        
        for severity in ["emergency", "critical", "high", "medium", "low", "info"]:
            if severity in by_severity:
                lines.append(f"{severity.upper()} ALERTS ({len(by_severity[severity])})")
                lines.append("-" * 80)
                
                for alert in by_severity[severity]:
                    lines.append(f"  Time:     {alert.get('timestamp', 'N/A')}")
                    lines.append(f"  Device:   {alert.get('device_id', 'N/A')}")
                    lines.append(f"  Variable: {alert.get('variable', 'N/A')}")
                    lines.append(f"  Message:  {alert.get('message', 'N/A')}")
                    lines.append("")
        
        lines.append("=" * 80)
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"alert_report_{timestamp}.txt"
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return str(filepath)
    
    def append_log_entry(self, entry: str, filename: str = "noc.log") -> str:
        """Append entry to log file."""
        filepath = self.output_dir / filename
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {entry}\n")
        
        return str(filepath)
