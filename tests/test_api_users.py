"""
Integration tests for the users management router (/api/users).

This router is the core of role-based access control (admin / team / observer),
so the priority here is (1) that every endpoint is admin-only and (2) that the
"last active administrator" guards cannot be bypassed — a privilege-escalation
or lockout bug in either would otherwise go undetected.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import CurrentUser, get_current_user
from app.main import app
from app.models.db import Team, TeamMembership, User
from app.security import hash_passcode, verify_passcode

# Every endpoint on this router is admin-only. Kept as (method, path, body) so
# the RBAC tests can sweep the whole surface without listing it three times.
ADMIN_ONLY_ENDPOINTS = [
    ("get", "/api/users", None),
    ("post", "/api/users", {"email": "x@test.com", "role": "observer"}),
    ("put", "/api/users/1", {"display_name": "x"}),
    ("put", "/api/users/1/password", {"new_password": "newpass123"}),
    ("delete", "/api/users/1", None),
    ("post", "/api/users/bulk", {"csv_content": "email\nx@test.com"}),
]


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def login_as(role: str, user_id: int = 1, team_id: str | None = None):
    """Override the auth dependency to simulate a logged-in user of the given role."""
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        user_id=user_id, email=f"{role}@test.com", role=role, team_id=team_id
    )


def make_user(db, email: str, role: str = "team", **kwargs) -> User:
    user = User(email=email, role=role, password_hash=hash_passcode("initial123"), **kwargs)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ──────────────────────────────────────────────
# Access control
# ──────────────────────────────────────────────


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY_ENDPOINTS)
@pytest.mark.parametrize("role", ["team", "observer"])
def test_non_admin_roles_are_denied(client, role, method, path, body):
    """A non-admin must never reach a user-management endpoint."""
    login_as(role)

    res = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)

    assert res.status_code == 403, f"{method.upper()} {path} allowed role '{role}'"


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY_ENDPOINTS)
def test_unauthenticated_requests_are_denied(client, method, path, body):
    """No cookie at all must be rejected as 401, not silently treated as a guest."""
    res = getattr(client, method)(path, json=body) if body else getattr(client, method)(path)

    assert res.status_code == 401, f"{method.upper()} {path} allowed anonymous access"


def test_admin_is_allowed(client, db_session_fixture):
    login_as("admin")

    res = client.get("/api/users")

    assert res.status_code == 200


# ──────────────────────────────────────────────
# Listing
# ──────────────────────────────────────────────


def test_list_users_returns_team_and_password_state(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    member = make_user(db, "member@test.com", role="team")
    db.add(TeamMembership(user_id=member.id, team_id="team_a"))
    # SSO-only user: no local password
    sso = User(email="sso@test.com", role="observer", password_hash=None)
    db.add(sso)
    db.commit()

    login_as("admin")
    res = client.get("/api/users")

    assert res.status_code == 200
    by_email = {u["email"]: u for u in res.json()}
    assert by_email["member@test.com"]["team_id"] == "team_a"
    assert by_email["member@test.com"]["has_password"] is True
    assert by_email["sso@test.com"]["team_id"] is None
    assert by_email["sso@test.com"]["has_password"] is False


def test_list_users_never_exposes_password_hash(client, db_session_fixture):
    """The response model must not leak credential material."""
    db = db_session_fixture
    make_user(db, "member@test.com")

    login_as("admin")
    res = client.get("/api/users")

    assert res.status_code == 200
    body = res.text
    assert "password_hash" not in body
    assert "$2b$" not in body  # bcrypt prefix


# ──────────────────────────────────────────────
# Creation
# ──────────────────────────────────────────────


def test_create_user_normalizes_email(client, db_session_fixture):
    db = db_session_fixture
    login_as("admin")

    res = client.post("/api/users", json={"email": "  MixedCase@Test.COM  ", "role": "observer"})

    assert res.status_code == 200
    assert db.query(User).filter(User.email == "mixedcase@test.com").first() is not None


def test_create_user_rejects_duplicate_email(client, db_session_fixture):
    db = db_session_fixture
    make_user(db, "taken@test.com", role="observer")

    login_as("admin")
    res = client.post("/api/users", json={"email": "TAKEN@test.com", "role": "observer"})

    assert res.status_code == 409


def test_create_user_rejects_duplicate_username(client, db_session_fixture):
    db = db_session_fixture
    make_user(db, "first@test.com", role="observer", username="takenname")

    login_as("admin")
    res = client.post("/api/users", json={"email": "second@test.com", "role": "observer", "username": "takenname"})

    assert res.status_code == 409


@pytest.mark.parametrize("username", ["ab", "a" * 31, "has space", "bad!char", "dot.name"])
def test_create_user_rejects_malformed_username(client, db_session_fixture, username):
    login_as("admin")

    res = client.post("/api/users", json={"email": "u@test.com", "role": "observer", "username": username})

    assert res.status_code == 400


def test_create_user_rejects_unknown_role(client, db_session_fixture):
    login_as("admin")

    res = client.post("/api/users", json={"email": "u@test.com", "role": "superadmin"})

    assert res.status_code == 400


def test_create_team_user_requires_team_id(client, db_session_fixture):
    login_as("admin")

    res = client.post("/api/users", json={"email": "u@test.com", "role": "team"})

    assert res.status_code == 400


def test_create_team_user_rejects_unknown_team(client, db_session_fixture):
    login_as("admin")

    res = client.post("/api/users", json={"email": "u@test.com", "role": "team", "team_id": "ghost_team"})

    assert res.status_code == 404


def test_create_user_stores_hashed_password(client, db_session_fixture):
    """Passwords must be hashed at rest, never stored verbatim."""
    db = db_session_fixture
    login_as("admin")

    res = client.post("/api/users", json={"email": "u@test.com", "role": "observer", "password": "plaintext123"})

    assert res.status_code == 200
    created = db.query(User).filter(User.email == "u@test.com").first()
    assert created.password_hash != "plaintext123"
    assert verify_passcode("plaintext123", created.password_hash)


def test_create_user_without_password_is_sso_only(client, db_session_fixture):
    db = db_session_fixture
    login_as("admin")

    res = client.post("/api/users", json={"email": "sso@test.com", "role": "observer"})

    assert res.status_code == 200
    assert db.query(User).filter(User.email == "sso@test.com").first().password_hash is None


# ──────────────────────────────────────────────
# Update — including the last-admin guard
# ──────────────────────────────────────────────


def test_cannot_demote_the_only_active_admin(client, db_session_fixture):
    """Guards against locking every administrator out of the instance."""
    db = db_session_fixture
    admin = make_user(db, "only@test.com", role="admin")

    login_as("admin")
    res = client.put(f"/api/users/{admin.id}", json={"role": "observer"})

    assert res.status_code == 400
    db.refresh(admin)
    assert admin.role == "admin"


def test_cannot_deactivate_the_only_active_admin(client, db_session_fixture):
    db = db_session_fixture
    admin = make_user(db, "only@test.com", role="admin")

    login_as("admin")
    res = client.put(f"/api/users/{admin.id}", json={"is_active": False})

    assert res.status_code == 400
    db.refresh(admin)
    assert admin.is_active is True


def test_inactive_admins_do_not_satisfy_the_last_admin_guard(client, db_session_fixture):
    """A deactivated admin is not a usable fallback, so demotion must still be refused."""
    db = db_session_fixture
    active_admin = make_user(db, "active@test.com", role="admin")
    make_user(db, "disabled@test.com", role="admin", is_active=False)

    login_as("admin")
    res = client.put(f"/api/users/{active_admin.id}", json={"role": "observer"})

    assert res.status_code == 400


def test_can_demote_admin_when_another_active_admin_exists(client, db_session_fixture):
    db = db_session_fixture
    admin_a = make_user(db, "a@test.com", role="admin")
    make_user(db, "b@test.com", role="admin")

    login_as("admin")
    res = client.put(f"/api/users/{admin_a.id}", json={"role": "observer"})

    assert res.status_code == 200
    db.refresh(admin_a)
    assert admin_a.role == "observer"


def test_update_rejects_unknown_role(client, db_session_fixture):
    db = db_session_fixture
    target = make_user(db, "u@test.com", role="observer")

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"role": "superadmin"})

    assert res.status_code == 400


def test_update_rejects_duplicate_username(client, db_session_fixture):
    db = db_session_fixture
    make_user(db, "first@test.com", role="observer", username="taken")
    target = make_user(db, "second@test.com", role="observer")

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"username": "taken"})

    assert res.status_code == 409


def test_update_allows_keeping_own_username(client, db_session_fixture):
    """Uniqueness must exclude the user being edited, or no-op saves would 409."""
    db = db_session_fixture
    target = make_user(db, "u@test.com", role="observer", username="mine")

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"username": "mine", "display_name": "Renamed"})

    assert res.status_code == 200


def test_update_clears_username_with_empty_string(client, db_session_fixture):
    db = db_session_fixture
    target = make_user(db, "u@test.com", role="observer", username="dropme")

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"username": ""})

    assert res.status_code == 200
    db.refresh(target)
    assert target.username is None


def test_update_returns_404_for_unknown_user(client, db_session_fixture):
    login_as("admin")

    res = client.put("/api/users/99999", json={"display_name": "x"})

    assert res.status_code == 404


def test_promoting_team_user_to_observer_drops_membership(client, db_session_fixture):
    """Role changes away from 'team' must not leave a stale team membership behind."""
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    target = make_user(db, "u@test.com", role="team")
    db.add(TeamMembership(user_id=target.id, team_id="team_a"))
    db.commit()

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"role": "observer"})

    assert res.status_code == 200
    assert db.query(TeamMembership).filter(TeamMembership.user_id == target.id).count() == 0


def test_reassigning_team_replaces_membership(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    db.add(Team(team_id="team_b"))
    target = make_user(db, "u@test.com", role="team")
    db.add(TeamMembership(user_id=target.id, team_id="team_a"))
    db.commit()

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"team_id": "team_b"})

    assert res.status_code == 200
    memberships = db.query(TeamMembership).filter(TeamMembership.user_id == target.id).all()
    assert [m.team_id for m in memberships] == ["team_b"]


def test_reassigning_to_unknown_team_is_rejected(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    target = make_user(db, "u@test.com", role="team")
    db.add(TeamMembership(user_id=target.id, team_id="team_a"))
    db.commit()

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"team_id": "ghost_team"})

    assert res.status_code == 404


def test_promoting_observer_to_team_requires_team_id(client, db_session_fixture):
    db = db_session_fixture
    target = make_user(db, "u@test.com", role="observer")

    login_as("admin")
    res = client.put(f"/api/users/{target.id}", json={"role": "team"})

    assert res.status_code == 400


# ──────────────────────────────────────────────
# Password reset
# ──────────────────────────────────────────────


def test_reset_password_replaces_the_hash(client, db_session_fixture):
    db = db_session_fixture
    target = make_user(db, "u@test.com", role="observer")
    original_hash = target.password_hash

    login_as("admin")
    res = client.put(f"/api/users/{target.id}/password", json={"new_password": "brandnew456"})

    assert res.status_code == 200
    db.refresh(target)
    assert target.password_hash != original_hash
    assert verify_passcode("brandnew456", target.password_hash)


def test_reset_password_returns_404_for_unknown_user(client, db_session_fixture):
    login_as("admin")

    res = client.put("/api/users/99999/password", json={"new_password": "brandnew456"})

    assert res.status_code == 404


# ──────────────────────────────────────────────
# Deletion
# ──────────────────────────────────────────────


def test_cannot_delete_the_only_active_admin(client, db_session_fixture):
    db = db_session_fixture
    admin = make_user(db, "only@test.com", role="admin")

    login_as("admin")
    res = client.delete(f"/api/users/{admin.id}")

    assert res.status_code == 400
    assert db.query(User).filter(User.id == admin.id).first() is not None


def test_delete_removes_user_and_membership(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    target = make_user(db, "u@test.com", role="team")
    db.add(TeamMembership(user_id=target.id, team_id="team_a"))
    db.commit()
    target_id = target.id

    login_as("admin")
    res = client.delete(f"/api/users/{target_id}")

    assert res.status_code == 200
    assert db.query(User).filter(User.id == target_id).first() is None
    assert db.query(TeamMembership).filter(TeamMembership.user_id == target_id).count() == 0


def test_delete_returns_404_for_unknown_user(client, db_session_fixture):
    login_as("admin")

    res = client.delete("/api/users/99999")

    assert res.status_code == 404


# ──────────────────────────────────────────────
# Bulk CSV import
# ──────────────────────────────────────────────


def test_bulk_import_creates_users(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    db.commit()

    login_as("admin")
    csv_content = "email,team_id,role,display_name,username\n" "alice@test.com,team_a,team,Alice,alice\n"
    res = client.post("/api/users/bulk", json={"csv_content": csv_content})

    assert res.status_code == 200
    assert res.json() == {"created": 1, "skipped": 0}
    alice = db.query(User).filter(User.email == "alice@test.com").first()
    assert alice.username == "alice"
    assert db.query(TeamMembership).filter(TeamMembership.user_id == alice.id).count() == 1


def test_bulk_import_respects_header_order(client, db_session_fixture):
    """Columns are matched by header name, not position."""
    db = db_session_fixture
    login_as("admin")

    csv_content = "role,display_name,email\nobserver,Bob,bob@test.com\n"
    res = client.post("/api/users/bulk", json={"csv_content": csv_content})

    assert res.status_code == 200
    bob = db.query(User).filter(User.email == "bob@test.com").first()
    assert bob.role == "observer"
    assert bob.display_name == "Bob"


def test_bulk_import_requires_email_header(client, db_session_fixture):
    login_as("admin")

    res = client.post("/api/users/bulk", json={"csv_content": "alice@test.com,team_a\n"})

    assert res.status_code == 400


def test_bulk_import_skips_duplicates_and_bad_usernames(client, db_session_fixture):
    db = db_session_fixture
    make_user(db, "existing@test.com", role="observer")

    login_as("admin")
    csv_content = (
        "email,role,username\n"
        "existing@test.com,observer,\n"  # duplicate email
        "bad@test.com,observer,no spaces\n"  # malformed username
        "good@test.com,observer,gooduser\n"
        ",observer,\n"  # empty email
    )
    res = client.post("/api/users/bulk", json={"csv_content": csv_content})

    assert res.status_code == 200
    assert res.json() == {"created": 1, "skipped": 3}
    assert db.query(User).filter(User.email == "good@test.com").first() is not None


def test_bulk_import_auto_creates_missing_team(client, db_session_fixture):
    """Unlike single creation, bulk import creates unknown teams rather than failing the row."""
    db = db_session_fixture
    login_as("admin")

    csv_content = "email,team_id,role\nnew@test.com,brand_new_team,team\n"
    res = client.post("/api/users/bulk", json={"csv_content": csv_content})

    assert res.status_code == 200
    assert res.json()["created"] == 1
    assert db.query(Team).filter(Team.team_id == "brand_new_team").first() is not None


def test_bulk_import_falls_back_to_team_role_for_unknown_role(client, db_session_fixture):
    db = db_session_fixture
    db.add(Team(team_id="team_a"))
    db.commit()

    login_as("admin")
    csv_content = "email,team_id,role\nu@test.com,team_a,superadmin\n"
    res = client.post("/api/users/bulk", json={"csv_content": csv_content})

    assert res.status_code == 200
    assert db.query(User).filter(User.email == "u@test.com").first().role == "team"


def test_bulk_import_assigns_random_password_when_omitted(client, db_session_fixture):
    """Users imported without a password must not end up with an empty or null credential."""
    db = db_session_fixture
    login_as("admin")

    res = client.post("/api/users/bulk", json={"csv_content": "email,role\nu@test.com,observer\n"})

    assert res.status_code == 200
    created = db.query(User).filter(User.email == "u@test.com").first()
    assert created.password_hash
    assert not verify_passcode("", created.password_hash)


def test_bulk_import_of_empty_content_is_a_noop(client, db_session_fixture):
    login_as("admin")

    res = client.post("/api/users/bulk", json={"csv_content": "   \n"})

    assert res.status_code == 200
    assert res.json() == {"created": 0, "skipped": 0}
