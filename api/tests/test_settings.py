"""API responses do not echo secrets. No Snowflake connection is opened."""

from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_are_booleans_and_hide_secrets(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct-123")
    monkeypatch.setenv("SNOWFLAKE_ROLE", "QUERY_ROLE")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "super-secret-password")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY", "")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_shouldnotappear")
    monkeypatch.setenv("GITHUB_REPO", "octo/warehouse")
    with TestClient(app) as client:
        response = client.get("/api/settings")
        token = client.post("/api/settings/test-token")
    assert response.status_code == 200
    body = response.json()
    text = response.text + token.text
    assert "super-secret-password" not in text
    assert "ghp_shouldnotappear" not in text
    assert body["account"] == "acct-123"
    assert body["role"] == "QUERY_ROLE"
    assert body["repo"] == "octo/warehouse"
    assert body["vars"]["SNOWFLAKE_PASSWORD"] is True
    assert body["vars"]["SNOWFLAKE_ACCOUNT"] is True
    assert token.json()["token_set"] is True
    assert token.json()["ok"] is True
