# Architecture Documentation

> 📋 **See [Complete Features Reference](FEATURES.md) for detailed list of all 50+ implemented modules**

## System Layers Explained

### 1. Presentation Layer
The user interface layer providing CLI access and system interfaces.

**Components:**
- **CLI Tool (nocctl)**: Main command-line interface for all operations
- **Shell Completion**: Bash/Zsh/Fish autocomplete scripts
- **Workflow Visualizer**: ASCII/Mermaid diagram generation
- **Health Probes**: Kubernetes-style readiness/liveness endpoints

### 2. Workflow Orchestration Layer
The core engine enforcing the 7-stage pipeline with strict ordering.

**Pipeline Stages:**

#### OBSERVE
- Device discovery and OS fingerprinting
- Validates device accessibility
- Detects OS type with confidence score
- **Input**: Device ID and configuration
- **Output**: OS type, discovery method, confidence level

#### COLLECT
- SSH/Telnet connection establishment
- Command execution from plugin maps
- Handles paging, timeouts, retries
- **Input**: OS type, device credentials
- **Output**: Raw CLI outputs, execution errors

#### NORMALIZE
- Parse raw CLI output using plugin parsers
- Extract metrics per variable_map schema
- Normalize to standard units
- **Input**: Raw command outputs
- **Output**: Structured metrics with types (gauge/counter/state)

#### ANALYZE (AI)
- Run AI detection algorithms
- Threshold checks, anomaly detection
- Calculate health scores
- Generate predictions
- **Input**: Normalized metrics
- **Output**: AI findings, alerts, health score

#### CORRELATE
- Cluster related alerts into incidents
- Build impact chains via dependencies
- Identify root causes
- **Input**: AI findings, alerts
- **Output**: Incidents, related devices, root causes

#### ALERT
- Deduplicate alerts
- Apply routing rules by severity/tags
- Send notifications (Telegram, Voice, Email)
- Create audit trail
- **Input**: Alerts, incidents
- **Output**: Sent notifications, acknowledged alerts

#### REPORT
- Store metrics to time-series DB
- Generate summary reports
- Update dashboard data
- Export to JSON/Excel/Telegram
- **Input**: All processed data
- **Output**: Stored metrics, reports, dashboard updates

### 3. Business Logic Layer
Core intelligence and decision-making components.

**AI Engine:**
- **Threshold Detector**: Static limit monitoring
- **Anomaly Detector**: Statistical deviation (Z-score)
- **Trend Analyzer**: Directional change detection
- **Flap Detector**: State instability counting
- **Health Scorer**: Weighted composite calculation
- **Predictor**: Time-to-threshold forecasting

**Correlation Engine:**
- Time-window incident clustering
- Dependency-based impact analysis
- Multi-device root cause linking

**Alerting Engine:**
- Deduplication with cooldown
- Severity-based routing
- Escalation policies
- Maintenance window handling

### 4. Plugin & Collection Layer
Device interaction and data acquisition.

**Plugin System:**
Each plugin consists of:
- `command_map.yaml`: CLI commands per mode
- `variable_map.yaml`: Metric definitions with weights
- `parser.py`: Output parsing logic
- `help.yaml`: Device help topics

**Collection Engines:**
- SSH (Paramiko): Multi-session, prompt-aware
- Telnet: Fallback with retry logic
- SNMP: Discovery and basic monitoring

### 5. Integration Layer
External system connectivity.

**Notification Channels:**
- Telegram Bot API: Chat messages
- Twilio: Voice calls for critical alerts
- Webhooks: Signed HTTP POST
- Prometheus: Metrics export
- StatsD: Performance metrics

### 6. Enterprise Layer
Production-grade operational features.

**Security:**
- RBAC: 6 predefined roles
- Multi-tenancy: Resource isolation
- Audit Logging: Tamper-proof trails
- API Keys: Secure authentication

**Resilience:**
- Circuit Breaker: Fail-fast patterns
- Rate Limiting: Per-device and global
- Bulk Operations: Parallel execution

### 7. Data Layer
Persistence and caching.

**Storage (SQLite):**
- Time-series metrics
- Alert history
- Audit events
- Rollup aggregations (hourly/daily)

**Cache:**
- LRU cache for device data
- Result memoization
- TTL-based expiration

## Data Flow Diagram

```
Device Config
     │
     ▼
┌─────────────┐
│   OBSERVE   │◀─── Plugin Loader (command_map.yaml)
│             │      Discovery Engine (fingerprints.py)
└──────┬──────┘
       │ OS type, commands
       ▼
┌─────────────┐
│   COLLECT   │◀─── SSH/Telnet Collector
│             │      Retry logic, timeout handling
└──────┬──────┘
       │ Raw CLI outputs
       ▼
┌─────────────┐
│  NORMALIZE  │◀─── Parser (parser.py)
│             │      Variable Map (variable_map.yaml)
└──────┬──────┘
       │ Normalized metrics
       ▼
┌─────────────┐
│   ANALYZE   │◀─── AI Detectors (8 algorithms)
│             │      Threshold/Anomaly/Trend/Flap
└──────┬──────┘
       │ AI findings, alerts
       ▼
┌─────────────┐
│  CORRELATE  │◀─── Correlation Engine
│             │      Incident clustering
└──────┬──────┘
       │ Correlated incidents
       ▼
┌─────────────┐
│   ALERT     │◀─── Aggregation, Routing
│             │      Telegram/Twilio/Webhook
└──────┬──────┘
       │ Notifications sent
       ▼
┌─────────────┐
│   REPORT    │◀─── Storage (SQLite)
│             │      Reporting Engine (JSON/Excel)
└─────────────┘
```

## Component Interactions

### Device Scanning Flow
```
nocctl scan --device r1
     │
     ▼
WorkflowOrchestrator.create_pipeline()
     │
     ▼
WorkflowOrchestrator.run_pipeline()
     │
     ├──▶ OBSERVE: detect_os()
     │       └── fingerprints.py classify_os()
     │
     ├──▶ COLLECT: run_commands()
     │       ├── SSHCollector.connect()
     │       ├── Plugin.get_commands()
     │       └── Execute via Paramiko
     │
     ├──▶ NORMALIZE: parse()
     │       └── Plugin.parser.parse()
     │
     ├──▶ ANALYZE: ai_engine.analyze()
     │       ├── threshold_check()
     │       ├── anomaly_detect()
     │       └── health_score_calc()
     │
     ├──▶ CORRELATE: correlation_engine.correlate()
     │       ├── find_related_incidents()
     │       └── build_impact_chain()
     │
     ├──▶ ALERT: alerting_engine.process()
     │       ├── deduplicate()
     │       ├── route_alert()
     │       └── telegram_sender.send()
     │
     └──▶ REPORT: reporting_engine.generate()
             ├── sqlite_store.store_metrics()
             └── report_generator.create()
```

### Alert Notification Flow
```
Alert Generated
     │
     ▼
AlertAggregator.add_alert()
     │ (Group similar alerts)
     ▼
NotificationRouter.route()
     │ (Apply routing rules)
     ├──▶ severity == critical?
     │       └── Telegram + Voice Call
     ├──▶ tags contains "core"?
     │       └── Escalation group
     └──▶ maintenance window?
             └── Suppress
```

## Deployment Architecture

### Single Node Deployment
```
┌─────────────────────────────────────┐
│           1CNG_NOC_AutoDetector      │
│  ┌───────────────────────────────┐  │
│  │        nocctl.py              │  │
│  │   (CLI Entry Point)           │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │    Workflow Orchestrator      │  │
│  │    (7-Stage Pipeline)         │  │
│  └───────────────────────────────┘  │
│  ┌───────────────────────────────┐  │
│  │     SQLite Database           │  │
│  │   (metrics, alerts, audit)    │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
 Network   Servers   Hypervisors
 Devices
```

### High Availability Deployment
```
┌─────────────────────────────────────────────────────┐
│              Load Balancer (HAProxy/Nginx)           │
└─────────────────────────────────────────────────────┘
              │
    ┌─────────┴─────────┐
    ▼                   ▼
┌──────────┐      ┌──────────┐
│ NOC Node │      │ NOC Node │
│    #1    │◀────▶│    #2    │  (Active-Active)
└────┬─────┘      └────┬─────┘
     │                 │
     └────────┬────────┘
              ▼
     ┌─────────────────┐
     │  Shared SQLite  │
     │  (NFS/EFS)      │
     │  or PostgreSQL  │
     └─────────────────┘
```

## Security Architecture

### Authentication Flow
```
User Request
     │
     ▼
API Key / Token
     │
     ▼
┌─────────────┐
│   RBAC      │──▶ Check Role Permissions
│   Manager   │
└──────┬──────┘
       │
       ▼
Tenant Check
     │
     ▼
Resource Access Control
     │
     ▼
Audit Logger (with integrity hash)
```

## Performance Considerations

### Scaling Dimensions
- **Horizontal**: Multiple NOC nodes with shared storage
- **Vertical**: Increase concurrent device limit
- **Caching**: Device data cached with TTL
- **Batching**: Bulk operations for efficiency

### Bottlenecks & Mitigations
| Bottleneck | Mitigation |
|------------|------------|
| SSH connection time | Connection pooling |
| Parser CPU usage | Regex optimization, caching |
| Database writes | Batch inserts, WAL mode |
| Memory for metrics | Rollup aggregation, retention |

## Extension Points

### Adding a New OS Plugin
1. Create directory: `autodetector/plugins/builtin/{os_name}/`
2. Create files:
   - `command_map.yaml`: Define CLI commands
   - `variable_map.yaml`: Define metrics with weights
   - `parser.py`: Implement parse() function
   - `help.yaml`: Device help topics
3. Register in `_registry.yaml`
4. Run validation: `nocctl plugin validate {os_name}`

### Adding a New AI Detector
1. Create detector class in `autodetector/ai/detectors.py`
2. Implement `detect(metrics, thresholds)` method
3. Register in AIEngine detector list
4. Add configuration to `config.yaml`

### Adding a New Notification Channel
1. Create sender in `autodetector/integrations/`
2. Implement `send(notification)` method
3. Register in alerting configuration
4. Add routing rule support

---

## 👥 Credits & Community

Created by: **Lily Yang**, **0xff**, **Community**, **Black Roots**, **CifSec**  
Sponsored by: **1Cloud Next Generation (1CNG)**

🌐 [1cng.cloud](https://1cng.cloud) | 💬 [Telegram](https://t.me/noc_community) | 🐦 [@1CNG_NOC](https://twitter.com/1CNG_NOC)

See [CREDITS.md](CREDITS.md) for full details.
