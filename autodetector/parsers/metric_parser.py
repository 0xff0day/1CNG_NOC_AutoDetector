"""
Metric Parser Engine

Parses command outputs and extracts normalized metrics.
Supports various output formats and vendor-specific patterns.
"""

from __future__ import annotations

import re
import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


@dataclass
class ParsedMetric:
    """Single parsed metric value."""
    name: str
    value: Union[float, int, str, bool]
    unit: str = ""
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseMetricParser(ABC):
    """Abstract base class for metric parsers."""
    
    @abstractmethod
    def parse(self, output: str, command: str = "") -> List[ParsedMetric]:
        """Parse command output and return metrics."""
        pass
    
    @abstractmethod
    def supports(self, command: str, device_type: str) -> bool:
        """Check if parser supports this command/device."""
        pass


class RegexMetricParser(BaseMetricParser):
    """Parser using regex patterns to extract metrics."""
    
    def __init__(self, patterns: Dict[str, str]):
        """
        Initialize with regex patterns.
        
        Args:
            patterns: Dict mapping metric name to regex pattern
        """
        self.patterns = patterns
        self._compiled = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns."""
        for name, pattern in self.patterns.items():
            try:
                self._compiled[name] = re.compile(pattern, re.MULTILINE)
            except re.error as e:
                logger.error(f"Invalid pattern for {name}: {e}")
    
    def parse(self, output: str, command: str = "") -> List[ParsedMetric]:
        """Parse output using regex patterns."""
        metrics = []
        
        for name, compiled in self._compiled.items():
            match = compiled.search(output)
            if match:
                try:
                    # Try to extract numeric value
                    value_str = match.group(1) if match.groups() else match.group(0)
                    
                    # Try int first, then float
                    try:
                        value = int(value_str)
                    except ValueError:
                        try:
                            value = float(value_str)
                        except ValueError:
                            value = value_str
                    
                    metrics.append(ParsedMetric(
                        name=name,
                        value=value,
                        unit=self._detect_unit(name, value_str)
                    ))
                except Exception as e:
                    logger.debug(f"Failed to parse {name}: {e}")
        
        return metrics
    
    def _detect_unit(self, name: str, value_str: str) -> str:
        """Detect unit from metric name or value string."""
        name_lower = name.lower()
        value_lower = value_str.lower()
        
        if "%" in value_lower or "percent" in name_lower:
            return "%"
        elif "mbps" in value_lower or "mb/s" in value_lower:
            return "Mbps"
        elif "gbps" in value_lower or "gb/s" in value_lower:
            return "Gbps"
        elif "ms" in value_lower:
            return "ms"
        elif "sec" in value_lower:
            return "s"
        elif "celsius" in value_lower or "°c" in value_lower:
            return "°C"
        elif "bytes" in name_lower:
            return "B"
        elif "kb" in name_lower and "kbps" not in name_lower:
            return "KB"
        elif "mb" in name_lower and "mbps" not in name_lower:
            return "MB"
        elif "gb" in name_lower and "gbps" not in name_lower:
            return "GB"
        
        return ""
    
    def supports(self, command: str, device_type: str) -> bool:
        """Check support based on command."""
        return True  # Generic parser supports all


class JSONMetricParser(BaseMetricParser):
    """Parser for JSON formatted output."""
    
    def __init__(self, field_mapping: Dict[str, str]):
        """
        Initialize with field mappings.
        
        Args:
            field_mapping: Dict mapping JSON field path to metric name
        """
        self.field_mapping = field_mapping
    
    def parse(self, output: str, command: str = "") -> List[ParsedMetric]:
        """Parse JSON output."""
        metrics = []
        
        try:
            data = json.loads(output)
            
            for json_path, metric_name in self.field_mapping.items():
                value = self._extract_json_path(data, json_path)
                if value is not None:
                    metrics.append(ParsedMetric(
                        name=metric_name,
                        value=value
                    ))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
        except Exception as e:
            logger.error(f"JSON parsing error: {e}")
        
        return metrics
    
    def _extract_json_path(self, data: Any, path: str) -> Any:
        """Extract value from nested JSON using dot notation."""
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                if idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        
        return current
    
    def supports(self, command: str, device_type: str) -> bool:
        """Check if command likely produces JSON."""
        json_indicators = ["json", "format json", "-json"]
        return any(ind in command.lower() for ind in json_indicators)


class TableMetricParser(BaseMetricParser):
    """Parser for tabular/text table output."""
    
    def __init__(
        self,
        column_mapping: Dict[str, str],
        header_row: Optional[int] = None
    ):
        """
        Initialize table parser.
        
        Args:
            column_mapping: Dict mapping column name or index to metric name
            header_row: Row index of header (None for no header)
        """
        self.column_mapping = column_mapping
        self.header_row = header_row
    
    def parse(self, output: str, command: str = "") -> List[ParsedMetric]:
        """Parse table output."""
        metrics = []
        lines = output.strip().splitlines()
        
        if not lines:
            return metrics
        
        # Skip header if specified
        start_row = 0
        if self.header_row is not None:
            start_row = self.header_row + 1
        
        for line in lines[start_row:]:
            if not line.strip() or line.startswith("-"):
                continue
            
            # Split by whitespace or | for table
            if "|" in line:
                cols = [c.strip() for c in line.split("|")]
            else:
                cols = line.split()
            
            for key, metric_name in self.column_mapping.items():
                try:
                    if key.isdigit():
                        idx = int(key)
                        if idx < len(cols):
                            value = self._convert_value(cols[idx])
                            metrics.append(ParsedMetric(
                                name=metric_name,
                                value=value
                            ))
                    else:
                        # Named column - would need header parsing
                        pass
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse column {key}: {e}")
        
        return metrics
    
    def _convert_value(self, value_str: str) -> Union[float, int, str]:
        """Convert string value to appropriate type."""
        value_str = value_str.strip()
        
        # Remove common suffixes
        for suffix in ["%", "ms", "s", "MB", "GB", "KB"]:
            if value_str.endswith(suffix):
                value_str = value_str[:-len(suffix)].strip()
        
        # Try numeric conversion
        try:
            return int(value_str)
        except ValueError:
            try:
                return float(value_str)
            except ValueError:
                return value_str
    
    def supports(self, command: str, device_type: str) -> bool:
        """Generic table parser supports all."""
        return True


class MetricParserEngine:
    """
    Engine that selects and applies appropriate parsers.
    """
    
    def __init__(self):
        self._parsers: List[BaseMetricParser] = []
        self._vendor_parsers: Dict[str, List[BaseMetricParser]] = {}
    
    def register_parser(
        self,
        parser: BaseMetricParser,
        vendors: Optional[List[str]] = None
    ) -> None:
        """
        Register a parser.
        
        Args:
            parser: Parser instance
            vendors: List of vendor OS types this parser handles
        """
        if vendors:
            for vendor in vendors:
                if vendor not in self._vendor_parsers:
                    self._vendor_parsers[vendor] = []
                self._vendor_parsers[vendor].append(parser)
        else:
            self._parsers.append(parser)
    
    def parse(
        self,
        output: str,
        command: str = "",
        device_type: str = "",
        format_hint: str = "auto"
    ) -> List[ParsedMetric]:
        """
        Parse output using appropriate parser.
        
        Args:
            output: Command output
            command: Command that produced output
            device_type: Vendor/OS type
            format_hint: Hint for format (auto, json, table, regex)
        
        Returns:
            List of parsed metrics
        """
        metrics = []
        
        # Try vendor-specific parsers first
        if device_type in self._vendor_parsers:
            for parser in self._vendor_parsers[device_type]:
                if parser.supports(command, device_type):
                    metrics = parser.parse(output, command)
                    if metrics:
                        break
        
        # Try generic parsers
        if not metrics:
            for parser in self._parsers:
                if parser.supports(command, device_type):
                    metrics = parser.parse(output, command)
                    if metrics:
                        break
        
        # Auto-detect if no hint
        if not metrics and format_hint == "auto":
            metrics = self._auto_parse(output, command)
        
        return metrics
    
    def _auto_parse(
        self,
        output: str,
        command: str
    ) -> List[ParsedMetric]:
        """Auto-detect format and parse."""
        # Try JSON first
        try:
            json.loads(output)
            parser = JSONMetricParser({})
            return parser.parse(output, command)
        except json.JSONDecodeError:
            pass
        
        # Try table format
        if "|" in output or output.count("\n") > 2:
            lines = output.splitlines()
            if len(lines) >= 2:
                # Simple heuristic: multiple lines with similar structure
                parser = TableMetricParser({}, header_row=0)
                return parser.parse(output, command)
        
        # Fall back to regex
        return []
    
    def create_vendor_parser(
        self,
        vendor_os: str,
        patterns: Dict[str, str]
    ) -> None:
        """Create and register a regex parser for vendor."""
        parser = RegexMetricParser(patterns)
        self.register_parser(parser, [vendor_os])
        logger.info(f"Created parser for {vendor_os} with {len(patterns)} patterns")


# Pre-defined vendor parsers
CISCO_PATTERNS = {
    "cpu_usage": r"CPU utilization.*?(\d+)%",
    "memory_used": r"Processor Pool Total:.*?(\d+)K",
    "memory_free": r"Processor Pool Total:.*?Used:.*?(\d+)K",
    "uptime": r"uptime is\s+(.*?)(?:\n|$)",
}

JUNOS_PATTERNS = {
    "cpu_idle": r"CPU idle:\s+(\d+)%",
    "memory_util": r"Memory utilization:\s+(\d+)%",
    "active_users": r"(\d+) users",
}

LINUX_PATTERNS = {
    "load_1min": r"load average:\s+([\d.]+)",
    "memory_total": r"Mem:\s+(\d+)",
    "memory_used": r"Mem:\s+\d+\s+(\d+)",
    "cpu_user": r"%Cpu\(s\):\s+([\d.]+)\s+us",
}
