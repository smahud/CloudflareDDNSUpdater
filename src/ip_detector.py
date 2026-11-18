"""Public IP detection with multiple provider fallback."""
import requests
import socket
import logging
from typing import Optional, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger('cloudflare_ddns.ip_detector')


@dataclass
class IPAddresses:
    """Detected IP addresses."""
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None


class IPDetector:
    """Detect public IPv4 and IPv6 addresses using multiple providers."""

    # IPv4-only providers
    IPV4_PROVIDERS = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
        "https://icanhazip.com",
        "https://ident.me",
    ]

    # IPv6-capable providers (return IPv6 if available)
    IPV6_PROVIDERS = [
        "https://api6.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip",
        "https://icanhazip.com",
        "https://ident.me",
    ]

    def __init__(self, providers: List[str], timeout: int = 10,
                 ipv4_enabled: bool = True, ipv6_enabled: bool = True):
        self.providers = providers
        self.timeout = timeout
        self.ipv4_enabled = ipv4_enabled
        self.ipv6_enabled = ipv6_enabled
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Cloudflare-DDNS-Updater/1.0'
        })

    def _fetch_ip(self, url: str) -> Optional[str]:
        """Fetch IP from a single provider."""
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            ip = response.text.strip()
            # Validate it's a valid IP
            if self._is_valid_ip(ip):
                return ip
            logger.warning(f"Invalid IP from {url}: {ip}")
        except requests.RequestException as e:
            logger.debug(f"Failed to fetch from {url}: {e}")
        return None

    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            socket.inet_pton(socket.AF_INET, ip)
            return True
        except OSError:
            try:
                socket.inet_pton(socket.AF_INET6, ip)
                return True
            except OSError:
                return False

    def _is_ipv4(self, ip: str) -> bool:
        """Check if IP is IPv4."""
        try:
            socket.inet_pton(socket.AF_INET, ip)
            return True
        except OSError:
            return False

    def _is_ipv6(self, ip: str) -> bool:
        """Check if IP is IPv6."""
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except OSError:
            return False

    def detect_ipv4(self) -> Optional[str]:
        """Detect public IPv4 address."""
        if not self.ipv4_enabled:
            return None

        for provider in self.providers:
            logger.debug(f"Trying IPv4 provider: {provider}")
            ip = self._fetch_ip(provider)
            if ip and self._is_ipv4(ip):
                logger.info(f"Detected IPv4: {ip} (via {provider})")
                return ip
            elif ip and self._is_ipv6(ip):
                logger.debug(f"Provider {provider} returned IPv6, skipping for IPv4 detection")

        logger.warning("Failed to detect IPv4 from all providers")
        return None

    def detect_ipv6(self) -> Optional[str]:
        """Detect public IPv6 address."""
        if not self.ipv6_enabled:
            return None

        for provider in self.providers:
            logger.debug(f"Trying IPv6 provider: {provider}")
            ip = self._fetch_ip(provider)
            if ip and self._is_ipv6(ip):
                logger.info(f"Detected IPv6: {ip} (via {provider})")
                return ip
            elif ip and self._is_ipv4(ip):
                logger.debug(f"Provider {provider} returned IPv4, skipping for IPv6 detection")

        logger.warning("Failed to detect IPv6 from all providers")
        return None

    def detect_all(self) -> IPAddresses:
        """Detect both IPv4 and IPv6 addresses."""
        return IPAddresses(
            ipv4=self.detect_ipv4(),
            ipv6=self.detect_ipv6()
        )


def get_local_ips() -> Tuple[List[str], List[str]]:
    """Get local network IPs (for debugging)."""
    ipv4_list = []
    ipv6_list = []

    try:
        for interface, addrs in socket.getaddrinfo(socket.gethostname(), None):
            pass
    except Exception:
        pass

    return ipv4_list, ipv6_list