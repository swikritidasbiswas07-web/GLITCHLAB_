"""Core API regression tests using real bearer authentication and scratch SQLite."""

def test_core_workflow(authenticated_client):
    client = authenticated_client
    a = client.post('/drafts', json={
        'title': 'Test launch', 'channel': 'social',
        'content': 'Guaranteed 72 hours. The best in India!',
    })
    assert a.status_code == 201, a.text
    did = a.json()['id']
    run = client.post(f'/drafts/{did}/run')
    assert run.status_code == 200, run.text
    assert len(run.json()['findings']) >= 3
    blocked = client.post(f'/drafts/{did}/reviews', json={
        'decision': 'approved', 'reviewer': 'Test', 'comment': '',
    })
    assert blocked.status_code == 409
    r = client.post(f'/drafts/{did}/revisions', json={
        'content': 'NovaCell X delivers up to 48 hours of performance.',
    })
    assert r.status_code == 201, r.text
    clean = client.post(f'/drafts/{did}/run')
    assert clean.status_code == 200, clean.text
    assert len(clean.json()['findings']) == 0
    approved = client.post(f'/drafts/{did}/reviews', json={
        'decision': 'approved', 'reviewer': 'Demo Reviewer',
        'comment': 'Reviewed approved specs.',
    })
    assert approved.status_code == 201, approved.text
    history = client.get(f'/drafts/{did}').json()
    assert len(history['versions']) == 2 and len(history['reviews']) == 1


def test_invalid_regex(authenticated_client):
    response = authenticated_client.post('/rules', json={
        'code': 'BAD-REGEX', 'category': 'tone', 'title': 'Invalid rule',
        'explanation': 'Bad expression must be rejected',
        'source': 'synthetic test source', 'pattern': '[', 'replacement': '',
    })
    assert response.status_code == 422, response.text
