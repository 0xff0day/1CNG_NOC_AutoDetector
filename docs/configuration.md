# Configuration Reference

Complete reference for `config/config.yaml`.

## Table of Contents
1. [System Settings](#system-settings)
2. [Device Configuration](#device-configuration)
3. [Credentials](#credentials)
4. [Collection Settings](#collection-settings)
5. [AI Configuration](#ai-configuration)
6. [Correlation Settings](#correlation-settings)
7. [Alerting Configuration](#alerting-configuration)
8. [Integration Settings](#integration-settings)
9. [Reporting Settings](#reporting-settings)
10. [Retention Settings](#retention-settings)

---

## System Settings

```yaml
system:
  # Timezone for all timestamps
  timezone: "UTC"
  
  # Data directory path
  data_dir: "./data"
  
  # SQLite database path
  db_path: "./data/noc.db"
  
  # Log level: DEBUG, INFO, WARNING, ERROR
  log_level: "INFO"
  
  # Log file path (optional, defaults to stdout)
  log_file: "./logs/noc.log"
  
  # Max log file size (MB) before rotation
  log_max_size: 100
  
  # Number of backup log files to keep
  log_backup_count: 5
  
  # Worker processes for parallel operations
  max_workers: 10
  
  # Enable debug mode (verbose output)
  debug: false
```

---

## Device Configuration

```yaml
devices:
  # Example: Cisco Router
  - id: "r1"
    name: "Core Router 1"
    host: "10.0.0.1"
    transport: "ssh"           # ssh or telnet
    os: "cisco_ios"              # Must match plugin name
    credential_ref: "network-admin"
    port: 22                     # Optional, defaults to 22/23
    tags:
      - "network"
      - "core"
      - "critical"
    location: "Main Datacenter"
    notes: "Core aggregation router"
    
    # Per-device polling intervals (optional)
    polling:
      fast_sec: 10
      normal_sec: 60
      deep_audit_sec: 3600
    
    # Device-specific variables (optional)
    custom_variables:
      SLA: "99.99%"
      Owner: "Network Team"
    
    # Dependencies (for impact analysis)
    depends_on:
      - "upstream-router"
    downstream_devices:
      - "switch-01"
      - "switch-02"
  
  # Example: Linux Server
  - id: "srv1"
    name: "Web Server 1"
    host: "10.0.1.10"
    transport: "ssh"
    os: "ubuntu"
    credential_ref: "server-admin"
    tags:
      - "server"
      - "web"
      - "production"
    location: "Server Room A"
```

### Device Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (alphanumeric, dashes, underscores) |
| `name` | Yes | Human-readable name |
| `host` | Yes | IP address or hostname |
| `transport` | Yes | `ssh` or `telnet` |
| `os` | Yes | OS type (must match plugin name) |
| `credential_ref` | Yes | Reference to credentials entry |
| `port` | No | SSH/Telnet port (default: 22 for SSH, 23 for Telnet) |
| `tags` | No | List of string tags for grouping/filtering |
| `location` | No | Physical location string |
| `notes` | No | Free-form notes |
| `polling` | No | Custom polling intervals |
| `depends_on` | No | List of device IDs this device depends on |
| `downstream_devices` | No | List of device IDs that depend on this |

---

## Credentials

```yaml
credentials:
  # Method 1: Username/Password
  network-admin:
    username: "admin"
    password: "${NETWORK_ADMIN_PASSWORD}"  # Env variable
    
  # Method 2: SSH Key
  server-admin:
    username: "noc-monitor"
    ssh_key: "./keys/noc_id_rsa"
    # Optional: SSH key password
    ssh_key_password: "${SSH_KEY_PASSWORD}"
    
  # Method 3: SSH Agent
  secure-admin:
    username: "admin"
    use_ssh_agent: true
    
  # Method 4: Vault integration
  vault-credentials:
    username: "admin"
    vault_path: "secret/network-devices/core-router"
    vault_key: "password"
```

### Credentials Reference

| Field | Description |
|-------|-------------|
| `username` | SSH/Telnet username |
| `password` | Password (plaintext or ${ENV_VAR}) |
| `ssh_key` | Path to private key file |
| `ssh_key_password` | Password for encrypted key |
| `use_ssh_agent` | Use running SSH agent |
| `vault_path` | HashiCorp Vault secret path |
| `vault_key` | Key within Vault secret |

**Security Best Practice**: Never commit plaintext passwords. Use environment variables:

```bash
export NETWORK_ADMIN_PASSWORD="secure-password-here"
nocctl scan --device r1
```

---

## Collection Settings

```yaml
collector:
  ssh:
    # Connection timeout in seconds
    connect_timeout_sec: 10
    
    # Command execution timeout
    command_timeout_sec: 15
    
    # Max concurrent SSH sessions
    max_sessions: 50
    
    # Automatically disable paging
    disable_paging: true
    
    # Paging disable commands by device type
    paging_commands:
      cisco_ios: "terminal length 0"
      junos: "set cli screen-length 0"
      # ... auto-populated from plugins
    
    # Keep connections alive
    keep_alive: true
    keep_alive_interval: 30
    
    # Host key verification
    verify_host_keys: true
    host_keys_file: "~/.ssh/known_hosts"
    
    # Ciphers and algorithms
    preferred_ciphers:
      - "aes256-gcm@openssh.com"
      - "aes128-gcm@openssh.com"
    
  telnet:
    connect_timeout_sec: 10
    command_timeout_sec: 20
    
    # Telnet negotiation options
    negotiation_timeout: 5
    
  retries:
    # Number of retry attempts
    attempts: 2
    
    # Seconds between retries
    sleep_sec: 0.5
    
    # Exponential backoff
    exponential_backoff: true
    max_backoff_sec: 30
  
  # Rate limiting per device
  rate_limit:
    enabled: true
    max_commands_per_minute: 60
    burst_size: 10
```

---

## AI Configuration

```yaml
ai:
  # Threshold-based detection
  thresholds:
    CPU_USAGE:
      warn: 75
      crit: 90
    MEMORY_USAGE:
      warn: 80
      crit: 95
    DISK_USAGE:
      warn: 80
      crit: 95
    INTERFACE_ERRORS:
      warn: 100    # errors per minute
      crit: 500
    
    # Custom thresholds per tag
    per_tag:
      critical:
        CPU_USAGE:
          warn: 60
          crit: 80
      server:
        LOAD:
          warn: 2.0
          crit: 5.0
  
  # Anomaly detection
  anomaly:
    # Number of data points for baseline
    window_points: 30
    
    # Z-score thresholds
    zscore_warn: 2.5
    zscore_crit: 3.5
    
    # Minimum data points before detection
    min_data_points: 10
    
    # Seasonality detection
    detect_seasonality: true
    seasonality_periods:
      - "1h"   # Hourly patterns
      - "1d"   # Daily patterns
  
  # Flapping detection
  flapping:
    # Time window in seconds
    window_sec: 300
    
    # State change counts
    state_change_warn: 6
    state_change_crit: 12
    
    # Hysteresis to avoid rapid toggling
    hysteresis_pct: 5
  
  # Trend analysis
  trend:
    # Prediction window
    forecast_hours: 24
    
    # Alert if reaching threshold within
    eta_alert_hours: 72
  
  # Health scoring weights (per variable)
  weights:
    CPU_USAGE: 1.2
    MEMORY_USAGE: 1.0
    DISK_USAGE: 0.8
    INTERFACE_STATUS: 1.5
    INTERFACE_ERRORS: 1.2
    ROUTING_STATE: 1.4
    LOG_ERRORS: 0.7
    UPTIME: 0.2
```

---

## Correlation Settings

```yaml
correlation:
  # Incident clustering window
  incident_window_sec: 300
  
  # Maximum devices in one incident
  max_devices_per_incident: 10
  
  # Dependency mapping
  dependencies:
    # Explicit dependencies
    - upstream: "core-router-01"
      downstream: "agg-switch-01"
      relationship: "layer2"
    
    - upstream: "agg-switch-01"
      downstream: "access-switch-01"
      relationship: "layer2"
    
    - upstream: "firewall-01"
      downstream: "web-server-01"
      relationship: "security"
  
  # Auto-detect dependencies
  auto_detect:
    enabled: true
    methods:
      - "lldp"
      - "cdp"
      - "routing"
  
  # Correlation rules
  rules:
    # Interface errors on connected devices
    - name: "link_issues"
      conditions:
        - variable: "INTERFACE_ERRORS"
          threshold: 100
      correlate_by: "connected_interfaces"
    
    # High CPU on multiple devices
    - name: "cpu_spike"
      conditions:
        - variable: "CPU_USAGE"
          threshold: 90
      min_devices: 3
      time_window: 300
      create_incident: true
```

---

## Alerting Configuration

```yaml
alerting:
  # Deduplication
  dedupe_key_fields:
    - "device_id"
    - "variable"
    - "alert_type"
  
  # Cooldown periods
  cooldown_sec: 300
  cooldown_by_severity:
    info: 600
    warning: 300
    critical: 120
  
  # Auto-escalation
  escalation:
    enabled: true
    policies:
      - name: "critical-escalation"
        condition:
          severity: "critical"
          unacknowledged_minutes: 15
        action:
          escalate_to: "noc-manager"
          channels: ["voice_call", "sms"]
      
      - name: "repeated-failure"
        condition:
          same_alert_count: 3
          within_minutes: 60
        action:
          escalate_to: "senior-engineer"
  
  # Maintenance windows
  maintenance_windows:
    - tags: ["core"]
      start_ts: "2024-02-10T02:00:00+00:00"
      end_ts: "2024-02-10T03:00:00+00:00"
      reason: "Core router firmware upgrade"
      suppress_severities: ["warning", "info"]
      created_by: "noc-manager"
  
  # Silence rules
  silences:
    - tags: ["server"]
      variables: ["LOG_ERRORS"]
      start_ts: "2024-02-10T00:00:00+00:00"
      end_ts: "2024-02-10T06:00:00+00:00"
      reason: "Scheduled patching"
      created_by: "noc-manager"
  
  # Contact groups
  contact_groups:
    default:
      telegram_chat_id: "${TELEGRAM_CHAT_ID}"
      email: "noc@company.com"
    
    noc_oncall:
      telegram_chat_id: "${TELEGRAM_ONCALL_CHAT_ID}"
      phone_numbers:
        - "+15555550101"
        - "+15555550102"
      email: "oncall@company.com"
      pager_duty_key: "${PAGERDUTY_KEY}"
    
    noc_manager:
      telegram_chat_id: "${TELEGRAM_MANAGER_CHAT_ID}"
      email: "noc-manager@company.com"
      voice_numbers:
        - "+15555550300"
  
  # Routing rules
  routes:
    # Critical core network alerts
    - tags: ["core", "network"]
      severities: ["critical"]
      contact_group: "noc_oncall"
      channels: ["telegram", "voice_call"]
      priority: 100
    
    # Server warnings
    - tags: ["server"]
      severities: ["warning"]
      contact_group: "default"
      channels: ["telegram"]
      priority: 50
    
    # Info alerts to dashboard only
    - severities: ["info"]
      channels: []  # Dashboard only
      priority: 10
    
    # Security alerts to security team
    - tags: ["security"]
      variables: ["ACL_VIOLATIONS", "AUTH_FAILURES"]
      contact_group: "security_team"
      channels: ["telegram", "email"]
      priority: 90
```

---

## Integration Settings

### Telegram

```yaml
integrations:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
    
    # Message templates
    templates:
      alert: |
        🚨 <b>{severity}</b> Alert
        
        Device: {device_name} ({device_id})
        Variable: {variable}
        Value: {value} {unit}
        Threshold: {threshold}
        
        Time: {timestamp}
        
        {message}
      
      report: |
        📊 <b>{report_type}</b> Report
        
        Period: {period}
        Generated: {generated_at}
        
        {summary}
    
    # Rate limiting
    rate_limit:
      messages_per_minute: 20
      burst_size: 5
```

### Voice Calls (Twilio)

```yaml
  voice_call:
    enabled: true
    provider: "twilio"
    account_sid: "${TWILIO_ACCOUNT_SID}"
    auth_token: "${TWILIO_AUTH_TOKEN}"
    
    # From number (must be Twilio number)
    from_number: "+15555550100"
    
    # To numbers (can be multiple)
    to_numbers:
      - "+15555550101"
      - "+15555550102"
    
    # Call settings
    timeout_sec: 30
    max_calls_per_hour: 10
    
    # Message template (TwiML)
    message_template: |
      Alert from NOC system.
      Device {device_name} has critical {variable} at {value}.
      Please acknowledge.
```

### Webhooks

```yaml
  webhooks:
    enabled: true
    endpoints:
      - name: "pagerduty"
        url: "https://events.pagerduty.com/integration/${PAGERDUTY_KEY}/enqueue"
        events: ["alert.created", "alert.escalated"]
        headers:
          Content-Type: "application/json"
        secret: "${WEBHOOK_SECRET}"  # For HMAC signature
        retry_count: 3
        timeout_sec: 10
      
      - name: "slack"
        url: "${SLACK_WEBHOOK_URL}"
        events: ["*"]  # All events
        format: "slack"
```

### Prometheus

```yaml
  prometheus:
    enabled: true
    # Export metrics for scraping
    exporter_port: 9090
    exporter_path: "/metrics"
    
    # Or push to remote
    remote_write:
      url: "https://prometheus.example.com/api/v1/write"
      username: "${PROM_USERNAME}"
      password: "${PROM_PASSWORD}"
```

---

## Reporting Settings

```yaml
reporting:
  # Output directory
  output_dir: "./reports"
  
  # Default formats
  formats: ["json", "xlsx", "txt"]
  
  # Report schedules
  schedules:
    # Hourly summary
    hourly:
      enabled: true
      format: "json"
      send_via: ["telegram"]
      include_metrics: ["CPU_USAGE", "MEMORY_USAGE", "INTERFACE_STATUS"]
    
    # Daily detailed report
    daily:
      enabled: true
      format: "xlsx"
      send_via: ["telegram", "email"]
      include_categories: ["network", "server", "hypervisor"]
      retention_days: 30
    
    # Monthly capacity report
    monthly:
      enabled: true
      format: "xlsx"
      include_categories: ["capacity", "performance"]
      retention_days: 365
    
    # Yearly summary
    yearly:
      enabled: false
  
  # Report templates
  templates:
    summary:
      sections:
        - "executive_summary"
        - "critical_alerts"
        - "top_devices_by_health"
        - "capacity_forecast"
    
    detailed:
      sections:
        - "all_devices"
        - "all_metrics"
        - "alert_history"
        - "correlation_analysis"
  
  # Dashboard export
  dashboard:
    enabled: true
    formats: ["json", "prometheus"]
    realtime_updates: true
```

---

## Retention Settings

```yaml
retention:
  # Raw metrics retention
  metrics_days: 30
  
  # Alert history retention
  alerts_days: 180
  
  # Audit log retention (compliance)
  audit_days: 2555  # 7 years
  
  # Workflow history
  workflow_days: 90
  
  # Rollup retention (aggregated data)
  rollup_keep_days: 365
  
  # Automatic cleanup
  auto_cleanup:
    enabled: true
    schedule: "0 2 * * *"  # Daily at 2 AM
    vacuum: true  # Reclaim disk space
  
  # Archive old data before deletion
  archive:
    enabled: true
    archive_dir: "./archive"
    before_delete_days: 30
```

---

## Security Settings

```yaml
security:
  # Encryption
  encryption:
    enabled: true
    # Key file for sensitive data encryption
    key_file: "./config/.encryption_key"
  
  # Audit
  audit:
    enabled: true
    log_all_commands: true
    log_retention_days: 365
    tamper_protection: true  # Integrity hashes
  
  # Network
  network:
    allowed_hosts: []  # Empty = all (restrict in production)
    blocked_hosts: []
    
  # RBAC
  rbac:
    enabled: true
    default_role: "viewer"
    enforce_on_cli: true
```

---

## Complete Example Configuration

See `config/config.example.yaml` in the repository for a complete, production-ready configuration template.

---

## Environment Variables Reference

| Variable | Description | Used In |
|----------|-------------|---------|
| `NOC_CONFIG` | Config file path | All commands |
| `NOC_LOG_LEVEL` | Logging level | System |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | Telegram integration |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID | Telegram integration |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | Voice calls |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | Voice calls |
| `DB_PASSWORD` | Database password | PostgreSQL storage |
| `WEBHOOK_SECRET` | Webhook HMAC secret | Webhook integration |

---

## Configuration Validation

Validate your configuration:

```bash
# Basic validation
nocctl config validate

# Validate specific file
nocctl config validate --file config/production.yaml

# Check with environment variables
TELEGRAM_BOT_TOKEN=test nocctl config validate
```

Common validation errors:
- Missing required fields
- Invalid OS type (no plugin found)
- Credential reference not defined
- Invalid YAML syntax
- Circular dependencies
