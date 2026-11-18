# Cloudflare DDNS Updater - Linux Version

Linux systemd service for automatic Cloudflare DNS updates.

## Requirements

- Linux with systemd (Ubuntu 18.04+, Debian 10+, CentOS 7+, RHEL 7+, etc.)
- Python 3.6+
- Root/sudo access for installation

## Quick Install

```bash
# 1. Copy linux folder to target machine
scp -r linux/ user@server:/tmp/cloudflare-ddns/

# 2. On target machine, configure FIRST
cd /tmp/cloudflare-ddns/linux
sudo mkdir -p /etc/cloudflare-ddns
cp config.yaml.example /etc/cloudflare-ddns/config.yaml

# 3. EDIT CONFIG (REQUIRED!)
sudo nano /etc/cloudflare-ddns/config.yaml
# Fill in: api_token, zone_identifier, records

# 4. Run installer
sudo ./install.sh
```

## Configuration

Edit `/etc/cloudflare-ddns/config.yaml` before installing:

```yaml
api_token: "cf_xxxxxxxxxxxxx"          # Your Cloudflare API token
zone_identifier: "example.com"         # Your domain
records:
  - name: "home"                       # Subdomain
    type: "A"                          # A or AAAA
    proxied: false                     # DNS only
    comment: "DDNS managed"
```

### Get API Token
1. Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens)
2. Create Token → Custom token
3. Permissions: `Zone > DNS > Edit` + `Zone > Zone > Read`
4. Zone Resources: Specific zone (your domain)

## Installer Actions

`install.sh` performs:
1. ✅ Validates config.yaml (exits if invalid)
2. ✅ Installs Python dependencies (requests, pyyaml)
3. ✅ Copies files to `/opt/cloudflare-ddns/`
4. ✅ Creates systemd service at `/etc/systemd/system/cloudflare-ddns.service`
5. ✅ Enables and starts service
6. ✅ Hardens service (no new privs, private tmp, protect system)

## Service Management

```bash
# Status
systemctl status cloudflare-ddns

# Logs (follow)
journalctl -u cloudflare-ddns -f

# Start/Stop/Restart
systemctl start cloudflare-ddns
systemctl stop cloudflare-ddns
systemctl restart cloudflare-ddns

# Disable auto-start
systemctl disable cloudflare-ddns
```

## Uninstall

```bash
cd /tmp/cloudflare-ddns/linux
sudo ./uninstall.sh
```

Options:
- Removes service and binary
- Optionally removes config (`/etc/cloudflare-ddns/`)
- Optionally removes logs (`/var/log/cloudflare-ddns.log`)

## How It Works

- Runs as `python3 -m src.main --service` (background daemon)
- Detects public IPv4/IPv6 every `interval_minutes`
- Updates only configured A/AAAA records
- If no native IPv6 but AAAA record exists → uses IPv4-mapped `::ffff:<ipv4>`
- Only manages records listed in config.yaml
- Logs to systemd journal + optional file

## File Locations

| Component | Path |
|-----------|------|
| Binary | `/opt/cloudflare-ddns/` |
| Config | `/etc/cloudflare-ddns/config.yaml` |
| Service | `/etc/systemd/system/cloudflare-ddns.service` |
| Logs | `journalctl -u cloudflare-ddns` |
| Log file | `/var/log/cloudflare-ddns.log` (optional) |

## Security

The systemd service runs with hardening:
- `NoNewPrivileges=true`
- `PrivateTmp=true`
- `ProtectSystem=strict`
- `ProtectHome=true`
- `ReadWritePaths` limited to config and log dirs only

## Troubleshooting

**Service won't start:**
```bash
journalctl -u cloudflare-ddns -n 50
```

**Config validation fails:**
```bash
python3 -c "
import yaml
with open('/etc/cloudflare-ddns/config.yaml') as f:
    print(yaml.safe_load(f))
"
```

**Test manually:**
```bash
cd /opt/cloudflare-ddns
python3 -m src.main --test
python3 -m src.main --once
```

## IPv6 Handling

If your network doesn't have native IPv6 but you have AAAA records configured:
- The updater automatically uses IPv4-mapped IPv6 addresses (`::ffff:1.2.3.4`)
- This ensures AAAA records always have valid content
- Native IPv6 is used when available

## License

MIT License