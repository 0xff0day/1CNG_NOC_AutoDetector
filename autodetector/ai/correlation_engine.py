"""
AI Correlation Engine

Correlates alerts across devices to identify root causes
and cascading failures.
"""

from __future__ import annotations

import time
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert instance."""
    id: str
    device_id: str
    variable: str
    severity: str
    message: str
    timestamp: float
    metadata: Dict = field(default_factory=dict)


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    primary_device: str
    root_cause: str
    confidence: float
    related_devices: List[str]
    impact_chain: List[str]
    time_window_minutes: float
    common_patterns: List[str]
    recommendation: str


@dataclass
class DeviceDependency:
    """Dependency between devices."""
    upstream_device: str
    downstream_device: str
    dependency_type: str  # network, power, service
    critical: bool = False


class CorrelationEngine:
    """
    Correlates alerts to find common causes.
    
    Features:
    - Temporal correlation (same time window)
    - Spatial correlation (connected devices)
    - Pattern matching
    - Root cause analysis
    """
    
    def __init__(
        self,
        time_window_seconds: int = 300,
        min_correlation_confidence: float = 0.7
    ):
        self.time_window_seconds = time_window_seconds
        self.min_confidence = min_correlation_confidence
        self._dependencies: List[DeviceDependency] = []
        self._pattern_weights = {
            "same_time": 0.3,
            "connected_devices": 0.4,
            "same_type": 0.2,
            "cascade_pattern": 0.5,
        }
    
    def add_dependency(
        self,
        upstream: str,
        downstream: str,
        dep_type: str = "network",
        critical: bool = False
    ) -> None:
        """Add device dependency."""
        self._dependencies.append(DeviceDependency(
            upstream_device=upstream,
            downstream_device=downstream,
            dependency_type=dep_type,
            critical=critical
        ))
    
    def correlate_alerts(
        self,
        alerts: List[Alert]
    ) -> List[CorrelationResult]:
        """
        Analyze alerts for correlations.
        
        Returns:
            List of correlation results
        """
        if len(alerts) < 2:
            return []
        
        results = []
        
        # Group by time window
        time_groups = self._group_by_time(alerts)
        
        for time_group in time_groups:
            if len(time_group) < 2:
                continue
            
            # Check for dependencies
            dep_correlation = self._check_dependencies(time_group)
            if dep_correlation:
                results.append(dep_correlation)
            
            # Check for pattern correlations
            pattern_corr = self._check_patterns(time_group)
            if pattern_corr:
                results.append(pattern_corr)
        
        return results
    
    def _group_by_time(
        self,
        alerts: List[Alert]
    ) -> List[List[Alert]]:
        """Group alerts by time windows."""
        if not alerts:
            return []
        
        # Sort by timestamp
        sorted_alerts = sorted(alerts, key=lambda a: a.timestamp)
        
        groups = []
        current_group = [sorted_alerts[0]]
        
        for alert in sorted_alerts[1:]:
            time_diff = alert.timestamp - current_group[0].timestamp
            
            if time_diff <= self.time_window_seconds:
                current_group.append(alert)
            else:
                groups.append(current_group)
                current_group = [alert]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _check_dependencies(
        self,
        alerts: List[Alert]
    ) -> Optional[CorrelationResult]:
        """Check for dependency-based correlations."""
        devices = {a.device_id for a in alerts}
        
        # Find affected dependencies
        affected_deps = [
            d for d in self._dependencies
            if d.upstream_device in devices and d.downstream_device in devices
        ]
        
        if not affected_deps:
            return None
        
        # Most likely root cause is the upstream device with earliest alert
        upstream_alerts = [
            a for a in alerts
            if a.device_id in {d.upstream_device for d in affected_deps}
        ]
        
        if not upstream_alerts:
            return None
        
        earliest = min(upstream_alerts, key=lambda a: a.timestamp)
        
        # Calculate confidence
        confidence = 0.5 + len(affected_deps) * 0.1
        confidence = min(1.0, confidence)
        
        if confidence < self.min_confidence:
            return None
        
        # Build impact chain
        related = list(devices)
        chain = self._build_impact_chain(earliest.device_id, devices)
        
        return CorrelationResult(
            primary_device=earliest.device_id,
            root_cause=f"Upstream failure affecting dependent devices",
            confidence=confidence,
            related_devices=related,
            impact_chain=chain,
            time_window_minutes=self.time_window_seconds / 60,
            common_patterns=["dependency_cascade"],
            recommendation=f"Check {earliest.device_id} first, then verify downstream devices"
        )
    
    def _check_patterns(
        self,
        alerts: List[Alert]
    ) -> Optional[CorrelationResult]:
        """Check for pattern-based correlations."""
        devices = list({a.device_id for a in alerts})
        
        # Same variable type across devices
        variables = defaultdict(list)
        for alert in alerts:
            variables[alert.variable].append(alert)
        
        # Find common variable with multiple devices
        for var, var_alerts in variables.items():
            var_devices = {a.device_id for a in var_alerts}
            
            if len(var_devices) >= 2:
                confidence = 0.6 + min(0.3, len(var_devices) * 0.05)
                
                if confidence >= self.min_confidence:
                    earliest = min(var_alerts, key=lambda a: a.timestamp)
                    
                    return CorrelationResult(
                        primary_device=earliest.device_id,
                        root_cause=f"Common {var} issue across multiple devices",
                        confidence=confidence,
                        related_devices=list(var_devices),
                        impact_chain=list(var_devices),
                        time_window_minutes=self.time_window_seconds / 60,
                        common_patterns=[f"common_{var}"],
                        recommendation=f"Investigate shared infrastructure for {var}"
                    )
        
        return None
    
    def _build_impact_chain(
        self,
        root_device: str,
        affected_devices: Set[str]
    ) -> List[str]:
        """Build chain of impact from root device."""
        chain = [root_device]
        remaining = affected_devices - {root_device}
        
        # Simple approach: add devices that depend on the last device in chain
        while remaining:
            last = chain[-1]
            
            # Find devices that depend on last
            downstream = {
                d.downstream_device for d in self._dependencies
                if d.upstream_device == last and d.downstream_device in remaining
            }
            
            if downstream:
                chain.extend(downstream)
                remaining -= downstream
            else:
                # No more dependencies, add remaining arbitrarily
                chain.extend(remaining)
                break
        
        return chain
    
    def find_common_root_cause(
        self,
        device_ids: List[str],
        alert_history: List[Alert]
    ) -> Optional[str]:
        """
        Find common root cause for multiple device failures.
        
        Returns:
            Device ID of likely root cause or None
        """
        if len(device_ids) < 2:
            return device_ids[0] if device_ids else None
        
        # Check for common upstream
        common_upstream = set()
        
        for device in device_ids:
            upstreams = {
                d.upstream_device for d in self._dependencies
                if d.downstream_device == device
            }
            
            if not common_upstream:
                common_upstream = upstreams
            else:
                common_upstream &= upstreams
        
        if common_upstream:
            # Return earliest alerting common upstream
            upstream_alerts = [
                a for a in alert_history
                if a.device_id in common_upstream
            ]
            
            if upstream_alerts:
                earliest = min(upstream_alerts, key=lambda a: a.timestamp)
                return earliest.device_id
            
            return list(common_upstream)[0]
        
        # No common upstream, return device with earliest alert
        device_alerts = [
            a for a in alert_history
            if a.device_id in device_ids
        ]
        
        if device_alerts:
            earliest = min(device_alerts, key=lambda a: a.timestamp)
            return earliest.device_id
        
        return None
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """Get dependency graph as adjacency list."""
        graph = defaultdict(list)
        
        for dep in self._dependencies:
            graph[dep.upstream_device].append(dep.downstream_device)
        
        return dict(graph)
    
    def load_dependencies_from_config(
        self,
        config: List[Dict]
    ) -> None:
        """Load dependencies from configuration."""
        for item in config:
            self.add_dependency(
                upstream=item["upstream"],
                downstream=item["downstream"],
                dep_type=item.get("type", "network"),
                critical=item.get("critical", False)
            )
        
        logger.info(f"Loaded {len(config)} device dependencies")


class AlertCluster:
    """Cluster of related alerts."""
    
    def __init__(self, alerts: List[Alert]):
        self.alerts = alerts
        self.devices = {a.device_id for a in alerts}
        self.variables = {a.variable for a in alerts}
        self.severities = [a.severity for a in alerts]
        self.time_range = (
            min(a.timestamp for a in alerts),
            max(a.timestamp for a in alerts)
        )
    
    def has_critical(self) -> bool:
        """Check if cluster contains critical alerts."""
        return "critical" in self.severities
    
    def get_summary(self) -> str:
        """Get human-readable summary."""
        return (
            f"{len(self.alerts)} alerts across {len(self.devices)} devices, "
            f"variables: {', '.join(self.variables)}"
        )
