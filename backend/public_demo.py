"""Explicit public, read-only, synthetic Nivara judge entry.

Unlike local demo_entry.py, this is a distinct endpoint that only provisions
sessions for the four *already seeded* Render staging personas. The read-only
middleware is mandatory for the entire staging-demo server, including normal
password login. Do not mount this router in production/private environments.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import os
import time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse

import auth
from pg_compat import pg_db

from public_demo_policy import (WORKSPACE, PEOPLE, FLAG, assert_demo_enabled,
                                is_read_only_request)
router = APIRouter(prefix='/auth/demo', tags=['Public, synthetic read-only demo'])
# Best-effort throttling. Replace with shared edge/Redis rate limiting before
# deploying multiple workers; reverse proxies may share peer IPs.
_attempts = defaultdict(deque)


class PublicDemoReadOnlyGate:
    """Blocks ALL mutating workspace/policy/evidence endpoints, not merely UI buttons."""
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or is_read_only_request(scope.get('method',''), scope.get('path','')):
            return await self.app(scope, receive, send)
        return await JSONResponse(
            {'detail':'Public judge sandbox is read-only. All Nivara sample records are preserved.'},
            status_code=403,
        )(scope, receive, send)


class PublicDemoAuthGuard(auth.AuthGuard):
    """Permit only the two explicit public demo entry endpoints before login."""
    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and (
            (scope.get('method') == 'GET' and scope.get('path') == '/auth/demo/personas')
            or (scope.get('method') == 'POST' and scope.get('path') == '/auth/demo/enter')
        ):
            return await self.app(scope, receive, send)
        return await super().__call__(scope, receive, send)


class EnterRequest(BaseModel):
    identity: Literal['aarohi', 'kabir', 'ishani', 'reyansh']


@router.get('/personas')
def personas():
    assert_demo_enabled()
    return {'enabled':True, 'read_only':True, 'personas':[
        {'id':pid, 'name':name, 'role':role, 'workspace':WORKSPACE}
        for pid,(name,email,role) in PEOPLE.items()
    ], 'notice':'Public, synthetic, read-only judging sandbox. No confidential data.'}


def _throttle(peer: str, identity: str):
    # Bounded in-memory 1-hour window: 30 sign-ins / peer+identity / hour.
    key = (peer[:100],identity)
    current = time.monotonic()
    q = _attempts[key]
    while q and current-q[0] > 3600:
        q.popleft()
    if len(q) >= 30:
        raise HTTPException(429, 'Too many demo sign-ins; try again later.')
    q.append(current)
    # Mitigate unbounded unique-peer growth in this best-effort process store.
    if len(_attempts) > 2048:
        _attempts.clear()


@router.post('/enter')
def enter(body: EnterRequest, request: Request):
    assert_demo_enabled()
    peer = request.client.host if request.client else 'unknown'
    _throttle(peer, body.identity)
    name,email,role = PEOPLE[body.identity]
    with pg_db() as con:
        rows = con.execute('''SELECT u.* FROM auth_users u
             JOIN gl_memberships m ON m.user_id=u.id
             JOIN gl_workspaces w ON w.id=m.workspace_id
             WHERE u.email=? AND u.display_name=? AND m.role=? AND w.name=?''',
             (email,name,role,WORKSPACE)).fetchall()
        if len(rows) != 1:
            raise HTTPException(503, 'The synthetic judging workspace is not provisioned.')
        session = auth.issue(con, rows[0]); session['read_only'] = True
        session['workspace_notice'] = 'Public synthetic Nivara sandbox. Read-only access for all four personas.'
        return session
