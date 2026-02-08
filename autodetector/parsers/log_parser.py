"""
Log Parser Engine

Parses device logs and extracts meaningful events and errors.
Supports multiple log formats and vendor-specific patterns.
"""

from __future__ import annotations

import re
from typing import List, Dict, Optional, Pattern
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Parsed log entry."""
    timestamp: Optional[datetime]
    severity: str  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    facility: str
    message: str
    raw_line: str
    host: str = ""
    parsed_fields: Dict = None
    
    def __post_init__(self):
        if self.parsed_fields is None:
            self.parsed_fields = {}


@dataclass
class LogPattern:
    """Log parsing pattern."""
    name: str
    pattern: str
    severity: str
    category: str
    extract_fields: List[str]


class LogParserEngine:
    """
    Multi-format log parser with pattern matching.
    
    Supports:
    - Syslog formats
    - Vendor-specific logs (Cisco, Juniper, etc.)
    - Custom pattern definitions
    - Severity classification
    """
    
    # Standard syslog severity levels
    SYSLOG_PRIORITIES = {
        0: "EMERG", 1: "ALERT", 2: "CRIT", 3: "ERR",
        4: "WARNING", 5: "NOTICE", 6: "INFO", 7: "DEBUG"
    }
    
    # Built-in critical patterns for NOC
    CRITICAL_PATTERNS = [
        LogPattern("interface_down", r"Interface (\S+) changed state to administratively down", "CRITICAL", "interface", ["interface"]),
        LogPattern("bgp_down", r"BGP neighbor (\S+) Down", "CRITICAL", "routing", ["neighbor"]),
        LogPattern("ospf_neighbor_down", r"OSPF neighbor (\S+) is (Dead|Down)", "CRITICAL", "routing", ["neighbor", "state"]),
        LogPattern("power_supply_fail", r"Power supply (\S+) (failed|error)", "CRITICAL", "hardware", ["psu"]),
        LogPattern("temperature_critical", r"Temperature (?:alarm|critical|threshold exceeded)", "CRITICAL", "hardware", []),
        LogPattern("memory_critical", r"System memory usage is critical", "CRITICAL", "system", []),
        LogPattern("disk_full", r"Disk is (full|at \d+% capacity)", "CRITICAL", "storage", ["percent"]),
        LogPattern("authentication_fail", r"(?:Authentication|Login) (?:fail|error|denied)", "ERROR", "security", []),
        LogPattern("acl_violation", r"ACL (?:violation|deny|drop)", "WARNING", "security", []),
        LogPattern("flapping", r"Interface (\S+) flapping", "WARNING", "interface", ["interface"]),
        LogPattern("stp_change", r"STP (?:topology change|blocking)", "WARNING", "spanning-tree", []),
    ]
    
    # Syslog format patterns
    SYSLOG_PATTERNS = [
        # RFC 3164 format
        r"<(\d+)>(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(.*)",
        # ISO8601 format
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\+\-]\d{2}:\d{2})\s+(\S+)\s+(.*)",
        # Cisco format
        r"(\*\w+\s+\d+\s+\d+:\d+:\d+\.\d+):\s+%(\w+)-(\d)-(\w+):\s+(.*)",
        # Simple format
        r"(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\w+):\s+(.*)",
    ]
    
    def __init__(self):
        self._compiled_patterns: List[Pattern] = []
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile syslog patterns."""
        for pattern in self.SYSLOG_PATTERNS:
            try:
                self._compiled_patterns.append(re.compile(pattern))
            except re.error as e:
                logger.warning(f"Failed to compile pattern: {e}")
    
    def parse_line(self, line: str, host: str = "") -> Optional[LogEntry]:
        """
        Parse a single log line.
        
        Args:
            line: Raw log line
            host: Source host name
        
        Returns:
            Parsed LogEntry or None if unparsable
        """
        line = line.strip()
        if not line:
            return None
        
        # Try each syslog pattern
        for pattern in self._compiled_patterns:
            match = pattern.match(line)
            if match:
                return self._create_entry_from_match(match, line, host)
        
        # Default: treat entire line as message
        return LogEntry(
            timestamp=None,
            severity="INFO",
            facility="unknown",
            message=line,
            raw_line=line,
            host=host
        )
    
    def _create_entry_from_match(
        self,
        match: re.Match,
        raw_line: str,
        host: str
    ) -> LogEntry:
        """Create LogEntry from regex match."""
        groups = match.groups()
        
        # Default values
        timestamp = None
        severity = "INFO"
        facility = "unknown"
        message = raw_line
        
        # Parse based on pattern structure (RFC 3164)
        if len(groups) >= 4:
            # Try to parse priority
            try:
                pri = int(groups[0])
                severity_code = pri & 0x07
                severity = self.SYSLOG_PRIORITIES.get(severity_code, "INFO")
                facility_code = (pri >> 3) & 0x1F
            except:
                pass
            
            # Parse timestamp and message
            try:
                timestamp_str = groups[1]
                timestamp = self._parse_timestamp(timestamp_str)
            except:
                pass
            
            message = groups[-1]
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            facility=facility,
            message=message,
            raw_line=raw_line,
            host=host
        )
    
    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        """Parse various timestamp formats."""
        formats = [
            "%b %d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%b %d %Y %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def parse_log(
        self,
        log_content: str,
        host: str = ""
    ) -> List[LogEntry]:
        """
        Parse entire log content.
        
        Args:
            log_content: Multi-line log text
            host: Source host name
        
        Returns:
            List of parsed LogEntry objects
        """
        entries = []
        
        for line in log_content.splitlines():
            entry = self.parse_line(line, host)
            if entry:
                entries.append(entry)
        
        return entries
    
    def analyze_critical_events(
        self,
        entries: List[LogEntry]
    ) -> List[Dict]:
        """
        Identify critical events in log entries.
        
        Returns list of critical events with details.
        """
        critical_events = []
        
        for entry in entries:
            # Check against critical patterns
            for pattern in self.CRITICAL_PATTERNS:
                match = re.search(pattern.pattern, entry.message, re.IGNORECASE)
                if match:
                    event = {
                        "pattern_name": pattern.name,
                        "category": pattern.category,
                        "severity": pattern.severity,
                        "timestamp": entry.timestamp,
                        "host": entry.host,
                        "message": entry.message,
                        "extracted_fields": {
                            field: match.group(i+1)
                            for i, field in enumerate(pattern.extract_fields)
                            if i+1 <= len(match.groups())
                        }
                    }
                    critical_events.append(event)
                    break
            
            # Check for high syslog severity
            if entry.severity in ("EMERG", "ALERT", "CRIT", "ERR"):
                if not any(e["host"] == entry.host and e["message"] == entry.message 
                          for e in critical_events):
                    critical_events.append({
                        "pattern_name": "syslog_severity",
                        "category": "system",
                        "severity": entry.severity,
                        "timestamp": entry.timestamp,
                        "host": entry.host,
                        "message": entry.message,
                        "extracted_fields": {}
                    })
        
        return critical_events
    
    def get_error_summary(
        self,
        entries: List[LogEntry]
    ) -> Dict[str, int]:
        """
        Get summary of errors by category.
        
        Returns:
            Dict mapping category to error count
        """
        summary = {}
        
        critical = self.analyze_critical_events(entries)
        for event in critical:
            category = event.get("category", "unknown")
            summary[category] = summary.get(category, 0) + 1
        
        return summary
    
    def filter_by_severity(
        self,
        entries: List[LogEntry],
        min_severity: str
    ) -> List[LogEntry]:
        """
        Filter entries by minimum severity level.
        
        Args:
            entries: Log entries to filter
            min_severity: Minimum severity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
        Returns:
            Filtered entries
        """
        severity_order = {
            "DEBUG": 0, "INFO": 1, "NOTICE": 2,
            "WARNING": 3, "ERR": 4, "ERROR": 4,
            "CRIT": 5, "CRITICAL": 5,
            "ALERT": 6, "EMERG": 7
        }
        
        min_level = severity_order.get(min_severity, 0)
        
        return [
            e for e in entries
            if severity_order.get(e.severity, 0) >= min_level
        ]
    
    def add_custom_pattern(
        self,
        name: str,
        pattern: str,
        severity: str,
        category: str,
        extract_fields: List[str]
    ) -> None:
        """Add a custom log pattern."""
        new_pattern = LogPattern(
            name=name,
            pattern=pattern,
            severity=severity,
            category=category,
            extract_fields=extract_fields
        )
        self.CRITICAL_PATTERNS.append(new_pattern)
        logger.info(f"Added custom pattern: {name}")


class VendorLogParser:
    """Vendor-specific log parsers."""
    
    VENDOR_PATTERNS = {
        "cisco": {
            "interface_updown": r"%LINEPROTO-5-UPDOWN: Line protocol on Interface (\S+), changed state to (up|down)",
            "link_updown": r"%LINK-3-UPDOWN: Interface (\S+), changed state to (up|down)",
            "ospf_neighbor": r"%OSPF-5-ADJCHG: Process (\d+), Nbr (\S+) on (\S+) from (\S+) to (\S+)",
            "bgp_neighbor": r"%BGP-5-ADJCHANGE: neighbor (\S+) (Up|Down)",
        },
        "juniper": {
            "interface_updown": r"(\S+) (.+): Interface (\S+), changed state to (up|down)",
            "bgp_neighbor": r"BGP neighbor (\S+) \((\S+)\) state changed to (\S+)",
        },
        "fortinet": {
            "interface_status": r"Interface (\S+) is (up|down)",
            "vpn_tunnel": r"VPN tunnel (\S+) (up|down)",
        }
    }
    
    @classmethod
    def parse_vendor_log(
        cls,
        vendor: str,
        log_content: str
    ) -> List[Dict]:
        """Parse logs with vendor-specific patterns."""
        patterns = cls.VENDOR_PATTERNS.get(vendor.lower(), {})
        events = []
        
        for line in log_content.splitlines():
            for event_type, pattern in patterns.items():
                match = re.search(pattern, line)
                if match:
                    events.append({
                        "event_type": event_type,
                        "raw": line,
                        "groups": match.groups()
                    })
                    break
        
        return events
