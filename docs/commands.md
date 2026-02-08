# Command Reference

> 📋 **See [Complete Features Reference](FEATURES.md) for all 50+ modules that these commands control**

Complete reference for all `nocctl` commands.

## Global Options

```bash
nocctl [GLOBAL_OPTIONS] <command> [args]
```

| Option | Description |
|--------|-------------|
| `--config PATH` | Configuration file path (default: config/config.yaml) |
| `--verbose, -v` | Enable verbose output |
| `--help, -h` | Show help message |

---

## Core Commands

### scan
Scan a device or group of devices for metrics.

```bash
nocctl scan [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--device ID` | Device ID to scan | `--device r1` |
| `--os TYPE` | OS type (auto-detected if not specified) | `--os cisco_ios` |
| `--host IP` | Target host IP/hostname | `--host 10.0.0.1` |
| `--tags TAGS` | Filter devices by tags (comma-separated) | `--tags network,core` |
| `--output FORMAT` | Output format: json, text, table | `--output json` |
| `--once` | Run once and exit (don't schedule) | `--once` |

**Examples:**
```bash
# Scan specific device
nocctl scan --device r1

# Scan by IP with OS hint
nocctl scan --host 10.0.0.1 --os cisco_ios

# Scan all core network devices
nocctl scan --tags core --output json

# Quick one-off scan
nocctl scan --host 192.168.1.1 --os mikrotik --once
```

---

### workflow
Manage and execute the NOC workflow pipeline.

#### workflow run
Execute the complete workflow pipeline for devices.

```bash
nocctl workflow run [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--devices IDS` | Comma-separated device IDs | `--devices r1,r2,srv1` |
| `--all` | Run for all configured devices | `--all` |
| `--skip STAGES` | Skip specific stages (comma-separated) | `--skip observe,report` |
| `--parallel N` | Parallel execution limit | `--parallel 5` |
| `--verbose, -v` | Show detailed stage output | `--verbose` |

**Examples:**
```bash
# Run workflow for specific devices
nocctl workflow run --devices r1,r2,r3

# Run for all devices with verbose output
nocctl workflow run --all --verbose

# Skip discovery and reporting (useful for testing)
nocctl workflow run --device r1 --skip observe,report
```

#### workflow status
Check workflow execution status.

```bash
nocctl workflow status [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--pipeline ID` | Check specific pipeline | `--pipeline PIPE-ABC123` |
| `--device ID` | Show device workflow history | `--device r1` |
| `--running` | Show only running workflows | `--running` |

**Examples:**
```bash
# Check specific pipeline
nocctl workflow status --pipeline PIPE-ABC123

# Check all running workflows
nocctl workflow status --running

# Show device workflow history
nocctl workflow status --device r1
```

#### workflow trace
Trace complete workflow execution with stage details.

```bash
nocctl workflow trace <pipeline_id>
```

**Example:**
```bash
nocctl workflow trace PIPE-ABC123
```

Output shows:
- Stage-by-stage execution
- Input/output data flow
- Duration per stage
- Errors and diagnostics

#### workflow history
Show workflow execution history.

```bash
nocctl workflow history [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--device ID` | Filter by device | `--device r1` |
| `--status STATUS` | Filter by status (completed/failed) | `--status failed` |
| `--limit N` | Limit results (default: 20) | `--limit 50` |
| `--since TIME` | Show since timestamp | `--since 2024-01-01T00:00:00` |

**Examples:**
```bash
# Show recent failures
nocctl workflow history --status failed --limit 10

# Show device history
nocctl workflow history --device r1 --limit 5
```

#### workflow schedule
Schedule automatic workflow execution.

```bash
nocctl workflow schedule <device_id> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--interval SEC` | Polling interval in seconds | `--interval 60` |
| `--enable` | Enable scheduled scanning | `--enable` |
| `--disable` | Disable scheduled scanning | `--disable` |
| `--mode MODE` | Polling mode: fast/normal/deep | `--mode normal` |

**Examples:**
```bash
# Enable 60-second polling for device
nocctl workflow schedule r1 --interval 60 --enable

# Disable scheduled scanning
nocctl workflow schedule r1 --disable

# Use fast polling mode
nocctl workflow schedule core-switch --interval 10 --mode fast
```

#### workflow diagram
Generate workflow pipeline diagrams.

```bash
nocctl workflow diagram [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--format FMT` | Output format: text, mermaid, graphviz | `--format mermaid` |
| `--output FILE` | Save to file | `--output diagram.mmd` |

**Examples:**
```bash
# Generate text diagram
nocctl workflow diagram

# Generate Mermaid diagram
nocctl workflow diagram --format mermaid --output workflow.mmd

# Generate Graphviz DOT
nocctl workflow diagram --format graphviz | dot -Tpng > workflow.png
```

---

### alerts
Manage and view alerts.

#### alerts list
List active or historical alerts.

```bash
nocctl alerts [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--severity LEVEL` | Filter by severity (critical/warning/info) | `--severity critical` |
| `--device ID` | Filter by device | `--device r1` |
| `--variable VAR` | Filter by variable name | `--variable CPU_USAGE` |
| `--acknowledged` | Show acknowledged alerts | `--acknowledged` |
| `--unacknowledged` | Show unacknowledged (default) | `--unacknowledged` |
| `--limit N` | Limit results | `--limit 50` |
| `--format FMT` | Output format | `--format json` |
| `--history` | Show alert history (not just active) | `--history` |

**Examples:**
```bash
# Show all unacknowledged critical alerts
nocctl alerts --severity critical --unacknowledged

# Show alerts for specific device
nocctl alerts --device r1 --limit 20

# Show alert history in JSON
nocctl alerts --history --format json

# Show all CPU-related alerts
nocctl alerts --variable CPU_USAGE --severity warning
```

#### alerts ack
Acknowledge an alert.

```bash
nocctl alerts ack <alert_id> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--notes TEXT` | Acknowledgment notes | `--notes "Checking with vendor"` |
| `--by USER` | Acknowledging user | `--by noc-engineer-1` |
| `--suppress N` | Suppress similar alerts for N minutes | `--suppress 30` |

**Examples:**
```bash
# Acknowledge with notes
nocctl alerts ack ALERT-20240208-001 --notes "Fiber link flapping, ISP notified"

# Acknowledge and suppress for 1 hour
nocctl alerts ack ALERT-20240208-001 --notes "Known issue" --suppress 60
```

#### alerts resolve
Mark alert as resolved.

```bash
nocctl alerts resolve <alert_id> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--notes TEXT` | Resolution notes | `--notes "Interface recovered"` |
| `--resolution TYPE` | Resolution type (auto/manual/temporary) | `--resolution manual` |

#### alerts suppress
Suppress alerts matching criteria.

```bash
nocctl alerts suppress [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--device ID` | Suppress device alerts | `--device r1` |
| `--variable VAR` | Suppress variable | `--variable CPU_USAGE` |
| `--duration MIN` | Suppression duration | `--duration 60` |
| `--reason TEXT` | Reason for suppression | `--reason "Maintenance window"` |

**Example:**
```bash
# Suppress CPU alerts during maintenance
nocctl alerts suppress --device srv1 --variable CPU_USAGE --duration 120 --reason "OS patching"
```

---

### report
Generate and send reports.

```bash
nocctl report [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--range RANGE` | Time range | `--range today` |
| `--start TIME` | Start time | `--start 2024-02-01T00:00:00` |
| `--end TIME` | End time | `--end 2024-02-08T23:59:59` |
| `--format FMT` | Output format: json, xlsx, txt, html | `--format xlsx` |
| `--output DIR` | Output directory | `--output ./reports/` |
| `--send CHANNEL` | Send via: telegram, email | `--send telegram` |
| `--category CAT` | Report category | `--category network` |
| `--devices IDS` | Filter devices | `--devices r1,r2,r3` |

**Time Range Presets:**
- `last5min`, `last15min`, `last30min`
- `last1h`, `last6h`, `last12h`, `last24h`
- `today`, `yesterday`
- `thisweek`, `lastweek`
- `thismonth`, `lastmonth`
- `thisyear`

**Categories:**
- `network` - Network device metrics
- `server` - Server metrics
- `hypervisor` - Virtualization metrics
- `performance` - Performance summary
- `security` - Security logs and events
- `capacity` - Capacity planning
- `all` - Complete summary

**Examples:**
```bash
# Generate daily report and send via Telegram
nocctl report --range today --format xlsx --send telegram

# Generate last 24h network report
nocctl report --range last24h --category network --format json

# Generate monthly capacity report
nocctl report --range thismonth --category capacity --format xlsx

# Custom date range
nocctl report --start 2024-02-01 --end 2024-02-08 --format html
```

---

### discover
Discover devices on the network.

```bash
nocctl discover [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--subnet CIDR` | Scan subnet | `--subnet 10.0.0.0/24` |
| `--range START-END` | IP range | `--range 10.0.0.1-10.0.0.254` |
| `--method METHOD` | Discovery method: ping, snmp, ssh | `--method snmp` |
| `--ports PORTS` | Ports to check (comma-separated) | `--ports 22,23,161,443` |
| `--timeout SEC` | Timeout per host | `--timeout 5` |
| `--output FILE` | Save discovery results | `--output discovered.yaml` |
| `--add-to-config` | Add discovered to config | `--add-to-config` |

**Examples:**
```bash
# Discover via ping sweep
nocctl discover --subnet 192.168.1.0/24 --method ping

# Discover via SNMP
nocctl discover --subnet 10.0.0.0/24 --method snmp --ports 161

# Scan specific range with multiple methods
nocctl discover --range 10.0.0.1-10.0.0.50 --method ping,snmp

# Discover and add to configuration
nocctl discover --subnet 192.168.1.0/24 --add-to-config
```

---

### detect-os
Detect operating system of a device.

```bash
nocctl detect-os <host> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--transport TYPE` | SSH or telnet | `--transport ssh` |
| `--port N` | Port number | `--port 22` |
| `--timeout SEC` | Connection timeout | `--timeout 10` |
| `--verbose, -v` | Show detection details | `--verbose` |

**Examples:**
```bash
# Basic OS detection
nocctl detect-os 10.0.0.1

# SSH detection with custom port
nocctl detect-os 192.168.1.1 --transport ssh --port 2222 --verbose

# Telnet detection
nocctl detect-os 10.0.0.2 --transport telnet --port 23
```

---

### plugin
Manage plugins.

#### plugin list
List all available plugins.

```bash
nocctl plugin list [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--category CAT` | Filter by category: network, server, hypervisor | `--category network` |
| `--format FMT` | Output format | `--format table` |
| `--real-only` | Show only real (non-skeleton) plugins | `--real-only` |
| `--skeleton-only` | Show only skeleton plugins | `--skeleton-only` |

**Output Columns:**
- OS Name
- Category
- Status (real/skeleton)
- Variables supported
- Commands defined

**Example:**
```bash
# List all network device plugins
nocctl plugin list --category network

# List only implemented plugins
nocctl plugin list --real-only
```

#### plugin validate
Validate a plugin's configuration.

```bash
nocctl plugin validate <os_name>
```

**Validation Checks:**
- command_map.yaml syntax
- variable_map.yaml schema
- parser.py imports
- Help file format

**Example:**
```bash
# Validate Cisco IOS plugin
nocctl plugin validate cisco_ios

# Validate all plugins (bulk)
for os in $(nocctl plugin list --format json | jq -r '.[].name'); do
    nocctl plugin validate $os
done
```

#### plugin init
Initialize a new plugin skeleton.

```bash
nocctl plugin init <os_name> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--category CAT` | Plugin category | `--category network` |
| `--template OS` | Copy from existing plugin | `--template cisco_ios` |
| `--force` | Overwrite if exists | `--force` |

**Example:**
```bash
# Create new plugin for Arista EOS
nocctl plugin init arista_eos --category network --template cisco_ios
```

#### plugin bootstrap
Generate skeleton plugins for all unimplemented OSes.

```bash
nocctl plugin bootstrap [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--force` | Overwrite existing | `--force` |
| `--category CAT` | Only specific category | `--category hypervisor` |

**Example:**
```bash
# Generate all missing plugin skeletons
nocctl plugin bootstrap

# Regenerate network plugins only
nocctl plugin bootstrap --category network
```

#### plugin help
Show help for a specific OS/topic.

```bash
nocctl plugin help <os_name> [topic]
```

**Examples:**
```bash
# Show general help for Cisco IOS
nocctl plugin help cisco_ios

# Show CPU monitoring help
nocctl plugin help cisco_ios cpu

# Show interface commands
nocctl plugin help junos interfaces
```

---

### health
Check system health.

```bash
nocctl health [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--verbose, -v` | Detailed health check | `--verbose` |
| `--check NAME` | Run specific check | `--check database` |
| `--format FMT` | Output format | `--format json` |

**Health Checks:**
- Database connectivity
- Collector responsiveness
- Disk space
- Memory usage
- Plugin load status

**Examples:**
```bash
# Quick health check
nocctl health

# Detailed check
nocctl health --verbose

# Check specific component
nocctl health --check database

# JSON output for monitoring
nocctl health --format json
```

---

### backup
Manage backups.

#### backup create
Create a system backup.

```bash
nocctl backup create [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--name NAME` | Backup name | `--name pre-upgrade-2024-02-08` |
| `--include-data` | Include collected data | `--include-data` |
| `--include-configs` | Include configurations | `--include-configs` |
| `--include-logs` | Include log files | `--include-logs` |

**Example:**
```bash
# Create full backup
nocctl backup create --name full-backup-$(date +%Y%m%d)

# Config-only backup
nocctl backup create --include-configs --name config-only
```

#### backup list
List available backups.

```bash
nocctl backup list
```

#### backup restore
Restore from backup.

```bash
nocctl backup restore <backup_name> [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--dry-run` | Show what would be restored | `--dry-run` |
| `--data-only` | Restore only data | `--data-only` |
| `--config-only` | Restore only config | `--config-only` |

**Example:**
```bash
# Preview restore
nocctl backup restore full-backup-20240208 --dry-run

# Perform restore
nocctl backup restore full-backup-20240208
```

---

### config
Configuration management.

#### config validate
Validate configuration file.

```bash
nocctl config validate [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--file PATH` | Config file to validate | `--file config/production.yaml` |

**Example:**
```bash
# Validate default config
nocctl config validate

# Validate specific file
nocctl config validate --file config/staging.yaml
```

#### config migrate
Migrate configuration to new version.

```bash
nocctl config migrate [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--to-version VER` | Target version | `--to-version 1.1.0` |
| `--dry-run` | Show changes without applying | `--dry-run` |

**Example:**
```bash
# Preview migration
nocctl config migrate --to-version 1.1.0 --dry-run

# Apply migration
nocctl config migrate --to-version 1.1.0
```

#### config export
Export configuration (for migration/backup).

```bash
nocctl config export [OPTIONS]
```

**Options:**
| Option | Description | Example |
|--------|-------------|---------|
| `--output FILE` | Export file path | `--output config-export.tar.gz` |
| `--include-secrets` | Include encrypted secrets | `--include-secrets` |

---

## Shell Completion

Generate shell completion scripts:

```bash
# Bash
nocctl completion bash > /etc/bash_completion.d/nocctl

# Zsh
nocctl completion zsh > /usr/local/share/zsh/site-functions/_nocctl

# Fish
nocctl completion fish > ~/.config/fish/completions/nocctl.fish
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Configuration error |
| 4 | Device unreachable |
| 5 | Authentication failed |
| 6 | Plugin error |
| 10 | Alert not found |
| 20 | Backup not found |
| 30 | Workflow failed |

---

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NOC_CONFIG` | Default config path | `/etc/noc/config.yaml` |
| `NOC_LOG_LEVEL` | Logging level | `DEBUG`, `INFO`, `WARNING` |
| `NOC_DATA_DIR` | Data directory | `/var/lib/noc` |
| `TELEGRAM_BOT_TOKEN` | Telegram token | `123456:ABC-DEF...` |
| `TELEGRAM_CHAT_ID` | Telegram chat | `-100123456789` |
| `TWILIO_ACCOUNT_SID` | Twilio SID | `ACxxxxxxxx...` |
| `TWILIO_AUTH_TOKEN` | Twilio token | `xxxxxxxx...` |

---

## Examples by Use Case

### Daily Operations

```bash
# Morning health check
nocctl health --verbose

# Check overnight alerts
nocctl alerts --unacknowledged --severity critical

# Acknowledge known issues
nocctl alerts ack ALERT-001 --notes "Known fiber issue, ISP working"

# Generate morning report
nocctl report --range last12h --format xlsx --send telegram
```

### Troubleshooting

```bash
# Deep scan problem device
nocctl scan --device r1 --verbose

# Trace workflow execution
nocctl workflow run --device r1 --verbose
nocctl workflow trace PIPE-XXX

# Check device help
nocctl plugin help cisco_ios interfaces
nocctl plugin help junos routing

# Manual command collection
nocctl scan --host 10.0.0.1 --os cisco_ios --once --output json
```

### Adding New Devices

```bash
# Discover devices
nocctl discover --subnet 192.168.1.0/24 --add-to-config

# Validate new device
nocctl plugin validate newly_discovered_os

# Test scan
nocctl scan --device newly_added_device --verbose

# Enable monitoring
nocctl workflow schedule newly_added_device --interval 60 --enable
```

### Maintenance Windows

```bash
# Suppress alerts during maintenance
nocctl alerts suppress --device srv1 --duration 120 --reason "OS upgrade"

# Generate pre-maintenance report
nocctl report --range last1h --device srv1 --format json

# Re-enable after maintenance
nocctl workflow schedule srv1 --enable
```

---

## See Also

- [Installation Guide](installation.md)
- [Configuration Reference](configuration.md)
- [Architecture Overview](architecture.md)
- [Troubleshooting](troubleshooting.md)

---

## 👥 Credits & Community

Created by: **Lily Yang**, **0xff**, **Community**, **Black Roots**, **CifSec**  
Sponsored by: **1Cloud Next Generation (1CNG)**

🌐 [1cng.cloud](https://1cng.cloud) | 💬 [Telegram](https://t.me/noc_community) | 🐦 [@1CNG_NOC](https://twitter.com/1CNG_NOC)

See [CREDITS.md](CREDITS.md) for full details.
