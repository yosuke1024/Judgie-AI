"""
Dynamic OIDC Settings resolver.
Retrieves settings from database 'settings' table, falling back to environment config.
"""

from typing import List
from app.config import (
    OIDC_ENABLED,
    OIDC_ISSUER,
    OIDC_CLIENT_ID,
    OIDC_CLIENT_SECRET,
    OIDC_REDIRECT_URI,
    OIDC_ALLOWED_DOMAINS,
    OIDC_ALLOWED_EMAILS,
)
from app.models.db import get_setting


def get_oidc_enabled() -> bool:
    val = get_setting("oidc_enabled")
    if val is not None:
        return val.lower() == "true"
    return OIDC_ENABLED


def get_oidc_issuer() -> str:
    val = get_setting("oidc_issuer")
    if val:
        return val
    return OIDC_ISSUER


def get_oidc_client_id() -> str:
    val = get_setting("oidc_client_id")
    if val:
        return val
    return OIDC_CLIENT_ID


def get_oidc_client_secret() -> str:
    val = get_setting("oidc_client_secret")
    if val:
        return val
    return OIDC_CLIENT_SECRET


def get_oidc_redirect_uri() -> str:
    val = get_setting("oidc_redirect_uri")
    if val:
        return val
    return OIDC_REDIRECT_URI


def get_oidc_allowed_domains() -> List[str]:
    val = get_setting("oidc_allowed_domains")
    if val is not None:
        return [d.strip() for d in val.split(",") if d.strip()]
    return OIDC_ALLOWED_DOMAINS


def get_oidc_allowed_emails() -> List[str]:
    val = get_setting("oidc_allowed_emails")
    if val is not None:
        return [e.strip() for e in val.split(",") if e.strip()]
    return OIDC_ALLOWED_EMAILS
