# Cloudflare DDNS Updater - Agent Contract

This document defines the expected behavior, interfaces, and constraints for any agent working on this project.

---

## 🎯 Project Purpose

Build and maintain a **cross-platform Cloudflare DDNS updater** with:
- **Windows**: Standalone GUI executable (`.exe`) with system tray
- **Linux**: systemd service with installer/uninstaller

Both share the same Python core (`src/`).

---

## 📋 Functional Requirements (MUST)

### Core Features
1. **DNS Record Management**
   - Update A (IPv4) and AAAA (IPv6) records in Cloudflare
   - Only manage records explicitly listed in `config.yaml`
   - Never touch other records in the zone

2. **IP Detection**
   - Detect public IPv4 via multiple providers (fallback chain)
   - Detect public IPv6 via multiple providers (fallback chain)
   - **Critical**: If no native IPv6 but AAAA record exists → use IPv4-mapped `::ffff:<ipv4>`

3. **Change Detection**
   - Only call Cloudflare API when IP actually changed
   - Track last known IP per record (name + type)

4. **Configuration**
   - YAML-based config (`config.yaml`)
   - Hot-reload: changes auto-saved, scheduler restarts on interval change
   - Validation on load with clear error messages

### Windows GUI Requirements
1. **Default behavior**: Double-click `.exe` → GUI appears immediately
2. **Window**: 460×360, resizable width only
3. **System Tray**:
   - Right-click menu: **Show**, **Update Now**, **Close App**
   - Hide to tray via: **Hide** button, **Close** (if "Hide to tray" checked)
   - Double-click tray icon → Show window
4. **Auto-start**: Checkbox → Windows Registry `Run` key
5. **Auto-hide on close**: Checkbox → Close button hides to tray
6. **Minimize**: Standard taskbar minimize (not hide)
7. **Process cleanup**: Close/Exit → **process completely gone** from Task Manager

### Linux Service Requirements
1. **Installer** (`install.sh`):
   - **Must validate config.yaml before ANY installation step**
   - Exit with error if config invalid (missing token, zone, records)
   - Install Python deps (requests, pyyaml)
   - Copy to `/opt/cloudflare-ddns/`
   - Create hardened systemd service
   - Enable and start service

2. **Service** (`--service` mode):
   - Run as background daemon
   - Read config from `/etc/cloudflare-ddns/config.yaml`
   - Log to systemd journal
   - Restart on failure (`Restart=always`)

3. **Uninstaller** (`uninstall.sh`):
   - Stop and disable service
   - Remove service file
   - Optionally remove config and logs

---

## 🔧 Technical Constraints

### Python Version
- **Minimum**: Python 3.8+
- **Target**: 3.10+ (tested on 3.12)

### Dependencies (minimal)
```
requests >= 2.31.0
pyyaml >= 6.0
pystray >= 0.19.0 (Windows GUI only)
pillow >= 10.0.0 (Windows GUI only)
```

### Cloudflare API
- **Auth**: API Token only (Bearer), never Global API Key
- **Permissions**: `Zone > DNS > Edit`, `Zone > Zone > Read`
- **Zone**: Specific zone only
- **Endpoints**:
  - `GET /zones?name={domain}` - resolve zone ID
  - `GET /zones/{id}/dns_records` - list records
  - `POST /zones/{id}/dns_records` - create record
  - `PUT /zones/{id}/dns_records/{id}` - update record

### Config Schema
```yaml
interval_minutes: int (>=1)
api_token: string (non-empty)
zone_identifier: string (non-empty)
records:
  - name: string (non-empty)
    type: "A" | "AAAA"
    proxied: bool (default: false)
    comment: string (default: "")
    ttl: int (default: 1)
ip_detection:
  ipv4_enabled: bool (default: true)
  ipv6_enabled: bool (default: true)
  providers: string[] (default: 5 providers)
  timeout_seconds: int (default: 10)
log_level: "DEBUG" | "INFO" | "WARNING" | "ERROR"
log_file: string
```

---

## 🚫 Anti-Patterns (MUST NOT)

| Anti-Pattern | Correct Approach |
|--------------|------------------|
| Use Global API Key | Use scoped API Token only |
| Update all zone records | Only update records in config |
| Skip IPv6 for AAAA | Use `::ffff:<ipv4>` fallback |
| Leave process on close | `os._exit(0)` after cleanup |
| Hardcode paths | Use `get_base_dir()` for frozen exe |
| Embed secrets in repo | `.gitignore` config.yaml, data.txt |
| Skip config validation | Validate on load, exit with errors |
| Single IP provider | Fallback chain (5 providers) |

---

## 🧪 Testing Requirements

### Before Any Push
```bash
# Windows
./dist/CloudflareDDNS.exe --test      # Must exit 0
./dist/CloudflareDDNS.exe --once      # Must exit 0

# Linux (source)
python -m src.main --test
python -m src.main --once
```

### Manual Verification Checklist
- [ ] Double-click exe → GUI shows
- [ ] Close (auto-hide OFF) → process gone
- [ ] Close (auto-hide ON) → hides to tray
- [ ] Tray → "Close App" → process gone
- [ ] Tray → "Update Now" → triggers update
- [ ] Minimize → taskbar (not tray)
- [ ] `--test` validates config + API + IP
- [ ] `--once` runs single cycle, exits
- [ ] `--service` runs daemon, logs to journal
- [ ] AAAA record gets `::ffff:<ipv4>` when no IPv6

---

## 📦 Build & Release

### Windows
```bash
pip install pyinstaller pystray pillow
pyinstaller --name CloudflareDDNS --onefile --windowed --icon=icon.ico \
  --add-data "config.yaml;." --add-data "config.yaml.example;." \
  src/main.py
```

### Linux Package
```bash
# Copy src/ to linux/src/
# Ensure install.sh, uninstall.sh executable
# Test: sudo ./install.sh (with valid config)
```

---

## 🔄 Change Management

### Adding New Features
1. Update `CONTRACT.md` first (this file)
2. Implement in `src/` (shared core)
3. Test both Windows GUI and Linux service modes
4. Update `README.md` and `linux/README.md`
5. Build Windows exe, test all scenarios

### Config Changes
- Add new fields with defaults in `config.py` dataclasses
- Maintain backward compatibility
- Document in `config.yaml.example` and README

---

## 📍 Key Files Reference

| File | Purpose |
|------|---------|
| `src/main.py` | Entry point (--gui, --service, --once, --test) |
| `src/gui.py` | Windows GUI (tkinter + pystray) |
| `src/config.py` | Config loader, validation, base_dir resolver |
| `src/ip_detector.py` | IP detection with fallback |
| `src/cloudflare.py` | Cloudflare API client |
| `src/scheduler.py` | Background scheduler + updater |
| `linux/install.sh` | Validates config, creates systemd service |
| `linux/uninstall.sh` | Clean removal |
| `dist/CloudflareDDNS.exe` | Windows build output |

---

## ✅ Definition of Done

A task is complete when:
1. All functional requirements met
2. All anti-patterns avoided
3. Windows exe tested: GUI, tray, close, minimize, process cleanup
4. Linux service tested: install, start, logs, uninstall
5. Config validation works (exits on invalid)
6. IPv4-mapped IPv6 works for AAAA
7. No credentials in repo (`.gitignore` verified)
8. README and CONTRACT updated

---

*This contract is binding for all agents working on this project. Update it when requirements change.*