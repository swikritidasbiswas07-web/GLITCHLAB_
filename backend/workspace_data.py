"""GLITCHLAB_ Round 3: isolated workspace data store (SQLite test stage).

This module is NOT wired to legacy /drafts, /rules, /sources or /governance routes.
Those routes remain shared until explicitly migrated. PostgreSQL is still TODO.
"""
from __future__ import annotations
import sqlite3
from uuid import uuid4
from datetime import datetime, timezone
from workspace_core import require_action


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def ident():
    return str(uuid4())


def initialize(con: sqlite3.Connection) -> None:
    con.executescript('''
        CREATE TABLE IF NOT EXISTS gl_content_drafts (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
            author_id TEXT NOT NULL REFERENCES auth_users(id), title TEXT NOT NULL,
            channel TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS gl_content_drafts_workspace_idx ON gl_content_drafts(workspace_id);
        CREATE TABLE IF NOT EXISTS gl_content_versions (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
            draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
            number INTEGER NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(draft_id, number));
        CREATE INDEX IF NOT EXISTS gl_content_versions_lookup_idx ON gl_content_versions(workspace_id,draft_id,number);
        CREATE TABLE IF NOT EXISTS gl_reference_sources (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
            filename TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL,
            uploaded_by TEXT NOT NULL REFERENCES auth_users(id), created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS gl_sources_workspace_idx ON gl_reference_sources(workspace_id);
        CREATE TABLE IF NOT EXISTS gl_policy_rules (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
            code TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL,
            pattern TEXT NOT NULL, replacement TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
            version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL,
            UNIQUE(workspace_id, code));
        CREATE INDEX IF NOT EXISTS gl_rules_workspace_idx ON gl_policy_rules(workspace_id);
        CREATE TABLE IF NOT EXISTS gl_guideline_cases (
            id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
            rule_id TEXT NOT NULL REFERENCES gl_policy_rules(id) ON DELETE CASCADE,
            channel TEXT NOT NULL, sample TEXT NOT NULL, expected_match INTEGER NOT NULL,
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS gl_cases_workspace_idx ON gl_guideline_cases(workspace_id);
    ''')
    cols = {r['name'] for r in con.execute('PRAGMA table_info(gl_content_versions)')}
    if 'created_by' not in cols:
        con.execute('ALTER TABLE gl_content_versions ADD COLUMN created_by TEXT')


class NotFound(LookupError):
    pass


class RevisionConflict(Exception):
    pass


def _row(row):
    return dict(row) if row is not None else None


def add_draft(con, *, actor_id, workspace_id, title, channel, content):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:create')
    if not title.strip() or not content.strip() or channel not in {'social','email','website','general'}:
        raise ValueError('Invalid title, content or channel')
    did, vid, stamp = ident(), ident(), now()
    con.execute('INSERT INTO gl_content_drafts VALUES (?,?,?,?,?,?)',
                (did, workspace_id, actor_id, title.strip(), channel, stamp))
    con.execute('INSERT INTO gl_content_versions (id,workspace_id,draft_id,number,content,created_at,created_by) VALUES (?,?,?,?,?,?,?)',
                (vid, workspace_id, did, 1, content, stamp, actor_id))
    return {'id': did, 'version_id': vid, 'version': 1}


def list_drafts(con, *, actor_id, workspace_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    return [dict(row) for row in con.execute('''
        SELECT d.id,d.title,d.channel,d.author_id,d.created_at,
               (SELECT MAX(v.number) FROM gl_content_versions v
                WHERE v.workspace_id=d.workspace_id AND v.draft_id=d.id) AS version
        FROM gl_content_drafts d WHERE d.workspace_id=? ORDER BY d.created_at DESC,d.id DESC
    ''', (workspace_id,))]


def get_draft(con, *, actor_id, workspace_id, draft_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    draft = _row(con.execute('SELECT * FROM gl_content_drafts WHERE id=? AND workspace_id=?',
                             (draft_id, workspace_id)).fetchone())
    if draft is None:
        raise NotFound('Draft not found')
    draft['versions'] = [dict(r) for r in con.execute('''SELECT * FROM gl_content_versions
        WHERE draft_id=? AND workspace_id=? ORDER BY number DESC''', (draft_id, workspace_id))]
    draft['current'] = draft['versions'][0]
    return draft


def revise_draft(con, *, actor_id, workspace_id, draft_id, content, expected_version=None):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:edit')
    if not content.strip():
        raise ValueError('Content cannot be empty')
    if hasattr(con, 'raw'):
        # Lock the draft parent before reading its latest version. PostgreSQL
        # serializes editors and reviewers on the same row.
        lock = con.execute('SELECT id FROM gl_content_drafts WHERE workspace_id=? AND id=? FOR UPDATE',
                           (workspace_id,draft_id)).fetchone()
        if lock is None:
            raise NotFound('Draft not found')
    draft = get_draft(con, actor_id=actor_id, workspace_id=workspace_id, draft_id=draft_id)
    if expected_version is not None and draft['current']['number'] != expected_version:
        raise RevisionConflict('Draft changed since you opened it; refresh before saving')
    num, vid = draft['current']['number'] + 1, ident()
    con.execute('INSERT INTO gl_content_versions (id,workspace_id,draft_id,number,content,created_at,created_by) VALUES (?,?,?,?,?,?,?)',
                (vid, workspace_id, draft_id, num, content, now(), actor_id))
    return {'version_id': vid, 'number': num}


def add_source(con, *, actor_id, workspace_id, filename, kind, content):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='evidence:write')
    if kind not in {'pdf','txt'} or not content.strip():
        raise ValueError('Invalid source')
    sid=ident()
    con.execute('INSERT INTO gl_reference_sources VALUES (?,?,?,?,?,?,?)',
                (sid,workspace_id,filename,kind,content,actor_id,now()))
    return {'id': sid}


def list_sources(con, *, actor_id, workspace_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='workspace:read')
    return [dict(r) for r in con.execute('''SELECT id,filename,kind,length(content) AS characters,created_at
        FROM gl_reference_sources WHERE workspace_id=? ORDER BY created_at DESC,id DESC''',(workspace_id,))]


def get_source(con, *, actor_id, workspace_id, source_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='workspace:read')
    item=_row(con.execute('SELECT * FROM gl_reference_sources WHERE id=? AND workspace_id=?',
                          (source_id,workspace_id)).fetchone())
    if item is None: raise NotFound('Source not found')
    return item


def add_rule(con, *, actor_id, workspace_id, code, category, title, pattern, replacement=''):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='policy:write')
    import re
    re.compile(pattern)
    if not code.strip() or not title.strip() or category not in {'fact','claim','tone','terminology'}:
        raise ValueError('Invalid rule')
    if hasattr(con, 'raw'):
        con.execute('SELECT id FROM gl_workspaces WHERE id=? FOR UPDATE', (workspace_id,))
    rid=ident()
    con.execute('INSERT INTO gl_policy_rules VALUES (?,?,?,?,?,?,?,?,?,?)',
                (rid,workspace_id,code,category,title,pattern,replacement,1,1,now()))
    return {'id':rid,'code':code}


def list_rules(con, *, actor_id, workspace_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='workspace:read')
    return [dict(r) for r in con.execute('SELECT * FROM gl_policy_rules WHERE workspace_id=? ORDER BY code',
                                         (workspace_id,))]


def add_unit_case(con, *, actor_id, workspace_id, rule_id, channel, sample, expected_match, note=''):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='policy:write')
    if con.execute('SELECT 1 FROM gl_policy_rules WHERE id=? AND workspace_id=?',
                   (rule_id,workspace_id)).fetchone() is None:
        raise NotFound('Rule not found')
    cid=ident()
    con.execute('INSERT INTO gl_guideline_cases VALUES (?,?,?,?,?,?,?,?)',
                (cid,workspace_id,rule_id,channel,sample,int(expected_match),note,now()))
    return {'id':cid}


def list_unit_cases(con, *, actor_id, workspace_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='workspace:read')
    return [dict(r) for r in con.execute('SELECT * FROM gl_guideline_cases WHERE workspace_id=? ORDER BY created_at,id',
                                         (workspace_id,))]
