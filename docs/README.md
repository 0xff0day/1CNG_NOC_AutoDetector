# 1CNG_NOC_AutoDetector

**AI-Based Network Health Check and Monitoring with Auto-Alert and Auto Phone Call**

A production-grade, CLI-based AI NOC system that replaces human NOC engineers using AI-driven detection, monitoring, alerting, correlation, and reporting based solely on CLI data collected over SSH/Telnet.

---

## 🎯 Project Overview

**1CNG_NOC_AutoDetector** is an intelligent Network Operations Center (NOC) automation platform that:

- **Monitors** 50+ device types (network devices, servers, hypervisors)
- **Collects** data via CLI (SSH/Telnet) using device-specific plugins
- **Analyzes** metrics using AI/ML detection algorithms
- **Correlates** incidents across devices for root cause analysis
- **Alerts** via Telegram, voice calls (Twilio), email, SMS, webhooks
- **Reports** in JSON/Excel/Text with automated delivery

---

## 🏗️ System Architecture

### Workflow Pipeline

```
┌─────────┐    ┌─────────┐    ┌───────────┐    ┌─────────┐    ┌───────────┐    ┌────────┐    ┌─────────┐
│ OBSERVE │───▶│ COLLECT │───▶│ NORMALIZE │───▶│ ANALYZE │───▶│ CORRELATE │───▶│ ALERT  │───▶│ REPORT  │
└─────────┘    └─────────┘    └───────────┘    └─────────┘    └───────────┘    └────────┘    └─────────┘
    │              │                │                │                │               │             │
    ▼              ▼                ▼                ▼                ▼               ▼             ▼
 Device        SSH/Telnet       Plugin Parser    AI Detection    Incident        Notifications   Storage
 Discovery     Command Exec     Variable Map     Threshold       Clustering      Deduplication   Metrics
 OS Detect     Data Pull        Normalization    Anomaly         Root Cause      Routing         Reports
                                 to Schema        Trend           Impact Chain    Escalation      Dashboard
                                                  Prediction
```

### Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  CLI Tool   │  │  Shell      │  │  Workflow   │  │  Health/Readiness   │  │
│  │  (nocctl)   │  │  Completion │  │  Visualizer │  │  Probes             │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         WORKFLOW ORCHESTRATION LAYER                       │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    Workflow Orchestrator                               │  │
│  │  OBSERVE → COLLECT → NORMALIZE → ANALYZE → CORRELATE → ALERT → REPORT │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         BUSINESS LOGIC LAYER                               │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ AI Engine  │ │ Correlation│ │  Alerting  │ │ Reporting  │ │ Analytics│  │
│  │ Detection  │ │ Engine     │ │ Engine     │ │ Generator  │ │ Benchmark│  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         PLUGIN & COLLECTION LAYER                          │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         Plugin System                                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │
│  │  │  Cisco   │ │  Juniper │ │  Palo    │ │  Linux   │ │  VMware  │   │  │
│  │  │  IOS/NXOS│ │  JunOS   │ │  Alto    │ │  Server  │ │  ESXi    │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │
│  │  │ MikroTik │ │  pfSense │ │ Windows  │ │  Proxmox │ │  +38 more│   │  │
│  │  │ RouterOS │ │          │ │  Server  │ │    VE    │ │  plugins │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      Collection Engines                                │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│  │  │ SSH Collector│  │Telnet Collect│  │SNMP Collector│               │  │
│  │  │  (Paramiko)  │  │   (Telnetlib)│  │  (pysnmp)    │               │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         INTEGRATION LAYER                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │  Telegram  │ │  Twilio    │ │  Webhook   │ │ Prometheus │ │  StatsD  │  │
│  │  Bot API   │ │  Voice     │ │  HTTP      │ │  Exporter  │ │  Client  │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         ENTERPRISE LAYER                                   │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────┐  │
│  │ Multi-     │ │    RBAC    │ │   Audit    │ │  Circuit   │ │   Rate   │  │
│  │ Tenancy    │ │  (Roles)   │ │   Logger   │ │  Breaker   │ │  Limiter │  │
│  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────────────────────────┤
│                         DATA LAYER                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                      SQLite Storage                                  │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │  │
│  │  │  Metrics │ │  Alerts  │ │  Audit   │ │   Rollup │ │   Cache  │   │  │
│  │  │  (Time-  │ │  (Events)│ │  (Events)│ │  (Hourly/│ │   (LRU)  │   │  │
│  │  │   Series)│ │          │ │          │ │   Daily) │ │          │   │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
1CNG_NOC_AutoDetector/
├── autodetector/                 # Core application
│   ├── ai/                       # AI detection engine
│   │   ├── detectors.py          # Threshold/anomaly/trend detection
│   │   ├── engine.py             # Main AI orchestration
│   │   └── scoring.py            # Health score calculation
│   ├── collector/                # Data collection
│   │   ├── ssh_collector.py      # SSH via Paramiko
│   │   ├── telnet_collector.py   # Telnet fallback
│   │   └── snmp_collector.py     # SNMP discovery
│   ├── correlation/              # Incident correlation
│   │   └── engine.py             # Root cause & impact analysis
│   ├── detection/                # OS fingerprinting
│   │   └── fingerprints.py       # 22 OS signatures
│   ├── discovery/                # Service discovery
│   │   └── service_discovery.py  # Port scanning & topology
│   ├── plugin/                   # Plugin system
│   │   ├── loader.py             # Plugin loading
│   │   ├── manager.py            # Plugin management
│   │   ├── schema.py             # Schema validation
│   │   └── builtin/              # Built-in plugins
│   │       ├── cisco_ios/        # Real implementation
│   │       ├── cisco_nxos/       # Real implementation
│   │       ├── junos/            # Real implementation
│   │       ├── panos/            # Real implementation
│   │       ├── fortios/          # Real implementation
│   │       ├── mikrotik/         # Real implementation
│   │       ├── pfsense/          # Real implementation
│   │       ├── windows_server/   # Real implementation
│   │       ├── rhel/             # Real implementation
│   │       ├── ubuntu/           # Real implementation
│   │       ├── vmware_esxi/      # Real implementation
│   │       ├── proxmox/          # Real implementation
│   │       └── _registry.yaml    # 43 supported OSes
│   ├── storage/                  # Data persistence
│   │   ├── sqlite_store.py       # Time-series storage
│   │   └── retention.py          # Data retention
│   └── alerting/                 # Alert management
├── alerting/                     # Advanced alerting
│   ├── aggregation.py            # Alert grouping
│   ├── alert_templates.py        # Custom templates
│   ├── notification_routing.py   # Smart routing
│   └── routing.py                # Contact group routing
├── analytics/                    # Performance analytics
│   └── benchmark.py              # Benchmarking & capacity
├── auth/                         # Authentication & authz
│   ├── multitenancy.py           # Tenant isolation
│   └── rbac.py                   # Role-based access
├── audit/                        # Audit logging
│   └── audit_logger.py           # Tamper-proof audit
├── cli/                          # Command-line interface
│   └── completion.py             # Shell autocomplete
├── compliance/                   # Configuration compliance
│   └── config_drift.py           # Drift detection
├── integrations/                 # External integrations
│   ├── telegram_sender.py        # Telegram bot
│   ├── voice_call.py             # Twilio voice
│   ├── webhooks.py               # Webhook dispatcher
│   └── prometheus_exporter.py    # Prometheus metrics
├── operations/                   # Bulk operations
│   └── bulk_operations.py        # Parallel device ops
├── reporting/                    # Report generation
│   ├── generator.py              # JSON/Excel/TXT reports
│   ├── dashboard_export.py       # Dashboard data
│   └── telegram_sender.py        # Report delivery
├── system/                       # System utilities
│   ├── health_checks.py          # Health probes
│   ├── circuit_breaker.py        # Resilience patterns
│   ├── rate_limiter.py           # Rate limiting
│   ├── cache_manager.py          # Caching layer
│   └── backup_restore.py         # Backup/restore
├── testing/                      # Testing framework
│   └── plugin_tests.py           # Plugin validation
├── workflow/                     # Workflow orchestration
│   ├── orchestrator.py           # 7-stage pipeline
│   ├── scheduler.py              # Auto-scheduling
│   ├── cli.py                    # Workflow CLI
│   └── reporter.py               # Workflow reporting
├── config/                       # Configuration
│   └── config.example.yaml       # Example config
├── data/                         # Runtime data
├── reports/                      # Generated reports
├── docs/                         # Documentation
├── nocctl.py                     # Main CLI entrypoint
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd 1CNG_NOC_AutoDetector

# Install dependencies
pip install -r requirements.txt

# Copy example configuration
cp config/config.example.yaml config/config.yaml

# Edit configuration
nano config/config.yaml
```

### Configuration

Edit `config/config.yaml`:

```yaml
system:
  timezone: "UTC"
  data_dir: "./data"
  db_path: "./data/noc.db"

devices:
  - id: "r1"
    name: "Core Router 1"
    host: "10.0.0.1"
    transport: "ssh"
    os: "cisco_ios"
    credential_ref: "lab"
    tags: ["network", "core"]

  - id: "srv1"
    name: "Production Server 1"
    host: "10.0.0.50"
    transport: "ssh"
    os: "ubuntu"
    credential_ref: "lab"
    tags: ["server", "production"]

credentials:
  vault_file: "./config/credentials.yaml"

integrations:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
  
  voice_call:
    enabled: true
    provider: "twilio"
    account_sid: "${TWILIO_ACCOUNT_SID}"
    auth_token: "${TWILIO_AUTH_TOKEN}"
    from_number: "+15555550100"
    to_numbers: ["+15555550101"]
```

### First Scan

```bash
# Scan a single device
nocctl scan --device r1

# Run workflow for all devices
nocctl workflow run --verbose

# Check alerts
nocctl alerts --severity critical

# Generate daily report
nocctl report --range today --format json
```

---

## 📚 Documentation

See the `docs/` directory for detailed documentation:

- [Installation Guide](installation.md)
- [Configuration Reference](configuration.md)
- [Command Reference](commands.md)
- [Architecture Overview](architecture.md)
- [Plugin Development](plugins.md)
- [Troubleshooting](troubleshooting.md)
- [Complete Features Reference](FEATURES.md) - **50+ Features & Modules**
- [Credits & Community](CREDITS.md)

---

## 🔧 Supported Devices

### Network Devices (20+)
- Cisco IOS, IOS-XE, NX-OS, XR, ASA
- Juniper JunOS
- Palo Alto PAN-OS
- Fortinet FortiOS
- MikroTik RouterOS
- Arista EOS
- Huawei VRP
- Ubiquiti EdgeOS
- pfSense/OPNsense
- +10 more

### Server Operating Systems (20+)
- Ubuntu/Debian
- RHEL/CentOS/Rocky/AlmaLinux
- SUSE Linux
- Amazon Linux
- FreeBSD
- Windows Server (PowerShell over SSH)
- +13 more

### Hypervisors (10)
- VMware ESXi
- Proxmox VE
- Microsoft Hyper-V
- XCP-ng/XenServer
- +6 more

### Programming Languages (1)
- **Go** - Runtime monitoring (goroutines, GC, heap, gops, pprof)

---

## 🤖 AI Detection Capabilities

1. **Threshold Detection** - Static threshold breaches
2. **Anomaly Detection** - Statistical outliers (Z-score)
3. **Trend Analysis** - Directional trends & predictions
4. **Flapping Detection** - State instability detection
5. **Interface Error Analysis** - CRC/drop monitoring
6. **Routing Instability** - BGP/OSPF stability
7. **Health Scoring** - Weighted composite scores (0-100%)
8. **Root Cause Suggestion** - AI-generated diagnoses
9. **Capacity Planning** - Resource exhaustion forecasting
10. **Log Error Correlation** - Pattern matching across logs

---

## 📞 Support

For issues, feature requests, or contributions:

- GitHub Issues: [project-issues-url]
- Documentation: [docs-url]
- Email: noc@1cng.local

---

## � Credits & Community

### Creators

This project was created by:

- **Lily Yang** - Project Lead & Architecture
- **0xff** - Core Development & AI Engine
- **Community** - Contributors & Feedback
- **Black Roots** - Infrastructure & Testing
- **CifSec** - Security Audit & Compliance

### Sponsors

Proudly sponsored by:

- **1Cloud Next Generation (1CNG)** - Cloud Infrastructure & Support

### Connect With Us

🌐 **Website**: [https://1cng.cloud](https://1cng.cloud)  
💬 **Telegram Community**: [https://t.me/noc_community](https://t.me/noc_community)  
🐦 **Twitter/X**: [@1CNG_NOC](https://twitter.com/1CNG_NOC)  
📧 **Email**: support@1cng.cloud  
📱 **Discord**: [Join our Discord](https://discord.gg/1cng)  

---

## �� License

MIT License - See LICENSE file for details.

---

**Built with ❤️ for Network Operations Teams**
