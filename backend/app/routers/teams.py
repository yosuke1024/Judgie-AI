"""
Teams management router.
"""

import csv

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    SessionLocal,
    User,
    db_session,
    delete_team,
    update_team_passcode,
    update_team_profile,
    update_user_active,
    update_user_role,
)
from app.schemas.schemas import (
    PasscodeChange,
    RoleUpdate,
    TeamActiveUpdate,
    TeamBulkCreate,
    TeamCreate,
    TeamProfileUpdate,
    TeamResponse,
)
from app.security import hash_passcode

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[TeamResponse])
def list_teams(
    user: CurrentUser = Depends(require_role("admin", "observer")),
):
    """List all teams."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.role.in_(["team", "observer"])).order_by(User.team_id).all()
        return [
            TeamResponse(
                team_id=u.team_id,
                role=u.role,
                product_name=u.product_name,
                team_name=u.team_name,
                one_liner=u.one_liner,
                is_active=u.is_active,
            )
            for u in users
        ]
    finally:
        db.close()


@router.post("", response_model=dict)
def create_team(
    req: TeamCreate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Add a single team."""
    with db_session() as db:
        existing = db.query(User).filter(User.team_id == req.team_id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Team ID '{req.team_id}' already exists")

        new_user = User(
            team_id=req.team_id,
            passcode=hash_passcode(req.passcode),
            role=req.role,
            product_name=req.product_name,
            team_name=req.team_name,
            one_liner=req.one_liner,
        )
        db.add(new_user)

    return {"message": f"Team '{req.team_id}' created"}


@router.post("/bulk", response_model=dict)
def bulk_create_teams(
    req: TeamBulkCreate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Bulk import teams from CSV content."""
    import os

    oidc_enabled = os.environ.get("OIDC_ENABLED") == "true"

    lines = req.csv_content.strip().splitlines()
    if not lines:
        return {"created": 0, "skipped": 0}

    reader = csv.reader(lines)
    created = 0
    skipped = 0

    with db_session() as db:
        for i, row in enumerate(reader):
            if not row or not str(row[0]).strip():
                skipped += 1
                continue

            # Skip header row if present
            if i == 0 and any(h in str(row[0]).lower() for h in ["team_id", "user_id", "team-id", "user-id"]):
                continue

            tid = str(row[0]).strip()
            pwd = None
            role_val = "team"
            email_val = None
            product_name = None
            team_name = None
            one_liner = None

            if oidc_enabled:
                if len(row) == 2:
                    email_val = str(row[1]).strip()
                elif len(row) == 3:
                    potential_role = str(row[1]).strip().lower()
                    if potential_role in ["team", "observer"]:
                        role_val = potential_role
                    email_val = str(row[2]).strip()
                elif len(row) >= 4:
                    pwd = str(row[1]).strip()
                    potential_role = str(row[2]).strip().lower()
                    if potential_role in ["team", "observer"]:
                        role_val = potential_role
                    email_val = str(row[3]).strip()
            else:
                if len(row) >= 2:
                    pwd = str(row[1]).strip()
                if len(row) == 3:
                    potential_role = str(row[2]).strip().lower()
                    if potential_role in ["team", "observer"]:
                        role_val = potential_role
                elif len(row) > 3:
                    potential_role = str(row[2]).strip().lower()
                    if potential_role in ["team", "observer"]:
                        role_val = potential_role
                        if len(row) >= 4:
                            team_name = str(row[3]).strip()
                        if len(row) >= 5:
                            product_name = str(row[4]).strip()
                        if len(row) >= 6:
                            one_liner = str(row[5]).strip()
                    else:
                        team_name = str(row[2]).strip()
                        if len(row) >= 4:
                            product_name = str(row[3]).strip()
                        if len(row) >= 5:
                            one_liner = str(row[4]).strip()

            if not pwd:
                import secrets

                pwd = secrets.token_urlsafe(32)

            existing = db.query(User).filter(User.team_id == tid).first()
            if existing:
                skipped += 1
                continue

            db.add(
                User(
                    team_id=tid,
                    passcode=hash_passcode(pwd),
                    role=role_val,
                    email=email_val,
                    product_name=product_name or None,
                    team_name=team_name or None,
                    one_liner=one_liner or None,
                )
            )
            created += 1

    return {"created": created, "skipped": skipped}


@router.put("/{team_id}/profile")
def update_profile(
    team_id: str,
    req: TeamProfileUpdate,
    user: CurrentUser = Depends(require_role("admin", "team")),
):
    """Update a team's profile (product name, team name, one-liner)."""
    # Teams can only update their own profile
    if user.role == "team" and user.team_id != team_id:
        raise HTTPException(status_code=403, detail="Cannot update another team's profile")

    update_team_profile(team_id, req.product_name, req.team_name, req.one_liner)
    return {"message": "Profile updated"}


@router.put("/{team_id}/passcode")
def change_passcode(
    team_id: str,
    req: PasscodeChange,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Reset a team's passcode (Admin only)."""
    success = update_team_passcode(team_id, req.new_passcode)
    if not success:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"message": "Passcode updated"}


@router.put("/{team_id}/role")
def change_role(
    team_id: str,
    req: RoleUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Change a team's role (team <-> observer)."""
    success = update_user_role(team_id, req.new_role)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid role or team not found")
    return {"message": f"Role changed to {req.new_role}"}


@router.put("/{team_id}/active")
def change_active(
    team_id: str,
    req: TeamActiveUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Change a team's active status (Admin only)."""
    success = update_user_active(team_id, req.is_active)
    if not success:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"message": "Team active status updated"}


@router.delete("/{team_id}")
def remove_team(
    team_id: str,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Delete a team and all its data."""
    delete_team(team_id)
    return {"message": f"Team '{team_id}' deleted"}
