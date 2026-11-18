# Cloudflare DDNS Updater

A Python-based Dynamic DNS updater for Cloudflare that automatically updates A/AAAA records with your current public IP address.

## Features

- **Multiple record support**: Manage multiple A and AAAA records
- **IPv4 & IPv6 detection**: Automatic detection with fallback providers
- **Scoped API Token**: Uses Cloudflare API Token (not Global API Key) for security
- **Configurable interval**: Run updates at any minute interval
- **Change detection**: Only updates records when IP actually changes
- **Structured logging**: Console and file logging with levels
- **Graceful shutdown**: Handles SIGINT/SIGTERM properly

## Quick Start

### 1. Create Cloudflare API Token

Go to [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) and create a token with:
- **Permissions**: `Zone > DNS > Edit` + `Zone > Zone > Read`
- **Zone Resources**: Specific zone (e.g., `yapsidarussalam.or.id`)

### 2. Configure

Copy `config.yaml.example` to `config.yaml` and edit:

```yaml
interval_minutes: 15
api_token: "your-api-token-here"
zone_identifier: "yourdomain.com"  # or zone ID
records:
  - name: "home"       # subdomain (e.g., home.yourdomain.com)
    type: "A"
    proxied: false
    comment: "DDNS managed"
  - name: "home"
    type: "AAAA"
    proxied: false
    comment: "DDNS managed"
```

### 3. Run

```bash
# Test configuration
python -m src.main --test

# Run once
python -m src.main --once

# Run as daemon (scheduler)
python -m src.main
```

## Configuration Reference

| Setting | Description | Default |
|---------|-------------|---------|
| `interval_minutes` | Update interval in minutes | Required |
| `api_token` | Cloudflare API Token | Required |
| `zone_identifier` | Domain name or Zone ID | Required |
| `records` | List of DNS records to manage | Required |
| `records[].name` | Subdomain (relative to zone) | Required |
| `records[].type` | "A" or "AAAA" | Required |
| `records[].proxied` | Enable Cloudflare proxy | `false` |
| `records[].comment` | Record comment | `""` |
| `records[].ttl` | TTL in seconds (1=auto) | `1` |
| `ip_detection.ipv4_enabled` | Enable IPv4 detection | `true` |
| `ip_detection.ipv6_enabled` | Enable IPv6 detection | `true` |
| `ip_detection.providers` | IP detection endpoints | See config |
| `ip_detection.timeout_seconds` | Request timeout | `10` |
| `log_level` | Logging level | `INFO` |
| `log_file` | Log file path | `ddns.log` |

## Record Name Format

- Use **relative names** in config (e.g., `home`, `@`, `vpn`)
- The tool automatically constructs full DNS names (e.g., `home.yourdomain.com`)
- `@` represents the root domain

## Running as a Service

### Windows (Task Scheduler)
1. Create a Basic Task
2. Trigger: Daily, repeat every 15 minutes
3. Action: `python.exe` with arguments `-m src.main --once`
4. Start in: `C:\path\to\CloudflareUpdater`

### Linux (systemd)
Create `/etc/systemd/system/cloudflare-ddns.service`:
```ini
[Unit]
Description=Cloudflare DDNS Updater
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/cloudflare-ddns
ExecStart=/usr/bin/python3 -m src.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now cloudflare-ddns
```

### Docker
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY src/ src/
COPY config.yaml .
CMD ["python", "-m", "src.main"]
```

## Logging

Logs are written to both console and `ddns.log` (configurable). Log levels:
- `DEBUG`: Detailed diagnostic info
- `INFO`: General operation info (default)
- `WARNING`: Issues that don't stop operation
- `ERROR`: Failed operations

## Security Notes

- **Never use Global API Key** - Use scoped API Tokens only
- **Restrict token permissions** - Only `Zone > DNS > Edit` and `Zone > Zone > Read`
- **Limit zone access** - Token should only access the specific zone
- **Rotate tokens periodically** - Treat tokens like passwords

## License

MIT License