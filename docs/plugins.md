# Plugin Development Guide

> 📋 **See [Complete Features Reference](FEATURES.md) for all 50+ available modules**

Create custom plugins for new device types.

## Plugin Structure

Each plugin is a directory under `autodetector/plugins/builtin/{os_name}/`:

```
{os_name}/
├── __init__.py          # (optional) Package marker
├── command_map.yaml     # CLI commands to execute
├── variable_map.yaml    # Metric definitions
├── parser.py            # Parsing logic
└── help.yaml            # Help topics
```

## Quick Start

### 1. Initialize Plugin

```bash
# Use CLI to create skeleton
nocctl plugin init my_custom_os --category network --template cisco_ios

# Or create manually
mkdir -p autodetector/plugins/builtin/my_custom_os
cd autodetector/plugins/builtin/my_custom_os
```

### 2. Define Commands

Create `command_map.yaml`:

```yaml
session:
  mode: exec                    # exec or shell
  prompt_regex: "[#>]\\s*$"       # Prompt pattern
  pre_commands:                 # Commands to disable paging
    - "terminal length 0"
    - "enable"

commands:
  # Normal collection commands
  normal:
    cpu: "show processes cpu"
    memory: "show memory statistics"
    interfaces: "show interfaces status"
    interface_errors: "show interfaces counters errors"
    routing: "show ip route summary"
    logs: "show logging last 50"
    uptime: "show version | include uptime"
  
  # Deep audit commands (run less frequently)
  deep_audit:
    config: "show running-config"
    neighbors: "show cdp neighbors detail"
    bgp: "show ip bgp summary"
    ospf: "show ip ospf neighbor"
```

### 3. Define Variables

Create `variable_map.yaml`:

```yaml
schema:
  os: my_custom_os              # Must match directory name
  description: "My Custom Router OS"
  version: "1.0.0"
  
  variables:
    # CPU Usage
    CPU_USAGE:
      type: gauge                 # gauge, counter, state
      unit: percent               # percent, bytes, count, seconds, etc.
      source_command: cpu         # Which command provides this
      description: "CPU utilization percentage"
      weight: 1.2                 # Health score weight (0.0-2.0)
      
    # Memory Usage
    MEMORY_USAGE:
      type: gauge
      unit: percent
      source_command: memory
      description: "Memory utilization percentage"
      weight: 1.0
      
    # Interface Status
    INTERFACE_STATUS:
      type: state                 # Discrete state values
      unit: text                  # State is text: up, down, degraded
      source_command: interfaces
      description: "Interface operational status"
      weight: 1.5
      valid_states:
        - "up"
        - "down"
        - "degraded"
        - "admin-down"
      
    # Interface Errors
    INTERFACE_ERRORS:
      type: counter               # Accumulating counter
      unit: count
      source_command: interface_errors
      description: "Interface error count"
      weight: 1.2
      
    # Routing State
    ROUTING_STATE:
      type: state
      unit: text
      source_command: routing
      description: "Routing table health"
      weight: 1.4
      
    # Log Errors
    LOG_ERRORS:
      type: counter
      unit: count
      source_command: logs
      description: "Error log entries"
      weight: 0.7
      
    # Uptime
    UPTIME:
      type: gauge
      unit: seconds
      source_command: uptime
      description: "System uptime"
      weight: 0.2
```

### 4. Implement Parser

Create `parser.py`:

```python
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def parse(
    outputs: Dict[str, str],
    errors: Dict[str, str],
    device: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Parse CLI outputs into normalized metrics.
    
    Args:
        outputs: Dict mapping command names to raw output strings
        errors: Dict mapping command names to error messages
        device: Device configuration dict with 'id', 'os', etc.
    
    Returns:
        Dict with 'metrics' list and optional 'variables' dict
    """
    metrics: List[Dict[str, Any]] = []
    
    # Helper to safely convert to float
    def safe_float(val: str) -> Optional[float]:
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
    
    # Parse CPU usage
    cpu_output = outputs.get("cpu", "")
    # Example output: "CPU utilization: 45%"
    cpu_match = re.search(r"CPU utilization:\s*(\d+)%", cpu_output, re.IGNORECASE)
    if cpu_match:
        val = safe_float(cpu_match.group(1))
        if val is not None:
            metrics.append({
                "variable": "CPU_USAGE",
                "value": val,
                "unit": "percent",
            })
    
    # Parse memory
    mem_output = outputs.get("memory", "")
    # Example: "Memory used: 45%, free: 55%"
    mem_match = re.search(r"used:\s*(\d+)%", mem_output, re.IGNORECASE)
    if mem_match:
        val = safe_float(mem_match.group(1))
        if val is not None:
            metrics.append({
                "variable": "MEMORY_USAGE",
                "value": val,
                "unit": "percent",
            })
    
    # Parse interface status
    iface_output = outputs.get("interfaces", "")
    # Count up/down interfaces
    up_count = len(re.findall(r"\bup\b", iface_output, re.IGNORECASE))
    down_count = len(re.findall(r"\bdown\b", iface_output, re.IGNORECASE))
    
    if up_count + down_count > 0:
        if down_count == 0:
            status = "up"
        elif up_count == 0:
            status = "down"
        else:
            status = "degraded"
        
        metrics.append({
            "variable": "INTERFACE_STATUS",
            "value_text": status,
            "meta": {
                "up_count": up_count,
                "down_count": down_count,
            }
        })
    
    # Parse interface errors
    error_output = outputs.get("interface_errors", "")
    # Sum all error counters
    error_numbers = re.findall(r"\b(\d+)\s+errors?\b", error_output, re.IGNORECASE)
    total_errors = sum(int(n) for n in error_numbers)
    
    metrics.append({
        "variable": "INTERFACE_ERRORS",
        "value": float(total_errors),
        "unit": "count",
    })
    
    # Parse routing
    route_output = outputs.get("routing", "")
    # Check if routes exist
    route_count = len(re.findall(r"^\s*\d+\.", route_output, re.MULTILINE))
    if route_count > 0:
        route_state = "up"
    else:
        route_state = "degraded"
    
    metrics.append({
        "variable": "ROUTING_STATE",
        "value_text": route_state,
        "meta": {
            "route_count": route_count,
        }
    })
    
    # Parse log errors
    log_output = outputs.get("logs", "")
    # Count error lines
    error_lines = [
        line for line in log_output.splitlines()
        if re.search(r"\b(error|critical|alert|emergency)\b", line, re.IGNORECASE)
    ]
    
    metrics.append({
        "variable": "LOG_ERRORS",
        "value": float(len(error_lines)),
        "unit": "count",
    })
    
    # Parse uptime
    uptime_output = outputs.get("uptime", "")
    # Example: "uptime is 5 days, 3 hours, 25 minutes"
    # Just store as text for now
    uptime_text = uptime_output.strip()
    
    metrics.append({
        "variable": "UPTIME",
        "value_text": uptime_text,
        "unit": "text",
    })
    
    return {
        "metrics": metrics,
        "raw": {
            "errors": errors,
            "outputs_sample": {k: v[:200] for k, v in outputs.items()},  # Truncated for debug
        }
    }
```

### 5. Add Help Topics

Create `help.yaml`:

```yaml
topics:
  overview:
    title: "My Custom OS Overview"
    description: "Enterprise router operating system"
    recommended_commands:
      - "show version"
      - "show processes cpu"
      - "show memory"
      
  cpu:
    title: "CPU Monitoring"
    description: "Monitor CPU utilization and processes"
    recommended_commands:
      - "show processes cpu"
      - "show processes cpu history"
    troubleshooting:
      - "High CPU: Check 'show processes cpu' for top processes"
      - "Use 'show processes cpu sorted' to find culprits"
      
  memory:
    title: "Memory Monitoring"
    description: "Monitor memory utilization"
    recommended_commands:
      - "show memory statistics"
      - "show processes memory"
      
  interfaces:
    title: "Interface Monitoring"
    description: "Check interface status and errors"
    recommended_commands:
      - "show interfaces status"
      - "show interfaces counters"
      - "show interfaces counters errors"
    troubleshooting:
      - "Interface down: Check cable and port status"
      - "High errors: Check duplex/speed mismatch"
      
  routing:
    title: "Routing Monitoring"
    description: "Verify routing table health"
    recommended_commands:
      - "show ip route summary"
      - "show ip route"
      - "show routing protocol"
    troubleshooting:
      - "No routes: Check routing protocol adjacencies"
      - "Missing routes: Verify route redistribution"
```

## Testing Your Plugin

### 1. Validate Plugin

```bash
nocctl plugin validate my_custom_os
```

Expected output:
```json
{
  "ok": true,
  "os": "my_custom_os",
  "command_map": {"ok": true, "errors": []},
  "variable_map": {"ok": true, "errors": []}
}
```

### 2. Test Parsing

```python
# test_parser.py
from autodetector.plugin.loader import PluginLoader

loader = PluginLoader()
plugin = loader.load("my_custom_os")

# Sample outputs
outputs = {
    "cpu": "CPU utilization: 45%",
    "memory": "Memory used: 60%, free: 40%",
    "interfaces": "Interface1 up\nInterface2 up\nInterface3 down",
    "interface_errors": "100 errors",
    "routing": "10.0.0.0/24 via 10.0.1.1",
    "logs": "Error: Interface down\nWarning: High CPU",
    "uptime": "uptime is 5 days",
}

result = plugin.parse(outputs, {}, {"id": "test-device"})
print(f"Parsed {len(result['metrics'])} metrics")
for m in result['metrics']:
    print(f"  - {m['variable']}: {m.get('value', m.get('value_text', 'N/A'))}")
```

### 3. Integration Test

```bash
# Add test device to config
cat >> config/config.yaml << 'EOF'
devices:
  - id: test-myos
    name: "Test My Custom OS"
    host: "192.168.1.100"
    transport: "ssh"
    os: "my_custom_os"
    credential_ref: "test-creds"
EOF

# Run scan
nocctl scan --device test-myos --once --verbose
```

## Advanced Topics

### Handling Different Output Formats

```python
def parse_cpu(output: str) -> Optional[float]:
    """Parse CPU from various formats."""
    patterns = [
        r"CPU utilization:\s*(\d+)%",           # Standard
        r"cpu:\s*(\d+)\s*%",                    # Lowercase
        r"five seconds:\s*(\d+)%",              # Cisco style
        r"load average:\s*[\d.]+,\s*[\d.]+,\s*(\d+)",  # Load average
    ]
    
    for pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE)
        if match:
            return safe_float(match.group(1))
    
    return None
```

### Multi-Command Variables

Some metrics need multiple commands:

```python
def parse_memory_with_calculation(outputs: Dict[str, str]) -> Optional[Dict]:
    """Calculate memory percentage from total/used."""
    total_output = outputs.get("memory_total", "")
    used_output = outputs.get("memory_used", "")
    
    total_match = re.search(r"Total:\s*(\d+)", total_output)
    used_match = re.search(r"Used:\s*(\d+)", used_output)
    
    if total_match and used_match:
        total = int(total_match.group(1))
        used = int(used_match.group(1))
        if total > 0:
            pct = (used / total) * 100
            return {"value": round(pct, 2), "meta": {"total": total, "used": used}}
    
    return None
```

### State-Based Variables

```python
def parse_interface_states(output: str) -> List[Dict]:
    """Parse per-interface states."""
    interfaces = []
    
    # Parse interface table
    for line in output.splitlines():
        # Match: "Eth0/0 up 1000mbps"
        match = re.match(r"(\S+)\s+(up|down)\s+(\d+)mbps", line)
        if match:
            iface, state, speed = match.groups()
            interfaces.append({
                "interface": iface,
                "state": state,
                "speed_mbps": int(speed),
            })
    
    return interfaces
```

### Error Handling

```python
def parse_with_error_handling(outputs: Dict[str, str], errors: Dict[str, str]) -> Dict:
    """Parse with detailed error tracking."""
    metrics = []
    parse_errors = []
    
    # Check for command errors
    for cmd, error in errors.items():
        if error:
            parse_errors.append({
                "command": cmd,
                "error": error,
            })
    
    # Try to parse each command
    try:
        cpu = parse_cpu(outputs.get("cpu", ""))
        if cpu:
            metrics.append({"variable": "CPU_USAGE", "value": cpu})
    except Exception as e:
        parse_errors.append({
            "command": "cpu",
            "error": f"Parse error: {str(e)}",
        })
    
    return {
        "metrics": metrics,
        "parse_errors": parse_errors,
        "success": len(parse_errors) == 0,
    }
```

## Best Practices

### 1. Regex Patterns

```python
# Bad - too strict
re.search(r"CPU: (\d+)%", output)

# Good - flexible
re.search(r"cpu.*?([0-9.]+)\s*%", output, re.IGNORECASE | re.DOTALL)
```

### 2. Unit Conversion

```python
def convert_to_bytes(value: str, unit: str) -> int:
    """Convert various units to bytes."""
    multipliers = {
        "b": 1,
        "kb": 1024,
        "mb": 1024**2,
        "gb": 1024**3,
        "tb": 1024**4,
    }
    
    val = safe_float(value)
    mult = multipliers.get(unit.lower(), 1)
    return int(val * mult)
```

### 3. Defensive Parsing

```python
def safe_parse(func, *args, **kwargs) -> Optional[Any]:
    """Wrap parser functions with error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # Log error but don't crash
        print(f"Parse error in {func.__name__}: {e}")
        return None
```

## Registering Your Plugin

### Add to Registry

Edit `autodetector/plugins/builtin/_registry.yaml`:

```yaml
plugins:
  network:
    - name: my_custom_os
      display_name: "My Custom Router OS"
      vendor: "MyVendor"
      category: network
      status: experimental
      
  server:
    # ... existing servers
    
  hypervisor:
    # ... existing hypervisors
```

### Validate Registration

```bash
# List plugins to confirm
nocctl plugin list --category network

# Should show: my_custom_os
```

## Debugging Tips

### Enable Debug Output

```bash
nocctl scan --device test-myos --verbose 2>&1 | tee debug.log
```

### Test Parser in REPL

```python
import sys
sys.path.insert(0, '/path/to/project')

from autodetector.plugins.builtin.my_custom_os import parser

# Test with real output
outputs = {
    "cpu": open('/tmp/cpu_output.txt').read(),
}

result = parser.parse(outputs, {}, {"id": "test"})
print(result)
```

### Mock Data Generator

```python
# mock_data.py
def generate_mock_outputs() -> Dict[str, str]:
    """Generate realistic mock data for testing."""
    return {
        "cpu": "CPU utilization: 45%",
        "memory": "Memory used: 60%, free: 40%",
        "interfaces": "\n".join([
            "Gig0/0 up 1000mbps",
            "Gig0/1 up 1000mbps",
            "Gig0/2 down 0mbps",
        ]),
        "uptime": "uptime is 5 days, 3 hours",
    }
```

## Examples

### Simple Network Device

See: `autodetector/plugins/builtin/mikrotik/`

### Complex Multi-OS Device

See: `autodetector/plugins/builtin/cisco_ios/`

### Server OS

See: `autodetector/plugins/builtin/ubuntu/`

### Hypervisor

See: `autodetector/plugins/builtin/vmware_esxi/`

## Submitting Your Plugin

1. **Test thoroughly**: Validate with `nocctl plugin validate`
2. **Document**: Add help topics
3. **Mock data**: Create test fixtures
4. **Register**: Add to `_registry.yaml`
5. **PR**: Submit pull request with:
   - Plugin files
   - Test cases
   - Documentation updates

---

For questions or issues, see [Troubleshooting](troubleshooting.md).

---

## 👥 Credits & Community

Created by: **Lily Yang**, **0xff**, **Community**, **Black Roots**, **CifSec**  
Sponsored by: **1Cloud Next Generation (1CNG)**

🌐 [1cng.cloud](https://1cng.cloud) | 💬 [Telegram](https://t.me/noc_community) | 🐦 [@1CNG_NOC](https://twitter.com/1CNG_NOC)

See [CREDITS.md](CREDITS.md) for full details.
