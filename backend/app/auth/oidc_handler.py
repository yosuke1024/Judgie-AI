"""
OIDC Authentication Handler.
Handles redirect URI generation, token exchange, and ID token verification.
"""

import urllib.parse

import jwt
import requests

from app.auth.oidc_settings import (
    get_oidc_allowed_domains,
    get_oidc_allowed_emails,
    get_oidc_client_id,
    get_oidc_client_secret,
    get_oidc_issuer,
    get_oidc_redirect_uri,
)

_oidc_config = None


def get_oidc_config() -> dict:
    """Fetch OIDC provider configuration from the well-known discovery endpoint."""
    global _oidc_config
    if _oidc_config is not None:
        return _oidc_config

    issuer = get_oidc_issuer().rstrip("/")
    well_known_url = f"{issuer}/.well-known/openid-configuration"
    try:
        res = requests.get(well_known_url, timeout=10)
        res.raise_for_status()
        _oidc_config = res.json()
        return _oidc_config
    except Exception as e:
        raise RuntimeError(f"Failed to fetch OIDC configuration from {well_known_url}: {e}")


def get_authorization_url(state: str) -> str:
    """Generate OIDC authorization URL for redirection."""
    config = get_oidc_config()
    auth_endpoint = config.get("authorization_endpoint")
    if not auth_endpoint:
        raise ValueError("OIDC provider configuration missing authorization_endpoint")

    params = {
        "client_id": get_oidc_client_id(),
        "redirect_uri": get_oidc_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }
    return f"{auth_endpoint}?{urllib.parse.urlencode(params)}"


def verify_code_and_get_email(code: str) -> str:
    """
    Exchange auth code for tokens and extract verified email from ID token.
    Raises ValueError if anything fails.
    """
    config = get_oidc_config()
    token_endpoint = config.get("token_endpoint")
    jwks_uri = config.get("jwks_uri")

    if not token_endpoint or not jwks_uri:
        raise ValueError("OIDC provider configuration missing token_endpoint or jwks_uri")

    # 1. Exchange authorization code for token
    data = {
        "client_id": get_oidc_client_id(),
        "client_secret": get_oidc_client_secret(),
        "redirect_uri": get_oidc_redirect_uri(),
        "grant_type": "authorization_code",
        "code": code,
    }

    try:
        res = requests.post(token_endpoint, data=data, timeout=10)
        res.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to exchange OIDC code: {e}")

    token_response = res.json()
    id_token = token_response.get("id_token")
    if not id_token:
        raise ValueError("No id_token in token response from OIDC provider")

    # 2. Decode and verify ID Token signature using JWKS
    try:
        jwks_client = jwt.PyJWKClient(jwks_uri)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=get_oidc_client_id(),
            issuer=get_oidc_issuer(),
            options={"verify_exp": True},
        )
    except Exception as e:
        raise ValueError(f"ID Token verification failed: {e}")

    email = payload.get("email")
    if not email:
        raise ValueError("Email claim is missing in ID Token")

    # 3. Optional checks: domain and email allowlists
    if not is_email_allowed(email):
        raise ValueError(f"Email {email} is not allowed to access this system")

    return email


def is_email_allowed(email: str) -> bool:
    """Check if the email passes configured restrictions."""
    allowed_emails = get_oidc_allowed_emails()
    if allowed_emails and email in allowed_emails:
        return True
    allowed_domains = get_oidc_allowed_domains()
    if allowed_domains:
        domain = email.split("@")[-1]
        if domain in allowed_domains:
            return True
    if not allowed_emails and not allowed_domains:
        return True
    return False
