"""
Export router: Markdown reports, template export/import.
"""

from urllib.parse import urlparse, urlunparse

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    Hackathon,
    SessionLocal,
    User,
    get_criteria,
    get_max_consultations,
    get_max_qa_turns,
    get_personas,
    get_re_evaluation_context_mode,
    set_criteria,
    set_max_consultations,
    set_max_qa_turns,
    set_personas,
    set_re_evaluation_context_mode,
)
from app.schemas.schemas import TemplateImport
from app.security import is_safe_url
from app.services.templates import TEMPLATES

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/markdown/{team_id}")
def get_team_markdown(
    team_id: str,
    user: CurrentUser = Depends(require_role("admin", "observer")),
):
    """Generate a Markdown evaluation report for a team."""
    from app.services.export_service import generate_team_markdown_report

    db = SessionLocal()
    try:
        team_user = (
            db.query(User)
            .filter(User.hackathon_id == user.hackathon_id, User.team_id == team_id)
            .first()
        )
        if not team_user:
            raise HTTPException(status_code=404, detail="Team not found in this project")
    finally:
        db.close()

    md = generate_team_markdown_report(user.hackathon_id, team_id)
    return Response(
        content=md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=report_{team_id}.md"},
    )


@router.get("/markdown-zip/all")
def get_all_markdown_zip(user: CurrentUser = Depends(require_role("admin"))):
    """Generate Markdown reports for all teams as a ZIP."""
    from app.services.export_service import generate_all_teams_markdown_zip

    zip_bytes = generate_all_teams_markdown_zip(user.hackathon_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=judgie-reports-{user.hackathon_id}.zip"},
    )


@router.get("/notebooklm-zip")
def get_notebooklm_zip(user: CurrentUser = Depends(require_role("admin"))):
    """Export all data as Markdown ZIP for NotebookLM."""
    from app.services.export_service import export_hackathon_to_markdown_zip

    zip_bytes = export_hackathon_to_markdown_zip(user.hackathon_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=judgie-markdown-export-{user.hackathon_id}.zip"},
    )


# ── Template Export/Import ──

@router.get("/template")
def export_template(user: CurrentUser = Depends(require_role("admin"))):
    """Export current project settings as a template JSON."""
    import json

    hid = user.hackathon_id
    db = SessionLocal()
    try:
        hackathon = db.query(Hackathon).filter(Hackathon.id == hid).first()
        h_name = hackathon.name if hackathon else "Unknown"
        tpl_id = hackathon.template_id if hackathon else None
    finally:
        db.close()

    tpl_desc = ""
    if tpl_id and tpl_id in TEMPLATES:
        tpl_desc = TEMPLATES[tpl_id].get("description", "")

    export_data = {
        "name": h_name,
        "description": tpl_desc,
        "re_evaluation_context_mode": get_re_evaluation_context_mode(hid),
        "max_qa_turns": get_max_qa_turns(hid),
        "max_consultations": get_max_consultations(hid),
        "criteria": get_criteria(hid),
        "personas": get_personas(hid),
    }

    pretty_json = json.dumps(export_data, indent=2, ensure_ascii=False)
    return Response(
        content=pretty_json,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=judgie-template.json"},
    )


@router.post("/template/import")
def import_template(
    req: TemplateImport,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Import a template from a GitHub Gist or public Raw JSON URL."""
    hid = user.hackathon_id
    url_to_fetch = req.url.strip()

    parsed = urlparse(url_to_fetch)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only HTTP/HTTPS URLs allowed")

    hostname = parsed.hostname

    # Auto convert standard Gist URL to raw
    if hostname == "gist.github.com" and not parsed.path.endswith("/raw"):
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            raw_url = f"https://gist.githubusercontent.com/{path_parts[0]}/{path_parts[1]}/raw"
            parsed = urlparse(raw_url)
            hostname = parsed.hostname

    allowed_domains = {
        "github.com", "raw.githubusercontent.com",
        "gist.githubusercontent.com", "githubusercontent.com",
    }
    if hostname not in allowed_domains:
        raise HTTPException(status_code=400, detail="Domain not allowed")

    safe_url = urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, parsed.query, parsed.fragment,
    ))

    if not is_safe_url(safe_url):
        raise HTTPException(status_code=400, detail="URL fails security checks")

    res = requests.get(safe_url, timeout=15)
    if res.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to fetch template: HTTP {res.status_code}")

    try:
        imported_data = res.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Response is not valid JSON")

    if not isinstance(imported_data, dict):
        raise HTTPException(status_code=400, detail="Template must be a JSON object")
    if "criteria" not in imported_data or "personas" not in imported_data:
        raise HTTPException(status_code=400, detail="Missing 'criteria' or 'personas' keys")

    # Validate criteria
    for idx, c in enumerate(imported_data["criteria"]):
        if not all(k in c for k in ("name", "weight", "description")):
            raise HTTPException(status_code=400, detail=f"Criteria at index {idx} missing required fields")

    # Validate personas
    for idx, p in enumerate(imported_data["personas"]):
        if not all(k in p for k in ("id", "name", "role", "avatar", "prompt", "active")):
            raise HTTPException(status_code=400, detail=f"Persona at index {idx} missing required fields")

    set_criteria(hid, imported_data["criteria"])
    set_personas(hid, imported_data["personas"])

    if "re_evaluation_context_mode" in imported_data:
        if imported_data["re_evaluation_context_mode"] in ("cumulative", "independent"):
            set_re_evaluation_context_mode(hid, imported_data["re_evaluation_context_mode"])
    if "max_qa_turns" in imported_data:
        if isinstance(imported_data["max_qa_turns"], int):
            set_max_qa_turns(hid, imported_data["max_qa_turns"])
    if "max_consultations" in imported_data:
        if isinstance(imported_data["max_consultations"], int):
            set_max_consultations(hid, imported_data["max_consultations"])

    return {"message": "Template imported successfully"}
