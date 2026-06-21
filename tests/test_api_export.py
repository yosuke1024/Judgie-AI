import pytest
import json
from fastapi.testclient import TestClient

from app.auth.deps import CurrentUser, get_current_user
from app.main import app
from app.models.db import Hackathon, User


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_team_markdown_authz_and_tenant_isolation(client, db_session_fixture):
    db = db_session_fixture

    # 1. Setup two different tenants
    h1 = Hackathon(id=1, name="Tenant 1")
    h2 = Hackathon(id=2, name="Tenant 2")
    db.add(h1)
    db.add(h2)
    db.commit()

    # 2. Register teams in both tenants
    t1 = User(
        hackathon_id=1,
        team_id="team_t1",
        passcode="pass1",
        role="team",
    )
    t2 = User(
        hackathon_id=2,
        team_id="team_t2",
        passcode="pass2",
        role="team",
    )
    db.add(t1)
    db.add(t2)
    db.commit()

    # 3. Simulate logged in user from Tenant 1 (Admin)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        team_id="admin1", role="admin", hackathon_id=1
    )

    # Allow access to own tenant's team
    res_own = client.get("/api/export/markdown/team_t1")
    assert res_own.status_code == 200
    assert "report_team_t1.md" in res_own.headers.get("Content-Disposition", "")

    # Deny access to other tenant's team (404 Not Found)
    res_other = client.get("/api/export/markdown/team_t2")
    assert res_other.status_code == 404
    assert res_other.json()["detail"] == "Team not found in this project"


def test_export_template_indented_json(client, db_session_fixture):
    db = db_session_fixture

    # 1. Setup tenant
    h1 = Hackathon(id=1, name="Tenant 1", re_evaluation_context_mode="cumulative")
    db.add(h1)
    db.commit()

    # 2. Simulate logged in user from Tenant 1 (Admin)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        team_id="admin1", role="admin", hackathon_id=1
    )

    # 3. Request template export
    res = client.get("/api/export/template")
    assert res.status_code == 200
    assert res.headers.get("Content-Type") == "application/json"
    assert "judgie-template.json" in res.headers.get("Content-Disposition", "")

    # Read response content as plain text and parse as JSON
    content_str = res.content.decode("utf-8")
    
    # Verify it is pretty-printed (has newlines and indentations)
    assert "\n" in content_str
    assert "  " in content_str

    parsed = json.loads(content_str)
    assert parsed["name"] == "Tenant 1"
    assert parsed["re_evaluation_context_mode"] == "cumulative"
