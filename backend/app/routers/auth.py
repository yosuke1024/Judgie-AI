"""
Authentication router: login, logout, current user.
"""

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response, status, Cookie
import jwt

from app.auth.deps import CurrentUser, get_current_user
from app.auth.jwt_handler import create_access_token
from app.config import OIDC_ENABLED, JWT_SECRET_KEY, JWT_ALGORITHM
from app.auth import oidc_handler
from app.models.db import verify_user
from app.schemas.schemas import (
    LoginRequest, LoginResponse, UserInfo,
    OIDCLoginInitResponse, OIDCCallbackRequest, OIDCCallbackResponse,
    TenantInfo, OIDCTenantSelectRequest, TenantSelectRequest
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/oidc/login", response_model=OIDCLoginInitResponse)
def oidc_login(response: Response):
    """Initialize OIDC login flow. Generate state and redirect URL."""
    if not OIDC_ENABLED:
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
def oidc_callback(
    req: OIDCCallbackRequest,
    response: Response,
    oidc_state: str | None = Cookie(default=None)
):
    """
    Callback endpoint for OIDC.
    Verifies code and state, queries DB by email, and sets JWT cookie or requests tenant selection.
    """
    if not OIDC_ENABLED:
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Query matching users in database
    from app.models.db import db_session, User, Hackathon

    with db_session() as db:
        user_records = db.query(User).filter(User.email == email).all()

        if not user_records:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your email is not registered in this system. Please contact the administrator.",
            )

        if len(user_records) == 1:
            # Single tenant: login directly
            user = user_records[0]
            token_data = {
                "team_id": user.team_id,
                "role": user.role,
                "hackathon_id": user.hackathon_id,
                "email": user.email,
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
                team_id=user.team_id,
                role=user.role,
                hackathon_id=user.hackathon_id,
            )

        # Multiple tenants: return list and issue a temporary select token
        tenants = []
        for u in user_records:
            h = db.query(Hackathon).filter(Hackathon.id == u.hackathon_id).first()
            h_name = h.name if h else f"Hackathon #{u.hackathon_id}"
            tenants.append(
                TenantInfo(
                    hackathon_id=u.hackathon_id,
                    hackathon_name=h_name,
                    team_id=u.team_id,
                    team_name=u.team_name,
                    role=u.role,
                )
            )

        # Create a temporary token containing email (expires in 5 minutes)
        temp_token_payload = {
            "email": email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5)
        }
        temp_token = jwt.encode(temp_token_payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

        response.delete_cookie("oidc_state")
        return OIDCCallbackResponse(
            status="select_tenant",
            tenants=tenants,
            temp_token=temp_token,
        )


@router.post("/oidc/select-tenant", response_model=LoginResponse)
def oidc_select_tenant(req: OIDCTenantSelectRequest, response: Response):
    """Verify temporary token and issue active session for selected tenant."""
    try:
        payload = jwt.decode(req.temp_token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        if not email:
            raise ValueError("No email in token")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired temporary token.",
        )

    from app.models.db import db_session, User

    with db_session() as db:
        user = db.query(User).filter(
            User.email == email,
            User.hackathon_id == req.hackathon_id,
            User.team_id == req.team_id
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for the selected tenant/team.",
            )

        token_data = {
            "team_id": user.team_id,
            "role": user.role,
            "hackathon_id": user.hackathon_id,
            "email": user.email,
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
        return LoginResponse(
            team_id=user.team_id,
            role=user.role,
            hackathon_id=user.hackathon_id,
        )


@router.get("/my-tenants", response_model=list[TenantInfo])
def get_my_tenants(user: CurrentUser = Depends(get_current_user)):
    """Return all tenants associated with the current user's email."""
    email = user.email
    if not email:
        # Fallback to DB query if email is not in JWT payload
        from app.models.db import db_session, User as DBUser
        with db_session() as db:
            db_user = db.query(DBUser).filter(
                DBUser.hackathon_id == user.hackathon_id,
                DBUser.team_id == user.team_id
            ).first()
            email = db_user.email if db_user else None

    if not email:
        # Fallback: return just the current tenant if no email registered
        from app.models.db import db_session, Hackathon
        with db_session() as db:
            h = db.query(Hackathon).filter(Hackathon.id == user.hackathon_id).first()
            h_name = h.name if h else f"Hackathon #{user.hackathon_id}"
            return [
                TenantInfo(
                    hackathon_id=user.hackathon_id or 0,
                    hackathon_name=h_name,
                    team_id=user.team_id,
                    role=user.role,
                )
            ]

    from app.models.db import db_session, User as DBUser, Hackathon

    with db_session() as db:
        user_records = db.query(DBUser).filter(DBUser.email == email).all()
        tenants = []
        for u in user_records:
            h = db.query(Hackathon).filter(Hackathon.id == u.hackathon_id).first()
            h_name = h.name if h else f"Hackathon #{u.hackathon_id}"
            tenants.append(
                TenantInfo(
                    hackathon_id=u.hackathon_id,
                    hackathon_name=h_name,
                    team_id=u.team_id,
                    team_name=u.team_name,
                    role=u.role,
                )
            )
        return tenants


@router.post("/switch-tenant", response_model=LoginResponse)
def switch_tenant(
    req: TenantSelectRequest,
    response: Response,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Switch user's current session to a different tenant they belong to."""
    email = current_user.email
    if not email:
        from app.models.db import db_session, User as DBUser
        with db_session() as db:
            db_user = db.query(DBUser).filter(
                DBUser.hackathon_id == current_user.hackathon_id,
                DBUser.team_id == current_user.team_id
            ).first()
            email = db_user.email if db_user else None

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot switch tenant: Current session has no registered email.",
        )

    from app.models.db import db_session, User as DBUser

    with db_session() as db:
        user = db.query(DBUser).filter(
            DBUser.email == email,
            DBUser.hackathon_id == req.hackathon_id,
            DBUser.team_id == req.team_id
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized for the selected tenant/team.",
            )

        token_data = {
            "team_id": user.team_id,
            "role": user.role,
            "hackathon_id": user.hackathon_id,
            "email": user.email,
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
        return LoginResponse(
            team_id=user.team_id,
            role=user.role,
            hackathon_id=user.hackathon_id,
        )


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    """Authenticate user and set JWT HTTPOnly cookie."""
    user_info = verify_user(req.team_id, req.passcode, req.hackathon_id)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token_data = {
        "team_id": req.team_id,
        "role": user_info["role"],
        "hackathon_id": user_info["hackathon_id"],
        "email": user_info.get("email"),
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
        team_id=req.team_id,
        role=user_info["role"],
        hackathon_id=user_info["hackathon_id"],
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
    if user.hackathon_id and user.role in ("team", "observer"):
        profile = get_team_profile(user.hackathon_id, user.team_id)
        max_consultations = get_max_consultations(user.hackathon_id)
        consultation_count = get_consultation_count(user.hackathon_id, user.team_id)
        max_qa_turns = get_max_qa_turns(user.hackathon_id)

    return UserInfo(
        team_id=user.team_id,
        role=user.role,
        hackathon_id=user.hackathon_id,
        product_name=profile.get("product_name"),
        team_name=profile.get("team_name"),
        one_liner=profile.get("one_liner"),
        max_consultations=max_consultations,
        consultation_count=consultation_count,
        max_qa_turns=max_qa_turns,
    )
