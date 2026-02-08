"""
Command Knowledge Base

Stores and retrieves command documentation, examples, and best practices.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandKnowledge:
    """Knowledge entry for a command."""
    command: str
    description: str
    full_syntax: str
    parameters: List[Dict[str, Any]]
    examples: List[Dict[str, str]]
    best_practices: List[str]
    common_mistakes: List[str]
    related_commands: List[str]
    version_added: str
    last_updated: str


class CommandKnowledgeBase:
    """
    Knowledge base for CLI commands.
    
    Provides:
    - Detailed command documentation
    - Usage examples
    - Best practices
    - Common mistakes to avoid
    """
    
    def __init__(self, kb_path: Optional[str] = None):
        self.kb_path = Path(kb_path) if kb_path else None
        self._commands: Dict[str, CommandKnowledge] = {}
        self._load_builtin_knowledge()
    
    def _load_builtin_knowledge(self) -> None:
        """Load built-in command knowledge."""
        builtin_data = {
            "device_add": {
                "command": "device add",
                "description": "Add a new device to monitoring",
                "full_syntax": "nocctl device add <hostname> [--type TYPE] [--group GROUP] [--credentials ID]",
                "parameters": [
                    {"name": "hostname", "required": True, "description": "Device hostname or IP"},
                    {"name": "--type", "required": False, "description": "Device type (router, switch, server)"},
                    {"name": "--group", "required": False, "description": "Device group to assign"},
                    {"name": "--credentials", "required": False, "description": "Credential vault ID"},
                ],
                "examples": [
                    {"command": "nocctl device add router1", "description": "Add with auto-detection"},
                    {"command": "nocctl device add 192.168.1.1 --type cisco_ios", "description": "Add with specific type"},
                    {"command": "nocctl device add server1 --group production", "description": "Add to group"},
                ],
                "best_practices": [
                    "Always verify connectivity before adding",
                    "Use descriptive hostnames",
                    "Assign to appropriate groups for organization",
                    "Test credentials before bulk addition",
                ],
                "common_mistakes": [
                    "Adding devices without proper credentials",
                    "Using IP addresses that change (use DNS if possible)",
                    "Forgetting to assign to groups",
                ],
                "related_commands": ["device remove", "device scan", "device list"],
                "version_added": "1.0.0",
                "last_updated": "2024-01-15"
            },
            "scan_auto": {
                "command": "scan auto",
                "description": "Automatically discover devices on configured networks",
                "full_syntax": "nocctl scan auto [--networks NETWORKS] [--snmp-community COMMUNITY]",
                "parameters": [
                    {"name": "--networks", "required": False, "description": "Comma-separated networks (CIDR)"},
                    {"name": "--snmp-community", "required": False, "description": "SNMP community string"},
                    {"name": "--icmp", "required": False, "description": "Use ping sweep only"},
                ],
                "examples": [
                    {"command": "nocctl scan auto", "description": "Use configured networks"},
                    {"command": "nocctl scan auto --networks 192.168.1.0/24,10.0.0.0/24", "description": "Scan specific networks"},
                ],
                "best_practices": [
                    "Start with small network segments",
                    "Use SNMP for best discovery results",
                    "Review discovered devices before adding all",
                    "Run during low-traffic periods",
                ],
                "common_mistakes": [
                    "Scanning huge networks at once",
                    "Not configuring SNMP communities first",
                    "Adding all discovered devices without review",
                ],
                "related_commands": ["scan network", "device add", "config set"],
                "version_added": "1.0.0",
                "last_updated": "2024-01-15"
            },
            "health": {
                "command": "health",
                "description": "Show device health status and scores",
                "full_syntax": "nocctl health [device_id] [--format FORMAT] [--history]",
                "parameters": [
                    {"name": "device_id", "required": False, "description": "Specific device to check"},
                    {"name": "--format", "required": False, "description": "Output format (table, json, yaml)"},
                    {"name": "--history", "required": False, "description": "Show health history"},
                ],
                "examples": [
                    {"command": "nocctl health", "description": "Show all devices health"},
                    {"command": "nocctl health router1", "description": "Check specific device"},
                    {"command": "nocctl health --format json", "description": "JSON output"},
                ],
                "best_practices": [
                    "Review health scores regularly",
                    "Investigate devices with dropping scores",
                    "Use trends to predict issues",
                ],
                "common_mistakes": [
                    "Ignoring warning-level health scores",
                    "Not investigating health score trends",
                ],
                "related_commands": ["status", "metrics", "alerts"],
                "version_added": "1.0.0",
                "last_updated": "2024-01-15"
            },
            "ai_predict": {
                "command": "ai predict",
                "description": "Predict future metric values and capacity needs",
                "full_syntax": "nocctl ai predict <device_id> <variable> [--hours HOURS]",
                "parameters": [
                    {"name": "device_id", "required": True, "description": "Target device"},
                    {"name": "variable", "required": True, "description": "Metric to predict (cpu, memory, disk)"},
                    {"name": "--hours", "required": False, "description": "Prediction horizon (default 24)"},
                ],
                "examples": [
                    {"command": "nocctl ai predict server1 disk --hours 72", "description": "Predict disk usage 3 days out"},
                    {"command": "nocctl ai predict router1 cpu", "description": "Predict CPU for next 24h"},
                ],
                "best_practices": [
                    "Use at least 7 days of historical data",
                    "Review predictions daily for capacity planning",
                    "Set alerts for predicted threshold breaches",
                ],
                "common_mistakes": [
                    "Trusting predictions with limited history",
                    "Not accounting for scheduled changes",
                ],
                "related_commands": ["ai analyze", "ai train", "trends"],
                "version_added": "1.2.0",
                "last_updated": "2024-01-20"
            },
        }
        
        for name, data in builtin_data.items():
            self._commands[name] = CommandKnowledge(
                command=data["command"],
                description=data["description"],
                full_syntax=data["full_syntax"],
                parameters=data["parameters"],
                examples=data["examples"],
                best_practices=data["best_practices"],
                common_mistakes=data["common_mistakes"],
                related_commands=data["related_commands"],
                version_added=data["version_added"],
                last_updated=data["last_updated"]
            )
    
    def get_knowledge(self, command: str) -> Optional[CommandKnowledge]:
        """Get knowledge for a command."""
        # Try exact match
        if command in self._commands:
            return self._commands[command]
        
        # Try with underscores
        command_normalized = command.replace(" ", "_")
        if command_normalized in self._commands:
            return self._commands[command_normalized]
        
        return None
    
    def search(self, query: str) -> List[str]:
        """Search for commands matching query."""
        results = []
        query_lower = query.lower()
        
        for name, knowledge in self._commands.items():
            if (query_lower in name.lower() or 
                query_lower in knowledge.description.lower() or
                any(query_lower in p.get("name", "") for p in knowledge.parameters)):
                results.append(name)
        
        return results
    
    def format_knowledge(self, knowledge: CommandKnowledge) -> str:
        """Format command knowledge for display."""
        lines = [
            f"Command: {knowledge.command}",
            f"Version: {knowledge.version_added} (updated: {knowledge.last_updated})",
            "",
            f"Description: {knowledge.description}",
            "",
            f"Syntax: {knowledge.full_syntax}",
            "",
            "Parameters:",
        ]
        
        for param in knowledge.parameters:
            req = "required" if param.get("required") else "optional"
            lines.append(f"  {param['name']:<20} - {param['description']} ({req})")
        
        lines.extend(["", "Examples:"])
        for example in knowledge.examples:
            lines.append(f"  $ {example['command']}")
            lines.append(f"    # {example['description']}")
        
        lines.extend(["", "Best Practices:"])
        for bp in knowledge.best_practices:
            lines.append(f"  • {bp}")
        
        lines.extend(["", "Common Mistakes to Avoid:"])
        for mistake in knowledge.common_mistakes:
            lines.append(f"  ⚠ {mistake}")
        
        if knowledge.related_commands:
            lines.extend([
                "",
                "Related Commands:",
                "  " + ", ".join(knowledge.related_commands)
            ])
        
        return "\n".join(lines)
    
    def list_all_commands(self) -> List[str]:
        """List all documented commands."""
        return list(self._commands.keys())
    
    def save_to_file(self, filepath: str) -> None:
        """Save knowledge base to JSON file."""
        data = {
            name: {
                "command": k.command,
                "description": k.description,
                "full_syntax": k.full_syntax,
                "parameters": k.parameters,
                "examples": k.examples,
                "best_practices": k.best_practices,
                "common_mistakes": k.common_mistakes,
                "related_commands": k.related_commands,
                "version_added": k.version_added,
                "last_updated": k.last_updated,
            }
            for name, k in self._commands.items()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_from_file(self, filepath: str) -> None:
        """Load knowledge base from JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for name, cmd_data in data.items():
            self._commands[name] = CommandKnowledge(**cmd_data)
