"""
Health Score Engine

Calculates overall device health scores based on multiple metrics.
Supports weighted scoring and customizable thresholds.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class HealthScoreResult:
    """Device health score result."""
    device_id: str
    overall_score: float  # 0-100
    status: str  # healthy, warning, critical
    component_scores: Dict[str, float]
    weights: Dict[str, float]
    degrading_factors: List[str]
    recommendation: str
    calculated_at: float


class HealthScoreEngine:
    """
    Calculates device health scores from metrics.
    
    Components:
    - CPU health (weight: 0.25)
    - Memory health (weight: 0.20)
    - Disk health (weight: 0.20)
    - Network health (weight: 0.15)
    - Hardware health (weight: 0.10)
    - Uptime/reliability (weight: 0.10)
    """
    
    DEFAULT_WEIGHTS = {
        "cpu": 0.25,
        "memory": 0.20,
        "disk": 0.20,
        "network": 0.15,
        "hardware": 0.10,
        "uptime": 0.10,
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        
        # Normalize weights to sum to 1.0
        total = sum(self.weights.values())
        if total != 1.0:
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def calculate(
        self,
        device_id: str,
        metrics: Dict[str, float],
        thresholds: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> HealthScoreResult:
        """
        Calculate health score from metrics.
        
        Args:
            device_id: Device identifier
            metrics: Dict of metric values
            thresholds: Dict of (warn, crit) thresholds per metric
        
        Returns:
            HealthScoreResult with detailed scoring
        """
        thresholds = thresholds or {}
        component_scores = {}
        degrading_factors = []
        
        # Calculate CPU health (inverse of usage)
        cpu_usage = metrics.get("cpu_usage", 0)
        cpu_health = max(0, 100 - cpu_usage)
        component_scores["cpu"] = cpu_health
        
        if cpu_usage > 80:
            degrading_factors.append(f"High CPU usage: {cpu_usage:.1f}%")
        
        # Calculate Memory health
        mem_usage = metrics.get("memory_usage", 0)
        mem_health = max(0, 100 - mem_usage)
        component_scores["memory"] = mem_health
        
        if mem_usage > 85:
            degrading_factors.append(f"High memory usage: {mem_usage:.1f}%")
        
        # Calculate Disk health
        disk_usage = metrics.get("disk_usage", 0)
        disk_health = max(0, 100 - disk_usage)
        component_scores["disk"] = disk_health
        
        if disk_usage > 85:
            degrading_factors.append(f"High disk usage: {disk_usage:.1f}%")
        
        # Calculate Network health
        net_errors = metrics.get("interface_errors", 0)
        interface_down = metrics.get("interface_down", 0)
        
        net_health = 100.0
        if net_errors > 10:
            net_health -= min(50, net_errors)
        if interface_down > 0:
            net_health -= min(40, interface_down * 20)
        
        net_health = max(0, net_health)
        component_scores["network"] = net_health
        
        if net_errors > 0:
            degrading_factors.append(f"Network errors: {net_errors}")
        if interface_down > 0:
            degrading_factors.append(f"Down interfaces: {interface_down}")
        
        # Calculate Hardware health
        temp = metrics.get("temperature", 25)
        power_ok = metrics.get("power_ok", 1)
        fan_ok = metrics.get("fan_ok", 1)
        
        # Temperature scoring (optimal at 25-40C)
        if temp < 60:
            temp_health = 100 - max(0, (temp - 40) * 2)
        else:
            temp_health = max(0, 60 - (temp - 60) * 2)
        
        hw_health = temp_health * 0.5 + (100 if power_ok else 0) * 0.25 + (100 if fan_ok else 0) * 0.25
        component_scores["hardware"] = hw_health
        
        if temp > 70:
            degrading_factors.append(f"High temperature: {temp:.1f}C")
        if not power_ok:
            degrading_factors.append("Power supply issue")
        if not fan_ok:
            degrading_factors.append("Fan failure")
        
        # Calculate Uptime/reliability
        uptime_hours = metrics.get("uptime_hours", 24)
        reboot_count = metrics.get("reboot_count", 0)
        
        # Score based on uptime stability
        if uptime_hours > 720:  # 30 days
            uptime_health = 100
        elif uptime_hours > 168:  # 7 days
            uptime_health = 90
        elif uptime_hours > 24:
            uptime_health = 75
        else:
            uptime_health = 50
        
        # Penalty for recent reboots
        uptime_health -= reboot_count * 10
        uptime_health = max(0, uptime_health)
        
        component_scores["uptime"] = uptime_health
        
        if uptime_hours < 24:
            degrading_factors.append(f"Recent reboot (uptime: {uptime_hours:.1f}h)")
        
        # Calculate weighted overall score
        overall_score = 0.0
        for component, score in component_scores.items():
            weight = self.weights.get(component, 0.1)
            overall_score += score * weight
        
        overall_score = max(0, min(100, overall_score))
        
        # Determine status
        if overall_score >= 90:
            status = "healthy"
        elif overall_score >= 70:
            status = "warning"
        else:
            status = "critical"
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            overall_score, component_scores, degrading_factors
        )
        
        return HealthScoreResult(
            device_id=device_id,
            overall_score=round(overall_score, 1),
            status=status,
            component_scores={k: round(v, 1) for k, v in component_scores.items()},
            weights=self.weights,
            degrading_factors=degrading_factors,
            recommendation=recommendation,
            calculated_at=datetime.now().timestamp()
        )
    
    def _generate_recommendation(
        self,
        overall_score: float,
        component_scores: Dict[str, float],
        degrading_factors: List[str]
    ) -> str:
        """Generate health recommendation."""
        if overall_score >= 90:
            return "Device is healthy. Continue normal monitoring."
        
        if overall_score < 50:
            return f"CRITICAL: Multiple issues detected. {len(degrading_factors)} problems require immediate attention."
        
        # Find lowest scoring component
        lowest_component = min(component_scores, key=component_scores.get)
        lowest_score = component_scores[lowest_component]
        
        if lowest_score < 50:
            return f"WARNING: {lowest_component.upper()} health is critically low ({lowest_score:.1f}). {degrading_factors[0] if degrading_factors else ''}"
        
        return f"WARNING: {len(degrading_factors)} issues detected. Focus on {lowest_component.upper()} optimization."
    
    def calculate_group_health(
        self,
        device_scores: List[HealthScoreResult]
    ) -> Dict[str, any]:
        """
        Calculate aggregate health for a group of devices.
        
        Returns:
            Group health statistics
        """
        if not device_scores:
            return {
                "average_score": 0,
                "status_distribution": {},
                "unhealthy_devices": []
            }
        
        scores = [d.overall_score for d in device_scores]
        
        # Status distribution
        status_dist = {"healthy": 0, "warning": 0, "critical": 0}
        for score in device_scores:
            status_dist[score.status] += 1
        
        # Unhealthy devices
        unhealthy = [
            d.device_id for d in device_scores
            if d.status != "healthy"
        ]
        
        return {
            "device_count": len(device_scores),
            "average_score": round(sum(scores) / len(scores), 1),
            "min_score": round(min(scores), 1),
            "max_score": round(max(scores), 1),
            "status_distribution": status_dist,
            "healthy_percentage": round(status_dist["healthy"] / len(scores) * 100, 1),
            "unhealthy_devices": unhealthy,
            "unhealthy_count": len(unhealthy)
        }
