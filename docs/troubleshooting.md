# Troubleshooting Guide

## Common Issues and Solutions

### 1. Connection Issues

#### SSH Connection Failures

**Symptoms:**
```
ERROR: Failed to connect to device r1 (10.0.0.1): Connection refused
ERROR: Authentication failed for user 'admin'
```

**Diagnostic Steps:**

```bash
# Test basic connectivity
ping 10.0.0.1

# Test SSH port
telnet 10.0.0.1 22
# or
nc -zv 10.0.0.1 22

# Test SSH manually with verbose output
ssh -vvv -i ~/.ssh/noc_key admin@10.0.0.1

# Check SSH key permissions
ls -la ~/.ssh/noc_key
# Should be: -rw------- (600)

# Fix permissions if needed
chmod 600 ~/.ssh/noc_key
chmod 700 ~/.ssh
```

**Common Causes:**
1. **Wrong credentials** - Verify username/password or SSH key
2. **Host key changed** - Clear from known_hosts: `ssh-keygen -R 10.0.0.1`
3. **SSH algorithm mismatch** - Update algorithms in config
4. **Rate limiting** - Device blocking connections

**Solutions:**

```yaml
# config/config.yaml - Increase timeouts
collector:
  ssh:
    connect_timeout_sec: 30  # Increase from default 10
    command_timeout_sec: 60
    
  retries:
    attempts: 5  # Increase retries
    sleep_sec: 2.0
```

#### Telnet Connection Issues

**Symptoms:**
```
ERROR: Telnet connection timeout
ERROR: Expecting password prompt, got '>' instead
```

**Diagnostic Steps:**

```bash
# Test telnet manually
telnet 10.0.0.1 23

# Check if device supports telnet
nmap -p 23 10.0.0.1
```

**Solutions:**

```yaml
# config/config.yaml
collector:
  telnet:
    connect_timeout_sec: 20
    negotiation_timeout: 10
    
# Enable telnet fallback
devices:
  - id: r1
    transport: "ssh"  # Try SSH first
    fallback_transport: "telnet"  # Fallback to telnet
```

---

### 2. Collection Failures

#### Commands Not Found

**Symptoms:**
```
WARNING: Command 'show version' not found in output
ERROR: Parser returned empty metrics
```

**Diagnostic Steps:**

```bash
# Check plugin commands
nocctl plugin help cisco_ios

# Validate plugin
nocctl plugin validate cisco_ios

# Manually test command
cat > /tmp/test_commands.yaml << 'EOF'
commands:
  test: "show version"
EOF

ssh admin@10.0.0.1 "show version"
```

**Common Causes:**
1. **Wrong OS type** - Device OS different from configured
2. **Command not supported** - Different OS version
3. **Paging not disabled** - Output truncated

**Solutions:**

```bash
# Re-detect OS
nocctl detect-os 10.0.0.1 --verbose

# Update device OS in config
nano config/config.yaml
# Change: os: "cisco_ios" to correct type

# Check if paging is disabled
nocctl scan --device r1 --verbose | grep -i "more\|pager\|--more--"
```

#### Empty Output

**Symptoms:**
```
WARNING: Empty output for command 'show interfaces'
```

**Diagnostic Steps:**

```bash
# Enable verbose mode
nocctl scan --device r1 --verbose --output json 2>&1 | tee debug.log

# Check collector logs
tail -f logs/collector.log
```

**Solutions:**

```yaml
# Disable paging in config
collector:
  ssh:
    disable_paging: true
    paging_commands:
      cisco_ios: "terminal length 0"
      junos: "set cli screen-length 0"
      # Add per OS type
```

---

### 3. Parser Errors

#### No Metrics Generated

**Symptoms:**
```
WARNING: Parser returned 0 metrics
```

**Diagnostic Steps:**

```bash
# Save raw output for analysis
nocctl scan --device r1 --output json > /tmp/raw_output.json

# Check parser manually
python3 << 'EOF'
import json
from autodetector.plugin.loader import PluginLoader

loader = PluginLoader()
plugin = loader.load("cisco_ios")

# Load raw output
with open("/tmp/raw_output.json") as f:
    raw = json.load(f)

# Try parsing
result = plugin.parse(raw["outputs"], raw["errors"], {"id": "r1"})
print(f"Metrics: {len(result['metrics'])}")
print(f"Metrics: {result['metrics']}")
EOF
```

**Common Causes:**
1. **Output format changed** - OS version update
2. **Parser regex doesn't match** - Localization issues
3. **Missing command output** - Command failed

**Solutions:**

```python
# Update parser regex in autodetector/plugins/builtin/cisco_ios/parser.py

# Example: Fix CPU parsing
# Old:
# m = re.search(r"CPU utilization.*?(\?\n?\d+)%", output)

# New (handle different format):
m = re.search(r"CPU utilization.*?([0-9.]+)%", output, re.IGNORECASE | re.DOTALL)
```

---

### 4. Alert Issues

#### Alerts Not Being Sent

**Symptoms:**
```
INFO: Alert generated but no notification sent
WARNING: Telegram API returned 400 Bad Request
```

**Diagnostic Steps:**

```bash
# Test Telegram manually
curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test message"

# Check Telegram token
echo $TELEGRAM_BOT_TOKEN

# Check routing configuration
nocctl alerts test --verbose
```

**Common Causes:**
1. **Wrong chat_id** - Must include - for groups/channels
2. **Bot not in channel** - Add bot to channel
3. **Missing contact group** - Routing rule not matched

**Solutions:**

```yaml
# Get correct chat ID
# For groups: -100xxxxxxxxxx (includes -100 prefix)
# For channels: @channel_name or -100xxxxxxxxxx
# For private: Your user ID

integrations:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "-1001234567890"  # For groups
    
# Ensure routing is configured
alerting:
  routes:
    - tags: []
      severities: ["critical", "warning"]
      contact_group: "default"
      channels: ["telegram"]
```

#### Too Many Alerts (Alert Storm)

**Symptoms:**
```
INFO: 50 alerts generated in last minute
WARNING: Rate limiting triggered
```

**Diagnostic Steps:**

```bash
# Check alert history
nocctl alerts --history --limit 50

# View alert aggregation
nocctl alerts stats
```

**Solutions:**

```yaml
# Increase cooldown periods
alerting:
  cooldown_by_severity:
    info: 3600      # 1 hour
    warning: 1800   # 30 minutes
    critical: 600    # 10 minutes
  
  # Enable aggregation
  aggregation:
    enabled: true
    window_sec: 300  # Group alerts in 5 min windows
    group_by: ["device_id", "variable", "severity"]
  
  # Suppress flapping
  flapping_detection:
    enabled: true
    window_sec: 600
    max_alerts: 5  # Max 5 alerts per window
```

---

### 5. Database Issues

#### Database Locked

**Symptoms:**
```
ERROR: sqlite3.OperationalError: database is locked
ERROR: Timeout waiting for database lock
```

**Solutions:**

```yaml
# config/config.yaml - Increase timeout
storage:
  sqlite:
    timeout: 30.0  # seconds
    journal_mode: "WAL"  # Write-Ahead Logging for better concurrency
    synchronous: "NORMAL"
```

#### Database Corruption

**Symptoms:**
```
ERROR: Database image is malformed
ERROR: file is not a database
```

**Recovery Steps:**

```bash
# 1. Stop NOC
sudo systemctl stop noc-autodetector

# 2. Backup corrupted database
cp ./data/noc.db ./data/noc.db.corrupt.$(date +%Y%m%d)

# 3. Try SQLite recovery
sqlite3 ./data/noc.db ".mode insert" ".output ./data/noc_dump.sql" ".dump"

# 4. Recreate database
rm ./data/noc.db
sqlite3 ./data/noc.db < ./data/noc_dump.sql

# 5. Verify
sqlite3 ./data/noc.db "PRAGMA integrity_check;"

# 6. Restart
sudo systemctl start noc-autodetector
```

---

### 6. Performance Issues

#### Slow Collection

**Symptoms:**
```
WARNING: Collection took 45 seconds (threshold: 30s)
ERROR: Command timeout
```

**Diagnostic Steps:**

```bash
# Check device response time
 time ssh admin@10.0.0.1 "show version"

# Profile collection
 nocctl scan --device r1 --verbose 2>&1 | grep -E "(duration|timeout|took)"

# Monitor system resources
 htop
 iostat -x 1
```

**Solutions:**

```yaml
# Optimize collection
collector:
  ssh:
    command_timeout_sec: 60
    max_sessions: 20  # Reduce concurrent sessions
    
  # Enable caching
  cache:
    enabled: true
    ttl_sec: 120
    
# Device-specific timeouts
devices:
  - id: slow-device
    host: 10.0.0.100
    collection_settings:
      timeout_multiplier: 2.0  # 2x timeout for this device
```

#### High Memory Usage

**Symptoms:**
```
WARNING: Memory usage at 85%
ERROR: MemoryError: Unable to allocate
```

**Solutions:**

```yaml
# Enable data retention
retention:
  metrics_days: 7        # Reduce from default 30
  auto_cleanup:
    enabled: true
    schedule: "0 */6 * * *"  # Every 6 hours
    
# Limit concurrent operations
system:
  max_workers: 5  # Reduce from default 10
  
# Disable verbose logging
system:
  log_level: "WARNING"
```

---

### 7. Workflow Failures

#### Pipeline Stuck

**Symptoms:**
```
WARNING: Pipeline PIPE-XXX stuck at stage COLLECT for 300 seconds
```

**Diagnostic Steps:**

```bash
# Check pipeline status
nocctl workflow status --pipeline PIPE-XXX

# List all running workflows
nocctl workflow status --running

# Check for blocking operations
ps aux | grep -E "(ssh|telnet)"
```

**Solutions:**

```bash
# Cancel stuck pipeline
nocctl workflow cancel PIPE-XXX

# Kill hanging SSH processes
pkill -f "ssh.*10.0.0.1"

# Restart scheduler
sudo systemctl restart noc-autodetector
```

#### Stage Failures

**Symptoms:**
```
ERROR: Stage NORMALIZE failed: Parser error
ERROR: Stage ANALYZE failed: Division by zero
```

**Diagnostic Steps:**

```bash
# Trace specific pipeline
nocctl workflow trace PIPE-XXX

# Run with specific stage skipped
nocctl workflow run --device r1 --skip analyze
```

---

### 8. Plugin Issues

#### Plugin Not Found

**Symptoms:**
```
ERROR: Plugin 'custom_os' not found
ERROR: No plugin registered for OS type 'unknown_os'
```

**Solutions:**

```bash
# List available plugins
nocctl plugin list

# Check if plugin exists
ls autodetector/plugins/builtin/custom_os/

# Bootstrap if missing
nocctl plugin bootstrap

# Validate plugin structure
nocctl plugin validate custom_os
```

#### Parser Import Error

**Symptoms:**
```
ERROR: Failed to import parser: No module named 'custom_os'
ERROR: Parser syntax error in line 45
```

**Solutions:**

```bash
# Check Python syntax
python3 -m py_compile autodetector/plugins/builtin/custom_os/parser.py

# Check imports
cd autodetector/plugins/builtin
python3 -c "from custom_os import parser"

# View detailed error
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
try:
    from custom_os import parser
except Exception as e:
    print(f"Import error: {e}")
    import traceback
    traceback.print_exc()
EOF
```

---

### 9. Integration Issues

#### Webhook Failures

**Symptoms:**
```
WARNING: Webhook 'pagerduty' returned 401 Unauthorized
ERROR: Connection timeout to webhook endpoint
```

**Solutions:**

```yaml
integrations:
  webhooks:
    endpoints:
      - name: "pagerduty"
        url: "https://events.pagerduty.com/..."
        timeout_sec: 30  # Increase timeout
        retry_count: 5     # More retries
        retry_backoff: 2.0  # Exponential backoff
```

#### Prometheus Metrics Not Available

**Symptoms:**
```
curl http://localhost:9090/metrics
# Returns empty or connection refused
```

**Solutions:**

```yaml
integrations:
  prometheus:
    enabled: true
    exporter_port: 9090
    exporter_host: "0.0.0.0"  # Bind to all interfaces
    
# Check if port is in use
sudo netstat -tlnp | grep 9090

# Change port if conflict
integrations:
  prometheus:
    exporter_port: 9091
```

---

## Debug Mode

Enable comprehensive debugging:

```yaml
# config/config.yaml
system:
  debug: true
  log_level: "DEBUG"
  log_file: "./logs/debug.log"
  
collector:
  ssh:
    log_commands: true
    log_responses: true
```

Run with debug output:

```bash
nocctl scan --device r1 --verbose 2>&1 | tee debug_output.log
```

## Getting Help

### Collect Diagnostic Information

```bash
# System info
nocctl health --format json > health.json

# Recent logs
tail -n 1000 logs/noc.log > recent_logs.txt

# Configuration (sanitized)
cat config/config.yaml | sed 's/password:.*/password: "***"/' > config_sanitized.yaml

# Plugin status
nocctl plugin list --format json > plugins.json

# Database status
sqlite3 data/noc.db "SELECT COUNT(*) FROM metrics;" > db_stats.txt
sqlite3 data/noc.db "SELECT COUNT(*) FROM alerts;" >> db_stats.txt
```

### Report Issues

When reporting issues, include:
1. **Version**: `git describe --tags`
2. **Config**: Sanitized config.yaml
3. **Logs**: Recent error logs
4. **Reproduction**: Steps to reproduce
5. **Expected**: What should happen
6. **Actual**: What actually happens

---

## Emergency Procedures

### Stop All Operations

```bash
# Stop service
sudo systemctl stop noc-autodetector

# Kill all NOC processes
pkill -f "nocctl"
pkill -f "python.*noc"

# Verify stopped
ps aux | grep -E "(noc|python)" | grep -v grep
```

### Database Recovery Mode

```bash
# Single-user mode
sqlite3 data/noc.db ".mode line" ".headers on"

# Check integrity
sqlite3 data/noc.db "PRAGMA integrity_check;"

# Vacuum to reclaim space
sqlite3 data/noc.db "VACUUM;"

# Reindex
sqlite3 data/noc.db "REINDEX;"
```

### Reset to Defaults

```bash
# Backup first
nocctl backup create --name emergency-backup

# Reset config
cp config/config.example.yaml config/config.yaml

# Clear database (DESTRUCTIVE)
mv data/noc.db data/noc.db.bak.$(date +%Y%m%d)

# Clear cache
rm -rf data/cache/*

# Re-initialize
nocctl config validate
```

---

## FAQ

**Q: Why are metrics not showing up in reports?**
A: Check retention settings and verify the device is scheduled for collection.

**Q: How do I add a new device type?**
A: Use `nocctl plugin init <os_name>` or manually create plugin files.

**Q: Can I monitor SNMP-only devices?**
A: Yes, set `transport: "snmp"` in device config (requires snmp plugin).

**Q: How do I reduce alert noise?**
A: Increase cooldown periods, enable aggregation, add maintenance windows.

**Q: What if a device doesn't support SSH/Telnet?**
A: Use SNMP transport or create a custom collector.

**Q: How do I backup the database?**
A: Use `nocctl backup create` or copy data/noc.db while service is stopped.

**Q: Can I run multiple NOC instances?**
A: Yes, use separate config files and data directories.
