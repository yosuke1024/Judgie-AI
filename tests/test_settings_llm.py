from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.deps import CurrentUser, get_current_user


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def admin_auth():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=1, email="admin@test.com", role="admin")
    yield
    app.dependency_overrides.clear()


def test_get_llm_config_unauthorized(client):
    res = client.get("/api/settings/llm")
    assert res.status_code == 401


def test_get_llm_config_forbidden_for_team(client):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(user_id=2, email="user@test.com", role="team", team_id="teamA")
    try:
        res = client.get("/api/settings/llm")
        assert res.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_get_llm_config_admin(client, admin_auth):
    res = client.get("/api/settings/llm")
    assert res.status_code == 200
    data = res.json()
    assert "llm_provider" in data
    assert "gemini_model" in data
    assert "openai_model" in data
    assert "anthropic_model" in data
    assert "has_gemini_api_key" in data


def test_update_llm_config_provider(client, admin_auth):
    # Test switching provider
    res = client.put("/api/settings/llm", json={"llm_provider": "openai"})
    assert res.status_code == 200

    res = client.get("/api/settings/llm")
    assert res.json()["llm_provider"] == "openai"

    # Restore default
    client.put("/api/settings/llm", json={"llm_provider": "gemini"})


def test_update_llm_config_unsupported_provider(client, admin_auth):
    res = client.put("/api/settings/llm", json={"llm_provider": "invalid-provider"})
    assert res.status_code == 400


def test_update_llm_config_model(client, admin_auth):
    # Test updating model
    res = client.put("/api/settings/llm", json={"llm_provider": "gemini", "model": "gemini-3.1-pro"})
    assert res.status_code == 200

    res = client.get("/api/settings/llm")
    assert res.json()["gemini_model"] == "gemini-3.1-pro"


def test_update_llm_config_api_key_invalid(client, admin_auth):
    # Test setting API key (which fails verification)
    with patch("app.services.gemini.list_available_llm_models", side_effect=ValueError("Invalid key format")):
        res = client.put("/api/settings/llm", json={"llm_provider": "anthropic", "api_key": "bad-key"})
        assert res.status_code == 400
        assert "API key verification failed" in res.json()["detail"]


def test_update_llm_config_api_key_success(client, admin_auth):
    # Test setting API key success
    with patch("app.services.gemini.list_available_llm_models", return_value=["claude-3-5-sonnet-20241022"]):
        res = client.put("/api/settings/llm", json={"llm_provider": "anthropic", "api_key": "sk-ant-12345"})
        assert res.status_code == 200

        res = client.get("/api/settings/llm")
        assert res.json()["has_anthropic_api_key"] is True
