"""Cloudflare DDNS Updater - Main entry point."""
import sys
import argparse
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config, setup_logging, get_base_dir
from ip_detector import IPDetector
from cloudflare import CloudflareClient
from scheduler import DDNSUpdater, Scheduler


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Cloudflare DDNS Updater',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  CloudflareDDNS.exe                    # Launch GUI (default)
  CloudflareDDNS.exe --once             # Run once and exit
  CloudflareDDNS.exe --test             # Test configuration and exit
  CloudflareDDNS.exe --service          # Run as background service (no GUI)
  CloudflareDDNS.exe -c custom.yaml     # Use custom config file
        """
    )
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (no scheduler)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test configuration and API connectivity, then exit'
    )
    parser.add_argument(
        '--service',
        action='store_true',
        help='Run as background service (no GUI)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable debug logging'
    )
    return parser.parse_args()


def test_config(config: Config, logger) -> bool:
    """Test configuration and API connectivity."""
    logger.info("Testing configuration...")

    # Test Cloudflare API
    try:
        cf = CloudflareClient(config.api_token, config.zone_identifier)
        zone_id = cf.get_zone_id()
        logger.info(f"[OK] Cloudflare API connected (zone_id: {zone_id})")

        # Test record access
        for record_config in config.records:
            existing = cf.get_dns_record(record_config.name, record_config.type)
            if existing:
                logger.info(f"[OK] Found existing {record_config.type} record: {record_config.name} -> {existing.content}")
            else:
                logger.info(f"[OK] No existing {record_config.type} record for {record_config.name} (will create)")

    except Exception as e:
        logger.error(f"[ERROR] Cloudflare API test failed: {e}")
        return False

    # Test IP detection
    try:
        detector = IPDetector(
            providers=config.ip_detection.providers,
            timeout=config.ip_detection.timeout_seconds,
            ipv4_enabled=config.ip_detection.ipv4_enabled,
            ipv6_enabled=config.ip_detection.ipv6_enabled
        )
        ips = detector.detect_all()
        if ips.ipv4:
            logger.info(f"[OK] IPv4 detected: {ips.ipv4}")
        else:
            logger.warning("[WARN] No IPv4 detected")
        if ips.ipv6:
            logger.info(f"[OK] IPv6 detected: {ips.ipv6}")
        else:
            logger.warning("[WARN] No IPv6 detected")

        if not ips.ipv4 and not ips.ipv6:
            logger.error("[ERROR] No IP addresses detected")
            return False

    except Exception as e:
        logger.error(f"[ERROR] IP detection test failed: {e}")
        return False

    logger.info("[OK] All tests passed!")
    return True


def run_gui():
    """Launch GUI application."""
    try:
        from gui import main as gui_main
        gui_main()
    except ImportError as e:
        print(f"GUI not available: {e}")
        print("Install dependencies: pip install pystray pillow")
        sys.exit(1)
    except Exception as e:
        print(f"GUI error: {e}")
        sys.exit(1)


def run_service(config: Config, logger):
    """Run as background service (no GUI)."""
    # Initialize components
    cf_client = CloudflareClient(config.api_token, config.zone_identifier)
    ip_detector = IPDetector(
        providers=config.ip_detection.providers,
        timeout=config.ip_detection.timeout_seconds,
        ipv4_enabled=config.ip_detection.ipv4_enabled,
        ipv6_enabled=config.ip_detection.ipv6_enabled
    )
    updater = DDNSUpdater(config, cf_client, ip_detector, logger)

    # Scheduler mode
    scheduler = Scheduler(config.interval_minutes, updater)
    scheduler.run()


def main():
    args = parse_args()
    base_dir = get_base_dir()

    # Default behavior (no args or double-click) -> GUI mode
    # Unless --service, --once, or --test explicitly specified
    if args.service:
        # Load configuration
        try:
            config = Config.load(args.config, base_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error parsing config: {e}")
            sys.exit(1)

        if args.verbose:
            config.log_level = 'DEBUG'

        logger = setup_logging(config, base_dir)
        logger.info("Cloudflare DDNS Updater starting (service mode)...")

        errors = config.validate()
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            sys.exit(1)

        run_service(config, logger)
        return

    if args.once or args.test:
        # Load configuration
        try:
            config = Config.load(args.config, base_dir)
        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"Error parsing config: {e}")
            sys.exit(1)

        if args.verbose:
            config.log_level = 'DEBUG'

        logger = setup_logging(config, base_dir)
        logger.info("Cloudflare DDNS Updater starting...")

        errors = config.validate()
        if errors:
            for error in errors:
                logger.error(f"Config error: {error}")
            sys.exit(1)

        # Initialize components
        cf_client = CloudflareClient(config.api_token, config.zone_identifier)
        ip_detector = IPDetector(
            providers=config.ip_detection.providers,
            timeout=config.ip_detection.timeout_seconds,
            ipv4_enabled=config.ip_detection.ipv4_enabled,
            ipv6_enabled=config.ip_detection.ipv6_enabled
        )
        updater = DDNSUpdater(config, cf_client, ip_detector, logger)

        # Test mode
        if args.test:
            success = test_config(config, logger)
            sys.exit(0 if success else 1)

        # Run once mode
        if args.once:
            logger.info("Running single update cycle...")
            updater.run_once()
            logger.info("Done.")
        return

    # Default: GUI mode
    run_gui()


if __name__ == '__main__':
    # Ensure clean exit on Windows
    os._exit(main() or 0)