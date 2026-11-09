"""Isolated authenticated HTTP client for legacy endpoint tests.

No bypass of AuthGuard; each test registers through the real API.
"""
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def login_headers(client: TestClient) -> dict[str, str]:
    email = f"qa-{uuid4().hex}@example.com"
    response = client.post('/auth/register', json={
        'email': email,
        'display_name': 'Regression Tester',
        'password': 'local-only-qa-password-2026',
    })
    assert response.status_code == 201, response.text
    return {'Authorization': f"Bearer {response.json()['token']}"}


@pytest.fixture
def authenticated_client(tmp_path, monkeypatch):
    import main
    import auth
    monkeypatch.setattr(main, 'DB', Path(tmp_path) / 'isolated-test.db')
    main.initialize()
    auth.install(main.db)
    with TestClient(main.app) as client:
        client.headers.update(login_headers(client))
        yield client
