from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class CLICompleter:
    """Command-line autocompletion engine."""
    
    COMMANDS = {
        "scan": {
            "description": "Scan devices for metrics",
            "args": ["device_id", "os", "host", "--tags", "--output"],
            "examples": [
                "nocctl scan --device r1",
                "nocctl scan --host 10.0.0.1 --os cisco_ios",
            ],
        },
        "schedule": {
            "description": "Run scheduled polling",
            "args": ["--mode", "--devices", "--once"],
            "examples": [
                "nocctl schedule --mode normal",
                "nocctl schedule --once",
            ],
        },
        "alerts": {
            "description": "List active alerts",
            "args": ["--severity", "--device", "--acknowledged", "--limit"],
            "examples": [
                "nocctl alerts --severity critical",
                "nocctl alerts --device r1",
            ],
        },
        "ack": {
            "description": "Acknowledge an alert",
            "args": ["alert_id", "--notes"],
            "examples": [
                'nocctl ack ALERT-123 --notes "Checking with vendor"',
            ],
        },
        "report": {
            "description": "Generate reports",
            "args": ["--range", "--format", "--output", "--send"],
            "examples": [
                "nocctl report --range last24h --format json",
                "nocctl report --range today --format xlsx --output ./reports/",
            ],
        },
        "help": {
            "description": "Show help for OS or topic",
            "args": ["os", "topic"],
            "examples": [
                "nocctl help cisco_ios",
                "nocctl help junos interfaces",
            ],
        },
        "discover": {
            "description": "Discover devices on network",
            "args": ["--subnet", "--range", "--method", "--output"],
            "examples": [
                "nocctl discover --subnet 10.0.0.0/24",
                "nocctl discover --range 10.0.0.1-10.0.0.254 --method snmp",
            ],
        },
        "detect-os": {
            "description": "Detect OS of a device",
            "args": ["host", "--transport", "--port"],
            "examples": [
                "nocctl detect-os 10.0.0.1 --transport ssh",
            ],
        },
        "plugin": {
            "description": "Plugin management",
            "args": ["list", "validate", "init", "bootstrap", "--os"],
            "examples": [
                "nocctl plugin list",
                "nocctl plugin validate cisco_ios",
                "nocctl plugin bootstrap",
            ],
        },
        "health": {
            "description": "Check system health",
            "args": ["--verbose", "--check"],
            "examples": [
                "nocctl health",
                "nocctl health --verbose",
            ],
        },
        "backup": {
            "description": "Create or restore backups",
            "args": ["create", "restore", "list", "--name", "--dry-run"],
            "examples": [
                "nocctl backup create",
                "nocctl backup restore backup_20240208",
            ],
        },
        "config": {
            "description": "Configuration management",
            "args": ["validate", "migrate", "export", "--version"],
            "examples": [
                "nocctl config validate",
                "nocctl config migrate --version 1.1.0",
            ],
        },
    }
    
    PLUGIN_OSES = [
        "cisco_ios", "cisco_nxos", "cisco_xr", "cisco_asa",
        "junos", "panos", "fortios", "mikrotik",
        "arista_eos", "huawei_vrp", "edgeos", "pfsense",
        "ubuntu", "debian", "rhel", "centos", "rocky", "alma", "suse",
        "amazon_linux", "freebsd",
        "windows_server",
        "vmware_esxi", "proxmox", "xcpng",
    ]
    
    def __init__(self):
        self.history: List[str] = []
    
    def complete(self, text: str, cursor_pos: int = None) -> List[str]:
        """Get completions for partial command."""
        if cursor_pos is None:
            cursor_pos = len(text)
        
        parts = text[:cursor_pos].split()
        
        if len(parts) == 0:
            # Complete command name
            return [cmd for cmd in self.COMMANDS if cmd.startswith(text)]
        
        if len(parts) == 1:
            # Complete command name
            prefix = parts[0]
            return [cmd for cmd in self.COMMANDS if cmd.startswith(prefix)]
        
        # Complete command arguments
        cmd = parts[0]
        if cmd not in self.COMMANDS:
            return []
        
        cmd_info = self.COMMANDS[cmd]
        current = parts[-1]
        
        # Special completions
        if current.startswith("--"):
            return [arg for arg in cmd_info["args"] if arg.startswith(current)]
        
        if cmd == "scan" and "--os" in parts:
            idx = parts.index("--os") + 1
            if len(parts) == idx or (len(parts) == idx + 1 and parts[idx] == current):
                return [os for os in self.PLUGIN_OSES if os.startswith(current)]
        
        if cmd == "plugin" and "validate" in parts:
            idx = parts.index("validate") + 1
            if len(parts) == idx or (len(parts) == idx + 1 and parts[idx] == current):
                return [os for os in self.PLUGIN_OSES if os.startswith(current)]
        
        if cmd in ["help"]:
            return [os for os in self.PLUGIN_OSES if os.startswith(current)]
        
        return []
    
    def suggest(self, partial: str) -> List[Dict[str, str]]:
        """Get command suggestions with descriptions."""
        suggestions = []
        
        for cmd, info in self.COMMANDS.items():
            if cmd.startswith(partial) or partial in info["description"].lower():
                suggestions.append({
                    "command": cmd,
                    "description": info["description"],
                    "usage": f"nocctl {cmd} {' '.join(info['args'][:3])}...",
                })
        
        return suggestions
    
    def get_help(self, command: str) -> Optional[Dict[str, Any]]:
        """Get detailed help for a command."""
        if command not in self.COMMANDS:
            return None
        
        info = self.COMMANDS[command]
        return {
            "command": command,
            "description": info["description"],
            "arguments": info["args"],
            "examples": info["examples"],
        }
    
    def generate_completion_script(self, shell: str = "bash") -> str:
        """Generate shell completion script."""
        if shell == "bash":
            return self._generate_bash_completion()
        elif shell == "zsh":
            return self._generate_zsh_completion()
        elif shell == "fish":
            return self._generate_fish_completion()
        else:
            raise ValueError(f"Unsupported shell: {shell}")
    
    def _generate_bash_completion(self) -> str:
        """Generate bash completion script."""
        commands = " ".join(self.COMMANDS.keys())
        os_list = " ".join(self.PLUGIN_OSES)
        
        script = f'''#!/bin/bash
_nocctl_complete() {{
    local cur prev opts
    COMPREPLY=()
    cur="${{COMP_WORDS[COMP_CWORD]}}"
    prev="${{COMP_WORDS[COMP_CWORD-1]}}"
    
    # Main commands
    if [[ ${{COMP_CWORD}} -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "{commands}" -- $cur) )
        return 0
    fi
    
    # OS completions for help and plugin commands
    if [[ ${{prev}} == "--os" ]] || [[ ${{prev}} == "validate" ]] || [[ ${{prev}} == "help" ]]; then
        COMPREPLY=( $(compgen -W "{os_list}" -- $cur) )
        return 0
    fi
    
    # Command-specific arguments
    case "${{COMP_WORDS[1]}}" in
        scan)
            opts="--device --os --host --tags --output"
            ;;
        alerts)
            opts="--severity --device --acknowledged --limit"
            ;;
        report)
            opts="--range --format --output --send"
            ;;
        discover)
            opts="--subnet --range --method --output"
            ;;
        *)
            opts=""
            ;;
    esac
    
    COMPREPLY=( $(compgen -W "${{opts}}" -- $cur) )
    return 0
}}

complete -F _nocctl_complete nocctl
'''
        return script
    
    def _generate_zsh_completion(self) -> str:
        """Generate zsh completion script."""
        return f'''#compdef nocctl

_nocctl() {{
    local curcontext="$curcontext" state line
    typeset -A opt_args
    
    _arguments -C \\
        '1: :->command' \\
        '*:: :->args'
    
    case "$state" in
        command)
            _values 'commands' \\
                'scan[Scan devices for metrics]' \\
                'schedule[Run scheduled polling]' \\
                'alerts[List active alerts]' \\
                'ack[Acknowledge an alert]' \\
                'report[Generate reports]' \\
                'help[Show help for OS or topic]' \\
                'discover[Discover devices on network]' \\
                'detect-os[Detect OS of a device]' \\
                'plugin[Plugin management]'
            ;;
        args)
            case "$line[1]" in
                scan|plugin)
                    _values 'os' {' '.join(f"'{os}'" for os in self.PLUGIN_OSES)}
                    ;;
                help)
                    _values 'os' {' '.join(f"'{os}'" for os in self.PLUGIN_OSES)}
                    ;;
            esac
            ;;
    esac
}}

_nocctl "$@"
'''
    
    def _generate_fish_completion(self) -> str:
        """Generate fish completion script."""
        lines = []
        
        for cmd, info in self.COMMANDS.items():
            lines.append(f'complete -c nocctl -n "__fish_use_subcommand" -a "{cmd}" -d "{info["description"]}"')
        
        return "\n".join(lines)
