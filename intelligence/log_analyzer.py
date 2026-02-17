"""
Log Intelligence Module

Extracts insights from device logs using pattern recognition.
Identifies security events, errors, and operational issues.
Provides real-time streaming analysis and log correlation.
"""

from __future__ import annotations

import re
import json
from typing import Dict, List, Optional, Tuple, Iterator, Any
from dataclasses import dataclass, asdict
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import logging
from threading import Lock

logger = logging.getLogger(__name__)


@dataclass
class LogInsight:
    """Log analysis insight."""
    insight_type: str  # security, error, performance, operational
    severity: str
    description: str
    count: int
    recommendation: str
    timestamp: Optional[datetime] = None
    source_ip: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_type": self.insight_type,
            "severity": self.severity,
            "description": self.description,
            "count": self.count,
            "recommendation": self.recommendation,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "source_ip": self.source_ip,
            "metadata": self.metadata,
        }


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: datetime
    level: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    source: str
    message: str
    raw_line: str
    parsed_fields: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.parsed_fields is None:
            self.parsed_fields = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "parsed_fields": self.parsed_fields,
        }


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
    
    def parse_structured_log(self, log_line: str, format_type: str = "syslog") -> Optional[LogEntry]:
        """
        Parse a log line into structured format.
        
        Supports: syslog, json, apache, nginx, csv
        """
        timestamp = datetime.now()
        level = "INFO"
        source = "unknown"
        message = log_line
        parsed_fields = {}
        
        try:
            if format_type == "json":
                # JSON format
                data = json.loads(log_line)
                timestamp_str = data.get("timestamp") or data.get("time") or data.get("ts")
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except:
                        pass
                level = data.get("level", data.get("severity", "INFO")).upper()
                source = data.get("source", data.get("logger", "unknown"))
                message = data.get("message", data.get("msg", log_line))
                parsed_fields = {k: v for k, v in data.items() if k not in ["timestamp", "level", "source", "message"]}
                
            elif format_type == "syslog":
                # Standard syslog format
                syslog_pattern = r"<(\d+)>?(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\w+):\s*(.*)"
                match = re.match(syslog_pattern, log_line)
                if match:
                    priority, ts_str, source, level, message = match.groups()
                    try:
                        timestamp = datetime.strptime(f"{datetime.now().year} {ts_str}", "%Y %b %d %H:%M:%S")
                    except:
                        pass
                    parsed_fields["priority"] = priority
                    
            elif format_type == "apache":
                # Apache combined log format
                apache_pattern = r'(\S+)\s+-\s+(\S+)\s+\[(.*?)\]\s+"(.*?)"\s+(\d+)\s+(\S+)'
                match = re.match(apache_pattern, log_line)
                if match:
                    ip, ident, ts_str, request, status, size = match.groups()
                    try:
                        timestamp = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
                    except:
                        pass
                    source = ip
                    level = "ERROR" if int(status) >= 500 else "WARNING" if int(status) >= 400 else "INFO"
                    message = f"{request} -> {status}"
                    parsed_fields = {"ip": ip, "status_code": int(status), "response_size": size, "request": request}
                    
        except Exception as e:
            logger.warning(f"Failed to parse log line: {e}")
            return None
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            source=source,
            message=message,
            raw_line=log_line,
            parsed_fields=parsed_fields
        )
    
    def analyze_stream(self, log_stream: Iterator[str], window_size: int = 100) -> Iterator[LogInsight]:
        """
        Real-time streaming log analysis.
        
        Yields insights as they are detected.
        """
        window = []
        
        for log_line in log_stream:
            window.append(log_line)
            
            # Keep window size manageable
            if len(window) > window_size:
                window = window[-window_size:]
            
            # Check for immediate insights
            insights = self.analyze_logs([log_line])
            for insight in insights:
                if insight.severity in ["critical", "high"]:
                    yield insight
        
        # Final analysis of full window
        final_insights = self.analyze_logs(window)
        for insight in final_insights:
            yield insight
    
    def correlate_logs(self, logs: List[str], time_window_seconds: int = 300) -> List[LogInsight]:
        """
        Correlate related log events within a time window.
        
        Detects event sequences and cascading failures.
        """
        insights = []
        
        # Group logs by inferred source
        source_logs = defaultdict(list)
        for log in logs:
            # Try to extract IP or hostname
            ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', log)
            source = ip_match.group(1) if ip_match else "unknown"
            source_logs[source].append(log)
        
        # Check for patterns across sources
        for source, src_logs in source_logs.items():
            # Check for error cascades
            error_count = len([l for l in src_logs if "error" in l.lower()])
            if error_count >= 10:
                insights.append(LogInsight(
                    insight_type="correlation",
                    severity="high",
                    description=f"Error cascade detected from {source}",
                    count=error_count,
                    recommendation="Investigate source for cascading failures",
                    source_ip=source,
                    metadata={"time_window": time_window_seconds, "log_count": len(src_logs)}
                ))
            
            # Check for rapid authentication failures followed by success (potential breach)
            auth_failures = [l for l in src_logs if "authentication fail" in l.lower()]
            auth_success = [l for l in src_logs if "authentication success" in l.lower()]
            if len(auth_failures) >= 5 and auth_success:
                insights.append(LogInsight(
                    insight_type="correlation",
                    severity="critical",
                    description=f"Potential brute force success from {source}",
                    count=len(auth_failures),
                    recommendation="Immediately investigate and potentially block source",
                    source_ip=source,
                    metadata={"failures": len(auth_failures), "success_after": True}
                ))
        
        return insights
    
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
    Specialized security log analyzer with advanced threat detection.
    """
    
    def __init__(self):
        self._brute_force_threshold = 5
        self._scan_threshold = 10  # Unique ports scanned
        self._suspicious_ips = set()
        self._failed_attempts = defaultdict(list)  # IP -> list of timestamps
        self._lock = Lock()
    
    def detect_brute_force(self, logs: List[str]) -> Optional[Dict]:
        """Detect brute force login attempts with time-based analysis."""
        failed_logins = []
        
        for log in logs:
            if "fail" in log.lower() and ("auth" in log.lower() or "login" in log.lower()):
                # Extract timestamp if present
                ts_match = re.search(r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})', log)
                timestamp = datetime.fromisoformat(ts_match.group(1)) if ts_match else datetime.now()
                
                # Extract IP
                ip_match = re.search(r"from\s+(\d+\.\d+\.\d+\.\d+)", log)
                if ip_match:
                    failed_logins.append((ip_match.group(1), timestamp, log))
        
        # Group by IP and time windows
        ip_attempts = defaultdict(list)
        for ip, ts, log in failed_logins:
            ip_attempts[ip].append(ts)
        
        attackers = {}
        for ip, attempts in ip_attempts.items():
            # Check attempts within 5-minute window
            attempts.sort()
            for i, start_ts in enumerate(attempts):
                window_end = start_ts + timedelta(minutes=5)
                count = sum(1 for ts in attempts if start_ts <= ts <= window_end)
                if count >= self._brute_force_threshold:
                    attackers[ip] = {
                        "count": len(attempts),
                        "window_count": count,
                        "first_attempt": min(attempts).isoformat(),
                        "last_attempt": max(attempts).isoformat(),
                    }
                    break
        
        if attackers:
            return {
                "attack_type": "brute_force",
                "severity": "high",
                "sources": attackers,
                "recommendation": "Block attacking IPs and review authentication policies.",
                "indicators": ["rapid authentication failures", "multiple source IPs"] if len(attackers) > 1 else ["concentrated auth failures"]
            }
        
        return None
    
    def detect_port_scan(self, logs: List[str]) -> Optional[Dict]:
        """Detect port scanning attempts."""
        # Extract connection attempts
        connections = []
        for log in logs:
            # Match patterns like "connection from X to port Y" or SYN packets
            match = re.search(r'(?:connection|syn|probe).*?(\d+\.\d+\.\d+\.\d+).*?port\s+(\d+)', log, re.IGNORECASE)
            if match:
                ip, port = match.groups()
                connections.append((ip, int(port)))
        
        # Group by source IP and count unique ports
        ip_ports = defaultdict(set)
        for ip, port in connections:
            ip_ports[ip].add(port)
        
        scanners = {ip: len(ports) for ip, ports in ip_ports.items() if len(ports) >= self._scan_threshold}
        
        if scanners:
            return {
                "attack_type": "port_scan",
                "severity": "medium",
                "sources": scanners,
                "recommendation": "Monitor scanning sources. Consider IPS blocking.",
                "indicators": ["multi-port probing", "sequential port access"]
            }
        
        return None
    
    def detect_anomalies(self, logs: List[str], baseline: Optional[Dict] = None) -> List[Dict]:
        """Detect anomalous patterns based on statistical analysis."""
        anomalies = []
        
        # Analyze log volume by hour
        hour_counts = defaultdict(int)
        for log in logs:
            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}):', log)
            if ts_match:
                hour = int(ts_match.group(1).split(':')[0])
                hour_counts[hour] += 1
        
        # Detect unusual spikes (3x average)
        if hour_counts:
            avg_count = sum(hour_counts.values()) / len(hour_counts)
            for hour, count in hour_counts.items():
                if count > avg_count * 3:
                    anomalies.append({
                        "type": "volume_spike",
                        "severity": "medium",
                        "hour": hour,
                        "count": count,
                        "average": round(avg_count, 1),
                        "description": f"Unusual log volume at hour {hour}: {count} entries (avg: {avg_count:.1f})"
                    })
        
        # Detect new error types
        if baseline:
            current_errors = set(self._extract_error_signatures(logs))
            baseline_errors = set(baseline.get("error_signatures", []))
            new_errors = current_errors - baseline_errors
            
            if new_errors:
                anomalies.append({
                    "type": "new_error_type",
                    "severity": "high",
                    "new_signatures": list(new_errors)[:10],  # Limit
                    "description": f"Detected {len(new_errors)} new error types not seen in baseline"
                })
        
        return anomalies
    
    def _extract_error_signatures(self, logs: List[str]) -> List[str]:
        """Extract unique error signatures for anomaly detection."""
        signatures = set()
        for log in logs:
            if "error" in log.lower() or "exception" in log.lower():
                # Create signature by removing timestamps and variable data
                sig = re.sub(r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}', 'TIMESTAMP', log)
                sig = re.sub(r'\d+\.\d+\.\d+\.\d+', 'IPADDR', sig)
                sig = re.sub(r'\b\d+\b', 'NUM', sig)  # Replace standalone numbers
                signatures.add(sig[:100])  # Truncate
        return list(signatures)
    
    def analyze_threat_level(self, logs: List[str]) -> Dict[str, Any]:
        """Overall threat level assessment."""
        threats = []
        
        # Run all detection methods
        brute_force = self.detect_brute_force(logs)
        if brute_force:
            threats.append(brute_force)
        
        port_scan = self.detect_port_scan(logs)
        if port_scan:
            threats.append(port_scan)
        
        anomalies = self.detect_anomalies(logs)
        threats.extend([{"attack_type": a["type"], **a} for a in anomalies])
        
        # Calculate overall threat level
        severity_scores = {
            "critical": 10,
            "high": 7,
            "medium": 4,
            "low": 1
        }
        
        total_score = sum(severity_scores.get(t.get("severity", "low"), 1) for t in threats)
        
        threat_level = "low"
        if total_score >= 20:
            threat_level = "critical"
        elif total_score >= 12:
            threat_level = "high"
        elif total_score >= 5:
            threat_level = "medium"
        
        return {
            "threat_level": threat_level,
            "threat_score": total_score,
            "threat_count": len(threats),
            "threats": threats,
            "timestamp": datetime.now().isoformat(),
            "recommendation": self._get_threat_recommendation(threat_level)
        }
    
    def _get_threat_recommendation(self, threat_level: str) -> str:
        """Get recommendation based on threat level."""
        recommendations = {
            "critical": "Immediate action required. Activate incident response team.",
            "high": "Urgent investigation needed. Consider blocking suspicious sources.",
            "medium": "Monitor closely. Review security policies.",
            "low": "Normal monitoring. Log for trend analysis."
        }
        return recommendations.get(threat_level, "Continue monitoring.")


class LogCorrelationEngine:
    """
    Advanced log correlation for identifying complex patterns.
    """
    
    def __init__(self):
        self._event_chains = []
        self._sequence_rules = [
            {
                "name": "config_change_error",
                "pattern": ["config.*changed", "error.*restart"],
                "time_window": 300,
                "severity": "high"
            },
            {
                "name": "auth_escalation",
                "pattern": ["user.*created", "privilege.*elevated"],
                "time_window": 600,
                "severity": "critical"
            }
        ]
    
    def find_sequences(self, logs: List[str]) -> List[Dict]:
        """Find event sequences that match correlation rules."""
        matched_sequences = []
        
        for rule in self._sequence_rules:
            pattern = rule["pattern"]
            matches = []
            
            for i, log in enumerate(logs):
                for p in pattern:
                    if re.search(p, log, re.IGNORECASE):
                        matches.append((i, log, p))
            
            # Check if all patterns found in order
            if len(set(m[2] for m in matches)) == len(pattern):
                matched_sequences.append({
                    "rule": rule["name"],
                    "severity": rule["severity"],
                    "matched_events": len(matches),
                    "description": f"Detected sequence: {rule['name']}"
                })
        
        return matched_sequences
