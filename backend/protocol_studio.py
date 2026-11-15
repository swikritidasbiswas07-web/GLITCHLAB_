"""Immutable workspace policy snapshots and read-only RippleMap impact analysis.

Build 05J. Publishing records the *currently active* Policy Vault rules; it does not
change them. The original deterministic checker remains the source of live checks.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import uuid4
from workspace_core import require_action

class ProtocolConflict(Exception):
    pass


def _stamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _rules(con, workspace_id):
    return [dict(row) for row in con.execute('''SELECT id,code,category,title,pattern,replacement,version
        FROM gl_policy_rules WHERE workspace_id=? AND active=1 ORDER BY code,id''', (workspace_id,))]


def _canonical(rules):
    return json.dumps(rules, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _hash(rules):
    return hashlib.sha256(_canonical(rules).encode('utf-8')).hexdigest()


def _load_json(value):
    return json.loads(value) if isinstance(value, str) else value


def _latest_release(con, workspace_id):
    row = con.execute('''SELECT * FROM gl_policy_releases WHERE workspace_id=?
        ORDER BY number DESC LIMIT 1''', (workspace_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    result['rules'] = _load_json(result.pop('snapshot'))
    return result


def _cases(con, workspace_id, rules):
    rules_by_id = {r['id']: r for r in rules}
    tests = []
    for c in con.execute('''SELECT id,rule_id,sample,expected_match,channel,note FROM gl_guideline_cases
        WHERE workspace_id=? ORDER BY created_at,id''',(workspace_id,)):
        c=dict(c)
        rule=rules_by_id.get(c['rule_id'])
        if not rule:
            continue  # Inactive rules are out of release scope.
        try:
            got = bool(re.search(rule['pattern'],c['sample'],re.IGNORECASE))
            error = None
        except re.error as ex:
            got = None
            error = str(ex)
        c.update(rule_code=rule['code'], expected_match=bool(c['expected_match']), actual_match=got,
                 passed=(got is not None and got == bool(c['expected_match'])), error=error)
        tests.append(c)
    return tests


def preview(con, *, actor_id, workspace_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='workspace:read')
    rules=_rules(con,workspace_id)
    tests=_cases(con,workspace_id,rules)
    last=_latest_release(con,workspace_id)
    before={r['code']:r for r in last['rules']} if last else {}
    after={r['code']:r for r in rules}
    added=sorted(set(after)-set(before))
    removed=sorted(set(before)-set(after))
    modified=sorted(k for k in set(after)&set(before) if after[k] != before[k])
    return dict(active_rules=rules, active_hash=_hash(rules), current_release=last,
                next_number=1 if last is None else last['number']+1,
                change=dict(added=added,removed=removed,modified=modified),
                tests=tests, test_passed=sum(bool(t['passed']) for t in tests),
                test_failed=sum(not t['passed'] for t in tests),
                eligible=bool(rules) and all(t['passed'] for t in tests),
                limitation='Publication snapshots active rules; it does not apply a pending rule edit. No unit cases means regression coverage is absent.')


def publish(con, *, actor_id, workspace_id, note, expected_hash):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='policy:release')
    if not note.strip() or len(note)>500:
        raise ValueError('A release note (up to 500 characters) is required')
    # Use same lock that add_rule and review approval use on PostgreSQL.
    if hasattr(con,'raw'):
        con.execute('SELECT id FROM gl_workspaces WHERE id=? FOR UPDATE',(workspace_id,)).fetchone()
    p=preview(con,actor_id=actor_id,workspace_id=workspace_id)
    if expected_hash != p['active_hash']:
        raise ProtocolConflict('Active policies changed since preview. Refresh before publishing.')
    if not p['eligible']:
        raise ProtocolConflict('At least one active rule and passing regression cases are required')
    last=p['current_release']
    if last and last['snapshot_hash']==p['active_hash']:
        raise ProtocolConflict('This policy snapshot is already published')
    data=dict(id=str(uuid4()),workspace_id=workspace_id,number=p['next_number'],
              snapshot_hash=p['active_hash'],snapshot=_canonical(p['active_rules']),
              note=note.strip(),published_by=actor_id,published_at=_stamp())
    con.execute('''INSERT INTO gl_policy_releases
        (id,workspace_id,number,snapshot_hash,snapshot,note,published_by,published_at)
        VALUES (?,?,?,?,?,?,?,?)''',tuple(data.values()))
    return dict(id=data['id'],number=data['number'],snapshot_hash=data['snapshot_hash'],
                note=data['note'],published_at=data['published_at'])


def history(con, *, actor_id,workspace_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='workspace:read')
    return [dict(r) for r in con.execute('''SELECT id,number,snapshot_hash,note,published_by,published_at
        FROM gl_policy_releases WHERE workspace_id=? ORDER BY number DESC''',(workspace_id,))]


def _run_sig(snapshot):
    # Evaluation snapshots currently record only these 4 fields; compare only them.
    try:
        rs=_load_json(snapshot)
        return sorted((str(r['id']),str(r['code']),int(r['version']),str(r['pattern'])) for r in rs)
    except (TypeError,ValueError,KeyError,AttributeError):
        return None


def impact(con, *, actor_id,workspace_id):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='workspace:read')
    active=_rules(con,workspace_id)
    current=sorted((str(r['id']),str(r['code']),int(r['version']),str(r['pattern'])) for r in active)
    release=_latest_release(con,workspace_id)
    published_matches=bool(release and release['snapshot_hash']==_hash(active))
    drafts=[]
    for d in con.execute('''SELECT id,title,channel,author_id FROM gl_content_drafts
        WHERE workspace_id=? ORDER BY title,id''',(workspace_id,)):
        d=dict(d)
        v=con.execute('''SELECT id,number,content FROM gl_content_versions
            WHERE workspace_id=? AND draft_id=? ORDER BY number DESC LIMIT 1''',(workspace_id,d['id'])).fetchone()
        if v is None:continue
        v=dict(v)
        run=con.execute('''SELECT id,checked_rules,rule_snapshot,created_at FROM gl_evaluation_runs
            WHERE workspace_id=? AND draft_id=? AND version_id=?
            ORDER BY created_at DESC,id DESC LIMIT 1''',(workspace_id,d['id'],v['id'])).fetchone()
        review=con.execute('''SELECT id,created_at FROM gl_review_decisions
            WHERE workspace_id=? AND draft_id=? AND version_id=? AND decision='approved'
            ORDER BY created_at DESC,id DESC LIMIT 1''',(workspace_id,d['id'],v['id'])).fetchone()
        stale=not run or int(run['checked_rules'])!=len(active) or _run_sig(run['rule_snapshot'])!=current
        hits=[]
        for r in active:
            try:
                if re.search(r['pattern'],v['content'],re.IGNORECASE):hits.append(r['code'])
            except re.error:
                hits.append(r['code']+' (invalid pattern)')
        status='untested' if not run else ('retest_required' if stale else ('findings_possible' if hits else 'current'))
        drafts.append(dict(draft_id=d['id'],title=d['title'],channel=d['channel'],version=v['number'],
                           has_approval=bool(review),last_run_id=run['id'] if run else None,
                           status=status,needs_retest=bool(stale),matched_rules=hits,
                           approval_needs_revalidation=bool(review and stale)))
    return dict(current_release=release['number'] if release else None,
                published_matches_active=published_matches,active_rules=len(active),
                draft_count=len(drafts),retest_count=sum(int(d['needs_retest']) for d in drafts),
                approvals_at_risk=sum(int(d['approval_needs_revalidation']) for d in drafts),
                drafts=drafts,
                limitation='Impact is advisory: regex matches and evaluation freshness, not a full re-evaluation or automatic revocation of historical approvals.')
