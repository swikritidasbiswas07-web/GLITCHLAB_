"""Opt-in, loopback-only one-click entry for four synthetic GLITCHLAB_ demo users.

Never enable on a public/forwarded service. Not a production impersonation feature.
The session belongs to the explicitly provisioned synthetic account; the backend's
existing membership/permission system still enforces all workspace actions.
"""
from __future__ import annotations

import ipaddress
import os
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from auth import issue
from demo_accounts import PERSONAS, DEFAULT_WORKSPACE

router = APIRouter(prefix='/auth/demo', tags=['Local demonstration entry'])
_db_provider: Callable | None = None


def enabled_for(request: Request) -> bool:
    if os.getenv('GLITCHLAB_LOCAL_DEMO_LOGIN', '').lower() not in ('true', '1', 'yes'):
        return False
    if os.getenv('GLITCHLAB_DEMO_MODE', '').lower() == 'public':
        return False
    # Never expose this convenience feature through a reverse proxy or a
    # public hostname, even if the proxy connects to Uvicorn over loopback.
    if request.url.hostname not in ('127.0.0.1', 'localhost', '::1', 'testserver'):
        return False
    if any(k in request.headers for k in ('forwarded', 'x-forwarded-for', 'x-real-ip')):
        return False
    peer = request.client.host if request.client else ''
    try:
        return ipaddress.ip_address(peer).is_loopback
    except ValueError:
        return False


def install(db_provider: Callable):
    global _db_provider
    _db_provider = db_provider
    return router


def get_personas():
    return [{'id': email.split('@')[0].split('.')[0], 'name': name,
             'email': email, 'role': role, 'workspace': DEFAULT_WORKSPACE}
            for name, email, role in PERSONAS]


@router.get('/personas')
def personas(request: Request):
    if not enabled_for(request):
        raise HTTPException(404, 'Local demonstration entry is disabled')
    return {'enabled': True, 'personas': get_personas(),
            'notice': 'Synthetic local demonstration identities only. No confidential data.'}


class EnterIn(BaseModel):
    identity: Literal['aarohi', 'kabir', 'ishani', 'reyansh']


@router.post('/enter')
def enter(request: Request, body: EnterIn):
    if not enabled_for(request):
        raise HTTPException(404, 'Local demonstration entry is disabled')

    target = next((p for p in PERSONAS if p[1].startswith(body.identity + '.')), None)
    if target is None:
        raise HTTPException(404, 'Unknown demonstration identity')
    name, email, role = target
    with _db_provider() as con:
        rows = con.execute('''SELECT u.* FROM auth_users u
                              JOIN gl_memberships m ON m.user_id=u.id
                              JOIN gl_workspaces w ON w.id=m.workspace_id
                              WHERE u.email=? AND u.display_name=? AND m.role=?
                                AND w.name=?''', (email, name, role, DEFAULT_WORKSPACE)).fetchall()
        if len(rows) != 1:
            raise HTTPException(409, 'Demo identity not provisioned in Nivara Studio')
        return issue(con, rows[0])
