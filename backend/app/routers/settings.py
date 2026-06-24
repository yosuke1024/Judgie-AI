"""
Settings router: criteria, personas, Gemini config, project behavior, languages.
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, require_role
from app.auth.oidc_settings import (
    get_oidc_allowed_domains,
    get_oidc_allowed_emails,
    get_oidc_client_id,
    get_oidc_client_secret,
    get_oidc_enabled,
    get_oidc_issuer,
    get_oidc_redirect_uri,
)
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
    update_admin_passcode,
)
from app.schemas.schemas import (
    CriteriaUpdate,
    GeminiConfig,
    LanguageSettings,
    OIDCSettings,
    OIDCSettingsUpdate,
    PasscodeChange,
    PasswordChange,
    PersonasUpdate,
    ProjectInitialize,
    ProjectSettings,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Criteria ──


@router.get("/criteria")
def get_criteria_endpoint(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get evaluation criteria."""
    return get_criteria()


@router.put("/criteria")
def update_criteria(
    req: CriteriaUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update evaluation criteria."""
    set_criteria(req.criteria)
    return {"message": "Criteria updated"}


# ── Personas ──


@router.get("/personas")
def get_personas_endpoint(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get AI judge personas."""
    return get_personas()


@router.put("/personas")
def update_personas(
    req: PersonasUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update AI judge personas."""
    set_personas(req.personas)
    return {"message": "Personas updated"}


# ── Gemini Config ──


@router.get("/gemini")
def get_gemini_config(user: CurrentUser = Depends(require_role("admin"))):
    """Get Gemini API configuration."""
    api_key = get_setting("gemini_api_key")
    model = get_setting("gemini_model")
    api_tier = get_setting("gemini_api_tier") or "Free Tier"

    models_val = get_setting("gemini_available_models")
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
    if req.api_key:
        # Validate by listing models
        from app.services.gemini import list_available_gemini_models

        models = list_available_gemini_models(api_key_override=req.api_key)
        if not models:
            raise HTTPException(status_code=400, detail="Invalid API key or no models available")
        set_setting("gemini_api_key", req.api_key)
        set_setting("gemini_available_models", json.dumps(models))

    if req.model:
        set_setting("gemini_model", req.model)

    if req.api_tier:
        set_setting("gemini_api_tier", req.api_tier)

    return {"message": "Gemini config updated"}


# ── Project Settings ──


@router.get("/project")
def get_project_settings(user: CurrentUser = Depends(require_role("admin", "observer"))):
    """Get project behavior settings."""
    return {
        "re_evaluation_context_mode": get_re_evaluation_context_mode(),
        "max_qa_turns": get_max_qa_turns(),
        "max_consultations": get_max_consultations(),
        "video_upload_enabled": is_video_upload_enabled(),
    }


@router.put("/project")
def update_project_settings(
    req: ProjectSettings,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update project behavior settings."""
    if req.re_evaluation_context_mode is not None:
        set_re_evaluation_context_mode(req.re_evaluation_context_mode)
    if req.max_qa_turns is not None:
        set_max_qa_turns(req.max_qa_turns)
    if req.max_consultations is not None:
        set_max_consultations(req.max_consultations)
    if req.video_upload_enabled is not None:
        set_video_upload_enabled(req.video_upload_enabled)

    return {"message": "Project settings updated"}


# ── AI Response Languages ──


@router.get("/languages")
def get_languages(user: CurrentUser = Depends(require_role("admin", "observer", "team"))):
    """Get configured AI response languages."""
    return {"languages": get_ai_response_languages()}


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
    set_ai_response_languages(req.languages)
    return {"message": "Languages updated"}


# ── Password Change ──


@router.post("/change-password")
def change_password(
    req: PasswordChange,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Change the current user's password."""
    success = change_my_passcode(
        user.team_id,
        req.current_password,
        req.new_password,
    )
    if not success:
        raise HTTPException(status_code=400, detail="Incorrect current password")
    return {"message": "Password changed"}


# ── Templates Preset ──


@router.get("/templates")
def get_templates(user: CurrentUser = Depends(require_role("admin"))):
    """Get list of available project templates."""
    from app.services.templates import TEMPLATES

    return {k: {"name": t.get("name"), "description": t.get("description")} for k, t in TEMPLATES.items()}


@router.post("/templates/initialize")
def initialize_template(
    req: ProjectInitialize,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Initialize project setting with a preset template."""
    from app.models.db import initialize_project_template

    try:
        initialize_project_template(req.template_id, req.custom_template_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"message": "Project template initialized"}


@router.put("/admin-passcode")
def reset_admin_passcode(
    req: PasscodeChange,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Reset the admin passcode."""
    update_admin_passcode(req.new_passcode)
    return {"message": "Admin passcode updated"}


# ── OIDC settings ──


@router.get("/oidc", response_model=OIDCSettings)
def get_oidc_settings_endpoint(user: CurrentUser = Depends(require_role("admin"))):
    """Get OIDC configuration settings."""
    allowed_domains = get_oidc_allowed_domains()
    allowed_emails = get_oidc_allowed_emails()

    return OIDCSettings(
        oidc_enabled=get_oidc_enabled(),
        oidc_issuer=get_oidc_issuer(),
        oidc_client_id=get_oidc_client_id(),
        has_client_secret=bool(get_oidc_client_secret()),
        oidc_redirect_uri=get_oidc_redirect_uri(),
        oidc_allowed_domains=",".join(allowed_domains) if allowed_domains else "",
        oidc_allowed_emails=",".join(allowed_emails) if allowed_emails else "",
    )


@router.put("/oidc")
def update_oidc_settings(
    req: OIDCSettingsUpdate,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Update OIDC configuration settings."""
    if req.oidc_enabled is not None:
        set_setting("oidc_enabled", "true" if req.oidc_enabled else "false")
    if req.oidc_issuer is not None:
        set_setting("oidc_issuer", req.oidc_issuer)
    if req.oidc_client_id is not None:
        set_setting("oidc_client_id", req.oidc_client_id)
    if req.oidc_client_secret:  # Only update if not empty/None
        set_setting("oidc_client_secret", req.oidc_client_secret)
    if req.oidc_redirect_uri is not None:
        set_setting("oidc_redirect_uri", req.oidc_redirect_uri)
    if req.oidc_allowed_domains is not None:
        set_setting("oidc_allowed_domains", req.oidc_allowed_domains)
    if req.oidc_allowed_emails is not None:
        set_setting("oidc_allowed_emails", req.oidc_allowed_emails)

    return {"message": "OIDC settings updated"}
