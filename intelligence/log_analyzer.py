"""
Log Intelligence Module

Extracts insights from device logs using pattern recognition.
Identifies security events, errors, and operational issues.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import Counter
import logging

logger = logging.getLogger(__name__)


@dataclass
class LogInsight:
    """Log analysis insight."""
    insight_type: str  # security, error, performance, operational
    severity: str
    description: str
    count: int
    recommendation: str


class LogIntelligence:
    """
    Analyzes logs for actionable insights.
    
    Detects:
    - Security incidents
    - Error patterns
    - Performance degradation
    - Configuration issues
    """
    
    def __init__(self):
        self._patterns = {
            "security": [
                (r"authentication fail", "high", "Authentication failures detected"),
                (r"login.*denied", "high", "Login attempts denied"),
                (r"acl.*deny", "medium", "ACL violations"),
                (r"intrusion", "critical", "Possible intrusion detected"),
            ],
            "error": [
                (r"error", "medium", "Errors in logs"),
                (r"failure", "high", "System/component failures"),
                (r"exception", "medium", "Exceptions detected"),
                (r"crash", "critical", "System crashes"),
            ],
            "performance": [
                (r"high cpu", "high", "High CPU utilization events"),
                (r"memory.*exhausted", "critical", "Memory exhaustion"),
                (r"timeout", "medium", "Timeout events"),
                (r"slow", "low", "Performance degradation"),
            ],
        }
    
    def analyze_logs(self, logs: List[str]) -> List[LogInsight]:
        """
        Analyze log entries for insights.
        
        Args:
            logs: Log lines to analyze
        
        Returns:
            List of insights
        """
        insights = []
        
        for category, patterns in self._patterns.items():
            for pattern, severity, description in patterns:
                matches = [log for log in logs if re.search(pattern, log, re.IGNORECASE)]
                
                if matches:
                    insights.append(LogInsight(
                        insight_type=category,
                        severity=severity,
                        description=description,
                        count=len(matches),
                        recommendation=self._generate_recommendation(category, pattern, len(matches))
                    ))
        
        return insights
    
    def _generate_recommendation(
        self,
        category: str,
        pattern: str,
        count: int
    ) -> str:
        """Generate recommendation based on insight."""
        if category == "security" and count > 10:
            return "Investigate security events. Consider blocking source IPs."
        elif category == "error" and count > 5:
            return "Review error logs. May indicate hardware or configuration issues."
        elif category == "performance":
            return "Monitor resource usage. Consider capacity planning."
        return "Monitor for patterns."
    
    def extract_top_errors(self, logs: List[str], n: int = 5) -> List[Tuple[str, int]]:
        """Extract most common error patterns."""
        error_lines = [log for log in logs if "error" in log.lower()]
        
        # Extract error message (simplified)
        messages = []
        for line in error_lines:
            match = re.search(r"[Ee]rror[:\s]+(.+)", line)
            if match:
                messages.append(match.group(1)[:50])  # Truncate
        
        return Counter(messages).most_common(n)


class SecurityAnalyzer:
    """
    Specialized security log analyzer.
    """
    
    def __init__(self):
        self._brute_force_threshold = 5
    
    def detect_brute_force(self, logs: List[str]) -> Optional[Dict]:
        """Detect brute force login attempts."""
        failed_logins = [log for log in logs if "fail" in log.lower()]
        
        # Group by source IP (simplified)
        ips = {}
        for log in failed_logins:
            match = re.search(r"from\s+(\d+\.\d+\.\d+\.\d+)", log)
            if match:
                ip = match.group(1)
                ips[ip] = ips.get(ip, 0) + 1
        
        # Find brute force sources
        attackers = {ip: count for ip, count in ips.items() if count >= self._brute_force_threshold}
        
        if attackers:
            return {
                "attack_type": "brute_force",
                "sources": attackers,
                "recommendation": "Block attacking IPs and review authentication policies."
            }
        
        return None
