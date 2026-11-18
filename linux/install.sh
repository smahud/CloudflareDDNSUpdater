#!/bin/bash
# Cloudflare DDNS Updater - Linux Installer
# Must run as root: sudo ./install.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="cloudflare-ddns"
INSTALL_DIR="/opt/${APP_NAME}"
CONFIG_DIR="/etc/${APP_NAME}"
SERVICE_NAME="${APP_NAME}.service"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}"
LOG_FILE="/var/log/${APP_NAME}.log"
PYTHON_CMD="python3"

# Print functions
print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Check Python availability
check_python() {
    if ! command -v ${PYTHON_CMD} &> /dev/null; then
        print_error "Python 3 is not installed. Please install python3 first."
        exit 1
    fi
    print_info "Python found: $(${PYTHON_CMD} --version)"
}

# Check required Python packages
check_python_packages() {
    print_info "Checking Python dependencies..."
    local missing=()

    for pkg in requests pyyaml; do
        if ! ${PYTHON_CMD} -c "import ${pkg}" 2>/dev/null; then
            missing+=("${pkg}")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        print_warning "Missing Python packages: ${missing[*]}"
        print_info "Installing via pip..."
        ${PYTHON_CMD} -m pip install --quiet "${missing[@]}" || {
            print_error "Failed to install Python packages. Please install manually: pip install ${missing[*]}"
            exit 1
        }
    fi
    print_success "All Python dependencies satisfied"
}

# Validate config.yaml
validate_config() {
    local config_file="${CONFIG_DIR}/config.yaml"

    if [[ ! -f "${config_file}" ]]; then
        print_error "Config file not found: ${config_file}"
        print_info "Please create config.yaml in ${CONFIG_DIR} before running installer."
        print_info "Example:"
        cat << EOF
# ${CONFIG_DIR}/config.yaml
interval_minutes: 15
api_token: "your-cloudflare-api-token"
zone_identifier: "yourdomain.com"
records:
  - name: "home"
    type: "A"
    proxied: false
    comment: "DDNS managed"
  - name: "home"
    type: "AAAA"
    proxied: false
    comment: "DDNS managed"
ip_detection:
  ipv4_enabled: true
  ipv6_enabled: true
  providers:
    - "https://api.ipify.org"
    - "https://ifconfig.me/ip"
    - "https://ipinfo.io/ip"
  timeout_seconds: 10
log_level: "INFO"
log_file: "/var/log/cloudflare-ddns.log"
EOF
        exit 1
    fi

    print_info "Validating configuration..."

    # Use Python to validate config
    ${PYTHON_CMD} -c "
import yaml, sys
from pathlib import Path

config_path = Path('${config_file}')
with open(config_path) as f:
    data = yaml.safe_load(f)

errors = []

if not data.get('api_token') or not data['api_token'].strip():
    errors.append('api_token is required')
if not data.get('zone_identifier') or not data['zone_identifier'].strip():
    errors.append('zone_identifier is required')
if not data.get('records'):
    errors.append('At least one record must be configured')
else:
    for i, r in enumerate(data['records']):
        if r.get('type') not in ('A', 'AAAA'):
            errors.append(f'Record {i}: type must be A or AAAA')
        if not r.get('name') or not r['name'].strip():
            errors.append(f'Record {i}: name is required')

if errors:
    for e in errors:
        print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)

print('Config validation passed')
" || exit 1

    print_success "Configuration validated successfully"
}

# Create directories
create_directories() {
    print_info "Creating directories..."
    mkdir -p "${INSTALL_DIR}/src"
    mkdir -p "${CONFIG_DIR}"
    mkdir -p "$(dirname "${LOG_FILE}")"
    print_success "Directories created"
}

# Copy application files
copy_files() {
    print_info "Copying application files..."

    # Copy source files
    cp -r src/* "${INSTALL_DIR}/src/"

    # Copy config if not exists
    if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
        cp config.yaml.example "${CONFIG_DIR}/config.yaml"
        print_warning "Created example config at ${CONFIG_DIR}/config.yaml - PLEASE EDIT IT!"
    fi

    # Set permissions
    chmod 755 "${INSTALL_DIR}/src/main.py"
    chmod 644 "${CONFIG_DIR}/config.yaml"

    print_success "Files copied"
}

# Create systemd service file
create_service() {
    print_info "Creating systemd service..."

    cat > "${SERVICE_FILE}" << EOF
[Unit]
Description=Cloudflare DDNS Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
ExecStart=${PYTHON_CMD} -m src.main --service
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${APP_NAME}

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=${CONFIG_DIR} $(dirname "${LOG_FILE}")
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
EOF

    print_success "Service file created: ${SERVICE_FILE}"
}

# Reload systemd and enable service
enable_service() {
    print_info "Reloading systemd daemon..."
    systemctl daemon-reload

    print_info "Enabling service..."
    systemctl enable "${SERVICE_NAME}"

    print_success "Service enabled"
}

# Start service
start_service() {
    print_info "Starting service..."
    systemctl start "${SERVICE_NAME}"

    sleep 2

    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        print_success "Service started successfully"
        print_info "Check status: systemctl status ${SERVICE_NAME}"
        print_info "View logs: journalctl -u ${SERVICE_NAME} -f"
    else
        print_error "Service failed to start"
        systemctl status "${SERVICE_NAME}" --no-pager
        exit 1
    fi
}

# Main installation flow
main() {
    echo "=========================================="
    echo "  Cloudflare DDNS Updater - Linux Installer"
    echo "=========================================="
    echo ""

    check_root
    check_python
    check_python_packages
    validate_config
    create_directories
    copy_files
    create_service
    enable_service
    start_service

    echo ""
    echo "=========================================="
    print_success "Installation completed successfully!"
    echo "=========================================="
    echo ""
    echo "Service: ${SERVICE_NAME}"
    echo "Config: ${CONFIG_DIR}/config.yaml"
    echo "Logs: journalctl -u ${SERVICE_NAME} -f"
    echo ""
    echo "Commands:"
    echo "  Start:   systemctl start ${SERVICE_NAME}"
    echo "  Stop:    systemctl stop ${SERVICE_NAME}"
    echo "  Restart: systemctl restart ${SERVICE_NAME}"
    echo "  Status:  systemctl status ${SERVICE_NAME}"
    echo "  Logs:    journalctl -u ${SERVICE_NAME} -f"
    echo "  Uninstall: sudo ./uninstall.sh"
}

main "$@"