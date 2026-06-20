import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth.deps import get_current_user, CurrentUser
from app.models.db import Hackathon as DBHackathon

@pytest.fixture
def client():
    # Ensure app imports cleanly and reset overrides after each test
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_initialize_template_authz(client, db_session_fixture):
    # Setup test tenants
    h1 = DBHackathon(id=1, name="Tenant 1")
    h2 = DBHackathon(id=2, name="Tenant 2")
    db_session_fixture.add(h1)
    db_session_fixture.add(h2)
    db_session_fixture.commit()

    # 1. Superadmin role should be allowed to initialize any tenant
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        team_id="superadmin", role="superadmin", hackathon_id=None
    )

    res_super1 = client.post("/api/hackathons/1/initialize", json={"template_id": "hackathon"})
    assert res_super1.status_code == 200

    res_super2 = client.post("/api/hackathons/2/initialize", json={"template_id": "hackathon"})
    assert res_super2.status_code == 200

    # 2. Admin role for tenant 1 should be allowed to initialize tenant 1
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        team_id="admin1", role="admin", hackathon_id=1
    )

    res_admin_own = client.post("/api/hackathons/1/initialize", json={"template_id": "hackathon"})
    assert res_admin_own.status_code == 200

    # 3. Admin role for tenant 1 trying to initialize tenant 2 should be rejected (403 Forbidden)
    res_admin_other = client.post("/api/hackathons/2/initialize", json={"template_id": "hackathon"})
    assert res_admin_other.status_code == 403
    assert res_admin_other.json()["detail"] == "Not authorized to initialize this project template"
