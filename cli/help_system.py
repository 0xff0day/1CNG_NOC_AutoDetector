"""
CLI Help System

Interactive help and documentation for CLI commands.
Provides command reference, examples, and troubleshooting.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import textwrap


class HelpCategory(Enum):
    """Help topic categories."""
    GETTING_STARTED = "getting_started"
    COMMANDS = "commands"
    CONFIGURATION = "configuration"
    TROUBLESHOOTING = "troubleshooting"
    ADVANCED = "advanced"


@dataclass
class HelpTopic:
    """Help topic definition."""
    name: str
    category: HelpCategory
    title: str
    content: str
    examples: List[str]
    related_topics: List[str]
    aliases: List[str]


class CLIHelpSystem:
    """
    Interactive help system for the NOC CLI.
    
    Features:
    - Topic search
    - Command reference
    - Usage examples
    - Troubleshooting guides
    """
    
    def __init__(self):
        self.topics: Dict[str, HelpTopic] = {}
        self.commands: Dict[str, Dict] = {}
        self._setup_default_topics()
    
    def _setup_default_topics(self) -> None:
        """Setup default help topics."""
        topics_data = [
            {
                "name": "overview",
                "category": HelpCategory.GETTING_STARTED,
                "title": "NOC AutoDetector Overview",
                "content": """
The NOC AutoDetector is a CLI-based network monitoring system.

Key Features:
• Monitor 50+ device types (routers, switches, servers, hypervisors)
• AI-powered anomaly detection and trend analysis
• Automatic device discovery and OS detection
• Multi-channel alerting (Telegram, Voice, Email)
• Time-series metrics storage
• Customizable health scoring

Quick Start:
1. Add devices: nocctl device add <hostname>
2. Run discovery: nocctl scan auto
3. Start monitoring: nocctl daemon start
4. View status: nocctl status
                """,
                "examples": ["nocctl --help", "nocctl status"],
                "related": ["installation", "configuration", "commands"],
                "aliases": ["intro", "about"]
            },
            {
                "name": "commands",
                "category": HelpCategory.COMMANDS,
                "title": "Command Reference",
                "content": """
Core Commands:

Device Management:
  device add       - Add a new device
  device list      - List all devices
  device remove    - Remove a device
  device scan      - Scan single device

Monitoring:
  status           - Show overall status
  health           - Show device health
  alerts           - Show active alerts
  metrics          - Show device metrics

Discovery:
  scan auto        - Auto-discover devices
  scan network     - Scan network range

Reporting:
  report excel     - Generate Excel report
  report json      - Export to JSON
  report txt       - Generate text report

Configuration:
  config show      - Show configuration
  config set       - Set configuration value
  config reload    - Reload configuration

AI Features:
  ai predict       - Predict future trends
  ai analyze       - Analyze device patterns
  ai train         - Train custom models
                """,
                "examples": ["nocctl device list", "nocctl status --verbose"],
                "related": ["overview", "configuration"],
                "aliases": ["cmd", "reference"]
            },
            {
                "name": "configuration",
                "category": HelpCategory.CONFIGURATION,
                "title": "Configuration Guide",
                "content": """
Configuration Files:

Main config: ~/.noc/config.yaml
Credentials: ~/.noc/credentials.enc
Device DB:   ~/.noc/devices.db

Key Settings:
• polling.interval - How often to poll devices (seconds)
• alerting.telegram.token - Bot API token
• alerting.telegram.chat_id - Default chat ID
• discovery.networks - Networks to scan
• ai.enabled - Enable AI features
• storage.retention_days - Data retention

Environment Variables:
  NOC_CONFIG_PATH - Override config location
  NOC_LOG_LEVEL   - Set logging level
  NOC_VAULT_KEY   - Master key for credential vault

Example config.yaml:
  polling:
    interval: 300
    timeout: 30
    retry: 3
  
  alerting:
    telegram:
      enabled: true
      token: "your_bot_token"
      chat_id: "your_chat_id"
                """,
                "examples": ["nocctl config show", "nocctl config set polling.interval 60"],
                "related": ["commands", "troubleshooting"],
                "aliases": ["config", "settings"]
            },
            {
                "name": "troubleshooting",
                "category": HelpCategory.TROUBLESHOOTING,
                "title": "Troubleshooting Guide",
                "content": """
Common Issues:

Connection Failures:
• Check SSH/Telnet connectivity
• Verify credentials in vault
• Check device firewall rules
• Test with: nocctl device test <device_id>

High CPU Usage:
• Reduce polling frequency: nocctl config set polling.interval 600
• Disable unnecessary metrics
• Use selective device groups

Missing Alerts:
• Check Telegram token is valid
• Verify bot has access to chat
• Test notification: nocctl notify test

Database Errors:
• Check disk space
• Verify permissions on ~/.noc/
• Run: nocctl db verify

Discovery Not Finding Devices:
• Check SNMP community strings
• Verify network range
• Check firewall for ICMP
• Enable verbose mode: nocctl scan auto --verbose

AI Not Working:
• Verify Python dependencies installed
• Check model files exist
• Review logs: nocctl logs --tail 100
• Rebuild models: nocctl ai rebuild
                """,
                "examples": ["nocctl device test router1", "nocctl logs --tail 50"],
                "related": ["configuration", "commands"],
                "aliases": ["debug", "issues", "faq"]
            },
        ]
        
        for data in topics_data:
            topic = HelpTopic(
                name=data["name"],
                category=data["category"],
                title=data["title"],
                content=textwrap.dedent(data["content"]).strip(),
                examples=data["examples"],
                related_topics=data["related"],
                aliases=data.get("aliases", [])
            )
            self.register_topic(topic)
    
    def register_topic(self, topic: HelpTopic) -> None:
        """Register a help topic."""
        self.topics[topic.name] = topic
        
        # Register aliases
        for alias in topic.aliases:
            self.topics[alias] = topic
    
    def register_command(
        self,
        command: str,
        description: str,
        usage: str,
        arguments: List[Dict],
        examples: List[str]
    ) -> None:
        """Register a CLI command for help."""
        self.commands[command] = {
            "description": description,
            "usage": usage,
            "arguments": arguments,
            "examples": examples
        }
    
    def show_help(
        self,
        topic_or_command: Optional[str] = None
    ) -> str:
        """
        Get help text for topic or command.
        
        Args:
            topic_or_command: Topic name, command, or None for general help
        
        Returns:
            Formatted help text
        """
        if topic_or_command is None:
            return self._general_help()
        
        # Check topics
        if topic_or_command in self.topics:
            return self._format_topic(self.topics[topic_or_command])
        
        # Check commands
        if topic_or_command in self.commands:
            return self._format_command(topic_or_command, self.commands[topic_or_command])
        
        # Search for similar
        matches = self._search_topics(topic_or_command)
        if matches:
            return f"Topic '{topic_or_command}' not found. Did you mean:\n" + \
                   "\n".join(f"  • {m}" for m in matches[:5])
        
        return f"No help found for '{topic_or_command}'. Use 'help' for available topics."
    
    def _general_help(self) -> str:
        """Generate general help text."""
        lines = [
            "NOC AutoDetector - Network Operations Center Monitoring System",
            "",
            "Usage: nocctl <command> [options]",
            "",
            "Getting Started:",
            "  nocctl help overview      - System overview",
            "  nocctl help commands      - Command reference",
            "  nocctl help configuration - Configuration guide",
            "",
            "Common Commands:",
            "  nocctl status             - Show system status",
            "  nocctl device list        - List devices",
            "  nocctl scan auto          - Auto-discover devices",
            "  nocctl health             - Show health overview",
            "  nocctl alerts             - Show active alerts",
            "",
            "Help Topics:",
        ]
        
        for name, topic in sorted(self.topics.items()):
            if name == topic.name:  # Don't show aliases
                lines.append(f"  {name:<20} - {topic.title}")
        
        lines.extend([
            "",
            "For detailed help: nocctl help <topic>",
            "For command help: nocctl <command> --help"
        ])
        
        return "\n".join(lines)
    
    def _format_topic(self, topic: HelpTopic) -> str:
        """Format a help topic for display."""
        lines = [
            f"{topic.title}",
            "=" * len(topic.title),
            "",
            topic.content,
            "",
        ]
        
        if topic.examples:
            lines.extend(["Examples:", ""])
            for ex in topic.examples:
                lines.append(f"  $ {ex}")
            lines.append("")
        
        if topic.related_topics:
            lines.extend([
                "See also:",
                "  " + ", ".join(topic.related_topics),
                ""
            ])
        
        return "\n".join(lines)
    
    def _format_command(self, name: str, cmd: Dict) -> str:
        """Format command help."""
        lines = [
            f"Command: {name}",
            "",
            cmd["description"],
            "",
            f"Usage: {cmd['usage']}",
            "",
        ]
        
        if cmd["arguments"]:
            lines.append("Arguments:")
            for arg in cmd["arguments"]:
                req = "required" if arg.get("required") else "optional"
                lines.append(f"  {arg['name']:<20} {arg['description']} ({req})")
            lines.append("")
        
        if cmd["examples"]:
            lines.append("Examples:")
            for ex in cmd["examples"]:
                lines.append(f"  $ {ex}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _search_topics(self, query: str) -> List[str]:
        """Search for topics matching query."""
        matches = []
        query_lower = query.lower()
        
        for name, topic in self.topics.items():
            if name == topic.name:  # Skip aliases
                if query_lower in name.lower() or query_lower in topic.title.lower():
                    matches.append(name)
        
        return matches
    
    def list_topics(self, category: Optional[HelpCategory] = None) -> List[str]:
        """List available topics."""
        topics = []
        
        for name, topic in self.topics.items():
            if name == topic.name:
                if category is None or topic.category == category:
                    topics.append(name)
        
        return topics


class InteractiveHelp:
    """
    Interactive help mode for exploring documentation.
    """
    
    def __init__(self, help_system: CLIHelpSystem):
        self.help_system = help_system
    
    def interactive_mode(self) -> None:
        """Start interactive help mode."""
        print("NOC Help System - Interactive Mode")
        print("Type 'quit' to exit, 'list' for topics\n")
        
        while True:
            try:
                query = input("help> ").strip()
                
                if query.lower() in ["quit", "exit", "q"]:
                    break
                
                if query.lower() == "list":
                    for topic in sorted(self.help_system.list_topics()):
                        print(f"  • {topic}")
                    continue
                
                if query:
                    print()
                    print(self.help_system.show_help(query))
                    print()
                
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n")
                break
        
        print("Exiting help.")
