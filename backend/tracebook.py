"""Workspace-bound activity reconstructed from actual persisted versions, runs and reviews.

Existing old versions have no recorded editor and therefore show unknown authorship.
No fabricated events or retrospective identities. All queries require membership.
"""
from __future__ import annotations
from difflib import SequenceMatcher
from workspace_core import require_action
from workspace_data import NotFound


def timeline(con, *, actor_id: str, workspace_id: str, draft_id: str):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    draft = con.execute('SELECT id,author_id FROM gl_content_drafts WHERE id=? AND workspace_id=?',
                        (draft_id, workspace_id)).fetchone()
    if draft is None:
        raise NotFound('Draft not found')
    users = {r['id']: r['display_name'] for r in con.execute('SELECT u.id,u.display_name FROM auth_users u JOIN gl_memberships m ON m.user_id=u.id WHERE m.workspace_id=?', (workspace_id,))}
    # The author_id in gl_content_drafts is the initial author, not the editor of each revision.
    # Version 1 can be attributed from draft authorship. Pre-upgrade versions >1 lack an actor.
    versions = [dict(r) for r in con.execute('''
        SELECT id,number,created_at,created_by FROM gl_content_versions
        WHERE workspace_id=? AND draft_id=? ORDER BY number,id''', (workspace_id,draft_id))]
    entries = []
    for v in versions:
        uid = draft['author_id'] if v['number']==1 else v['created_by']
        entries.append({'id':'version:'+v['id'], 'type':'draft_created' if v['number']==1 else 'revision_saved',
                        'actor_id':uid, 'actor_name':users.get(uid, 'Unknown editor') if uid else 'Unknown editor',
                        'created_at':v['created_at'], 'version_id':v['id'], 'version_number':v['number'],
                        'description':'Draft created' if v['number']==1 else 'New version saved'})
    for r in con.execute('''SELECT id,version_id,tested_by,checked_rules,created_at
         FROM gl_evaluation_runs WHERE workspace_id=? AND draft_id=?''',(workspace_id,draft_id)):
        entries.append({'id':'test:'+r['id'],'type':'policy_test','actor_id':r['tested_by'],
                        'actor_name':users.get(r['tested_by'],'Former or unknown member'),
                        'created_at':r['created_at'],'version_id':r['version_id'],
                        'version_number':next((v['number'] for v in versions if v['id']==r['version_id']),None),
                        'description':f"Evaluated {r['checked_rules']} configured rules"})
    for r in con.execute('''SELECT id,version_id,actor_id,decision,comment,created_at
         FROM gl_review_decisions WHERE workspace_id=? AND draft_id=?''',(workspace_id,draft_id)):
        entries.append({'id':'review:'+r['id'],'type':'review_'+r['decision'],'actor_id':r['actor_id'],
                        'actor_name':users.get(r['actor_id'],'Former or unknown member'),
                        'created_at':r['created_at'],'version_id':r['version_id'],
                        'version_number':next((v['number'] for v in versions if v['id']==r['version_id']),None),
                        'description':r['comment'] or ('Approved' if r['decision']=='approved' else 'Changes requested')})
    return sorted(entries, key=lambda e:(e['created_at'], e['id']),reverse=True)


def compare_versions(con, *, actor_id: str, workspace_id: str, draft_id: str, before: int, after: int):
    require_action(con,user_id=actor_id,workspace_id=workspace_id,action='draft:read')
    if before<1 or after<1 or before==after:
        raise ValueError('Choose two different positive version numbers')
    draft=con.execute('SELECT 1 FROM gl_content_drafts WHERE id=? AND workspace_id=?',(draft_id,workspace_id)).fetchone()
    if not draft: raise NotFound('Draft not found')
    versions=con.execute('''SELECT number,content FROM gl_content_versions
       WHERE workspace_id=? AND draft_id=? AND number IN (?,?)''',(workspace_id,draft_id,before,after)).fetchall()
    items={r['number']:r['content'] for r in versions}
    if before not in items or after not in items: raise NotFound('Version not found')
    # Word-level diff with unchanged spans preserved, safely rendered as text in React.
    import re
    a=re.findall(r'\s+|\S+',items[before]); b=re.findall(r'\s+|\S+',items[after])
    before_parts=[]; after_parts=[]
    for op,i,j,k,l in SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if op in ('equal','replace','delete') and i!=j:
            before_parts.append({'kind':'unchanged' if op=='equal' else 'removed','text':''.join(a[i:j])})
        if op in ('equal','replace','insert') and k!=l:
            after_parts.append({'kind':'unchanged' if op=='equal' else 'added','text':''.join(b[k:l])})
    return {'before_version':before,'after_version':after,'before_parts':before_parts,'after_parts':after_parts}
