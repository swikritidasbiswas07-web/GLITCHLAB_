"""Build 05J.1: workspace-isolated saved regression cases.

Uses the existing gl_guideline_cases table. No migration needed.
Only policy admins may mutate test cases; all workspace members may inspect.
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from workspace_core import require_action


class CaseNotFound(ValueError):
    pass


def list_cases(con, *, actor_id, workspace_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='workspace:read')
    return [dict(row) for row in con.execute('''
        SELECT c.id,c.rule_id,r.code AS rule_code,r.title AS rule_title,
               c.channel,c.sample,c.expected_match,c.note,c.created_at,
               r.active AS rule_active
          FROM gl_guideline_cases c JOIN gl_policy_rules r
            ON r.id=c.rule_id AND r.workspace_id=c.workspace_id
         WHERE c.workspace_id=? ORDER BY c.created_at,c.id
    ''', (workspace_id,))]


def create_case(con, *, actor_id, workspace_id, rule_id, channel, sample, expected_match, note=''):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='policy:write')
    if not sample.strip() or len(sample) > 4000:
        raise ValueError('Enter a sample of 1 to 4000 characters')
    if not channel.strip() or len(channel) > 60:
        raise ValueError('Channel must be 1 to 60 characters')
    if len(note) > 500:
        raise ValueError('Case note must not exceed 500 characters')
    rule=con.execute('''SELECT id,active FROM gl_policy_rules
                       WHERE id=? AND workspace_id=?''',(rule_id,workspace_id)).fetchone()
    if rule is None or not bool(rule['active']):
        raise CaseNotFound('Active rule not found in this workspace')
    case_id=str(uuid4())
    created=datetime.now(timezone.utc).isoformat(timespec='microseconds')
    con.execute('''INSERT INTO gl_guideline_cases
        (id,workspace_id,rule_id,sample,expected_match,channel,note,created_at)
        VALUES (?,?,?,?,?,?,?,?)''',
        (case_id,workspace_id,rule_id,sample,int(expected_match),channel.strip(),note.strip(),created))
    return dict(id=case_id,rule_id=rule_id,expected_match=expected_match,created_at=created)


def delete_case(con, *, actor_id, workspace_id, case_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='policy:write')
    row=con.execute('SELECT id FROM gl_guideline_cases WHERE workspace_id=? AND id=?',
                    (workspace_id,case_id)).fetchone()
    if row is None:
        raise CaseNotFound('Regression case not found in this workspace')
    con.execute('DELETE FROM gl_guideline_cases WHERE workspace_id=? AND id=?',(workspace_id,case_id))
    return {'deleted':True,'id':case_id}
