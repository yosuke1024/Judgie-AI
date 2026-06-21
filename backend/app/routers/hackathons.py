"""
Hackathon (Project/Tenant) management router.
"""

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    Hackathon,
    SessionLocal,
    User,
    create_hackathon,
    delete_hackathon,
    initialize_hackathon_template,
    update_admin_passcode,
)
from app.schemas.schemas import HackathonCreate, HackathonInitialize, HackathonResponse
from app.services.templates import TEMPLATES
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func

router = APIRouter(prefix="/api/hackathons", tags=["hackathons"])


@router.get("", response_model=list[HackathonResponse])
def list_hackathons():
    """List all hackathons (public, used for login page tenant selection)."""
    db = SessionLocal()
    try:
        results = (
            db.query(
                Hackathon.id,
                Hackathon.name,
                Hackathon.template_id,
                Hackathon.created_at,
                User.team_id.label("admin_id"),
            )
            .outerjoin(User, (Hackathon.id == User.hackathon_id) & (User.role == "admin"))
            .order_by(Hackathon.id.desc())
            .all()
        )

        counts = (
            db.query(User.hackathon_id, func.count(User.id).label("team_count"))
            .filter(User.role == "team")
            .group_by(User.hackathon_id)
            .all()
        )
        team_counts = {c.hackathon_id: c.team_count for c in counts}

        return [
            HackathonResponse(
                id=r.id,
                name=r.name,
                template_id=r.template_id,
                admin_id=r.admin_id,
                team_count=team_counts.get(r.id, 0),
                created_at=str(r.created_at) if r.created_at else None,
            )
            for r in results
        ]
    finally:
        db.close()


@router.post("", response_model=dict)
def create_hackathon_endpoint(
    req: HackathonCreate,
    user: CurrentUser = Depends(require_role("superadmin")),
):
    """Create a new hackathon project (SuperAdmin only)."""
    try:
        new_id = create_hackathon(
            req.name, req.admin_id, req.admin_pass,
            template_id=req.template_id,
        )
        return {"id": new_id, "message": f"Created project '{req.name}'"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{hackathon_id}")
def delete_hackathon_endpoint(
    hackathon_id: int,
    user: CurrentUser = Depends(require_role("superadmin")),
):
    """Delete a hackathon and all associated data (SuperAdmin only)."""
    try:
        delete_hackathon(hackathon_id)
        return {"message": f"Deleted hackathon {hackathon_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{hackathon_id}/initialize")
def initialize_template(
    hackathon_id: int,
    req: HackathonInitialize,
    user: CurrentUser = Depends(require_role("admin", "superadmin")),
):
    """Initialize a hackathon with a template."""
    if user.role == "admin" and user.hackathon_id != hackathon_id:
        raise HTTPException(status_code=403, detail="Not authorized to initialize this project template")
    try:
        initialize_hackathon_template(
            hackathon_id, req.template_id, req.custom_template_data,
        )
        return {"message": "Template initialized"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/templates", response_model=dict)
def list_templates():
    """List available project templates."""
    result = {}
    for tid, tpl in TEMPLATES.items():
        result[tid] = {
            "name": tpl.get("name", tid),
            "description": tpl.get("description", ""),
        }
    return result


@router.put("/{hackathon_id}/admin-passcode")
def reset_admin_passcode(
    hackathon_id: int,
    req: dict,
    user: CurrentUser = Depends(require_role("superadmin")),
):
    """Reset the admin password for a tenant (SuperAdmin only)."""
    new_pass = req.get("new_passcode")
    if not new_pass:
        raise HTTPException(status_code=400, detail="new_passcode is required")
    update_admin_passcode(hackathon_id, new_pass)
    return {"message": "Admin passcode reset"}
