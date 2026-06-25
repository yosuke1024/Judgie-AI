"""
Users management router — individual user CRUD.
"""

import csv

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    SessionLocal,
    Team,
    TeamMembership,
    User,
    db_session,
)
from app.schemas.schemas import (
    PasswordReset,
    UserBulkCreate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.security import hash_passcode

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    user: CurrentUser = Depends(require_role("admin")),
):
    """List all users (excluding admin users)."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.role != "admin").order_by(User.email).all()
        result = []
        for u in users:
            membership = db.query(TeamMembership).filter(TeamMembership.user_id == u.id).first()
            result.append(
                UserResponse(
                    user_id=u.id,
                    email=u.email,
                    display_name=u.display_name,
                    role=u.role,
                    team_id=membership.team_id if membership else None,
                    is_active=u.is_active,
                    has_password=u.password_hash is not None,
                )
            )
        return result
    finally:
        db.close()


@router.post("", response_model=dict)
def create_user(
    req: UserCreate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Create a new user account."""
    with db_session() as db:
        existing = db.query(User).filter(User.email == req.email.strip().lower()).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Email '{req.email}' already exists")

        if req.role not in ("team", "observer"):
            raise HTTPException(status_code=400, detail="Role must be 'team' or 'observer'")

        # If role is team, team_id is required
        if req.role == "team" and not req.team_id:
            raise HTTPException(status_code=400, detail="team_id is required for team role users")

        # Validate team exists
        if req.team_id:
            team = db.query(Team).filter(Team.team_id == req.team_id).first()
            if not team:
                raise HTTPException(status_code=404, detail=f"Team '{req.team_id}' not found")

        password_hash = hash_passcode(req.password) if req.password else None

        new_user = User(
            email=req.email.strip().lower(),
            password_hash=password_hash,
            display_name=req.display_name,
            role=req.role,
        )
        db.add(new_user)
        db.flush()

        # Create team membership if team role
        if req.team_id:
            db.add(TeamMembership(user_id=new_user.id, team_id=req.team_id))

    return {"message": f"User '{req.email}' created"}


@router.put("/{user_id}", response_model=dict)
def update_user(
    user_id: int,
    req: UserUpdate,
    admin: CurrentUser = Depends(require_role("admin")),
):
    """Update a user's details."""
    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "admin":
            raise HTTPException(status_code=403, detail="Cannot modify admin user via this endpoint")

        if req.display_name is not None:
            user.display_name = req.display_name
        if req.role is not None:
            if req.role not in ("team", "observer"):
                raise HTTPException(status_code=400, detail="Role must be 'team' or 'observer'")
            user.role = req.role
        if req.is_active is not None:
            user.is_active = req.is_active

        # Handle team reassignment
        if req.team_id is not None:
            # Remove existing membership
            db.query(TeamMembership).filter(TeamMembership.user_id == user_id).delete()
            if req.team_id:  # Empty string means remove from team
                team = db.query(Team).filter(Team.team_id == req.team_id).first()
                if not team:
                    raise HTTPException(status_code=404, detail=f"Team '{req.team_id}' not found")
                db.add(TeamMembership(user_id=user_id, team_id=req.team_id))

    return {"message": "User updated"}


@router.put("/{user_id}/password", response_model=dict)
def reset_password(
    user_id: int,
    req: PasswordReset,
    admin: CurrentUser = Depends(require_role("admin")),
):
    """Reset a user's password (admin only)."""
    from app.models.db import update_user_password

    success = update_user_password(user_id, req.new_password)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Password reset successfully"}


@router.delete("/{user_id}", response_model=dict)
def delete_user(
    user_id: int,
    admin: CurrentUser = Depends(require_role("admin")),
):
    """Delete a user account."""
    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.role == "admin":
            raise HTTPException(status_code=403, detail="Cannot delete admin user")

        db.query(TeamMembership).filter(TeamMembership.user_id == user_id).delete()
        db.delete(user)

    return {"message": "User deleted"}


@router.post("/bulk", response_model=dict)
def bulk_create_users(
    req: UserBulkCreate,
    admin: CurrentUser = Depends(require_role("admin")),
):
    """Bulk import users from CSV.

    CSV format: email,team_id,role[,display_name][,password]
    """
    import secrets as _secrets

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

            # Skip header row
            if i == 0 and any(h in str(row[0]).lower() for h in ["email", "user", "mail"]):
                continue

            email = str(row[0]).strip().lower()
            team_id = str(row[1]).strip() if len(row) >= 2 else None
            role_val = str(row[2]).strip().lower() if len(row) >= 3 else "team"
            display_name = str(row[3]).strip() if len(row) >= 4 else None
            password = str(row[4]).strip() if len(row) >= 5 else None

            if role_val not in ("team", "observer"):
                role_val = "team"

            # Check if user already exists
            existing = db.query(User).filter(User.email == email).first()
            if existing:
                skipped += 1
                continue

            # Validate team exists (if team_id provided)
            if team_id:
                team = db.query(Team).filter(Team.team_id == team_id).first()
                if not team:
                    # Auto-create team
                    db.add(Team(team_id=team_id))
                    db.flush()

            password_hash = hash_passcode(password) if password else hash_passcode(_secrets.token_urlsafe(16))

            new_user = User(
                email=email,
                password_hash=password_hash,
                display_name=display_name,
                role=role_val,
            )
            db.add(new_user)
            db.flush()

            if team_id and role_val == "team":
                db.add(TeamMembership(user_id=new_user.id, team_id=team_id))

            created += 1

    return {"created": created, "skipped": skipped}
