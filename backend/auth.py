"""GLITCHLAB_ demo login: salted password hashing, expiring bearer sessions.

Accounts share the same synthetic demo workspace. No roles or tenant isolation.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from starlette.responses import JSONResponse

router = APIRouter(prefix='/auth', tags=['Authentication'])
_db: Callable | None = None
SESSION_HOURS = 24
ITERATIONS = 310_000


def utcnow():
    return datetime.now(timezone.utc)


def install(db_provider: Callable):
    global _db
    _db = db_provider
    with _db() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS auth_users (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
            salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL)''')
        con.execute('''CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES auth_users(id))''')
    return router


def pw_hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS).hex()


def issue(con, user):
    raw = secrets.token_urlsafe(36)
    expiration = utcnow() + timedelta(hours=SESSION_HOURS)
    con.execute('DELETE FROM auth_sessions WHERE expires_at < ?', (utcnow().isoformat(),))
    con.execute('INSERT INTO auth_sessions VALUES (?,?,?,?)',
                (hashlib.sha256(raw.encode()).hexdigest(), user['id'], expiration.isoformat(), utcnow().isoformat()))
    return {'token': raw, 'expires_at': expiration.isoformat(),
            'user': {'id': user['id'], 'email': user['email'], 'display_name': user['display_name']},
            'workspace_notice': 'Shared synthetic demonstration workspace; accounts are not private tenants.'}


class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=70)
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@router.post('/register', status_code=201)
def register(body: RegisterIn):
    if os.getenv('GLITCHLAB_ALLOW_SIGNUP', 'true').lower() not in {'1', 'true', 'yes'}:
        raise HTTPException(403, 'Public registration is disabled by the administrator.')
    email = str(body.email).strip().lower()
    salt = secrets.token_bytes(16)
    with _db() as con:
        try:
            con.execute('INSERT INTO auth_users VALUES (?,?,?,?,?,?)',
                        (str(uuid4()), email, body.display_name.strip(), salt.hex(), pw_hash(body.password, salt), utcnow().isoformat()))
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'An account with this email already exists.')
        user = con.execute('SELECT * FROM auth_users WHERE email=?', (email,)).fetchone()
        return issue(con, user)


@router.post('/login')
def login(body: LoginIn):
    email = str(body.email).strip().lower()
    with _db() as con:
        user = con.execute('SELECT * FROM auth_users WHERE email=?', (email,)).fetchone()
        # Perform comparable work when the email is unknown, avoiding easy account enumeration.
        salt = bytes.fromhex(user['salt']) if user else b'\0' * 16
        computed = pw_hash(body.password, salt)
        if not user or not hmac.compare_digest(computed, user['password_hash']):
            raise HTTPException(401, 'Incorrect email or password.')
        return issue(con, user)


def lookup_token(raw: str):
    if not raw or len(raw) > 256:
        return None
    digest = hashlib.sha256(raw.encode()).hexdigest()
    with _db() as con:
        row = con.execute('''SELECT u.id,u.email,u.display_name,s.expires_at
               FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
               WHERE s.token_hash=?''', (digest,)).fetchone()
    if not row or datetime.fromisoformat(row['expires_at']) <= utcnow():
        return None
    return dict(row)


@router.get('/me')
def me(request: Request):
    user = lookup_token(bearer(request.headers.get('authorization', '')))
    if not user:
        raise HTTPException(401, 'Session expired or invalid.')
    return {'id': user['id'], 'email': user['email'], 'display_name': user['display_name'],
            'workspace_notice': 'Shared synthetic demonstration workspace.'}


def bearer(header: str) -> str:
    match = re.fullmatch(r'Bearer\s+([^\s]+)', header, re.I)
    return match.group(1) if match else ''


@router.post('/logout')
def logout(request: Request):
    raw = bearer(request.headers.get('authorization', ''))
    if raw:
        with _db() as con:
            con.execute('DELETE FROM auth_sessions WHERE token_hash=?',
                        (hashlib.sha256(raw.encode()).hexdigest(),))
    return {'ok': True}


class AuthGuard:
    """Protect every application endpoint, including Governance Lab, with bearer sessions."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        path = scope.get('path', '')
        if (scope.get('method') == 'OPTIONS' or path == '/health'
            or path in {'/auth/login', '/auth/register'} or path.startswith('/docs')
            or path.startswith('/openapi') or path.startswith('/redoc')):
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get('headers', [])}
        raw = bearer(headers.get(b'authorization', b'').decode('latin-1'))
        if not lookup_token(raw):
            return await JSONResponse({'detail': 'Sign in to access GLITCHLAB_.'}, status_code=401)(scope, receive, send)
        return await self.app(scope, receive, send)
