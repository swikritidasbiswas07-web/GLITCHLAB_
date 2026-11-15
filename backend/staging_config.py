"""Strict configuration validation for GLITCHLAB_ public-facing staging.

This module does not connect to the database and never prints credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse, parse_qs


class StagingConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class StagingSettings:
    origins: tuple[str, ...]
    hosts: tuple[str, ...]


def _csv(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(s.strip() for s in value.split(',') if s.strip()))


def validate_staging_config(env=None) -> StagingSettings:
    e = os.environ if env is None else env
    if e.get('GLITCHLAB_STAGING_ENABLED', '') != 'I_ACCEPT_PUBLIC_NETWORK_ACCESS':
        raise StagingConfigurationError('Set GLITCHLAB_STAGING_ENABLED=I_ACCEPT_PUBLIC_NETWORK_ACCESS after reviewing staging risks.')
    if e.get('GLITCHLAB_LOCAL_DEMO_LOGIN', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        raise StagingConfigurationError('Local passwordless demo login must be disabled for staging.')
    if e.get('GLITCHLAB_PG_RUNTIME_LOCAL_ONLY', '').strip() == '1':
        raise StagingConfigurationError('Do not reuse the local-only runtime flag on staging.')
    if e.get('GLITCHLAB_ALLOW_SIGNUP', '').strip().lower() in {'1', 'true', 'yes', 'on'}:
        raise StagingConfigurationError('Public self-registration is disabled pending a reviewed onboarding flow.')
    origins = _csv(e.get('GLITCHLAB_ALLOWED_ORIGINS', ''))
    if not origins:
        raise StagingConfigurationError('Set GLITCHLAB_ALLOWED_ORIGINS to the exact HTTPS frontend origin.')
    for origin in origins:
        parsed = urlparse(origin)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment or '*' in origin
                or parsed.port is not None):
            raise StagingConfigurationError('Frontend origins must be exact HTTPS origins with no path, port or wildcard.')
    hosts = _csv(e.get('GLITCHLAB_ALLOWED_HOSTS', ''))
    if not hosts or any(h != h.lower() or ':' in h or '/' in h or '*' in h or ' ' in h or '.' not in h for h in hosts):
        raise StagingConfigurationError('Set GLITCHLAB_ALLOWED_HOSTS to explicit backend DNS hostnames.')
    raw_url = e.get('DATABASE_URL', '').strip()
    if not raw_url:
        raise StagingConfigurationError('DATABASE_URL must be set by the hosting platform, not a local .env fallback.')
    parsed_db = urlparse(raw_url)
    if parsed_db.scheme not in ('postgresql', 'postgres') or not parsed_db.hostname or not parsed_db.username or not parsed_db.path.strip('/'):
        raise StagingConfigurationError('DATABASE_URL must be a PostgreSQL connection URL with username and database.')
    sslmode = parse_qs(parsed_db.query).get('sslmode', [''])[0].lower()
    if sslmode not in ('require', 'verify-ca', 'verify-full'):
        raise StagingConfigurationError('DATABASE_URL must set sslmode=require (or stronger).')
    return StagingSettings(origins=origins, hosts=hosts)
