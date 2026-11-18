#!/bin/bash
# Cloudflare DDNS Updater - Linux Uninstaller
# Must run as root: sudo ./uninstall.sh

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

# Stop and disable service
stop_service() {
    print_info "Stopping service..."
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl stop "${SERVICE_NAME}"
        print_success "Service stopped"
    else
        print_info "Service not running"
    fi

    print_info "Disabling service..."
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        systemctl disable "${SERVICE_NAME}"
        print_success "Service disabled"
    else
        print_info "Service not enabled"
    fi
}

# Remove service file
remove_service_file() {
    print_info "Removing service file..."
    if [[ -f "${SERVICE_FILE}" ]]; then
        rm -f "${SERVICE_FILE}"
        systemctl daemon-reload
        print_success "Service file removed"
    else
        print_info "Service file not found"
    fi
}

# Remove installation files
remove_files() {
    print_info "Removing installation files..."

    if [[ -d "${INSTALL_DIR}" ]]; then
        rm -rf "${INSTALL_DIR}"
        print_success "Removed ${INSTALL_DIR}"
    fi

    # Ask about config removal
    if [[ -d "${CONFIG_DIR}" ]]; then
        echo ""
        read -p "Remove configuration directory ${CONFIG_DIR}? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "${CONFIG_DIR}"
            print_success "Removed ${CONFIG_DIR}"
        else
            print_info "Configuration preserved at ${CONFIG_DIR}"
        fi
    fi

    # Ask about log removal
    if [[ -f "${LOG_FILE}" ]]; then
        echo ""
        read -p "Remove log file ${LOG_FILE}? (y/N): " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "${LOG_FILE}"
            print_success "Removed ${LOG_FILE}"
        else
            print_info "Log file preserved at ${LOG_FILE}"
        fi
    fi
}

# Main uninstallation flow
main() {
    echo "=========================================="
    echo "  Cloudflare DDNS Updater - Linux Uninstaller"
    echo "=========================================="
    echo ""

    check_root

    print_warning "This will remove the Cloudflare DDNS Updater service and files."
    read -p "Continue? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Uninstall cancelled"
        exit 0
    fi

    stop_service
    remove_service_file
    remove_files

    echo ""
    echo "=========================================="
    print_success "Uninstallation completed!"
    echo "=========================================="
}

main "$@"