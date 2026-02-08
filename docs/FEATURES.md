# Complete Features Reference

This document provides a comprehensive list of all features and modules in 1CNG_NOC_AutoDetector.

---

## 🔌 Core Collection & Connection

### SSH Multi-Session Collector
- **File**: `autodetector/collectors/ssh_collector.py`
- **Features**:
  - Connection pooling and reuse
  - Concurrent command execution
  - Automatic reconnection
  - Session health monitoring
  - Keepalive handling
  - Statistics tracking

### Telnet Fallback
- **File**: `autodetector/collectors/telnet_collector.py`
- **Features**:
  - Automatic login detection
  - Prompt detection and matching
  - Timeout handling
  - Session reuse
  - Connection manager with SSH fallback

---

## 🔐 Security & Authentication

### Credential Vault
- **File**: `auth/vault.py`
- **Features**:
  - AES-256 encryption via Fernet
  - PBKDF2 key derivation
  - Master password protection
  - Per-device credential storage
  - Environment variable fallback
  - System keyring integration

---

## 🔍 Discovery & Detection

### Device Auto Discovery
- **File**: `autodetector/discovery/auto_discovery.py`
- **Features**:
  - SNMP network scanning
  - Ping sweeps
  - ARP table inspection
  - CDP/LLDP neighbor discovery
  - Route table analysis
  - Port scanning

### Vendor Detection
- **File**: `autodetector/discovery/vendor_detector.py`
- **Features**:
  - SSH banner analysis
  - SNMP sysDescr parsing
  - MAC OUI lookup
  - Device fingerprinting

### OS Detection
- **File**: `autodetector/discovery/os_detector.py`
- **Features**:
  - Multi-OS pattern matching
  - Prompt-based detection
  - Command response analysis

---

## 📊 Data Processing

### Variable Schema Loader
- **File**: `autodetector/schema/variable_loader.py`
- **Features**:
  - Schema validation
  - Vendor variable mapping
  - Transformation functions
  - Metric normalization
  - Threshold checking

### Log Parser Engine
- **File**: `autodetector/parsers/log_parser.py`
- **Features**:
  - Multi-format log parsing
  - Syslog format support
  - Vendor-specific patterns
  - Severity classification
  - Critical event detection

### Metric Parser Engine
- **File**: `autodetector/parsers/metric_parser.py`
- **Features**:
  - Regex-based parsing
  - JSON parsing
  - Table/text parsing
  - Vendor-specific parsers
  - Auto-detection

---

## 💾 Storage

### Time-Series Store
- **File**: `storage/timeseries.py`
- **Features**:
  - SQLite-based storage
  - Automatic partitioning
  - Efficient downsampling
  - Data retention policies
  - Concurrent access
  - Metric caching

---

## 🤖 AI & Analytics

### Anomaly Detection Engine
- **File**: `autodetector/ai/anomaly_engine.py`
- **Methods**:
  - Z-Score detection
  - MAD (Median Absolute Deviation)
  - IQR (Interquartile Range)
  - EWMA (Exponentially Weighted)
  - Multi-metric correlation

### Trend Detection Engine
- **File**: `autodetector/ai/trend_engine.py`
- **Features**:
  - Linear regression
  - Forecasting
  - ETA to threshold
  - Change point detection
  - Capacity prediction

### Correlation Engine
- **File**: `autodetector/ai/correlation_engine.py`
- **Features**:
  - Temporal correlation
  - Spatial correlation (device dependencies)
  - Pattern matching
  - Root cause analysis
  - Impact chain building

### Health Score Engine
- **File**: `autodetector/ai/health_engine.py`
- **Features**:
  - Weighted composite scoring
  - Component-based scoring
  - Group health aggregation
  - Recommendations

### Alert Severity Engine
- **File**: `autodetector/ai/severity_engine.py`
- **Features**:
  - Severity calculation
  - Custom rules
  - Device criticality
  - Escalation triggers

---

## 📢 Notifications

### Telegram Bot Sender
- **File**: `notifications/telegram_sender.py`
- **Features**:
  - Alert notifications
  - Status updates
  - Report delivery
  - Inline keyboards
  - Document sharing

### Voice Call Trigger
- **File**: `notifications/voice_caller.py`
- **Integrations**:
  - Twilio API
  - AWS SNS
  - TTS formatting
  - Call management

---

## 📈 Reporting

### Excel Report Generator
- **File**: `reporters/excel_reporter.py`
- **Features**:
  - Multi-worksheet reports
  - Charts and graphs
  - Conditional formatting
  - Auto-filter
  - Styled output

### JSON/JSONL Exporter
- **File**: `reporters/json_exporter.py`
- **Features**:
  - Pretty/compressed JSON
  - Streaming export
  - Schema validation
  - JSON Lines format

### TXT Reporter
- **File**: `reporters/txt_reporter.py`
- **Features**:
  - Plain text reports
  - Table formatting
  - ASCII borders
  - Log appending

### Category Report Splitter
- **File**: `reporters/category_splitter.py`
- **Features**:
  - Severity-based splitting
  - Device type splitting
  - Custom filters
  - Executive summaries
  - Technical reports

---

## 👥 Organization

### Device Grouping
- **File**: `groups/device_groups.py`
- **Features**:
  - Static groups
  - Dynamic groups (criteria-based)
  - Hierarchical groups
  - Group inheritance

### Contact Group Mapping
- **File**: `groups/contact_mapping.py`
- **Features**:
  - Contact management
  - Group mappings
  - Severity routing
  - Escalation contacts

---

## ⬆️ Escalation & Management

### Escalation Rules Engine
- **File**: `escalation/rules_engine.py`
- **Features**:
  - Time-based escalation
  - Ack timeout escalation
  - Severity-based rules
  - Manual escalation

### Alert Cooldown & Deduplication
- **Files**: `escalation/cooldown.py`
- **Features**:
  - Per-alert cooldown
  - Exponential backoff
  - Duplicate detection
  - Similarity matching

---

## ✅ Alert Lifecycle

### Acknowledge System
- **File**: `acknowledge/ack_system.py`
- **Features**:
  - Alert acknowledgment
  - Bulk acknowledge
  - Resolution tracking
  - Escalation alternative
  - User history

### History Logger
- **File**: `acknowledge/history_log.py`
- **Features**:
  - Persistent logging
  - Event tracking
  - Query interface
  - Statistics
  - Export to JSON

---

## 💻 CLI & Documentation

### Help System
- **File**: `cli/help_system.py`
- **Features**:
  - Topic search
  - Command reference
  - Usage examples
  - Interactive mode

### Knowledge Base
- **File**: `cli/knowledge_base.py`
- **Features**:
  - Command documentation
  - Best practices
  - Common mistakes
  - Search functionality

---

## 🔧 Plugins & Profiles

### Plugin Loader
- **File**: `plugins/loader.py`
- **Features**:
  - Dynamic loading
  - Hot-reload
  - Dependency checking
  - Registry management

### Device Profile Manager
- **File**: `plugins/profiles.py`
- **Features**:
  - Profile templates
  - Profile inheritance
  - Bulk device creation
  - Import/export

---

## ⏰ Scheduling

### Task Scheduler
- **File**: `scheduler/task_scheduler.py`
- **Features**:
  - Cron-like scheduling
  - Interval-based tasks
  - Priority queue
  - Concurrent execution

### Polling Modes
- **File**: `scheduler/polling_modes.py`
- **Modes**:
  - Fixed interval
  - Adaptive polling
  - On-demand
  - Event-driven
  - Smart (AI-optimized)

---

## ⚙️ Configuration

### Config Handler
- **File**: `config/handler.py`
- **Features**:
  - YAML/JSON loading
  - Schema validation
  - Default values
  - Config migration
  - Deep merging

---

## 🔄 Utilities

### Threading & Concurrency
- **File**: `utils/threading.py`
- **Features**:
  - Thread pool management
  - Parallel execution
  - Result collection

### Retry Logic
- **File**: `utils/retry.py`
- **Features**:
  - Exponential backoff
  - Circuit breaker pattern
  - Configurable retries

### Timeout Handler
- **File**: `utils/timeout.py`
- **Features**:
  - Context manager
  - Cross-platform support
  - Connection timeouts

---

## 📡 Monitors

### Offline Detection
- **File**: `monitors/offline_detector.py`
- **Features**:
  - Consecutive failure detection
  - Recovery detection
  - State transitions
  - Flapping detection

### Flapping Detector
- **File**: `monitors/flapping_detector.py`
- **Features**:
  - State oscillation detection
  - Stability scoring
  - Adaptive thresholds
  - Interface/BGP monitoring

### Routing Monitor
- **File**: `monitors/routing_monitor.py`
- **Features**:
  - BGP neighbor tracking
  - OSPF monitoring
  - Route churn detection
  - Instability alerts

### Interface Monitor
- **File**: `monitors/interface_monitor.py`
- **Features**:
  - Error counting
  - CRC monitoring
  - Performance tracking
  - Utilization trends

---

## 🔮 Prediction & Intelligence

### Capacity Prediction
- **File**: `prediction/capacity.py`
- **Features**:
  - Disk full prediction
  - Memory exhaustion
  - Growth rate analysis
  - Days-until-full calculation

### Log Intelligence
- **File**: `intelligence/log_analyzer.py`
- **Features**:
  - Pattern recognition
  - Security analysis
  - Error correlation
  - Brute force detection

---

## 📋 Analysis & Dashboard

### Root Cause Analyzer
- **File**: `analysis/root_cause.py`
- **Features**:
  - Alert pattern analysis
  - Contributing factors
  - Action recommendations
  - Human-readable output

### Health Dashboard
- **File**: `dashboard/health_view.py`
- **Features**:
  - CLI visualization
  - Health bars
  - Status summaries
  - Compact view

---

## 🖥️ CLI Commands

### Summary Command
- **File**: `cli/commands/summary_cmd.py`
- **Output**: System overview, device counts, alert summary, health scores

### Scan Command
- **File**: `cli/commands/scan_cmd.py`
- **Features**: Single device, group scan, all devices, verbose output

### Report Command
- **File**: `cli/commands/report_cmd.py`
- **Features**: On-demand reports, multiple formats, list/delete reports

---

## 🧠 Local LLM (AI NOC)

### LLM Core Module
- **File**: `autodetector/ai/llm/__init__.py`
- **Features**: Model registry, base adapter, configuration

### GPT Adapter
- **File**: `autodetector/ai/llm/adapters/gpt_adapter.py`
- **Engine**: llama-cpp-python for Llama/Mistral models

### Claude Adapter
- **File**: `autodetector/ai/llm/adapters/claude_adapter.py`
- **Engine**: Hugging Face transformers

### Gemini Adapter
- **File**: `autodetector/ai/llm/adapters/gemini_adapter.py`
- **Engine**: Multimodal transformers

### Training Pipeline
- **File**: `autodetector/ai/llm/training.py`
- **Methods**: LoRA, QLoRA, Full fine-tuning

### NOC Training Data Builder
- **File**: `autodetector/ai/llm/noc_training_data.py`
- **Features**: Synthetic NOC training examples

### LLM Integration
- **File**: `autodetector/ai/llm_integration.py`
- **Features**: Alert analysis, correlation insights, predictions

---

## 📊 Supported Devices

### Network Devices (20+)
- Cisco IOS, IOS-XE, NX-OS, ASA
- Juniper JunOS
- Palo Alto PAN-OS
- Fortinet FortiOS
- Arista EOS
- MikroTik RouterOS
- Huawei VRP
- F5 BIG-IP
- pfSense/OPNsense
- +10 more

### Server OS (20+)
- Linux: Ubuntu, RHEL, CentOS, Rocky, AlmaLinux, SUSE, Amazon Linux, Oracle Linux, Arch, Fedora
- BSD: FreeBSD, OpenBSD, NetBSD
- Windows: Server 2016/2019/2022
- macOS

### Hypervisors (10)
- VMware ESXi
- Proxmox VE
- Microsoft Hyper-V
- XCP-ng/XenServer
- KVM, Xen, Nutanix AHV
- OpenStack, VirtualBox
- Docker Host

---

## 🔗 Integrations

- **Telegram Bot API** - Instant messaging
- **Twilio Voice** - Phone call alerts
- **SMTP/Email** - Email notifications
- **Webhook** - HTTP callbacks
- **Prometheus** - Metrics export
- **SNMP** - Device discovery
- **SQLite/PostgreSQL** - Data storage

---

## 📈 AI Detection Algorithms (10)

1. **Threshold Detection** - Static limit monitoring
2. **Anomaly Detection** - Statistical outliers (Z-score, MAD, IQR)
3. **Trend Analysis** - Directional trends & predictions
4. **Flapping Detection** - State instability counting
5. **Interface Error Analysis** - CRC/drops monitoring
6. **Routing Instability** - BGP/OSPF stability
7. **Health Scoring** - Weighted composite scores
8. **Capacity Planning** - Resource exhaustion forecasting
9. **Root Cause Analysis** - AI-generated diagnoses
10. **Log Intelligence** - Pattern matching

---

**Total Features Implemented: 50+**

See individual module documentation for detailed usage instructions.
