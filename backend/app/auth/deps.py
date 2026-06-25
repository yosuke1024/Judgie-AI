"""
FastAPI dependencies for authentication and authorization.
Extracts JWT from HTTPOnly cookie and provides current user info.
"""

from fastapi import Cookie, Depends, HTTPException, status

from app.auth.jwt_handler import verify_token


class CurrentUser:
    """Represents the authenticated user extracted from JWT."""

    def __init__(self, user_id: int, email: str, role: str, team_id: str | None = None):
        self.user_id = user_id
        self.email = email
        self.role = role
        self.team_id = team_id  # None for admin/observer


def get_current_user(access_token: str | None = Cookie(default=None)) -> CurrentUser:
    """
    FastAPI dependency: extracts and validates JWT from the 'access_token' cookie.
    Raises 401 if not authenticated.
    """
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return CurrentUser(
        user_id=payload.get("user_id", 0),
        email=payload.get("email", ""),
        role=payload.get("role", ""),
        team_id=payload.get("team_id"),
    )


def require_role(*roles: str):
    """
    Returns a FastAPI dependency that enforces role-based access control.
    Usage: Depends(require_role("admin"))
    """

    def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(roles)}",
            )
        return user

    return _check
