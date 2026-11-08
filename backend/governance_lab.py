"""GLITCHLAB_ Round 2 Governance Lab.

Three advisory tools: scoped numeric contradiction candidates, policy unit tests,
and deterministic multi-edit preview. All content is demonstration data.
No AI claims, automatic approval, or persistent patch writes.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Any, Callable, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix='/governance', tags=['Governance Lab'])
DB_PROVIDER: Callable[[], Any] | None = None
RULE_PROVIDER: Callable[..., list[dict]] | None = None

CHANNEL = Literal['social', 'email', 'website', 'general']


def install(db_provider: Callable[[], Any], rules_provider: Callable[..., list[dict]]) -> APIRouter:
    global DB_PROVIDER, RULE_PROVIDER
    DB_PROVIDER, RULE_PROVIDER = db_provider, rules_provider
    with DB_PROVIDER() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS guideline_unit_cases (
            id TEXT PRIMARY KEY, rule_code TEXT NOT NULL, channel TEXT NOT NULL,
            sample TEXT NOT NULL, expected_match INTEGER NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL)''')
    return router


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _active(con, channel: str) -> list[dict]:
    return RULE_PROVIDER(con, channel)


def _hits(content: str, rules: list[dict]) -> list[dict]:
    result = []
    for rule in rules:
        try:
            for m in re.finditer(rule['pattern'], content, flags=re.IGNORECASE):
                if m.start() == m.end():
                    continue
                result.append({'rule_code': rule['code'], 'start': m.start(), 'end': m.end(),
                               'matched_text': m.group(), 'category': rule.get('category', '')})
        except (re.error, KeyError, TypeError):
            continue
    return sorted(result, key=lambda e: (e['start'], e['end']))


# Intentionally narrow metric vocabulary: a number alone never proves contradiction.
_METRIC_RE = re.compile(
    r'(?i)\b(?P<topic>battery\s+life|battery\s+runtime|battery\s+duration|'
    r'warranty(?:\s+period)?|charging\s+time|charge\s+time|'
    r'product\s+weight|device\s+weight|storage\s+capacity|memory\s+capacity)'
    r'\s*(?:(?:is|of|:|=|up\s+to|lasts?|approximately|about)\s*){0,3}'
    r'(?P<number>\d+(?:\.\d+)?)\s*'
    r'(?P<unit>hours?|hrs?|minutes?|mins?|days?|months?|years?|'
    r'kg|kilograms?|g|grams?|gb|tb|mb)\b'
)
_UNIT = {
    'hour': ('hour', 1), 'hr': ('hour', 1), 'minute': ('hour', 1/60),
    'min': ('hour', 1/60), 'day': ('hour', 24),
    'month': ('month', 1), 'year': ('month', 12),
    'kg': ('gram', 1000), 'kilogram': ('gram', 1000),
    'g': ('gram', 1), 'gram': ('gram', 1),
    'mb': ('gb', 1/1024), 'gb': ('gb', 1), 'tb': ('gb', 1024)
}


def _metrics(text: str, sid: str, filename: str, *, limit: int = 60) -> list[dict]:
    values = []
    for m in _METRIC_RE.finditer(text[:16000]):
        unit = m.group('unit').lower()
        unit = unit[:-1] if unit.endswith('s') and unit not in ('hrs', 'mins') else unit
        if unit in ('hrs', 'mins'):
            unit = unit[:-1]
        category, factor = _UNIT.get(unit, ('', 0))
        if not category:
            continue
        subject = re.sub(r'\s+', ' ', m.group('topic').lower())
        subject = {'battery runtime': 'battery life', 'battery duration': 'battery life',
                   'charge time': 'charging time', 'device weight': 'product weight',
                   'memory capacity': 'storage capacity', 'warranty period': 'warranty'}.get(subject, subject)
        start = max(0, m.start() - 90)
        stop = min(len(text), m.end() + 100)
        excerpt = text[start:stop].replace('\n', ' ').strip()
        values.append({'source_id': sid, 'filename': filename, 'metric': subject,
                       'value': float(m.group('number')), 'unit': m.group('unit'),
                       'normalized': round(float(m.group('number')) * factor, 6),
                       'normalized_unit': category, 'excerpt': excerpt,
                       'match': m.group()})
        if len(values) >= limit:
            break
    return values


class ContradictionIn(BaseModel):
    source_ids: list[str] = Field(default_factory=list, max_length=6)
    draft: str = Field(default='', max_length=12000)


@router.post('/contradictions')
def contradictions(body: ContradictionIn):
    if not body.source_ids and not body.draft.strip():
        raise HTTPException(422, 'Choose at least one document or provide draft text.')
    with DB_PROVIDER() as con:
        docs = []
        for sid in dict.fromkeys(body.source_ids):
            r = con.execute('SELECT id,filename,content FROM sources WHERE id=?', (sid,)).fetchone()
            if r is None:
                raise HTTPException(422, 'One of the selected documents was not found.')
            docs.append(dict(r))
    extracted = []
    for s in docs:
        extracted.extend(_metrics(s['content'], s['id'], s['filename']))
    if body.draft.strip():
        extracted.extend(_metrics(body.draft, 'draft', 'Current unsaved draft'))
    pairs = []
    seen = set()
    for i, a in enumerate(extracted):
        for b in extracted[i+1:]:
            if (a['source_id'] == b['source_id'] or a['metric'] != b['metric']
                    or a['normalized_unit'] != b['normalized_unit']):
                continue
            low, high = sorted((a['normalized'], b['normalized']))
            if abs(high - low) <= max(0.00001, 0.005 * max(high, 1)):
                continue
            marker = tuple(sorted([a['source_id'] + ':' + a['match'], b['source_id'] + ':' + b['match']]))
            if marker in seen:
                continue
            seen.add(marker)
            pairs.append({'id': str(uuid4()), 'metric': a['metric'], 'left': a,
                          'right': b, 'status': 'potential_conflict',
                          'explanation': 'Different numeric values appear for the same metric and compatible units. Check product version, conditions and effective dates before concluding they conflict.'})
            if len(pairs) >= 20:
                break
        if len(pairs) >= 20:
            break
    return {'comparisons': pairs, 'extracted_claims': len(extracted),
            'documents_compared': len(docs), 'status': 'potential_conflicts_found' if pairs else 'none_detected',
            'notice': 'Narrow deterministic numeric comparison. Does not establish which source is correct, and may miss semantic contradictions or differing conditions.'}


class UnitCaseIn(BaseModel):
    rule_code: str = Field(min_length=2, max_length=32)
    channel: CHANNEL = 'general'
    sample: str = Field(min_length=1, max_length=1200)
    expected_match: bool
    note: str = Field(default='', max_length=250)


@router.get('/unit-cases')
def unit_cases():
    with DB_PROVIDER() as con:
        return [dict(r) for r in con.execute('SELECT * FROM guideline_unit_cases ORDER BY created_at DESC,id DESC')]


@router.post('/unit-cases', status_code=201)
def create_unit_case(body: UnitCaseIn):
    with DB_PROVIDER() as con:
        rule = con.execute('SELECT code FROM rules WHERE code=?', (body.rule_code,)).fetchone()
        if not rule:
            raise HTTPException(404, 'Rule not found.')
        item = {'id': str(uuid4()), 'rule_code': body.rule_code, 'channel': body.channel,
                'sample': body.sample, 'expected_match': int(body.expected_match),
                'note': body.note, 'created_at': _now()}
        con.execute('INSERT INTO guideline_unit_cases VALUES (?,?,?,?,?,?,?)', tuple(item.values()))
    return item


@router.delete('/unit-cases/{case_id}')
def delete_unit_case(case_id: str):
    with DB_PROVIDER() as con:
        deleted = con.execute('DELETE FROM guideline_unit_cases WHERE id=?', (case_id,))
        if not deleted.rowcount:
            raise HTTPException(404, 'Test case not found.')
    return {'ok': True}


@router.post('/unit-cases/run')
def run_unit_cases():
    results = []
    with DB_PROVIDER() as con:
        cases = [dict(r) for r in con.execute('SELECT * FROM guideline_unit_cases ORDER BY created_at,id')]
        rule_by_code = {r['code']: r for r in con.execute('SELECT * FROM rules')}
        for item in cases:
            rule = rule_by_code.get(item['rule_code'])
            if not rule:
                results.append({**item, 'passed': False, 'actual_match': False, 'reason': 'Rule no longer exists'})
                continue
            applicable = _active(con, item['channel'])
            selected = next((r for r in applicable if r['code'] == item['rule_code']), None)
            try:
                actual = bool(re.search(selected['pattern'], item['sample'], flags=re.IGNORECASE)) if selected else False
                reason = 'Rule active and applicable' if selected else 'Rule inactive or excluded for this channel'
                passed = actual == bool(item['expected_match'])
            except re.error:
                actual, passed, reason = False, False, 'Invalid rule regex'
            results.append({**item, 'actual_match': actual, 'passed': passed, 'reason': reason})
    return {'total': len(results), 'passed': sum(int(x['passed']) for x in results),
            'failed': sum(int(not x['passed']) for x in results), 'results': results,
            'notice': 'Unit tests validate configured regex and channel scope, not semantic or legal correctness.'}


class MultiPatchIn(BaseModel):
    content: str = Field(min_length=1, max_length=12000)
    channel: CHANNEL = 'general'


@router.post('/multi-patch')
def multi_patch(body: MultiPatchIn):
    with DB_PROVIDER() as con:
        rules = _active(con, body.channel)
    hits = _hits(body.content, rules)
    by_code = {r['code']: r for r in rules}
    proposed_edits = []
    last_end = -1
    # Disallow overlapping edits and unsafe low-information replacements.
    for finding in hits:
        if finding['start'] < last_end:
            continue
        rule = by_code[finding['rule_code']]
        candidate = str(rule.get('replacement') or '').strip()
        category = rule.get('category')
        is_claim = category in ('claim', 'fact')
        # Factual and claim substitutions may be unsupported or change meaning.
        if is_claim:
            kind, replacement, accepted = 'review_required', candidate, False
        elif candidate and candidate.casefold() != finding['matched_text'].casefold():
            kind, replacement, accepted = 'editable_suggestion', candidate, True
        else:
            kind, replacement, accepted = 'review_required', candidate, False
        proposed_edits.append({'id': str(uuid4()), 'rule_code': finding['rule_code'],
                               'start': finding['start'], 'end': finding['end'],
                               'original': finding['matched_text'], 'replacement': replacement,
                               'kind': kind, 'default_selected': accepted,
                               'reason': ('Manual factual/source review required' if is_claim
                                          else 'Proposed dictionary/policy replacement; verify wording')})
        last_end = finding['end']
        if len(proposed_edits) >= 30:
            break
    selectable = [e for e in proposed_edits if e['default_selected']]
    candidate_text = body.content
    for e in reversed(selectable):
        candidate_text = (candidate_text[:e['start']] + e['replacement'] + candidate_text[e['end']:])
    after = _hits(candidate_text, rules)
    a = Counter(h['rule_code'] for h in hits)
    b = Counter(h['rule_code'] for h in after)
    return {'original': body.content, 'channel': body.channel, 'edits': proposed_edits,
            'proposed': candidate_text, 'before_count': len(hits), 'after_count': len(after),
            'new_or_increased_codes': sorted(k for k in b if b[k] > a[k]),
            'selected_count': len(selectable),
            'notice': 'Multi-edit preview is deterministic and advisory. High-risk fact/claim edits require manual wording and source review. Saving and approval remain separate.'}

def _editorial_warnings(text: str) -> list[dict]:
    """Conservative, explainable red flags for obviously broken copy.

    Not a grammar model or factual verifier. Avoid speculative stylistic checks.
    """
    checks = [
        (r"(?i)\b(?:the|a|an)\s+(?:a|an|the)\s+", "repeated_article",
         "Adjacent articles (e.g. 'The a') suggest a broken replacement."),
        (r"[.!?]\s+[a-z](?=[a-z])", "sentence_case",
         "A sentence appears to start with a lowercase letter."),
        (r"[.!?][A-Za-z]", "missing_sentence_space",
         "Two sentences may be missing a separating space."),
        (r"\b(?:48|72)[- ]hour\s+performance\b", "awkward_duration",
         "'48-hour performance' may be awkward; review the full sentence and applicable conditions."),
    ]
    warnings = []
    for pattern, code, explanation in checks:
        for match in list(re.finditer(pattern, text))[:3]:
            warnings.append({'code': code, 'start': match.start(), 'end': match.end(),
                             'excerpt': text[max(0,match.start()-25):min(len(text),match.end()+35)],
                             'message': explanation})
    return warnings[:12]


class MultiVerifyIn(BaseModel):
    original: str = Field(min_length=1, max_length=12000)
    proposed: str = Field(min_length=1, max_length=12000)
    channel: CHANNEL = 'general'


@router.post('/multi-patch/verify')
def verify_multi_patch(body: MultiVerifyIn):
    """Independently verify the exact, user-edited combined preview."""
    with DB_PROVIDER() as con:
        rules = _active(con, body.channel)
    before = _hits(body.original, rules)
    after = _hits(body.proposed, rules)
    old = Counter(item['rule_code'] for item in before)
    new = Counter(item['rule_code'] for item in after)
    introduced = sorted(code for code in new if new[code] > old[code])
    resolved = sorted(code for code in old if new[code] < old[code])
    improved = len(after) < len(before) and not introduced
    editorial_warnings = _editorial_warnings(body.proposed)
    safe = improved and not editorial_warnings
    return {'before_count': len(before), 'after_count': len(after),
            'editorial_warnings': editorial_warnings,
            'editorial_check': 'narrow_pattern_screen',
            'introduced_codes': introduced, 'resolved_codes': resolved,
            'safe_to_offer': safe,
            'status': ('improved_without_new_rule_failures' if safe else
                       'editorial_review_required' if improved and editorial_warnings else 'needs_review'),
            'notice': ('Some obvious editing defects were flagged. Correct the replacement text and retest. ' if editorial_warnings else '') +
                      'Only configured deterministic rules and limited editorial patterns were checked. Factual correctness, source approval and semantic preservation remain unverified.'}
