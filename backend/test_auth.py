"""Authentication smoke and regression tests using an isolated SQLite database."""
from pathlib import Path
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
import auth
import main


def test_login_protects_workspace_and_logout_revokes():
    with tempfile.TemporaryDirectory() as folder:
        with patch.object(main, 'DB', Path(folder) / 'auth-test.db'):
            main.initialize()
            auth.install(main.db)
            main.install_governance_lab(main.db, main.applicable_rules)
            with TestClient(main.app) as client:
                assert client.get('/health').status_code == 200
                assert client.get('/drafts').status_code == 401
                assert client.post('/rules', json={}).status_code == 401
                account = {'email':'Demo@Example.COM', 'display_name':'Demo Tester', 'password':'correct-horse-cloud-2026'}
                r = client.post('/auth/register', json=account)
                assert r.status_code == 201, r.text
                token = r.json()['token']
                assert r.json()['user']['email'] == 'demo@example.com'
                headers = {'Authorization':f'Bearer {token}'}
                assert client.get('/drafts', headers=headers).status_code == 200
                assert client.post('/governance/unit-cases/run', headers=headers).status_code == 200
                assert client.get('/auth/me', headers=headers).status_code == 200
                assert client.post('/auth/login', json={'email':account['email'],'password':'wrong'}).status_code == 401
                assert client.post('/auth/register', json=account).status_code == 409
                assert client.post('/auth/logout', headers=headers).status_code == 200
                assert client.get('/drafts', headers=headers).status_code == 401
                second = client.post('/auth/login', json={'email':account['email'],'password':account['password']})
                assert second.status_code == 200
                assert second.json()['token'] != token


def test_short_password_rejected_and_health_public():
    with TestClient(main.app) as client:
        r = client.post('/auth/register', json={'email':'test@example.com','display_name':'OK','password':'123'})
        assert r.status_code == 422
        assert client.get('/health').status_code == 200


def test_signup_switch_can_disable_public_registration():
    from unittest.mock import patch as mock_patch
    with mock_patch.dict('os.environ', {'GLITCHLAB_ALLOW_SIGNUP': 'false'}):
        with TestClient(main.app) as client:
            r = client.post('/auth/register', json={'email':'blocked@example.com','display_name':'Blocked User','password':'very-long-test-password'})
            assert r.status_code == 403


def test_cors_preflight_authorization_header_allowed():
    with TestClient(main.app) as client:
        r = client.options('/drafts', headers={'Origin':'http://localhost:5173', 'Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'})
        assert r.status_code == 200, r.text
        assert 'authorization' in r.headers.get('access-control-allow-headers', '').lower()
