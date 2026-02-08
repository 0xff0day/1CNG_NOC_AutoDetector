# 1CNG_NOC_AutoDetector

**AI-Based Network Health Check and Monitoring with Auto-Alert and Auto Phone Call**

A production-grade, CLI-based AI NOC (Network Operations Center) system that replaces human NOC engineers using AI-driven detection, monitoring, alerting, correlation, and reporting—based solely on CLI data collected over SSH/Telnet.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What is 1CNG_NOC_AutoDetector?

An intelligent network monitoring platform that:
- **Monitors** 50+ device types (network devices, servers, hypervisors)
- **Collects** data via CLI (SSH/Telnet) using device-specific plugins
- **Analyzes** metrics using AI/ML detection algorithms
- **Correlates** incidents across devices for root cause analysis
- **Alerts** via Telegram, voice calls (Twilio), email, SMS, webhooks
- **Reports** in JSON/Excel/Text with automated delivery

**Core Principle**: Zero GUI dependencies. Everything works via CLI commands your network devices already support.

---

## 🔄 Workflow Pipeline

The system enforces a strict 7-stage workflow:

```
OBSERVE → COLLECT → NORMALIZE → ANALYZE → CORRELATE → ALERT → REPORT
```

| Stage | Purpose | Output |
|-------|---------|--------|
| **OBSERVE** | Device discovery, OS fingerprinting | OS type, confidence score |
| **COLLECT** | SSH/Telnet command execution | Raw CLI outputs |
| **NORMALIZE** | Parse and normalize metrics | Structured variables |
| **ANALYZE** | AI detection (thresholds, anomalies, trends) | Alerts, health scores |
| **CORRELATE** | Incident clustering, root cause | Impact chains |
| **ALERT** | Notification routing, deduplication | Telegram/Voice/Webhook |
| **REPORT** | Metrics storage, report generation | JSON/Excel/Dashboard |

---

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd 1CNG_NOC_AutoDetector

# Install dependencies
pip install -r requirements.txt

# Copy and edit configuration
cp config/config.example.yaml config/config.yaml
nano config/config.yaml
```

### Basic Usage

```bash
# Scan a single device
python nocctl.py --config config/config.yaml scan --device r1

# Run full workflow for all devices
python nocctl.py --config config/config.yaml workflow run --all --verbose

# Check alerts
python nocctl.py --config config/config.yaml alerts --severity critical

# Generate and send report
python nocctl.py --config config/config.yaml report --range today --format xlsx --send telegram

# Run continuous scheduler
python nocctl.py --config config/config.yaml schedule --mode normal
```

---

## 📊 Key Features

### AI Detection (8 Algorithms)
1. **Threshold Detection** - Static limit monitoring
2. **Anomaly Detection** - Statistical outliers (Z-score)
3. **Trend Analysis** - Directional trends & predictions
4. **Flapping Detection** - State instability counting
5. **Interface Error Analysis** - CRC/drops monitoring
6. **Routing Instability** - BGP/OSPF stability
7. **Health Scoring** - Weighted composite scores (0-100%)
8. **Capacity Planning** - Resource exhaustion forecasting

### Supported Device Types (50+)

**Network Devices (20+)**
- Cisco: IOS, IOS-XE, NX-OS, XR, ASA
- Juniper: JunOS
- Palo Alto: PAN-OS
- Fortinet: FortiOS
- MikroTik: RouterOS
- Arista: EOS
- Huawei: VRP
- pfSense/OPNsense
- +10 more

**Server OS (20+)**
- Linux: Ubuntu, RHEL, CentOS, Rocky, AlmaLinux, SUSE, Amazon Linux, FreeBSD
- Windows: Server 2016/2019/2022 (PowerShell over SSH)
- +13 more

**Hypervisors (10)**
- VMware: ESXi
- Proxmox: VE
- Microsoft: Hyper-V
- XCP-ng/XenServer
- +6 more

### Alert Channels
- ✅ **Telegram Bot** - Instant messages
- ✅ **Voice Calls** - Twilio integration for critical alerts
- 🟡 **Email SMTP** - Email notifications (stub)
- 🟡 **SMS Gateway** - Text messages (stub)
- ✅ **Webhooks** - Signed HTTP POST with retries
- ✅ **Prometheus** - Metrics export

### Enterprise Features
- **RBAC** - 6 roles: super_admin, tenant_admin, noc_manager, noc_engineer, viewer, api_service
- **Multi-Tenancy** - Resource isolation with quotas
- **Audit Logging** - Tamper-proof trails with integrity hashes
- **Circuit Breaker** - Fail-fast for external services
- **Rate Limiting** - Per-device and global limits
- **Bulk Operations** - Parallel execution on N devices

---

## 🏗️ Architecture

### 7-Layer Stack

```
┌─────────────────────────────────────────┐
│  7. Presentation    - CLI, Autocomplete │
├─────────────────────────────────────────┤
│  6. Workflow        - 7-Stage Pipeline │
├─────────────────────────────────────────┤
│  5. Business Logic  - AI, Correlation  │
├─────────────────────────────────────────┤
│  4. Plugins         - 50+ OS Support   │
├─────────────────────────────────────────┤
│  3. Collection      - SSH/Telnet/SNMP  │
├─────────────────────────────────────────┤
│  2. Integrations    - Telegram/Voice/etc│
├─────────────────────────────────────────┤
│  1. Data            - SQLite Storage   │
└─────────────────────────────────────────┘
```

### Project Structure

```
1CNG_NOC_AutoDetector/
├── autodetector/          # Core application
│   ├── ai/               # AI detection engine
│   ├── collector/        # SSH/Telnet/SNMP collectors
│   ├── correlation/      # Incident correlation
│   ├── detection/        # OS fingerprinting
│   ├── plugin/           # Plugin system (50+ OSes)
│   └── alerting/         # Alert management
├── alerting/             # Advanced alerting features
├── analytics/            # Performance analytics
├── auth/                 # Multi-tenancy & RBAC
├── audit/                # Audit logging
├── cli/                  # Shell completion
├── compliance/           # Config drift detection
├── integrations/         # External integrations
├── operations/           # Bulk operations
├── reporting/            # Report generation
├── system/               # System utilities
├── testing/              # Test framework
├── workflow/             # Workflow orchestration
├── docs/                 # Documentation
├── config/               # Configuration
├── nocctl.py             # Main CLI entrypoint
└── requirements.txt        # Python dependencies
```

---

## 📖 Documentation

Comprehensive documentation in `docs/`:

| Document | Contents |
|----------|----------|
| [docs/README.md](docs/README.md) | Full project overview |
| [docs/installation.md](docs/installation.md) | Installation guide (3 methods) |
| [docs/configuration.md](docs/configuration.md) | Complete config reference |
| [docs/commands.md](docs/commands.md) | CLI command reference |
| [docs/architecture.md](docs/architecture.md) | Architecture & data flow |
| [docs/plugins.md](docs/plugins.md) | Plugin development guide |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Common issues & solutions |
| [docs/FEATURES.md](docs/FEATURES.md) | **Complete Features Reference (50+)** |
| [docs/CREDITS.md](docs/CREDITS.md) | Credits, sponsors & community |

---

## 🔌 Plugin System

Each plugin requires exactly **3 files**:

```
autodetector/plugins/builtin/{os_name}/
├── command_map.yaml      # CLI commands to execute
├── variable_map.yaml     # Metric definitions & weights
└── parser.py            # Parsing logic
```

Optional: `help.yaml` for `nocctl help <os> <topic>`

### Plugin SDK Commands

```bash
# List all plugins
python nocctl.py plugin list

# Validate a plugin
python nocctl.py plugin validate cisco_ios

# Create new plugin skeleton
python nocctl.py plugin init my_new_os

# Bootstrap all 43 plugin skeletons
python nocctl.py plugin bootstrap
```

See [docs/plugins.md](docs/plugins.md) for development guide.

---

## ⚙️ Configuration Example

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
    credential_ref: "network-admin"
    tags: ["network", "core"]

  - id: "srv1"
    name: "Web Server 1"
    host: "10.0.0.50"
    transport: "ssh"
    os: "ubuntu"
    credential_ref: "server-admin"
    tags: ["server", "production"]

credentials:
  network-admin:
    username: "admin"
    password: "${NETWORK_ADMIN_PASSWORD}"  # Use env var
  server-admin:
    username: "noc-monitor"
    ssh_key: "./keys/noc_id_rsa"

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

alerting:
  routes:
    - tags: ["core"]
      severities: ["critical"]
      channels: ["telegram", "voice_call"]
```

---

## 📊 Reporting & Analytics

Report types automatically generated:

| Report | Frequency | Formats | Delivery |
|--------|-----------|---------|----------|
| **Second-level** | Real-time | JSON | Dashboard |
| **Hourly** | Every hour | JSON | Telegram |
| **Daily** | Daily | XLSX, JSON | Telegram, Email |
| **Monthly** | Monthly | XLSX | Email |
| **Yearly** | Yearly | XLSX | Email |

Categories: network, server, hypervisor, performance, security, capacity

---

## 🛠️ Advanced Usage

### Workflow Commands

```bash
# Run workflow with verbose output
nocctl workflow run --devices r1,r2,r3 --verbose

# Trace specific pipeline execution
nocctl workflow trace PIPE-ABC123

# View workflow history
nocctl workflow history --device r1 --limit 10

# Generate workflow diagram
nocctl workflow diagram --format mermaid
```

### Alert Management

```bash
# List critical unacknowledged alerts
nocctl alerts --severity critical --unacknowledged

# Acknowledge with notes
nocctl alerts ack ALERT-001 --notes "Fiber link issue, ISP notified"

# Suppress during maintenance
nocctl alerts suppress --device srv1 --duration 120 --reason "OS upgrade"
```

### Device Discovery

```bash
# Discover devices on subnet
nocctl discover --subnet 10.0.0.0/24 --add-to-config

# Detect OS of unknown device
nocctl detect-os 10.0.0.100 --verbose
```

---

## 🔒 Security

- **Credential Encryption**: Environment variables or vault integration
- **SSH Key Support**: Password-protected keys, SSH agent
- **Host Key Verification**: Strict known_hosts checking
- **Audit Logging**: Every action logged with integrity hashes
- **RBAC**: Role-based access control for multi-user environments
- **Rate Limiting**: Prevents abuse and device overload

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and test
4. Submit pull request

See [docs/plugins.md](docs/plugins.md) for plugin development.

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

## 📞 Support

- Documentation: [docs/](docs/)
- Issues: GitHub Issues
- Email: noc@1cng.local

---

**Built for Network Operations Teams who need reliable, AI-powered monitoring without the GUI overhead.**

