"""
Settings router: criteria, personas, Gemini config, project behavior, languages.
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role
from app.models.db import (
    change_my_passcode,
    get_ai_response_languages,
    get_criteria,
    get_max_consultations,
    get_max_qa_turns,
    get_personas,
    get_re_evaluation_context_mode,
    get_setting,
    is_video_upload_enabled,
    set_ai_response_languages,
    set_criteria,
    set_max_consultations,
    set_max_qa_turns,
    set_personas,
    set_re_evaluation_context_mode,
    set_setting,
    set_video_upload_enabled,
)
from app.schemas.schemas import (
    CriteriaUpdate,
    GeminiConfig,
    LanguageSettings,
    PasswordChange,
    PersonasUpdate,
    ProjectSettings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Criteria ──

@router.get("/criteria")
def get_criteria_endpoint(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get evaluation criteria for the current hackathon."""
    return get_criteria(user.hackathon_id)


@router.put("/criteria")
def update_criteria(
    req: CriteriaUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update evaluation criteria."""
    set_criteria(user.hackathon_id, req.criteria)
    return {"message": "Criteria updated"}


# ── Personas ──

@router.get("/personas")
def get_personas_endpoint(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get AI judge personas for the current hackathon."""
    return get_personas(user.hackathon_id)


@router.put("/personas")
def update_personas(
    req: PersonasUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update AI judge personas."""
    set_personas(user.hackathon_id, req.personas)
    return {"message": "Personas updated"}


# ── Gemini Config ──

@router.get("/gemini")
def get_gemini_config(user: CurrentUser = Depends(require_role("admin"))):
    """Get Gemini API configuration."""
    hid = user.hackathon_id
    api_key = get_setting(hid, "gemini_api_key")
    model = get_setting(hid, "gemini_model")
    api_tier = get_setting(hid, "gemini_api_tier") or "Free Tier"

    models_val = get_setting(hid, "gemini_available_models")
    available_models = []
    if models_val:
        try:
            available_models = json.loads(models_val)
        except Exception:
            pass

    return {
        "has_api_key": bool(api_key),
        "model": model or "gemini-2.5-flash",
        "api_tier": api_tier,
        "available_models": available_models,
    }


@router.put("/gemini")
def update_gemini_config(
    req: GeminiConfig,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update Gemini API configuration."""
    hid = user.hackathon_id

    if req.api_key:
        # Validate by listing models
        from app.services.gemini import list_available_gemini_models
        models = list_available_gemini_models(hid, api_key_override=req.api_key)
        if not models:
            raise HTTPException(status_code=400, detail="Invalid API key or no models available")
        set_setting(hid, "gemini_api_key", req.api_key)
        set_setting(hid, "gemini_available_models", json.dumps(models))

    if req.model:
        set_setting(hid, "gemini_model", req.model)

    if req.api_tier:
        set_setting(hid, "gemini_api_tier", req.api_tier)

    return {"message": "Gemini config updated"}


# ── Project Settings ──

@router.get("/project")
def get_project_settings(user: CurrentUser = Depends(require_role("admin", "observer"))):
    """Get project behavior settings."""
    hid = user.hackathon_id
    return {
        "re_evaluation_context_mode": get_re_evaluation_context_mode(hid),
        "max_qa_turns": get_max_qa_turns(hid),
        "max_consultations": get_max_consultations(hid),
        "video_upload_enabled": is_video_upload_enabled(hid),
    }


@router.put("/project")
def update_project_settings(
    req: ProjectSettings,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update project behavior settings."""
    hid = user.hackathon_id

    if req.re_evaluation_context_mode is not None:
        set_re_evaluation_context_mode(hid, req.re_evaluation_context_mode)
    if req.max_qa_turns is not None:
        set_max_qa_turns(hid, req.max_qa_turns)
    if req.max_consultations is not None:
        set_max_consultations(hid, req.max_consultations)
    if req.video_upload_enabled is not None:
        set_video_upload_enabled(hid, req.video_upload_enabled)

    return {"message": "Project settings updated"}


# ── AI Response Languages ──

@router.get("/languages")
def get_languages(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get configured AI response languages."""
    return {"languages": get_ai_response_languages(user.hackathon_id)}


@router.put("/languages")
def update_languages(
    req: LanguageSettings,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update AI response languages."""
    if not req.languages:
        raise HTTPException(status_code=400, detail="At least one language required")
    if len(req.languages) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 languages allowed")
    set_ai_response_languages(user.hackathon_id, req.languages)
    return {"message": "Languages updated"}


# ── Password Change ──

@router.post("/change-password")
def change_password(
    req: PasswordChange,
    user: CurrentUser = Depends(require_role("admin", "superadmin")),
):
    """Change the current user's password."""
    success = change_my_passcode(
        user.hackathon_id, user.team_id, req.current_password, req.new_password,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Incorrect current password")
    return {"message": "Password changed"}
