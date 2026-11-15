"""Separate GLITCHLAB_ PostgreSQL STAGING entry point.

NOT public-launch approval: use only with synthetic/non-confidential test data
until authenticated HTTP RBAC, concurrency and hosting reviews are complete.
Does not import or mount demo_entry, legacy SQLite routes or registration.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import hashlib
import hmac

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

import auth
import workspace_api
import evidence_api
import protocol_api
from workspace_policy_api import router as workspace_policy_router
from legacy_gate import LegacyContentGate
from pg_compat import pg_db
from staging_config import validate_staging_config
from public_demo import (router as public_demo_router, PublicDemoAuthGuard,
                         PublicDemoReadOnlyGate, assert_demo_enabled)

settings = validate_staging_config()
assert_demo_enabled()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Validation is repeated at startup to prevent stale import-time checks.
    validate_staging_config()
    assert_demo_enabled()
    with pg_db(read_only=True) as con:
        required = ('auth_users','auth_sessions','gl_workspaces','gl_memberships',
                    'gl_content_drafts','gl_content_versions','gl_evaluation_runs',
                    'gl_review_decisions','gl_reference_sources','gl_evidence_items',
                    'gl_claims','gl_claim_evidence','gl_policy_releases')
        placeholders = ','.join('?' for _ in required)
        sql = ('SELECT table_name FROM information_schema.tables '
               f"WHERE table_schema='public' AND table_name IN ({placeholders})")
        found = {row['table_name'] for row in con.execute(sql, required).fetchall()}
        missing = set(required) - found
        if missing:
            # Names only, never credentials.
            raise RuntimeError('Missing prerequisite PostgreSQL tables: ' + ', '.join(sorted(missing)))
    auth._db = pg_db
    workspace_api._db = pg_db
    yield


app = FastAPI(
    title='GLITCHLAB_ Public Read-Only Judge Demo',
    version='0.5-judge-demo',
    docs_url=None, redoc_url=None, openapi_url=None,
    lifespan=lifespan,
)
# Request-processing order is CORS -> TrustedHost -> LegacyGate -> AuthGuard.
app.add_middleware(PublicDemoAuthGuard)
app.add_middleware(PublicDemoReadOnlyGate)
app.add_middleware(LegacyContentGate, enabled=True)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.hosts))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.origins),
    allow_credentials=False,  # Bearer token sent via Authorization; no cookie auth.
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type'],
)


@app.middleware('http')
async def security_response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.get('/health')
def health():
    return {'ok': True, 'service': 'GLITCHLAB_ Workspace Staging',
            'storage': 'postgresql', 'local_test_only': False, 'read_only_demo': True,
            'legacy_content_routes': 'disabled'}


@app.post('/auth/login')
def login(body: auth.LoginIn):
    email = str(body.email).strip().lower()
    with pg_db() as con:
        user = con.execute('SELECT * FROM auth_users WHERE email=?', (email,)).fetchone()
        salt = bytes.fromhex(user['salt']) if user else b'\0' * 16
        computed = auth.pw_hash(body.password, salt)
        if not user or not hmac.compare_digest(computed, user['password_hash']):
            raise HTTPException(401, 'Incorrect email or password.')
        issued = auth.issue(con, user)
        issued['workspace_notice'] = 'Authenticated staging workspace; access limited by membership and role.'
        return issued


@app.post('/auth/register')
def register_disabled():
    raise HTTPException(403, 'Account registration is disabled.')


@app.get('/auth/me')
def me(request: Request):
    user = auth.lookup_token(auth.bearer(request.headers.get('authorization', '')))
    if user is None:
        raise HTTPException(401, 'Session expired or invalid.')
    return {'id': user['id'], 'email': user['email'],
            'display_name': user['display_name'],
            'workspace_notice': 'Authenticated staging workspace.'}


@app.post('/auth/logout')
def logout(request: Request):
    raw = auth.bearer(request.headers.get('authorization', ''))
    if raw:
        with pg_db() as con:
            con.execute('DELETE FROM auth_sessions WHERE token_hash=?',
                        (hashlib.sha256(raw.encode()).hexdigest(),))
    return {'ok': True}


# This router is public, synthetic and does not import local demo_entry.
app.include_router(public_demo_router)

# Every content endpoint must remain workspace-scoped.
app.include_router(workspace_api.router)
app.include_router(evidence_api.router)
app.include_router(workspace_policy_router)
app.include_router(protocol_api.router)
