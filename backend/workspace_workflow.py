"""Workspace-isolated deterministic evaluation and version-bound human reviews.

SQLite transition implementation; not a replacement for persistence/tenant hardening.
Every lookup includes workspace_id, even when IDs are unguessable.
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from workspace_core import require_action
from workspace_data import NotFound, ident, now


def initialize(con):
    con.executescript('''
      CREATE TABLE IF NOT EXISTS gl_evaluation_runs (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
        draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
        version_id TEXT NOT NULL REFERENCES gl_content_versions(id) ON DELETE CASCADE,
        tested_by TEXT NOT NULL REFERENCES auth_users(id), checked_rules INTEGER NOT NULL,
        rule_snapshot TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS gl_runs_scope_idx ON gl_evaluation_runs(workspace_id, draft_id, created_at);
      CREATE TABLE IF NOT EXISTS gl_evaluation_findings (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
        run_id TEXT NOT NULL REFERENCES gl_evaluation_runs(id) ON DELETE CASCADE,
        rule_code TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL,
        matched_text TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL,
        suggestion TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS gl_findings_scope_idx ON gl_evaluation_findings(workspace_id,run_id);
      CREATE TABLE IF NOT EXISTS gl_review_decisions (
        id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL REFERENCES gl_workspaces(id) ON DELETE CASCADE,
        draft_id TEXT NOT NULL REFERENCES gl_content_drafts(id) ON DELETE CASCADE,
        version_id TEXT NOT NULL REFERENCES gl_content_versions(id) ON DELETE CASCADE,
        actor_id TEXT NOT NULL REFERENCES auth_users(id), decision TEXT NOT NULL,
        comment TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS gl_reviews_scope_idx ON gl_review_decisions(workspace_id,draft_id,created_at);
    ''')


def _latest(con, workspace_id, draft_id):
    draft = con.execute('SELECT id,channel FROM gl_content_drafts WHERE id=? AND workspace_id=?',
                        (draft_id,workspace_id)).fetchone()
    if draft is None:
        raise NotFound('Draft not found')
    version = con.execute('''SELECT id,number,content FROM gl_content_versions
      WHERE workspace_id=? AND draft_id=? ORDER BY number DESC LIMIT 1''',
      (workspace_id,draft_id)).fetchone()
    if version is None:
        raise NotFound('Draft version not found')
    return draft, version


def _scoped_rules(con, workspace_id, channel):
    return [dict(r) for r in con.execute('''SELECT * FROM gl_policy_rules
      WHERE workspace_id=? AND active=1 ORDER BY code''', (workspace_id,))]


def evaluate(con, *, actor_id, workspace_id, draft_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='draft:test')
    draft,version = _latest(con,workspace_id,draft_id)
    rule_set=_scoped_rules(con,workspace_id,draft['channel'])
    run_id=ident()
    con.execute('''INSERT INTO gl_evaluation_runs VALUES (?,?,?,?,?,?,?,?)''',
                (run_id,workspace_id,draft_id,version['id'],actor_id,len(rule_set),
                 json.dumps([{'id':r['id'],'code':r['code'],'version':r['version'],
                              'pattern':r['pattern']} for r in rule_set]),datetime.now(timezone.utc).isoformat(timespec='microseconds')))
    findings=[]
    for rule in rule_set:
        try:
            matches=re.finditer(rule['pattern'],version['content'],re.IGNORECASE)
            for match in matches:
                if match.start()==match.end():
                    continue
                item={'id':ident(),'workspace_id':workspace_id,'run_id':run_id,
                      'rule_code':rule['code'],'category':rule['category'],
                      'title':rule['title'],'matched_text':match.group(),
                      'start':match.start(),'end':match.end(),
                      'suggestion':rule['replacement']}
                con.execute('''INSERT INTO gl_evaluation_findings VALUES (?,?,?,?,?,?,?,?,?,?)''',
                            tuple(item.values()))
                findings.append(item)
        except re.error:
            # Rule creation rejects invalid patterns; legacy/corrupt patterns are skipped.
            continue
    return {'run_id':run_id,'version_number':version['number'],
            'version_id':version['id'],'checked_rules':len(rule_set),
            'findings':findings,'status':'issues_found' if findings else 'no_issues_detected',
            'disclaimer':'Only configured deterministic rules evaluated; no factual or legal certification.'}


def run_detail(con, *, actor_id, workspace_id, run_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='draft:read')
    row=con.execute('SELECT * FROM gl_evaluation_runs WHERE id=? AND workspace_id=?',
                    (run_id,workspace_id)).fetchone()
    if row is None: raise NotFound('Run not found')
    result=dict(row)
    result['findings']=[dict(r) for r in con.execute('''SELECT * FROM gl_evaluation_findings
      WHERE workspace_id=? AND run_id=? ORDER BY start,id''',(workspace_id,run_id))]
    return result


def decide(con, *, actor_id, workspace_id, draft_id, decision, comment):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='review:decide')
    if decision not in ('approved','changes_requested'):
        raise ValueError('Invalid review decision')
    # PostgreSQL: serialize approval against revision creation. SQLite's own
    # transaction locking is retained for the existing local test mode.
    if hasattr(con, 'raw'):
        con.execute('SELECT id FROM gl_content_drafts WHERE workspace_id=? AND id=? FOR UPDATE',
                    (workspace_id,draft_id))
        # Serialize policy publication against approval; rule writes take the same lock.
        con.execute('SELECT id FROM gl_workspaces WHERE id=? FOR UPDATE', (workspace_id,))
    _,version = _latest(con,workspace_id,draft_id)
    if decision=='approved':
        # A reviewer must be independent of the draft author, even if they are an admin.
        author = con.execute('''SELECT author_id FROM gl_content_drafts
           WHERE id=? AND workspace_id=?''', (draft_id,workspace_id)).fetchone()
        if author is None:
            raise NotFound('Draft not found')
        if author['author_id'] == actor_id:
            raise ReviewConflict('You cannot approve a draft you authored; request an independent reviewer')
        latest_run=con.execute('''SELECT id,checked_rules,rule_snapshot FROM gl_evaluation_runs WHERE workspace_id=? AND draft_id=?
           AND version_id=? ORDER BY created_at DESC,id DESC LIMIT 1''',
           (workspace_id,draft_id,version['id'])).fetchone()
        if latest_run is None:
            raise ReviewConflict('Test the latest version before approval')
        if latest_run['checked_rules'] < 1:
            raise ReviewConflict('Approval requires at least one configured policy check; add workspace rules and retest')
        # Compare the exact evaluated active rule identities/versions/patterns,
        # not just the rule count; a changed policy invalidates an older run.
        active = _scoped_rules(con, workspace_id, '')
        current_snapshot = sorted(
            (str(r['id']), str(r['code']), int(r['version']), str(r['pattern']))
            for r in active
        )
        try:
            old = latest_run['rule_snapshot']
            stored = json.loads(old) if isinstance(old, str) else old
            tested_snapshot = sorted(
                (str(r['id']), str(r['code']), int(r['version']), str(r['pattern']))
                for r in stored
            )
        except (TypeError, ValueError, KeyError):
            raise ReviewConflict('Stored policy test snapshot is invalid; retest the latest version')
        if latest_run['checked_rules'] != len(active) or tested_snapshot != current_snapshot:
            raise ReviewConflict('Workspace policy changed since testing; retest the latest version')
        existing = con.execute('''SELECT id FROM gl_review_decisions
            WHERE workspace_id=? AND draft_id=? AND version_id=? AND decision=? LIMIT 1''',
            (workspace_id, draft_id, version['id'], 'approved')).fetchone()
        if existing is not None:
            raise ReviewConflict('This draft version already has an approval')
        failed=con.execute('''SELECT COUNT(*) FROM gl_evaluation_findings
          WHERE workspace_id=? AND run_id=?''',(workspace_id,latest_run['id'])).fetchone()[0]
        if failed:
            raise ReviewConflict('Latest version has unresolved findings')
    item={'id':ident(),'workspace_id':workspace_id,'draft_id':draft_id,
          'version_id':version['id'],'actor_id':actor_id,'decision':decision,
          'comment':comment,'created_at':now()}
    con.execute('INSERT INTO gl_review_decisions VALUES (?,?,?,?,?,?,?,?)',tuple(item.values()))
    return item


def review_history(con, *, actor_id, workspace_id, draft_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='draft:read')
    _latest(con,workspace_id,draft_id)
    return [dict(r) for r in con.execute('''SELECT * FROM gl_review_decisions WHERE workspace_id=?
      AND draft_id=? ORDER BY created_at DESC,id DESC''',(workspace_id,draft_id))]


class ReviewConflict(Exception):
    pass
