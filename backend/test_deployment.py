
"""GLITCHLAB_ deployment regression tests.

Run from backend:
    python -m pytest test_deployment.py -v

Tests use temporary SQLite databases and preserve glitchlab.db.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from conftest import login_headers


@pytest.fixture()
def local_client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "GLITCHLAB_DB_PATH",
        str(tmp_path / "test.db")
    )
    monkeypatch.setenv("GLITCHLAB_DEMO_MODE", "local")
    monkeypatch.delenv(
        "GLITCHLAB_ALLOWED_ORIGINS",
        raising=False
    )

    import main
    importlib.reload(main)

    with TestClient(main.app) as client:
        client.headers.update(login_headers(client))
        yield client


def test_local_health(local_client):
    r = local_client.get("/health")

    assert r.status_code == 200
    assert r.json()["mode"] == "local"


def test_local_create_run_and_insights(local_client):
    draft = local_client.post(
        "/drafts",
        json={
            "title": "Deployment smoke test",
            "channel": "social",
            "content": "NovaCell X battery life: 72 hours."
        }
    )

    assert draft.status_code == 201, draft.text

    checked = local_client.post(
        f"/drafts/{draft.json()['id']}/run"
    )

    assert checked.status_code == 200, checked.text
    assert checked.json()["findings"]

    insights = local_client.get("/insights").json()

    assert insights["counts"]["drafts"] == 1


def test_local_invalid_payload(local_client):
    r = local_client.post(
        "/drafts",
        json={
            "title": "",
            "channel": "unknown",
            "content": ""
        }
    )

    assert r.status_code == 422


def test_local_cors(local_client):
    r = local_client.options(
        "/drafts",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST"
        }
    )

    assert (
        r.headers.get("access-control-allow-origin")
        == "http://localhost:5173"
    )


def _public_client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "GLITCHLAB_DB_PATH",
        str(tmp_path / "public.db")
    )
    monkeypatch.setenv("GLITCHLAB_DEMO_MODE", "public")
    monkeypatch.setenv(
        "GLITCHLAB_ALLOWED_ORIGINS",
        "https://demo.example.test"
    )

    import main
    importlib.reload(main)

    return TestClient(main.app)


def test_public_cors_headers_and_write(tmp_path, monkeypatch):
    with _public_client(tmp_path, monkeypatch) as client:
        client.headers.update(login_headers(client))

        result = client.post(
            "/drafts",
            json={
                "title": "Demo",
                "content": "Test",
                "channel": "social"
            },
            headers={
                "Origin": "https://demo.example.test"
            }
        )

        assert result.status_code == 201, result.text

        assert (
            result.headers.get("access-control-allow-origin")
            == "https://demo.example.test"
        )

        assert (
            result.headers.get("x-content-type-options")
            == "nosniff"
        )

        assert (
            result.headers.get("cache-control")
            == "no-store"
        )


def test_public_size_limit(tmp_path, monkeypatch):
    with _public_client(tmp_path, monkeypatch) as client:
        result = client.post(
            "/drafts",
            content=b"x" * 2_300_001,
            headers={
                "Content-Type": "application/json"
            }
        )

        assert result.status_code == 413


def test_public_rate_limit(tmp_path, monkeypatch):
    with _public_client(tmp_path, monkeypatch) as client:
        # The public demo limits requests to 120 per minute.
        outcomes = [
            client.get("/health").status_code
            for _ in range(121)
        ]

    assert 429 in outcomes


def test_public_requires_persistence(tmp_path):
    env = dict(os.environ)

    env["GLITCHLAB_DEMO_MODE"] = "public"
    env["GLITCHLAB_ALLOWED_ORIGINS"] = (
        "https://demo.example.test"
    )

    env.pop("GLITCHLAB_DB_PATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15
    )

    assert result.returncode != 0
    assert "GLITCHLAB_DB_PATH" in result.stderr


def test_public_requires_https_origin(tmp_path):
    env = dict(os.environ)

    env["GLITCHLAB_DEMO_MODE"] = "public"
    env["GLITCHLAB_ALLOWED_ORIGINS"] = (
        "http://localhost:5173"
    )
    env["GLITCHLAB_DB_PATH"] = str(
        tmp_path / "public.db"
    )

    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        env=env,
        capture_output=True,
        text=True,
        timeout=15
    )

    assert result.returncode != 0
    assert "HTTPS" in result.stderr


@pytest.fixture(autouse=True)
def _restore_main_after_deployment_test():
    """Prevent public-mode settings leaking into other tests."""
    yield

    import main

    os.environ["GLITCHLAB_DEMO_MODE"] = "local"
    os.environ.pop("GLITCHLAB_DB_PATH", None)
    os.environ.pop("GLITCHLAB_ALLOWED_ORIGINS", None)

    importlib.reload(main)
