import pytest
from fastapi.testclient import TestClient

from app.auth.deps import CurrentUser, get_current_user
from app.main import app


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_manual_japanese(client):
    # Simulate logged in user (team role)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=1, email="test@test.com", role="team", team_id="test_team"
    )

    res = client.get("/api/manual?lang=ja")
    assert res.status_code == 200
    data = res.json()
    assert "content" in data
    assert "Judgie-AI 利用者マニュアル" in data["content"]


def test_get_manual_english(client):
    # Simulate logged in user (admin role)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=1, email="admin@test.com", role="admin")

    res = client.get("/api/manual?lang=en")
    assert res.status_code == 200
    data = res.json()
    assert "content" in data
    assert "Judgie-AI User Manual" in data["content"] or "User Manual" in data["content"]


def test_get_manual_unauthorized(client):
    # Do not mock get_current_user dependency, which should enforce authentication
    res = client.get("/api/manual?lang=ja")
    # Should yield 401 Unauthorized or 403 Forbidden since the default dependency fails when no token is present
    assert res.status_code in [401, 403]
