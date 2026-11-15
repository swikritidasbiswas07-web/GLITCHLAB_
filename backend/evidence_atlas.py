"""Evidence Atlas / ClaimScope.

No AI truth claims: statuses reflect human-attested source relationships only.
A source quote is verified as a substring of the exact stored source snapshot.
"""
from __future__ import annotations

import hashlib
from uuid import uuid4
from workspace_core import require_action, utcnow


class EvidenceMissing(LookupError):
    pass


class EvidenceConflict(Exception):
    pass


def _one(con, sql, args):
    row = con.execute(sql, args).fetchone()
    if row is None:
        raise EvidenceMissing('Workspace resource not found')
    return dict(row)


def _ensure_draft(con, workspace_id, draft_id, version_id=None):
    _one(con, 'SELECT id FROM gl_content_drafts WHERE id=? AND workspace_id=?', (draft_id, workspace_id))
    if version_id:
        return _one(con, '''SELECT id,content,number FROM gl_content_versions
            WHERE id=? AND workspace_id=? AND draft_id=?''', (version_id, workspace_id, draft_id))
    return None


def sources(con, *, workspace_id, actor_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    return [dict(r) for r in con.execute('''SELECT id,filename,kind,created_at,length(content) AS characters
        FROM gl_reference_sources WHERE workspace_id=? ORDER BY created_at DESC,id''', (workspace_id,))]


def create_evidence(con, *, workspace_id, actor_id, source_id, quote, locator=''):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='evidence:write')
    quote, locator = quote.strip(), locator.strip()
    if not 1 <= len(quote) <= 4000 or len(locator) > 250:
        raise ValueError('Quote must be 1–4000 characters; locator must be at most 250')
    source = _one(con, 'SELECT id,content FROM gl_reference_sources WHERE id=? AND workspace_id=?',
                  (source_id, workspace_id))
    if quote not in source['content']:
        raise EvidenceConflict('Quotation does not appear verbatim in this workspace source')
    item_id = str(uuid4())
    stamp = utcnow()
    digest = hashlib.sha256(source['content'].encode('utf-8')).hexdigest()
    con.execute('''INSERT INTO gl_evidence_items
       (id,workspace_id,source_id,quote,source_locator,source_sha256,recorded_by,created_at)
       VALUES (?,?,?,?,?,?,?,?)''', (item_id,workspace_id,source_id,quote,locator,digest,actor_id,stamp))
    return {'id':item_id,'source_id':source_id,'quote':quote,'source_locator':locator,'created_at':stamp,
            'quote_verified': True, 'warning':'Quote location verified, not factual accuracy'}


def list_evidence(con, *, workspace_id, actor_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    return [dict(r) for r in con.execute('''SELECT e.id,e.source_id,s.filename,e.quote,e.source_locator,
         e.recorded_by,e.created_at,
         CASE WHEN e.source_sha256 = '' THEN 0 ELSE 1 END AS stored_digest_present
         FROM gl_evidence_items e JOIN gl_reference_sources s
           ON s.id=e.source_id AND s.workspace_id=e.workspace_id
         WHERE e.workspace_id=? ORDER BY e.created_at DESC,e.id DESC''', (workspace_id,))]


def create_claim(con, *, workspace_id, actor_id, draft_id, version_id, claim_text):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:edit')
    version = _ensure_draft(con, workspace_id, draft_id, version_id)
    claim_text = claim_text.strip()
    if not 1 <= len(claim_text) <= 1200:
        raise ValueError('Claim text must be 1–1200 characters')
    if claim_text not in version['content']:
        raise EvidenceConflict('Claim must be an exact excerpt of this saved draft version')
    claim_id = str(uuid4()); stamp = utcnow()
    con.execute('''INSERT INTO gl_claims(id,workspace_id,draft_id,version_id,claim_text,recorded_by,created_at)
      VALUES (?,?,?,?,?,?,?)''',(claim_id,workspace_id,draft_id,version_id,claim_text,actor_id,stamp))
    return {'id':claim_id,'draft_id':draft_id,'version_id':version_id,'claim_text':claim_text,
            'status':'insufficient_evidence','created_at':stamp}


def link_evidence(con, *, workspace_id, actor_id, claim_id, evidence_id, stance, rationale):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='evidence:write')
    if stance not in ('supports','contradicts','context'):
        raise ValueError('Invalid evidence relationship')
    if not 4 <= len(rationale.strip()) <= 1500:
        raise ValueError('Reasoning must be 4–1500 characters')
    _one(con, 'SELECT id FROM gl_claims WHERE id=? AND workspace_id=?', (claim_id,workspace_id))
    _one(con, 'SELECT id FROM gl_evidence_items WHERE id=? AND workspace_id=?', (evidence_id,workspace_id))
    found = con.execute('''SELECT id FROM gl_claim_evidence WHERE claim_id=? AND evidence_id=?
        AND workspace_id=?''',(claim_id,evidence_id,workspace_id)).fetchone()
    if found:
        raise EvidenceConflict('This evidence is already linked to this claim')
    link_id = str(uuid4()); stamp = utcnow()
    con.execute('''INSERT INTO gl_claim_evidence
      (id,workspace_id,claim_id,evidence_id,stance,rationale,added_by,created_at)
      VALUES (?,?,?,?,?,?,?,?)''',
      (link_id,workspace_id,claim_id,evidence_id,stance,rationale.strip(),actor_id,stamp))
    return {'id':link_id,'claim_id':claim_id,'evidence_id':evidence_id,'stance':stance,
            'attested':False,'created_at':stamp}


def attest_link(con, *, workspace_id, actor_id, link_id):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='review:decide')
    link = _one(con, '''SELECT l.*,c.recorded_by AS claim_author,e.source_id,e.source_sha256,
         e.quote,s.content AS source_content
         FROM gl_claim_evidence l
         JOIN gl_claims c ON c.id=l.claim_id AND c.workspace_id=l.workspace_id
         JOIN gl_evidence_items e ON e.id=l.evidence_id AND e.workspace_id=l.workspace_id
         JOIN gl_reference_sources s ON s.id=e.source_id AND s.workspace_id=l.workspace_id
         WHERE l.id=? AND l.workspace_id=?''',(link_id,workspace_id))
    if link['claim_author'] == actor_id or link['added_by'] == actor_id:
        raise EvidenceConflict('Claim authors and evidence-link proposers cannot attest their own relationship')
    if link['attested_by']:
        raise EvidenceConflict('Evidence relationship already attested')
    if link['quote'] not in link['source_content'] or hashlib.sha256(link['source_content'].encode('utf-8')).hexdigest() != link['source_sha256']:
        raise EvidenceConflict('Source has changed since evidence was recorded; create a new evidence record')
    # Lock link (PostgreSQL) to prevent concurrent attestations.
    if hasattr(con,'raw'):
        locked = _one(con,'SELECT attested_by FROM gl_claim_evidence WHERE id=? AND workspace_id=? FOR UPDATE',
                      (link_id,workspace_id))
        if locked['attested_by']:
            raise EvidenceConflict('Evidence relationship already attested')
    stamp=utcnow()
    con.execute('''UPDATE gl_claim_evidence SET attested_by=?,attested_at=?
        WHERE id=? AND workspace_id=? AND attested_by IS NULL''',(actor_id,stamp,link_id,workspace_id))
    return {'id':link_id,'attested_by':actor_id,'attested_at':stamp}


def claim_scope(con, *, workspace_id, actor_id, draft_id, version_id=None):
    require_action(con, user_id=actor_id, workspace_id=workspace_id, action='draft:read')
    _ensure_draft(con,workspace_id,draft_id,version_id)
    sql='''SELECT c.id,c.draft_id,c.version_id,c.claim_text,c.recorded_by,c.created_at,
       v.number AS version_number
       FROM gl_claims c JOIN gl_content_versions v ON v.id=c.version_id AND v.workspace_id=c.workspace_id
       WHERE c.workspace_id=? AND c.draft_id=?'''
    args=[workspace_id,draft_id]
    if version_id:
        sql += ' AND c.version_id=?'; args.append(version_id)
    sql += ' ORDER BY v.number DESC,c.created_at DESC,c.id DESC'
    claims=[]
    for claim in con.execute(sql,tuple(args)):
        claim=dict(claim)
        links=[dict(r) for r in con.execute('''SELECT l.id,l.evidence_id,l.stance,l.rationale,l.added_by,
            l.attested_by,l.attested_at,e.quote,e.source_locator,e.source_sha256,s.content AS source_content,s.filename,s.id AS source_id
          FROM gl_claim_evidence l JOIN gl_evidence_items e
            ON e.id=l.evidence_id AND e.workspace_id=l.workspace_id
          JOIN gl_reference_sources s ON s.id=e.source_id AND s.workspace_id=l.workspace_id
          WHERE l.workspace_id=? AND l.claim_id=? ORDER BY l.created_at,l.id''',
          (workspace_id,claim['id']))]
        statuses={r['stance'] for r in links if r['attested_by'] and r['quote'] in r['source_content']
                  and hashlib.sha256(r['source_content'].encode('utf-8')).hexdigest()==r['source_sha256']}
        for link in links:
            link['source_unchanged']=(link['quote'] in link['source_content'] and hashlib.sha256(link['source_content'].encode('utf-8')).hexdigest()==link['source_sha256'])
            del link['source_content']
            del link['source_sha256']
        if 'contradicts' in statuses:
            result='contradicted'
        elif 'supports' in statuses:
            result='supported'
        else:
            result='insufficient_evidence'
        claim['status']=result
        claim['links']=links
        claim['disclaimer']='Human-attested source alignment, not independent factual verification.'
        claims.append(claim)
    return claims
