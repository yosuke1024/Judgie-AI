"""
Authentication router: login, logout, current user.
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth.deps import CurrentUser, get_current_user
from app.auth.jwt_handler import create_access_token
from app.models.db import verify_user
from app.schemas.schemas import LoginRequest, LoginResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
    from app.models.db import get_team_profile

    profile = {}
    if user.hackathon_id and user.role in ("team", "observer"):
        profile = get_team_profile(user.hackathon_id, user.team_id)

    return UserInfo(
        team_id=user.team_id,
        role=user.role,
        hackathon_id=user.hackathon_id,
        product_name=profile.get("product_name"),
        team_name=profile.get("team_name"),
        one_liner=profile.get("one_liner"),
    )
