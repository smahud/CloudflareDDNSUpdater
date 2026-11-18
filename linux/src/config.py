"""Configuration loader for Cloudflare DDNS Updater."""
import yaml
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
import logging


def get_base_dir() -> Path:
    """Get base directory (exe dir when frozen, script dir when running from source)."""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        return Path(sys.executable).parent
    else:
        # Running from source
        return Path(__file__).parent.parent


@dataclass
class RecordConfig:
    """Single DNS record configuration."""
    name: str
    type: str  # "A" or "AAAA"
    proxied: bool = False
    comment: str = ""
    ttl: int = 1  # 1 = auto


@dataclass
class IPDetectionConfig:
    """IP detection settings."""
    ipv4_enabled: bool = True
    ipv6_enabled: bool = True
    providers: List[str] = field(default_factory=lambda: [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://ipinfo.io/ip"
    ])
    timeout_seconds: int = 10


@dataclass
class Config:
    """Main configuration."""
    interval_minutes: int
    api_token: str
    zone_identifier: str
    records: List[RecordConfig]
    ip_detection: IPDetectionConfig = field(default_factory=IPDetectionConfig)
    log_level: str = "INFO"
    log_file: str = "ddns.log"

    @classmethod
    def load(cls, path: str = "config.yaml", base_dir: Optional[Path] = None) -> "Config":
        """Load configuration from YAML file."""
        if base_dir is None:
            base_dir = get_base_dir()
        config_path = base_dir / path
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        # Parse records
        records = []
        for r in data.get('records', []):
            records.append(RecordConfig(
                name=r['name'],
                type=r['type'],
                proxied=r.get('proxied', False),
                comment=r.get('comment', ''),
                ttl=r.get('ttl', 1)
            ))

        # Parse IP detection
        ip_detect_data = data.get('ip_detection', {})
        ip_detection = IPDetectionConfig(
            ipv4_enabled=ip_detect_data.get('ipv4_enabled', True),
            ipv6_enabled=ip_detect_data.get('ipv6_enabled', True),
            providers=ip_detect_data.get('providers', IPDetectionConfig().providers),
            timeout_seconds=ip_detect_data.get('timeout_seconds', 10)
        )

        return cls(
            interval_minutes=data['interval_minutes'],
            api_token=data['api_token'],
            zone_identifier=data['zone_identifier'],
            records=records,
            ip_detection=ip_detection,
            log_level=data.get('log_level', 'INFO'),
            log_file=data.get('log_file', 'ddns.log')
        )

    def validate(self) -> List[str]:
        """Validate configuration. Returns list of errors (empty if valid)."""
        errors = []

        if self.interval_minutes < 1:
            errors.append("interval_minutes must be >= 1")

        if not self.api_token or not self.api_token.strip():
            errors.append("api_token is required")

        if not self.zone_identifier or not self.zone_identifier.strip():
            errors.append("zone_identifier is required")

        if not self.records:
            errors.append("At least one record must be configured")

        for i, record in enumerate(self.records):
            if record.type not in ('A', 'AAAA'):
                errors.append(f"Record {i}: type must be 'A' or 'AAAA', got '{record.type}'")
            if not record.name or not record.name.strip():
                errors.append(f"Record {i}: name is required")

        return errors


def setup_logging(config: Config, base_dir: Optional[Path] = None) -> logging.Logger:
    """Setup logging based on config."""
    if base_dir is None:
        base_dir = get_base_dir()

    logger = logging.getLogger('cloudflare_ddns')
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler - use base_dir for log file
    log_path = base_dir / config.log_file
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger