"""
Teams management router — team profile CRUD only.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    SessionLocal,
    Team,
    TeamMembership,
    User,
    db_session,
    delete_team,
    update_team_active,
    update_team_profile,
)
from app.schemas.schemas import (
    TeamActiveUpdate,
    TeamCreate,
    TeamProfileUpdate,
    TeamResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[TeamResponse])
def list_teams(
    user: CurrentUser = Depends(require_role("admin", "observer")),
):
    """List all teams with their associated members."""
    db = SessionLocal()
    try:
        teams = db.query(Team).order_by(Team.team_id).all()
        result = []
        for t in teams:
            members = []
            for m in t.memberships:
                u = db.query(User).filter(User.id == m.user_id).first()
                if u:
                    members.append(
                        UserResponse(
                            user_id=u.id,
                            email=u.email,
                            display_name=u.display_name,
                            role=u.role,
                            team_id=t.team_id,
                            is_active=u.is_active,
                            has_password=u.password_hash is not None,
                        )
                    )
            result.append(
                TeamResponse(
                    team_id=t.team_id,
                    product_name=t.product_name,
                    team_name=t.team_name,
                    one_liner=t.one_liner,
                    is_active=t.is_active,
                    members=members,
                )
            )
        return result
    finally:
        db.close()


@router.post("", response_model=dict)
def create_team(
    req: TeamCreate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Create a new team (profile only, no auth info)."""
    with db_session() as db:
        existing = db.query(Team).filter(Team.team_id == req.team_id).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Team ID '{req.team_id}' already exists")

        new_team = Team(
            team_id=req.team_id,
            product_name=req.product_name,
            team_name=req.team_name,
            one_liner=req.one_liner,
        )
        db.add(new_team)

    return {"message": f"Team '{req.team_id}' created"}


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


@router.put("/{team_id}/active")
def change_active(
    team_id: str,
    req: TeamActiveUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Change a team's active status (Admin only)."""
    success = update_team_active(team_id, req.is_active)
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
