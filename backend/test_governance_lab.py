"""Isolated automated tests: do not touch the user's existing glitchlab.db."""
import json
import sqlite3
import tempfile
from pathlib import Path
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import governance_lab as gov

@pytest.fixture
def client(tmp_path, monkeypatch):
    path=tmp_path/'test_only.db'
    @contextmanager
    def db():
        con=sqlite3.connect(path)
        con.row_factory=sqlite3.Row
        try:
            yield con
            con.commit()
        finally:
            con.close()
    with db() as c:
        c.execute('CREATE TABLE sources (id TEXT, filename TEXT, content TEXT)')
        c.execute('CREATE TABLE rules (code TEXT, pattern TEXT, category TEXT, replacement TEXT, active INTEGER, channels TEXT)')
        c.executemany('INSERT INTO rules VALUES (?,?,?,?,?,?)',[
            ('BR-101',r'72[- ]hour','fact','up to 48 hours',1,'["all"]'),
            ('BR-104',r'Nova Cell X','terminology','NovaCell X',1,'["all"]'),
            ('BR-105',r'revolutionary','tone','new',1,'["social"]'),
        ])
        c.executemany('INSERT INTO sources VALUES (?,?,?)',[
            ('a','spec-1.txt','NovaCell X battery life: 48 hours under specified conditions.'),
            ('b','spec-2.txt','NovaCell X battery life: 72 hours under specified conditions.'),
        ])
    def applicable(con,channel):
        return [dict(r) for r in con.execute('SELECT * FROM rules WHERE active=1') if 'all' in json.loads(r['channels']) or channel in json.loads(r['channels'])]
    app=FastAPI();app.include_router(gov.install(db,applicable))
    with TestClient(app) as tc:
        yield tc

def test_contradiction_between_sources(client):
    r=client.post('/governance/contradictions',json={'source_ids':['a','b'],'draft':''})
    assert r.status_code==200
    values=r.json()['comparisons']
    assert len(values)==1
    assert values[0]['metric']=='battery life'
    assert {values[0]['left']['value'],values[0]['right']['value']}=={48,72}

def test_invalid_source_rejected(client):
    assert client.post('/governance/contradictions',json={'source_ids':['fake']}).status_code==422

def test_unit_cases_and_channel_isolation(client):
    cases=[('BR-105','social','revolutionary',True),('BR-105','email','revolutionary',False),('BR-104','email','Nova Cell X',True),('BR-101','email','up to 48 hours',False)]
    for code,channel,sample,expected in cases:
        r=client.post('/governance/unit-cases',json={'rule_code':code,'channel':channel,'sample':sample,'expected_match':expected})
        assert r.status_code==201
    result=client.post('/governance/unit-cases/run').json()
    assert result['total']==4 and result['passed']==4 and result['failed']==0

def test_unit_failure_visible(client):
    client.post('/governance/unit-cases',json={'rule_code':'BR-104','channel':'social','sample':'Nova Cell X','expected_match':False})
    res=client.post('/governance/unit-cases/run').json()
    assert res['failed']==1

def test_case_delete(client):
    case=client.post('/governance/unit-cases',json={'rule_code':'BR-104','sample':'Nova Cell X','expected_match':True}).json()
    assert client.delete('/governance/unit-cases/'+case['id']).json()=={'ok':True}
    assert client.get('/governance/unit-cases').json()==[]

def test_multi_patch_tone_and_terminology_only(client):
    r=client.post('/governance/multi-patch',json={'channel':'social','content':'The revolutionary Nova Cell X delivers 72-hour battery.'})
    assert r.status_code==200
    data=r.json()
    assert data['before_count']==3 and data['after_count']==1
    assert 'new NovaCell X' in data['proposed']
    assert '72-hour' in data['proposed']
    assert len([e for e in data['edits'] if e['kind']=='review_required'])==1

def test_multi_patch_channel_only_applicable_rules(client):
    data=client.post('/governance/multi-patch',json={'channel':'email','content':'revolutionary Nova Cell X'}).json()
    assert data['before_count']==1
    assert 'revolutionary NovaCell X'==data['proposed']


def test_verify_combined_edits(client):
    result=client.post('/governance/multi-patch/verify',json={'channel':'social','original':'revolutionary Nova Cell X','proposed':'new NovaCell X'}).json()
    assert result['safe_to_offer'] and result['before_count']==2 and result['after_count']==0

def test_verify_rejects_new_violation(client):
    result=client.post('/governance/multi-patch/verify',json={'channel':'social','original':'Nova Cell X','proposed':'revolutionary NovaCell X'}).json()
    assert not result['safe_to_offer'] and 'BR-105' in result['introduced_codes']


def test_editorial_gate_rejects_repeated_article(client):
    result=client.post('/governance/multi-patch/verify',json={
        'channel':'social', 'original':'The best Nova Cell X',
        'proposed':'The a powerful choice NovaCell X'}).json()
    assert result['after_count']==0
    assert result['safe_to_offer'] is False
    assert result['status']=='editorial_review_required'
    assert any(x['code']=='repeated_article' for x in result['editorial_warnings'])


def test_editorial_gate_rejects_lowercase_sentence_start(client):
    result=client.post('/governance/multi-patch/verify',json={
        'channel':'social', 'original':'revolutionary Nova Cell X',
        'proposed':'New NovaCell X! designed for comfort.'}).json()
    assert not result['safe_to_offer']
    assert any(x['code']=='sentence_case' for x in result['editorial_warnings'])


def test_editorial_gate_accepts_clean_edit(client):
    result=client.post('/governance/multi-patch/verify',json={
        'channel':'social', 'original':'revolutionary Nova Cell X',
        'proposed':'Introducing the new NovaCell X.'}).json()
    assert result['safe_to_offer']
    assert result['editorial_warnings']==[]


def test_editorial_gate_flags_awkward_duration(client):
    result=client.post('/governance/multi-patch/verify',json={
        'channel':'social', 'original':'72-hour performance.',
        'proposed':'Designed for up to 48-hour performance.'}).json()
    assert not result['safe_to_offer']
    assert any(x['code']=='awkward_duration' for x in result['editorial_warnings'])


def test_input_limits_and_no_persistence(client):
    oversized='A'*12001
    result=client.post('/governance/multi-patch/verify',json={
        'channel':'social','original':'Nova Cell X','proposed':oversized})
    assert result.status_code==422
    assert client.get('/governance/unit-cases').json()==[]
