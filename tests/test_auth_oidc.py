from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import User as DBUser


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_oidc_login_disabled(client):
    with patch("app.routers.auth.OIDC_ENABLED", False):
        res = client.get("/api/auth/oidc/login")
        assert res.status_code == 400
        assert "OIDC authentication is not enabled" in res.json()["detail"]


def test_oidc_login_enabled(client):
    with patch("app.routers.auth.OIDC_ENABLED", True), \
         patch("app.auth.oidc_handler.get_authorization_url", return_value="https://auth.example.com/oauth2"):
        res = client.get("/api/auth/oidc/login")
        assert res.status_code == 200
        data = res.json()
        assert data["auth_url"] == "https://auth.example.com/oauth2"
        assert "state" in data
        assert "oidc_state" in res.cookies


def test_oidc_callback_csrf_fail(client):
    with patch("app.routers.auth.OIDC_ENABLED", True):
        res = client.post("/api/auth/oidc/callback", json={"code": "authcode", "state": "badstate"})
        assert res.status_code == 400
        assert "CSRF verification failed" in res.json()["detail"]


def test_oidc_callback_success(client, db_session_fixture):
    # Setup registered user
    user = DBUser(
        team_id="teamA",
        passcode="hashedpasscode",
        role="team",
        email="user@example.com"
    )
    db_session_fixture.add(user)
    db_session_fixture.commit()

    # Initiate state
    with patch("app.routers.auth.OIDC_ENABLED", True), \
         patch("app.auth.oidc_handler.verify_code_and_get_email", return_value="user@example.com"):

        state = "valid-state-123"
        client.cookies.set("oidc_state", state)

        res = client.post("/api/auth/oidc/callback", json={"code": "authcode", "state": state})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["team_id"] == "teamA"
        assert data["role"] == "team"
        assert "access_token" in res.cookies


def test_get_auth_config(client):
    with patch("app.routers.auth.OIDC_ENABLED", True):
        res = client.get("/api/auth/config")
        assert res.status_code == 200
        assert res.json()["oidc_enabled"] is True

    with patch("app.routers.auth.OIDC_ENABLED", False):
        res = client.get("/api/auth/config")
        assert res.status_code == 200
        assert res.json()["oidc_enabled"] is False


def test_oidc_callback_unregistered(client):
    with patch("app.routers.auth.OIDC_ENABLED", True), \
         patch("app.auth.oidc_handler.verify_code_and_get_email", return_value="unregistered@example.com"):

        state = "valid-state-123"
        client.cookies.set("oidc_state", state)

        res = client.post("/api/auth/oidc/callback", json={"code": "authcode", "state": state})
        assert res.status_code == 403
        assert "not registered" in res.json()["detail"].lower()


def test_oidc_callback_domain_restricted(client):
    with patch("app.routers.auth.OIDC_ENABLED", True), \
         patch("app.auth.oidc_handler.verify_code_and_get_email", side_effect=ValueError("Email hacker@evil.com is not allowed to access this system")):

        state = "valid-state-123"
        client.cookies.set("oidc_state", state)

        res = client.post("/api/auth/oidc/callback", json={"code": "authcode", "state": state})
        assert res.status_code == 403
        assert "not allowed" in res.json()["detail"].lower()
