"""Cloudflare API client for DNS record management."""
import requests
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger('cloudflare_ddns.cloudflare')


@dataclass
class DNSRecord:
    """Cloudflare DNS record."""
    id: str
    name: str
    type: str
    content: str
    proxied: bool
    ttl: int
    comment: Optional[str] = None


class CloudflareClient:
    """Cloudflare API client for managing DNS records."""

    BASE_URL = "https://api.cloudflare.com/client/v4"

    def __init__(self, api_token: str, zone_identifier: str):
        self.api_token = api_token
        self.zone_identifier = zone_identifier
        self.zone_id: Optional[str] = None
        self._zone_name: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Cloudflare-DDNS-Updater/1.0'
        })

    def _get_zone_name(self) -> str:
        """Get the zone domain name (e.g., yapsidarussalam.or.id)."""
        if self._zone_name:
            return self._zone_name

        # If zone_identifier looks like a zone ID, we need to fetch the zone name
        if len(self.zone_identifier) == 32 and all(c in '0123456789abcdef' for c in self.zone_identifier.lower()):
            zone_id = self.get_zone_id()
            data = self._request('GET', f'/zones/{zone_id}')
            self._zone_name = data['result']['name']
        else:
            self._zone_name = self.zone_identifier

        return self._zone_name

    def _full_name(self, name: str) -> str:
        """Convert relative name to full DNS name."""
        # If already a full name (ends with zone name), return as-is
        zone_name = self._get_zone_name()
        if name.endswith('.' + zone_name) or name == zone_name:
            return name
        # If name is @ (root), return zone name
        if name == '@':
            return zone_name
        # Otherwise, prepend to zone name
        return f"{name}.{zone_name}"

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make API request with error handling."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            data = response.json()

            if not data.get('success', False):
                errors = data.get('errors', [])
                messages = data.get('messages', [])
                error_msg = '; '.join(
                    [e.get('message', str(e)) for e in errors] +
                    [m.get('message', str(m)) for m in messages]
                )
                raise CloudflareAPIError(f"API error: {error_msg}")

            return data
        except requests.RequestException as e:
            raise CloudflareAPIError(f"Request failed: {e}")

    def get_zone_id(self) -> str:
        """Get zone ID from zone identifier (domain name or zone ID)."""
        if self.zone_id:
            return self.zone_id

        # If it looks like a zone ID (32 hex chars), use it directly
        if len(self.zone_identifier) == 32 and all(c in '0123456789abcdef' for c in self.zone_identifier.lower()):
            self.zone_id = self.zone_identifier
            return self.zone_id

        # Otherwise, look up by domain name
        data = self._request('GET', f'/zones?name={self.zone_identifier}')
        results = data.get('result', [])

        if not results:
            raise CloudflareAPIError(f"Zone not found: {self.zone_identifier}")

        self.zone_id = results[0]['id']
        logger.info(f"Resolved zone '{self.zone_identifier}' to zone_id: {self.zone_id}")
        return self.zone_id

    def list_dns_records(self, name: Optional[str] = None, type_: Optional[str] = None) -> List[DNSRecord]:
        """List DNS records, optionally filtered by name and type."""
        zone_id = self.get_zone_id()
        params = {'per_page': 100}
        if name:
            params['name'] = self._full_name(name)
        if type_:
            params['type'] = type_

        data = self._request('GET', f'/zones/{zone_id}/dns_records', params=params)
        records = []

        for r in data.get('result', []):
            records.append(DNSRecord(
                id=r['id'],
                name=r['name'],
                type=r['type'],
                content=r['content'],
                proxied=r.get('proxied', False),
                ttl=r.get('ttl', 1),
                comment=r.get('comment')
            ))

        return records

    def get_dns_record(self, name: str, type_: str) -> Optional[DNSRecord]:
        """Get a specific DNS record by name and type."""
        records = self.list_dns_records(name=name, type_=type_)
        if records:
            return records[0]
        return None

    def create_dns_record(self, name: str, type_: str, content: str,
                          proxied: bool = False, ttl: int = 1,
                          comment: Optional[str] = None) -> DNSRecord:
        """Create a new DNS record."""
        zone_id = self.get_zone_id()
        full_name = self._full_name(name)
        payload = {
            'type': type_,
            'name': full_name,
            'content': content,
            'proxied': proxied,
            'ttl': ttl
        }
        if comment:
            payload['comment'] = comment

        data = self._request('POST', f'/zones/{zone_id}/dns_records', json=payload)
        r = data['result']
        logger.info(f"Created {type_} record: {full_name} -> {content}")
        return DNSRecord(
            id=r['id'],
            name=r['name'],
            type=r['type'],
            content=r['content'],
            proxied=r.get('proxied', False),
            ttl=r.get('ttl', 1),
            comment=r.get('comment')
        )

    def update_dns_record(self, record_id: str, name: str, type_: str, content: str,
                          proxied: bool = False, ttl: int = 1,
                          comment: Optional[str] = None) -> DNSRecord:
        """Update an existing DNS record."""
        zone_id = self.get_zone_id()
        full_name = self._full_name(name)
        payload = {
            'type': type_,
            'name': full_name,
            'content': content,
            'proxied': proxied,
            'ttl': ttl
        }
        if comment is not None:
            payload['comment'] = comment

        data = self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', json=payload)
        r = data['result']
        logger.info(f"Updated {type_} record: {full_name} -> {content}")
        return DNSRecord(
            id=r['id'],
            name=r['name'],
            type=r['type'],
            content=r['content'],
            proxied=r.get('proxied', False),
            ttl=r.get('ttl', 1),
            comment=r.get('comment')
        )

    def upsert_dns_record(self, name: str, type_: str, content: str,
                          proxied: bool = False, ttl: int = 1,
                          comment: Optional[str] = None) -> tuple[DNSRecord, bool]:
        """
        Create or update DNS record.
        Returns (record, changed) where changed=True if content was modified.
        """
        existing = self.get_dns_record(name, type_)

        if existing:
            if existing.content == content and existing.proxied == proxied:
                logger.debug(f"No change needed for {name} ({type_})")
                return existing, False

            logger.info(f"Updating {name} ({type_}): {existing.content} -> {content}")
            updated = self.update_dns_record(
                existing.id, name, type_, content, proxied, ttl, comment
            )
            return updated, True
        else:
            logger.info(f"Creating new {type_} record: {name} -> {content}")
            created = self.create_dns_record(name, type_, content, proxied, ttl, comment)
            return created, True


class CloudflareAPIError(Exception):
    """Cloudflare API error."""
    pass