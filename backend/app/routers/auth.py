"""
Authentication router: login, logout, current user.
"""

import uuid

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from app.auth import oidc_handler
from app.auth.deps import CurrentUser, get_current_user
from app.auth.jwt_handler import create_access_token
from app.auth.oidc_settings import get_oidc_enabled
from app.models.db import verify_user
from app.schemas.schemas import (
    LoginRequest,
    LoginResponse,
    OIDCCallbackRequest,
    OIDCCallbackResponse,
    OIDCLoginInitResponse,
    UserInfo,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def get_auth_config():
    """Return backend configurations related to authentication and LLM features."""
    from app.core.llm import get_llm_provider

    try:
        provider = get_llm_provider()
        supports_video = provider.supports_video
    except Exception:
        supports_video = True
    return {"oidc_enabled": get_oidc_enabled(), "supports_video": supports_video}


@router.get("/oidc/login", response_model=OIDCLoginInitResponse)
def oidc_login(response: Response):
    """Initialize OIDC login flow. Generate state and redirect URL."""
    if not get_oidc_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC authentication is not enabled.",
        )
    state = str(uuid.uuid4())
    auth_url = oidc_handler.get_authorization_url(state)

    # Store state in cookie to prevent CSRF
    response.set_cookie(
        key="oidc_state",
        value=state,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=300,  # 5 minutes
    )
    return OIDCLoginInitResponse(auth_url=auth_url, state=state)


@router.post("/oidc/callback", response_model=OIDCCallbackResponse)
def oidc_callback(req: OIDCCallbackRequest, response: Response, oidc_state: str | None = Cookie(default=None)):
    """
    Callback endpoint for OIDC.
    Verifies code and state, queries DB by email, and sets JWT cookie.
    """
    if not get_oidc_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OIDC authentication is not enabled.",
        )

    # Verify state against cookie
    if not oidc_state or oidc_state != req.state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter. CSRF verification failed.",
        )

    try:
        email = oidc_handler.verify_code_and_get_email(req.code)
    except ValueError as e:
        err_msg = str(e)
        if "not allowed" in err_msg or "restriction" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err_msg,
        )

    # Look up user by email
    from app.models.db import TeamMembership, User, db_session

    with db_session() as db:
        user = db.query(User).filter(User.email == email, User.is_active).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your email is not registered in this system. Please contact the administrator.",
            )

        # Get team membership
        membership = db.query(TeamMembership).filter(TeamMembership.user_id == user.id).first()
        team_id = membership.team_id if membership else None

        token_data = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "team_id": team_id,
        }
        token = create_access_token(token_data)

        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 12,
        )
        response.delete_cookie("oidc_state")
        return OIDCCallbackResponse(
            status="success",
            team_id=team_id,
            role=user.role,
        )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    """Authenticate user with email + password and set JWT HTTPOnly cookie."""
    user_info = verify_user(req.email, req.password)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token_data = {
        "user_id": user_info["user_id"],
        "email": user_info["email"],
        "role": user_info["role"],
        "team_id": user_info.get("team_id"),
    }
    token = create_access_token(token_data)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
        max_age=60 * 60 * 12,  # 12 hours
    )

    return LoginResponse(
        email=user_info["email"],
        role=user_info["role"],
        team_id=user_info.get("team_id"),
    )


@router.post("/logout")
def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserInfo)
def get_me(user: CurrentUser = Depends(get_current_user)):
    """Return current authenticated user info."""
    from app.models.db import get_consultation_count, get_max_consultations, get_max_qa_turns, get_team_profile

    profile = {}
    max_consultations = -1
    consultation_count = 0
    max_qa_turns = 1
    if user.team_id:
        profile = get_team_profile(user.team_id)
        max_consultations = get_max_consultations()
        consultation_count = get_consultation_count(user.team_id)
        max_qa_turns = get_max_qa_turns()

    # Get display name from DB
    from app.models.db import User as DBUser, db_session

    display_name = None
    with db_session() as db:
        db_user = db.query(DBUser).filter(DBUser.id == user.user_id).first()
        if db_user:
            display_name = db_user.display_name

    return UserInfo(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        team_id=user.team_id,
        display_name=display_name,
        product_name=profile.get("product_name"),
        team_name=profile.get("team_name"),
        one_liner=profile.get("one_liner"),
        max_consultations=max_consultations,
        consultation_count=consultation_count,
        max_qa_turns=max_qa_turns,
    )
