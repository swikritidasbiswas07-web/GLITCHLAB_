"""Security tests for LOCAL-ONLY synthetic one-click demo sessions."""
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import demo_entry
from demo_accounts import provision
from workspace_core import initialize as init_core
from workspace_data import initialize as init_data
from workspace_workflow import initialize as init_workflow


@pytest.fixture
def client(tmp_path, monkeypatch):
    dbpath = tmp_path / 'demo.sqlite'
    def db():
        @contextmanager
        def session():
            con=sqlite3.connect(dbpath)
            con.row_factory=sqlite3.Row
            con.execute('PRAGMA foreign_keys=ON')
            try:
                yield con
                con.commit()
            finally:
                con.close()
        return session()
    with db() as con:
        con.execute('''CREATE TABLE auth_users (
           id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,display_name TEXT NOT NULL,
           salt TEXT NOT NULL,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)''')
        con.execute('''CREATE TABLE auth_sessions (
           token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires_at TEXT NOT NULL,
           created_at TEXT NOT NULL)''')
        init_core(con);init_data(con);init_workflow(con)
        provision(con,password_factory=lambda:'test-secret-only-please-do-not-reuse')
    monkeypatch.setenv('GLITCHLAB_LOCAL_DEMO_LOGIN','true')
    monkeypatch.delenv('GLITCHLAB_DEMO_MODE',raising=False)
    app=FastAPI()
    app.include_router(demo_entry.install(db))
    return TestClient(app, client=('127.0.0.1',50000))


def test_list_four_personas(client):
    data=client.get('/auth/demo/personas').json()
    assert len(data['personas']) == 4
    assert {p['role'] for p in data['personas']} == {'admin','reviewer','editor','creator'}
    assert all('password' not in p for p in data['personas'])


def test_each_card_issues_real_distinct_session(client):
    tokens=[]
    for identity in ('aarohi','kabir','ishani','reyansh'):
        r=client.post('/auth/demo/enter',json={'identity':identity})
        assert r.status_code == 200, r.text
        tokens.append(r.json()['token'])
        assert r.json()['user']['email'].startswith(identity+'.')
    assert len(set(tokens)) == 4


def test_unknown_identity_refused(client):
    assert client.post('/auth/demo/enter',json={'identity':'owner'}).status_code == 422


def test_disabled_by_default(client,monkeypatch):
    monkeypatch.delenv('GLITCHLAB_LOCAL_DEMO_LOGIN',raising=False)
    assert client.get('/auth/demo/personas').status_code == 404
    assert client.post('/auth/demo/enter',json={'identity':'aarohi'}).status_code == 404


def test_public_mode_refuses_demo(client,monkeypatch):
    monkeypatch.setenv('GLITCHLAB_DEMO_MODE','public')
    assert client.get('/auth/demo/personas').status_code == 404
    assert client.post('/auth/demo/enter',json={'identity':'reyansh'}).status_code == 404


def test_remote_peer_refused(client):
    from starlette.requests import Request
    remote=Request({'type':'http','method':'GET','path':'/','headers':[],
                    'client':('203.0.113.25',4321),'server':('127.0.0.1',8000),
                    'scheme':'http','query_string':b''})
    assert not demo_entry.enabled_for(remote)


def test_unprovisioned_identity_refused(client):
    client.app.dependency_overrides.clear()
    # Since independent workspaces are mandatory, wrong workspace names also fail.
    from demo_accounts import DEFAULT_WORKSPACE
    original=demo_entry.DEFAULT_WORKSPACE
    try:
        demo_entry.DEFAULT_WORKSPACE='Another Workspace'
        assert client.post('/auth/demo/enter',json={'identity':'ishani'}).status_code == 409
    finally:
        demo_entry.DEFAULT_WORKSPACE=original
