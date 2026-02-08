"""
Root Cause Analyzer

Generates human-readable root cause analysis from alerts and correlations.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class RootCauseAnalysis:
    """Root cause analysis result."""
    primary_cause: str
    contributing_factors: List[str]
    impact_summary: str
    recommended_actions: List[str]
    confidence: float
    time_to_resolution_estimate: str


class RootCauseAnalyzer:
    """
    Generates root cause analysis for network issues.
    
    Analyzes:
    - Alert patterns
    - Device dependencies
    - Historical incidents
    - Correlation results
    """
    
    def __init__(self):
        self._knowledge_base = {
            "interface_down": {
                "causes": ["Physical layer issue", "Configuration change", "Remote end down"],
                "actions": ["Check cable", "Verify configuration", "Test remote end"]
            },
            "high_cpu": {
                "causes": ["Traffic surge", "Routing instability", "Process overload"],
                "actions": ["Analyze traffic", "Check routing table", "Identify heavy processes"]
            },
            "bgp_down": {
                "causes": ["Peer issue", "AS path problems", "Configuration error"],
                "actions": ["Check peer status", "Verify AS config", "Review routing policy"]
            },
        }
    
    def analyze(
        self,
        alerts: List[Dict],
        device_id: str,
        metric_history: Optional[Dict] = None
    ) -> RootCauseAnalysis:
        """
        Generate root cause analysis for device issues.
        
        Args:
            alerts: Active alerts for device
            device_id: Device identifier
            metric_history: Historical metrics
        
        Returns:
            RootCauseAnalysis
        """
        if not alerts:
            return RootCauseAnalysis(
                primary_cause="No issues detected",
                contributing_factors=[],
                impact_summary="Device is operating normally",
                recommended_actions=["Continue monitoring"],
                confidence=1.0,
                time_to_resolution_estimate="N/A"
            )
        
        # Identify primary issue type
        primary_alert = max(alerts, key=lambda a: self._severity_score(a.get("severity", "low")))
        issue_type = self._classify_issue(primary_alert)
        
        # Get knowledge for this issue type
        knowledge = self._knowledge_base.get(issue_type, {
            "causes": ["Unknown - investigation required"],
            "actions": ["Gather more diagnostic data"]
        })
        
        # Build contributing factors
        contributing = []
        for alert in alerts:
            if alert != primary_alert:
                contributing.append(f"{alert.get('variable')}: {alert.get('message')}")
        
        # Estimate resolution time
        if primary_alert.get("severity") == "critical":
            ttr = "15-30 minutes (urgent response needed)"
        elif primary_alert.get("severity") == "high":
            ttr = "30-60 minutes"
        else:
            ttr = "1-4 hours"
        
        return RootCauseAnalysis(
            primary_cause=knowledge["causes"][0],
            contributing_factors=contributing[:3],
            impact_summary=f"Device {device_id} experiencing {issue_type}",
            recommended_actions=knowledge["actions"][:3],
            confidence=0.8,
            time_to_resolution_estimate=ttr
        )
    
    def _severity_score(self, severity: str) -> int:
        """Convert severity to numeric score."""
        scores = {"low": 1, "medium": 2, "high": 3, "critical": 4, "emergency": 5}
        return scores.get(severity.lower(), 1)
    
    def _classify_issue(self, alert: Dict) -> str:
        """Classify alert into issue type."""
        variable = alert.get("variable", "").lower()
        
        if "interface" in variable:
            return "interface_down"
        elif "cpu" in variable:
            return "high_cpu"
        elif "bgp" in variable:
            return "bgp_down"
        elif "memory" in variable:
            return "memory_high"
        elif "disk" in variable:
            return "disk_full"
        
        return "general"
    
    def format_analysis(self, analysis: RootCauseAnalysis) -> str:
        """Format analysis as human-readable text."""
        lines = [
            "=" * 60,
            "ROOT CAUSE ANALYSIS",
            "=" * 60,
            "",
            f"Primary Cause: {analysis.primary_cause}",
            "",
            "Contributing Factors:",
        ]
        
        for factor in analysis.contributing_factors:
            lines.append(f"  • {factor}")
        
        lines.extend([
            "",
            f"Impact: {analysis.impact_summary}",
            "",
            "Recommended Actions:",
        ])
        
        for i, action in enumerate(analysis.recommended_actions, 1):
            lines.append(f"  {i}. {action}")
        
        lines.extend([
            "",
            f"Estimated Resolution Time: {analysis.time_to_resolution_estimate}",
            f"Confidence: {analysis.confidence * 100:.0f}%",
            "=" * 60,
        ])
        
        return "\n".join(lines)
