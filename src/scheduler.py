"""Scheduler for periodic DDNS updates."""
import time
import signal
import logging
from typing import Callable, Optional
from threading import Event

logger = logging.getLogger('cloudflare_ddns.scheduler')


class DDNSUpdater:
    """Main DDNS update logic."""

    def __init__(self, config, cloudflare_client, ip_detector, logger):
        self.config = config
        self.cloudflare = cloudflare_client
        self.ip_detector = ip_detector
        self.logger = logger
        self._last_ips = {}  # Track last known IPs per record type

    def _get_aaaa_content(self, ips) -> str:
        """Get AAAA record content. If no native IPv6, use IPv4-mapped IPv6 address."""
        if ips.ipv6:
            return ips.ipv6
        if ips.ipv4:
            return f"::ffff:{ips.ipv4}"
        return ""

    def run_once(self) -> bool:
        """Run a single update cycle. Returns True if any record was updated."""
        self.logger.info("Starting DDNS update cycle...")

        # Detect current public IPs
        ips = self.ip_detector.detect_all()

        if not ips.ipv4 and not ips.ipv6:
            self.logger.error("Failed to detect any public IP address")
            return False

        any_updated = False

        # Process each configured record
        for record_config in self.config.records:
            record_name = record_config.name
            record_type = record_config.type

            # Get the appropriate IP for this record type
            if record_type == 'A':
                current_ip = ips.ipv4
            elif record_type == 'AAAA':
                current_ip = self._get_aaaa_content(ips)
            else:
                self.logger.warning(f"Unknown record type: {record_type}, skipping")
                continue

            if not current_ip:
                self.logger.warning(f"No IP available for {record_type}, skipping {record_name}")
                continue

            # Check if IP changed since last update
            last_ip_key = f"{record_name}:{record_type}"
            if self._last_ips.get(last_ip_key) == current_ip:
                self.logger.debug(f"No IP change for {record_name} ({record_type}): {current_ip}")
                continue

            # Full domain name for Cloudflare
            full_name = f"{record_name}.{self.config.zone_identifier}"

            try:
                record, changed = self.cloudflare.upsert_dns_record(
                    name=record_name,
                    type_=record_type,
                    content=current_ip,
                    proxied=record_config.proxied,
                    ttl=record_config.ttl,
                    comment=record_config.comment
                )

                if changed:
                    self.logger.info(
                        f"Updated {full_name} ({record_type}): {current_ip}"
                    )
                    any_updated = True
                    self._last_ips[last_ip_key] = current_ip
                else:
                    self.logger.debug(
                        f"No change for {full_name} ({record_type}): {current_ip}"
                    )

            except Exception as e:
                self.logger.error(f"Failed to update {full_name} ({record_type}): {e}")

        if not any_updated:
            self.logger.info("No updates needed - all records current")

        return any_updated


class Scheduler:
    """Runs DDNS updates at configured intervals."""

    def __init__(self, interval_minutes: int, updater: DDNSUpdater):
        self.interval_seconds = interval_minutes * 60
        self.updater = updater
        self.logger = logging.getLogger('cloudflare_ddns.scheduler')
        self._stop_event = Event()
        self._setup_signals()

    def _setup_signals(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self._stop_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run(self):
        """Run the scheduler loop."""
        self.logger.info(f"Starting DDNS scheduler (interval: {self.interval_seconds//60} minutes)")

        # Run immediately on start
        self._run_cycle()

        while not self._stop_event.is_set():
            # Wait for interval or stop signal
            if self._stop_event.wait(timeout=self.interval_seconds):
                break

            self._run_cycle()

        self.logger.info("Scheduler stopped")

    def _run_cycle(self):
        """Run a single update cycle with error handling."""
        try:
            self.updater.run_once()
        except Exception as e:
            self.logger.error(f"Update cycle failed: {e}", exc_info=True)

    def stop(self):
        """Stop the scheduler."""
        self._stop_event.set()