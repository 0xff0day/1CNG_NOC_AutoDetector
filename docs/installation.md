# Installation Guide

## System Requirements

### Minimum Requirements
- **CPU**: 2 cores
- **RAM**: 4 GB
- **Disk**: 20 GB free space
- **OS**: Linux (Ubuntu 20.04+, RHEL 8+, Debian 11+) / macOS 11+ / Windows Server 2019+
- **Python**: 3.9 or higher
- **Network**: SSH access to target devices

### Recommended Requirements
- **CPU**: 4+ cores
- **RAM**: 8 GB
- **Disk**: 50 GB SSD
- **Database**: SQLite (default) or PostgreSQL (for production)

---

## Installation Methods

### Method 1: Direct Installation (Recommended)

#### Step 1: Install Python Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv git

# RHEL/CentOS/Rocky
sudo dnf install python3 python3-pip git

# macOS (using Homebrew)
brew install python3 git
```

#### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/1CNG_NOC_AutoDetector.git
cd 1CNG_NOC_AutoDetector
```

#### Step 3: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows
```

#### Step 4: Install Python Packages

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 5: Verify Installation

```bash
python nocctl.py --help
```

---

### Method 2: Docker Installation

#### Using Docker Compose (Recommended for Production)

```yaml
# docker-compose.yaml
version: '3.8'

services:
  noc:
    image: 1cng/noc-autodetector:latest
    container_name: noc-autodetector
    restart: unless-stopped
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./reports:/app/reports
    environment:
      - NOC_CONFIG=/app/config/config.yaml
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      - TWILIO_ACCOUNT_SID=${TWILIO_ACCOUNT_SID}
      - TWILIO_AUTH_TOKEN=${TWILIO_AUTH_TOKEN}
    ports:
      - "8080:8080"  # Health check endpoint
    command: ["python", "nocctl.py", "schedule", "--mode", "normal"]
```

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f noc

# Run one-time scan
docker-compose exec noc python nocctl.py scan --all
```

#### Using Docker Run

```bash
# Pull image
docker pull 1cng/noc-autodetector:latest

# Run container
docker run -d \
  --name noc-autodetector \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/reports:/app/reports \
  -e TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN \
  -e TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID \
  1cng/noc-autodetector:latest \
  python nocctl.py schedule --mode normal
```

---

### Method 3: Systemd Service (Linux Production)

#### Create Service File

```bash
sudo tee /etc/systemd/system/noc-autodetector.service << 'EOF'
[Unit]
Description=1CNG NOC AutoDetector
After=network.target

[Service]
Type=simple
User=noc
Group=noc
WorkingDirectory=/opt/noc-autodetector
Environment=PATH=/opt/noc-autodetector/venv/bin
Environment=NOC_CONFIG=/opt/noc-autodetector/config/config.yaml
Environment=TELEGRAM_BOT_TOKEN={{TELEGRAM_BOT_TOKEN}}
Environment=TELEGRAM_CHAT_ID={{TELEGRAM_CHAT_ID}}
Environment=TWILIO_ACCOUNT_SID={{TWILIO_ACCOUNT_SID}}
Environment=TWILIO_AUTH_TOKEN={{TWILIO_AUTH_TOKEN}}
ExecStart=/opt/noc-autodetector/venv/bin/python nocctl.py schedule --mode normal
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=noc-autodetector

[Install]
WantedBy=multi-user.target
EOF
```

#### Setup Service

```bash
# Create user
sudo useradd -r -s /bin/false -d /opt/noc-autodetector noc

# Set permissions
sudo chown -R noc:noc /opt/noc-autodetector
sudo chmod 750 /opt/noc-autodetector

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable noc-autodetector
sudo systemctl start noc-autodetector

# Check status
sudo systemctl status noc-autodetector
sudo journalctl -u noc-autodetector -f
```

---

## Initial Configuration

### Step 1: Copy Example Configuration

```bash
cp config/config.example.yaml config/config.yaml
```

### Step 2: Configure Devices

Edit `config/config.yaml`:

```yaml
devices:
  # Network Device Example - Cisco Router
  - id: "core-router-01"
    name: "Core Router 1"
    host: "10.0.0.1"
    transport: "ssh"
    os: "cisco_ios"
    credential_ref: "network-admin"
    tags: ["network", "core", "critical"]
    location: "Main DC"
    
  # Server Example - Ubuntu
  - id: "web-server-01"
    name: "Web Server 1"
    host: "10.0.1.10"
    transport: "ssh"
    os: "ubuntu"
    credential_ref: "server-admin"
    tags: ["server", "web", "production"]
    
  # Hypervisor Example - VMware ESXi
  - id: "esxi-host-01"
    name: "ESXi Host 1"
    host: "10.0.2.10"
    transport: "ssh"
    os: "vmware_esxi"
    credential_ref: "vmware-admin"
    tags: ["hypervisor", "vmware", "critical"]
```

### Step 3: Configure Credentials

Create `config/credentials.yaml`:

```yaml
credentials:
  network-admin:
    username: "admin"
    password: "${NETWORK_ADMIN_PASSWORD}"  # Use env var
    
  server-admin:
    username: "noc-monitor"
    ssh_key: "/opt/noc-autodetector/.ssh/id_rsa"
    
  vmware-admin:
    username: "root"
    password: "${ESXI_ROOT_PASSWORD}"
```

**Security Note**: Never commit credentials to git. Use environment variables or a secrets manager.

### Step 4: Configure Telegram

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get chat ID by messaging the bot
3. Set environment variables:

```bash
export TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export TELEGRAM_CHAT_ID="-1001234567890"
```

Or add to `config/config.yaml`:

```yaml
integrations:
  telegram:
    enabled: true
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"
```

### Step 5: Configure Voice Calls (Twilio)

1. Create [Twilio account](https://www.twilio.com/try-twilio)
2. Get Account SID and Auth Token
3. Buy a phone number
4. Set environment variables:

```bash
export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
export TWILIO_AUTH_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Add to config:

```yaml
integrations:
  voice_call:
    enabled: true
    provider: "twilio"
    account_sid: "${TWILIO_ACCOUNT_SID}"
    auth_token: "${TWILIO_AUTH_TOKEN}"
    from_number: "+15555550100"
    to_numbers:
      - "+15555550101"
      - "+15555550102"
```

---

## Post-Installation Verification

### 1. Test Configuration

```bash
# Validate config
nocctl config validate

# Expected output:
# Configuration is valid ✓
```

### 2. Test Device Connectivity

```bash
# Test single device
nocctl scan --device core-router-01 --once

# Test OS detection
nocctl detect-os 10.0.0.1 --verbose
```

### 3. Test Alerts

```bash
# Send test Telegram message
nocctl alerts test --channel telegram

# Test voice call
nocctl alerts test --channel voice
```

### 4. Check System Health

```bash
nocctl health --verbose
```

---

## Production Hardening

### 1. Database Migration (SQLite → PostgreSQL)

For high-volume deployments, migrate to PostgreSQL:

```yaml
# config/config.yaml
storage:
  type: "postgresql"
  host: "localhost"
  port: 5432
  database: "noc"
  username: "noc"
  password: "${DB_PASSWORD}"
  pool_size: 10
```

### 2. Enable SSL/TLS

```yaml
# For SSH connections
security:
  ssh:
    verify_host_keys: true
    allowed_key_types: ["rsa", "ecdsa", "ed25519"]
    
# For webhooks
integrations:
  webhooks:
    verify_ssl: true
    custom_ca: "/path/to/ca.crt"
```

### 3. Configure Retention

```yaml
retention:
  metrics_days: 90          # Keep metrics for 90 days
  alerts_days: 365          # Keep alerts for 1 year
  rollup_keep_days: 730     # Keep rollups for 2 years
  audit_days: 2555          # Keep audit logs for 7 years
  
rollup:
  enabled: true
  hourly: true
  daily: true
  monthly: true
```

### 4. Setup Log Rotation

```bash
# /etc/logrotate.d/noc-autodetector
/opt/noc-autodetector/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 noc noc
    sharedscripts
    postrotate
        systemctl reload noc-autodetector
    endscript
}
```

---

## Troubleshooting Installation

### Issue: Permission Denied

```bash
# Fix permissions
sudo chown -R $(whoami):$(whoami) /opt/noc-autodetector
chmod 750 /opt/noc-autodetector
chmod 600 /opt/noc-autodetector/config/credentials.yaml
```

### Issue: Python Module Not Found

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall requirements
pip install -r requirements.txt --force-reinstall
```

### Issue: SSH Connection Fails

```bash
# Test SSH manually
ssh -i ~/.ssh/noc_key noc-monitor@device-ip

# Check SSH key permissions
chmod 600 ~/.ssh/noc_key

# Enable verbose logging
nocctl scan --device test-device --verbose 2>&1 | tee debug.log
```

### Issue: Telegram Not Working

```bash
# Test Telegram bot
curl -X POST \
  "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}" \
  -d "text=Test message from NOC"
```

---

## Upgrade Procedures

### Upgrade to New Version

```bash
# 1. Stop service
sudo systemctl stop noc-autodetector

# 2. Backup
cd /opt/noc-autodetector
nocctl backup create --name pre-upgrade-$(date +%Y%m%d)

# 3. Pull updates
git pull origin main

# 4. Update dependencies
source venv/bin/activate
pip install -r requirements.txt --upgrade

# 5. Migrate config if needed
nocctl config migrate --to-version $(cat VERSION)

# 6. Validate
nocctl config validate
nocctl health

# 7. Start service
sudo systemctl start noc-autodetector
```

---

## Uninstallation

```bash
# Stop service
sudo systemctl stop noc-autodetector
sudo systemctl disable noc-autodetector

# Remove files
sudo rm -rf /opt/noc-autodetector
sudo rm /etc/systemd/system/noc-autodetector.service

# Remove data (optional)
sudo rm -rf /var/lib/noc-autodetector
```

---

## Next Steps

After installation:

1. **Add devices**: Use `nocctl discover` or edit `config/config.yaml`
2. **Test plugins**: Run `nocctl plugin validate` for each OS type
3. **Start monitoring**: `nocctl workflow schedule --all --enable`
4. **Setup alerts**: Configure routing in `config/config.yaml`
5. **Schedule reports**: Setup cron for daily/weekly reports

See [Configuration Reference](configuration.md) for detailed settings.
