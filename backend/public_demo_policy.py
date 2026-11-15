"""Pure, dependency-free safety policy for the public read-only judge sandbox."""
from __future__ import annotations

import os

WORKSPACE = 'Nivara Studio - Staging Demo'
PEOPLE = {
    'aarohi': ('Aarohi Sen', 'aarohi@glitchlab.example', 'creator'),
    'kabir': ('Kabir Mehta', 'kabir@glitchlab.example', 'editor'),
    'ishani': ('Ishani Roy', 'ishani@glitchlab.example', 'reviewer'),
    'reyansh': ('Reyansh Kapoor', 'reyansh@glitchlab.example', 'admin'),
}
ALLOWED_POST_PATHS = frozenset({'/auth/demo/enter', '/auth/login', '/auth/logout'})
FLAG = 'I_ACCEPT_PUBLIC_READ_ONLY_ACCESS'


def assert_demo_enabled(environ=None):
    e = os.environ if environ is None else environ
    if e.get('GLITCHLAB_PUBLIC_DEMO_READONLY') != FLAG:
        raise RuntimeError('Set GLITCHLAB_PUBLIC_DEMO_READONLY='+FLAG+' explicitly.')
    if e.get('GLITCHLAB_LOCAL_DEMO_LOGIN', '').lower() in {'true','1','yes'}:
        raise RuntimeError('Local passwordless demo bypass must remain disabled.')
    if e.get('GLITCHLAB_ALLOW_SIGNUP', '').lower() in {'true','1','yes'}:
        raise RuntimeError('Public account registration must remain disabled.')
    return True


def is_read_only_request(method: str, path: str) -> bool:
    return method.upper() in {'GET','HEAD','OPTIONS'} or (method.upper() == 'POST' and path in ALLOWED_POST_PATHS)
