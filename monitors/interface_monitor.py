"""
Interface Error Monitor

Monitors interface errors, discards, and performance metrics.
Detects physical layer issues and performance degradation.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of interface errors."""
    CRC = "crc"
    FRAME = "frame"
    OVERRUN = "overrun"
    IGNORED = "ignored"
    ABORT = "abort"
    GIANTS = "giants"
    RUNTS = "runts"
    COLLISIONS = "collisions"
    INPUT_ERRORS = "input_errors"
    OUTPUT_ERRORS = "output_errors"


@dataclass
class InterfaceStats:
    """Interface statistics."""
    interface: str
    input_errors: int = 0
    output_errors: int = 0
    crc_errors: int = 0
    frame_errors: int = 0
    overrun: int = 0
    ignored: int = 0
    collisions: int = 0
    input_packets: int = 0
    output_packets: int = 0
    error_rate: float = 0.0


@dataclass
class ErrorThreshold:
    """Error threshold configuration."""
    error_type: ErrorType
    warning_threshold: int
    critical_threshold: int
    time_window: int = 300  # 5 minutes


class InterfaceErrorMonitor:
    """
    Monitors interface errors and detects issues.
    
    Tracks:
    - Physical layer errors (CRC, framing)
    - Buffer issues (overruns, ignored)
    - Collision rates
    - Error rate trends
    """
    
    def __init__(self):
        self._stats_history: Dict[str, List[InterfaceStats]] = {}
        self._thresholds: Dict[ErrorType, ErrorThreshold] = {
            ErrorType.CRC: ErrorThreshold(ErrorType.CRC, 10, 100),
            ErrorType.INPUT_ERRORS: ErrorThreshold(ErrorType.INPUT_ERRORS, 50, 500),
            ErrorType.OUTPUT_ERRORS: ErrorThreshold(ErrorType.OUTPUT_ERRORS, 50, 500),
        }
    
    def parse_interface_counters(self, output: str) -> List[InterfaceStats]:
        """
        Parse interface counters from command output.
        
        Supports various vendor formats.
        """
        stats_list = []
        
        # Cisco format
        interface_blocks = re.split(r'\n\n', output)
        
        for block in interface_blocks:
            interface_match = re.search(r'(\S+) is (?:up|down)', block)
            if not interface_match:
                continue
            
            interface = interface_match.group(1)
            stats = InterfaceStats(interface=interface)
            
            # Extract error counts
            patterns = [
                (r'(\d+) input errors', 'input_errors'),
                (r'(\d+) output errors', 'output_errors'),
                (r'(\d+) CRC', 'crc_errors'),
                (r'(\d+) frame', 'frame_errors'),
                (r'(\d+) overrun', 'overrun'),
                (r'(\d+) ignored', 'ignored'),
                (r'(\d+) collisions', 'collisions'),
                (r'(\d+) packets input', 'input_packets'),
                (r'(\d+) packets output', 'output_packets'),
            ]
            
            for pattern, attr in patterns:
                match = re.search(pattern, block, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    setattr(stats, attr, value)
            
            # Calculate error rate
            if stats.input_packets > 0:
                stats.error_rate = (stats.input_errors / stats.input_packets) * 100
            
            stats_list.append(stats)
        
        return stats_list
    
    def update_stats(
        self,
        device_id: str,
        stats: InterfaceStats
    ) -> Optional[Dict]:
        """
        Update interface stats and check for issues.
        
        Returns:
            Alert dict if threshold exceeded
        """
        key = f"{device_id}:{stats.interface}"
        
        if key not in self._stats_history:
            self._stats_history[key] = []
        
        self._stats_history[key].append(stats)
        
        # Keep only last 10 records
        if len(self._stats_history[key]) > 10:
            self._stats_history[key] = self._stats_history[key][-10:]
        
        # Check thresholds
        alerts = self._check_thresholds(stats)
        
        if alerts:
            return {
                "device_id": device_id,
                "interface": stats.interface,
                "issues": alerts,
                "error_rate": stats.error_rate,
            }
        
        return None
    
    def _check_thresholds(self, stats: InterfaceStats) -> List[Dict]:
        """Check if stats exceed thresholds."""
        issues = []
        
        # CRC errors
        if stats.crc_errors > self._thresholds[ErrorType.CRC].critical_threshold:
            issues.append({
                "type": "critical",
                "error": "crc",
                "value": stats.crc_errors,
                "message": f"High CRC errors: {stats.crc_errors}"
            })
        elif stats.crc_errors > self._thresholds[ErrorType.CRC].warning_threshold:
            issues.append({
                "type": "warning",
                "error": "crc",
                "value": stats.crc_errors,
                "message": f"Elevated CRC errors: {stats.crc_errors}"
            })
        
        # Input errors
        if stats.input_errors > self._thresholds[ErrorType.INPUT_ERRORS].critical_threshold:
            issues.append({
                "type": "critical",
                "error": "input_errors",
                "value": stats.input_errors,
                "message": f"High input errors: {stats.input_errors}"
            })
        
        # Error rate
        if stats.error_rate > 1.0:
            issues.append({
                "type": "warning",
                "error": "error_rate",
                "value": stats.error_rate,
                "message": f"High error rate: {stats.error_rate:.2f}%"
            })
        
        return issues
    
    def get_interface_health(self, device_id: str, interface: str) -> Dict:
        """Get health status for specific interface."""
        key = f"{device_id}:{interface}"
        history = self._stats_history.get(key, [])
        
        if not history:
            return {"status": "unknown", "message": "No data available"}
        
        latest = history[-1]
        
        # Calculate trend
        if len(history) >= 2:
            prev = history[-2]
            crc_trend = latest.crc_errors - prev.crc_errors
        else:
            crc_trend = 0
        
        return {
            "interface": interface,
            "status": "healthy" if latest.error_rate < 0.1 else "degraded",
            "error_rate": latest.error_rate,
            "crc_errors": latest.crc_errors,
            "crc_trend": crc_trend,
            "total_checks": len(history),
        }


class PerformanceMonitor:
    """
    Monitors interface performance metrics.
    """
    
    def __init__(self):
        self._utilization_history: Dict[str, List[float]] = {}
    
    def record_utilization(
        self,
        device_id: str,
        interface: str,
        utilization_percent: float
    ) -> str:
        """
        Record interface utilization.
        
        Returns:
            Status string: "normal", "warning", "critical"
        """
        key = f"{device_id}:{interface}"
        
        if key not in self._utilization_history:
            self._utilization_history[key] = []
        
        self._utilization_history[key].append(utilization_percent)
        
        # Keep last 60 samples (5 hours at 5min intervals)
        if len(self._utilization_history[key]) > 60:
            self._utilization_history[key] = self._utilization_history[key][-60:]
        
        # Determine status
        if utilization_percent > 80:
            return "critical"
        elif utilization_percent > 50:
            return "warning"
        else:
            return "normal"
    
    def get_utilization_trend(self, device_id: str, interface: str) -> Dict:
        """Get utilization trend analysis."""
        key = f"{device_id}:{interface}"
        history = self._utilization_history.get(key, [])
        
        if len(history) < 2:
            return {"trend": "unknown"}
        
        avg = sum(history) / len(history)
        latest = history[-1]
        
        # Simple trend detection
        if latest > avg * 1.2:
            trend = "increasing"
        elif latest < avg * 0.8:
            trend = "decreasing"
        else:
            trend = "stable"
        
        return {
            "current": latest,
            "average": avg,
            "trend": trend,
            "peak": max(history),
        }
