"""GLITCHLAB_ Round 3 groundwork: workspace membership and authorization.

This module is deliberately NOT registered into the existing shared-workspace API.
Before enabling multi-tenant service, every data endpoint must scope queries to a
validated workspace, and PostgreSQL persistence must replace temporary SQLite.
Never use a UI role selector as a substitute for this authorization.
"""
from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from uuid import uuid4

ROLES = frozenset({'admin', 'editor', 'reviewer', 'creator'})
ACTIONS = {
    'workspace:read': ROLES,
    'workspace:manage': frozenset({'admin'}),
    'members:manage': frozenset({'admin'}),
    'policy:write': frozenset({'admin'}),
    'policy:release': frozenset({'admin'}),
    'draft:read': ROLES,
    'draft:create': frozenset({'admin', 'editor', 'creator'}),
    'draft:edit': frozenset({'admin', 'editor', 'creator'}),
    'draft:test': frozenset({'admin', 'editor', 'creator'}),
    'review:decide': frozenset({'admin', 'reviewer'}),
    'evidence:write': frozenset({'admin', 'editor'}),
    'audit:read': frozenset({'admin', 'reviewer'}),
}

class AccessDenied(PermissionError):
    pass

class WorkspaceNotFound(LookupError):
    pass

class WorkspaceConflict(ValueError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def initialize(con: sqlite3.Connection) -> None:
    """Add-only SQLite schema for local testing. Not the PostgreSQL migration."""
    con.executescript('''
    CREATE TABLE IF NOT EXISTS gl_workspaces (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_by TEXT NOT NULL REFERENCES auth_users(id),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS gl_memberships (
        workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
        user_id TEXT NOT NULL REFERENCES auth_users(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK(role IN ('admin','editor','reviewer','creator')),
        joined_at TEXT NOT NULL,
        PRIMARY KEY(workspace_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS gl_memberships_user_idx ON gl_memberships(user_id);
    ''')


def create_workspace(con: sqlite3.Connection, *, creator_id: str, name: str) -> dict:
    name = name.strip()
    if not 2 <= len(name) <= 100:
        raise ValueError('Workspace name must contain 2–100 characters')
    if con.execute('SELECT 1 FROM auth_users WHERE id=?', (creator_id,)).fetchone() is None:
        raise WorkspaceNotFound('Creating user does not exist')
    uid, created = str(uuid4()), utcnow()
    con.execute('INSERT INTO gl_workspaces VALUES (?,?,?,?)', (uid, name, creator_id, created))
    con.execute('INSERT INTO gl_memberships VALUES (?,?,?,?)', (uid, creator_id, 'admin', created))
    return {'id': uid, 'name': name, 'created_by': creator_id, 'created_at': created, 'role': 'admin'}


def membership_role(con: sqlite3.Connection, *, user_id: str, workspace_id: str) -> str | None:
    row = con.execute(
        'SELECT role FROM gl_memberships WHERE user_id=? AND workspace_id=?',
        (user_id, workspace_id),
    ).fetchone()
    return row[0] if row else None


def require_action(con: sqlite3.Connection, *, user_id: str, workspace_id: str, action: str) -> str:
    if action not in ACTIONS:
        raise ValueError('Unknown permission action')
    role = membership_role(con, user_id=user_id, workspace_id=workspace_id)
    if role is None or role not in ACTIONS[action]:
        raise AccessDenied(f'Not authorized to perform {action} in this workspace')
    return role


def list_workspaces(con: sqlite3.Connection, *, user_id: str) -> list[dict]:
    rows = con.execute('''
        SELECT w.id,w.name,w.created_at,m.role
        FROM gl_workspaces w JOIN gl_memberships m ON m.workspace_id=w.id
        WHERE m.user_id=? ORDER BY w.created_at,w.name,w.id
    ''', (user_id,)).fetchall()
    columns = ('id', 'name', 'created_at', 'role')
    return [
        dict(row) if hasattr(row, 'keys')
        else dict(zip(columns, row))
        for row in rows
    ]


def set_member_role(con: sqlite3.Connection, *, acting_user_id: str,
                    workspace_id: str, member_user_id: str, role: str) -> None:
    """Admin only; never permit removal of the workspace's final admin."""
    require_action(con, user_id=acting_user_id, workspace_id=workspace_id, action='members:manage')
    if role not in ROLES:
        raise ValueError('Unknown role')
    if con.execute('SELECT 1 FROM auth_users WHERE id=?', (member_user_id,)).fetchone() is None:
        raise WorkspaceNotFound('Account not found')
    old = membership_role(con, user_id=member_user_id, workspace_id=workspace_id)
    if old == 'admin' and role != 'admin':
        admins = con.execute('SELECT COUNT(*) FROM gl_memberships WHERE workspace_id=? AND role=?',
                             (workspace_id, 'admin')).fetchone()[0]
        if admins <= 1:
            raise WorkspaceConflict('Cannot demote the last workspace administrator')
    con.execute('''INSERT INTO gl_memberships(workspace_id,user_id,role,joined_at) VALUES (?,?,?,?)
                   ON CONFLICT(workspace_id,user_id) DO UPDATE SET role=excluded.role''',
                (workspace_id, member_user_id, role, utcnow()))


def remove_member(con: sqlite3.Connection, *, acting_user_id: str,
                  workspace_id: str, member_user_id: str) -> None:
    require_action(con, user_id=acting_user_id, workspace_id=workspace_id, action='members:manage')
    role = membership_role(con, user_id=member_user_id, workspace_id=workspace_id)
    if role is None:
        raise WorkspaceNotFound('Membership not found')
    if role == 'admin':
        admins = con.execute('SELECT COUNT(*) FROM gl_memberships WHERE workspace_id=? AND role=?',
                             (workspace_id, 'admin')).fetchone()[0]
        if admins <= 1:
            raise WorkspaceConflict('Cannot remove the last workspace administrator')
    con.execute('DELETE FROM gl_memberships WHERE workspace_id=? AND user_id=?',
                (workspace_id, member_user_id))
