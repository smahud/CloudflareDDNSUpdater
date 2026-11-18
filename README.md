# Cloudflare DDNS Updater

A cross-platform Dynamic DNS updater for Cloudflare with **Windows GUI** and **Linux systemd service**. Automatically updates A/AAAA records with your current public IP address.

## 🎯 Features

| Feature | Windows | Linux |
|---------|---------|-------|
| **GUI Application** | ✅ Compact 460×360 window | ❌ (CLI only) |
| **System Tray** | ✅ Show/Update Now/Close App | ❌ |
| **Auto-start** | ✅ Registry integration | ✅ systemd enable |
| **Background Service** | ✅ `--service` mode | ✅ systemd service |
| **IPv4 Detection** | ✅ Multi-provider fallback | ✅ Multi-provider fallback |
| **IPv6 Detection** | ✅ Native + IPv4-mapped fallback | ✅ Native + IPv4-mapped fallback |
| **Change Detection** | ✅ Only updates on IP change | ✅ Only updates on IP change |
| **Config Auto-save** | ✅ Real-time YAML persistence | ✅ Manual edit |

## 📦 Quick Start

### Windows (GUI)
```bash
# Double-click CloudflareDDNS.exe or run:
CloudflareDDNS.exe --gui

# CLI modes (same executable):
CloudflareDDNS.exe --test      # Test config & connectivity
CloudflareDDNS.exe --once      # Single update (Task Scheduler)
CloudflareDDNS.exe --service   # Background daemon (no GUI)
```

### Linux (systemd service)
```bash
# 1. Copy linux/ to target server
scp -r linux/ user@server:/tmp/cloudflare-ddns/

# 2. Configure BEFORE install (REQUIRED!)
sudo mkdir -p /etc/cloudflare-ddns
cp config.yaml.example /etc/cloudflare-ddns/config.yaml
sudo nano /etc/cloudflare-ddns/config.yaml
# Fill: api_token, zone_identifier, records

# 3. Install (validates config, creates service, starts it)
sudo ./install.sh

# Manage service:
systemctl status cloudflare-ddns
journalctl -u cloudflare-ddns -f
systemctl restart cloudflare-ddns
```

## ⚙️ Configuration

### Create Cloudflare API Token
1. Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Create Token → Custom token
3. **Permissions**: `Zone > DNS > Edit` + `Zone > Zone > Read`
4. **Zone Resources**: Specific zone (your domain)

### Config Structure (`config.yaml`)
```yaml
interval_minutes: 15                    # Update interval (min 1)
api_token: "cf_your_token_here"         # Cloudflare API Token
zone_identifier: "yourdomain.com"       # Domain or Zone ID

records:                                # Records to manage
  - name: "home"                        # Subdomain (relative)
    type: "A"                           # A or AAAA
    proxied: false                      # Cloudflare proxy
    comment: "DDNS managed"
    ttl: 1                              # 1 = auto

  - name: "home"
    type: "AAAA"                        # Uses ::ffff:<ipv4> if no native IPv6
    proxied: false
    comment: "DDNS managed"
    ttl: 1

ip_detection:
  ipv4_enabled: true
  ipv6_enabled: true
  providers:                            # Fallback chain
    - "https://api.ipify.org"
    - "https://ifconfig.me/ip"
    - "https://ipinfo.io/ip"
  timeout_seconds: 10

log_level: "INFO"                       # DEBUG, INFO, WARNING, ERROR
log_file: "ddns.log"
```

### Record Name Format
- Use **relative names**: `home`, `@`, `vpn`
- `@` = root domain
- Tool constructs full name: `home.yourdomain.com`

## 🔧 Architecture

```
src/
├── main.py           # Entry point (--gui, --service, --once, --test)
├── gui.py            # Windows GUI (tkinter + pystray)
├── config.py         # YAML config loader + validation
├── ip_detector.py    # Public IP detection (IPv4/IPv6)
├── cloudflare.py     # Cloudflare API client
└── scheduler.py      # Background scheduler + updater logic
```

### IPv6 Handling
- **Native IPv6 available**: Uses real IPv6 address
- **No native IPv6 + AAAA record configured**: Uses IPv4-mapped IPv6 `::ffff:<ipv4>`
- This ensures AAAA records always have valid content

## 🔒 Security

| Rule | Implementation |
|------|----------------|
| Scoped tokens only | `Zone > DNS > Edit` + `Zone > Zone > Read` |
| Zone restriction | Token limited to specific zone |
| No Global API Key | Never supported |
| Linux hardening | `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp` |
| Windows | Runs as user, no admin required |

## 📁 Project Structure

```
CloudflareUpdater/
├── dist/                       # Windows build output
│   ├── CloudflareDDNS.exe      # Standalone executable
│   ├── config.yaml             # Your config (gitignored)
│   └── run_*.bat               # Launch helpers
├── linux/                      # Linux deployment package
│   ├── install.sh              # Validates config, creates service
│   ├── uninstall.sh            # Clean removal
│   ├── cloudflare-ddns.service # systemd template
│   ├── config.yaml.example     # Template
│   ├── README.md               # Linux docs
│   └── src/                    # Python modules (copied)
├── src/                        # Source code
│   ├── main.py
│   ├── gui.py
│   ├── config.py
│   ├── ip_detector.py
│   ├── cloudflare.py
│   └── scheduler.py
├── config.yaml.example         # Template
├── requirements.txt
└── README.md
```

## 🛠️ Development

### Build Windows Executable
```bash
pip install pyinstaller pystray pillow
pyinstaller --name CloudflareDDNS --onefile --windowed --icon=icon.ico src/main.py
```

### Run from Source
```bash
pip install -r requirements.txt

# GUI
python -m src.main --gui

# CLI
python -m src.main --test
python -m src.main --once
python -m src.main --service
```

## 📋 License

MIT License