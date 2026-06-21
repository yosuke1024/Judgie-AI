import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.db import User as DBUser, Hackathon as DBHackathon


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


def test_oidc_callback_success_single_tenant(client, db_session_fixture):
    # Setup single registered user
    h1 = DBHackathon(id=1, name="Hackathon 1")
    db_session_fixture.add(h1)
    db_session_fixture.flush()

    user = DBUser(
        hackathon_id=1,
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
        assert data["hackathon_id"] == 1
        assert "access_token" in res.cookies


def test_oidc_callback_multiple_tenants(client, db_session_fixture):
    # Setup multiple tenants with same email
    h1 = DBHackathon(id=1, name="Hackathon 1")
    h2 = DBHackathon(id=2, name="Hackathon 2")
    db_session_fixture.add_all([h1, h2])
    db_session_fixture.flush()

    user1 = DBUser(
        hackathon_id=1,
        team_id="teamA",
        passcode="hashedpass1",
        role="team",
        email="user@example.com"
    )
    user2 = DBUser(
        hackathon_id=2,
        team_id="teamB",
        passcode="hashedpass2",
        role="observer",
        email="user@example.com"
    )
    db_session_fixture.add_all([user1, user2])
    db_session_fixture.commit()

    with patch("app.routers.auth.OIDC_ENABLED", True), \
         patch("app.auth.oidc_handler.verify_code_and_get_email", return_value="user@example.com"):

        state = "valid-state-123"
        client.cookies.set("oidc_state", state)

        res = client.post("/api/auth/oidc/callback", json={"code": "authcode", "state": state})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "select_tenant"
        assert len(data["tenants"]) == 2
        assert "temp_token" in data
        assert "access_token" not in res.cookies

        # Test selecting a tenant
        temp_token = data["temp_token"]

        # Test selection success
        res_select = client.post(
            "/api/auth/oidc/select-tenant",
            json={"temp_token": temp_token, "hackathon_id": 1, "team_id": "teamA"}
        )
        assert res_select.status_code == 200
        data_select = res_select.json()
        assert data_select["team_id"] == "teamA"
        assert data_select["role"] == "team"
        assert data_select["hackathon_id"] == 1
        assert "access_token" in res_select.cookies

        # Test selection unauthorized (selecting tenant user is not in)
        res_select_bad = client.post(
            "/api/auth/oidc/select-tenant",
            json={"temp_token": temp_token, "hackathon_id": 999, "team_id": "badteam"}
        )
        assert res_select_bad.status_code == 403
