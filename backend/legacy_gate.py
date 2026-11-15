"""GLITCHLAB_ Round 3 migration safeguard.

Set GLITCHLAB_BLOCK_LEGACY_API=true *only after* the React frontend and all
background clients use workspace-scoped API routes. This blocks every old
shared-workspace content route, even if the request has a valid bearer token.

This does NOT implement tenant isolation or replace checking permissions in
workspace-scoped endpoints. It is an additional fail-closed boundary.
"""
from __future__ import annotations

import os
from starlette.responses import JSONResponse

# Deliberately allow /health, /auth/*, docs and /workspaces/* through.
# Prefix matching requires a whole path segment, not just shared characters.
LEGACY_PREFIXES = ('/drafts', '/runs', '/rules', '/sources', '/governance', '/ai', '/insights')


def is_legacy_content_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + '/') for prefix in LEGACY_PREFIXES)


def legacy_block_enabled() -> bool:
    return os.getenv('GLITCHLAB_BLOCK_LEGACY_API', 'false').strip().lower() in {'1', 'true', 'yes', 'on'}


class LegacyContentGate:
    """ASGI gate that denies legacy shared content routes in strict mode.

    Strict mode is selected at request time to allow reliable isolated tests.
    In deployment, set environment configuration and restart the server.
    """
    def __init__(self, app, *, enabled=None):
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        strict = legacy_block_enabled() if self.enabled is None else self.enabled
        if strict and is_legacy_content_path(scope.get('path', '')):
            response = JSONResponse(
                {'detail': 'Legacy shared-workspace endpoint is disabled. Use an authorized /workspaces/... endpoint.'},
                status_code=410,
                headers={'Cache-Control': 'no-store'},
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)
