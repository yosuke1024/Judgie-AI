import os
import secrets
import urllib.parse

import requests
import streamlit as st

# Module-level cache for OIDC configuration
_oidc_config = None

def get_oidc_config():
    """Retrieve and cache OIDC provider configuration from discovery document."""
    global _oidc_config
    if _oidc_config is not None:
        return _oidc_config

    issuer = os.environ.get("OIDC_ISSUER", "https://accounts.google.com")
    issuer = issuer.rstrip("/")
    discovery_url = f"{issuer}/.well-known/openid-configuration"

    try:
        response = requests.get(discovery_url, timeout=5)
        response.raise_for_status()
        _oidc_config = response.json()
        return _oidc_config
    except Exception as e:
        st.error(f"Failed to fetch OIDC configuration from {discovery_url}: {e}")
        st.stop()

def get_auth_url(state: str) -> str:
    """Generate the authorization URL to redirect the user to the OIDC provider."""
    config = get_oidc_config()
    auth_endpoint = config.get("authorization_endpoint")

    if not auth_endpoint:
        st.error("OIDC configuration is missing 'authorization_endpoint'.")
        st.stop()

    client_id = os.environ.get("OIDC_CLIENT_ID")
    redirect_uri = os.environ.get("OIDC_REDIRECT_URI")

    if not client_id or not redirect_uri:
        st.error("OIDC_CLIENT_ID or OIDC_REDIRECT_URI environment variables are not set.")
        st.stop()

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state
    }

    query_string = urllib.parse.urlencode(params)
    return f"{auth_endpoint}?{query_string}"

def verify_code_and_get_email(code: str) -> str:
    """Exchange authorization code for tokens and fetch user email via UserInfo endpoint."""
    config = get_oidc_config()
    token_endpoint = config.get("token_endpoint")
    userinfo_endpoint = config.get("userinfo_endpoint")

    if not token_endpoint or not userinfo_endpoint:
        st.error("OIDC configuration is missing 'token_endpoint' or 'userinfo_endpoint'.")
        st.stop()

    client_id = os.environ.get("OIDC_CLIENT_ID")
    client_secret = os.environ.get("OIDC_CLIENT_SECRET")
    redirect_uri = os.environ.get("OIDC_REDIRECT_URI")

    # 1. Exchange authorization code for access token
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    try:
        token_response = requests.post(token_endpoint, data=data, timeout=5)
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError("No access_token returned from OIDC provider.")
    except Exception as e:
        st.error(f"OIDC token exchange failed: {e}")
        st.stop()

    # 2. Get user info using the access token
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        userinfo_response = requests.get(userinfo_endpoint, headers=headers, timeout=5)
        userinfo_response.raise_for_status()
        user_info = userinfo_response.json()

        email = user_info.get("email")
        email_verified = user_info.get("email_verified")

        if email_verified is not None and not email_verified:
            st.error("User email is not verified by OIDC provider.")
            st.stop()

        if not email:
            raise ValueError("No email field returned in UserInfo response.")

        return email
    except Exception as e:
        st.error(f"Failed to fetch OIDC userinfo: {e}")
        st.stop()

def is_authorized(email: str) -> bool:
    """Validate user email against domain and email whitelists."""
    allowed_domains_str = os.environ.get("OIDC_ALLOWED_DOMAINS", "")
    allowed_emails_str = os.environ.get("OIDC_ALLOWED_EMAILS", "")

    # If no restrictions are set, allow all authenticated users
    if not allowed_domains_str and not allowed_emails_str:
        return True

    email_lower = email.lower()

    # 1. Check domains
    if allowed_domains_str:
        allowed_domains = [d.strip().lower() for d in allowed_domains_str.split(",") if d.strip()]
        domain = email_lower.split("@")[-1]
        if domain in allowed_domains:
            return True

    # 2. Check individual emails
    if allowed_emails_str:
        allowed_emails = [e.strip().lower() for e in allowed_emails_str.split(",") if e.strip()]
        if email_lower in allowed_emails:
            return True

    return False

def enforce_oidc_gateway():
    """
    App-level gatekeeper checking OIDC verification state.
    Renders login wall and stops execution if unauthenticated.
    """
    # Pass if user is already OIDC verified in this session
    if st.session_state.get("oidc_verified") is True:
        return

    # Check for OIDC authorization code in URL parameters
    code = st.query_params.get("code")

    if not code:
        import base64
        import json

        # Generate and store a CSRF state token
        if "oidc_state" not in st.session_state:
            st.session_state.oidc_state = secrets.token_hex(16)

        # Pack CSRF token and current query parameters into state
        current_params = {k: v for k, v in st.query_params.items() if k not in ["code", "state"]}
        state_data = {
            "csrf": st.session_state.oidc_state,
            "params": current_params
        }
        state_payload = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

        auth_url = get_auth_url(state_payload)

        # Render a modern, centered login interface
        st.markdown(
            """
            <style>
            .oidc-outer {
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 40px 10px;
            }
            .oidc-card {
                max-width: 450px;
                width: 100%;
                padding: 40px;
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                text-align: center;
                box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.25);
            }
            .oidc-title {
                font-size: 1.8em;
                font-weight: 700;
                margin-bottom: 15px;
                color: #f8fafc;
            }
            .oidc-desc {
                font-size: 0.95em;
                line-height: 1.5;
                margin-bottom: 30px;
                color: #94a3b8;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        with st.container():
            st.markdown(
                """
                <div class="oidc-outer">
                    <div class="oidc-card">
                        <div class="oidc-title">⚖️ Judgie-AI Secure Gate</div>
                        <div class="oidc-desc">This application is protected. Please sign in with your authorized Google or OIDC account to continue.</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            st.link_button("Sign in with Google / OIDC", auth_url, type="primary", use_container_width=True)
            st.stop()

    else:
        import base64
        import json

        # Code received; handle callback and state validation
        state_payload = st.query_params.get("state")
        saved_csrf = st.session_state.get("oidc_state")

        try:
            state_data = json.loads(base64.urlsafe_b64decode(state_payload.encode()).decode())
            state_csrf = state_data.get("csrf")
            restored_params = state_data.get("params", {})
        except Exception:
            state_csrf = None
            restored_params = {}

        if saved_csrf and state_csrf != saved_csrf:
            st.error("Invalid session state (possible CSRF attempt or session timeout). Please try again.")
            if st.button("Reset and Retry Login", use_container_width=True):
                st.query_params.clear()
                if "oidc_state" in st.session_state:
                    del st.session_state.oidc_state
                st.rerun()
            st.stop()

        email = verify_code_and_get_email(code)

        if is_authorized(email):
            st.session_state.oidc_verified = True
            st.session_state.oidc_email = email

            # Clear OAuth parameters from the browser address bar, but restore original query params
            st.query_params.clear()
            for k, v in restored_params.items():
                st.query_params[k] = v
            st.rerun()
        else:
            # Render access denied message with account detail
            st.markdown(
                f"""
                <div style="display: flex; justify-content: center; padding: 40px 10px;">
                    <div style="max-width: 450px; width: 100%; padding: 40px; background: rgba(239, 68, 68, 0.08); backdrop-filter: blur(12px); border-radius: 16px; border: 1px solid rgba(239, 68, 68, 0.2); text-align: center; box-shadow: 0 10px 30px 0 rgba(0, 0, 0, 0.25);">
                        <h2 style="color: #ef4444; font-size: 1.6em; margin-bottom: 15px; font-weight: 700;">🚫 Access Denied</h2>
                        <p style="color: #f1f5f9; font-size: 0.95em; line-height: 1.5; margin-bottom: 20px;">
                            Your account <strong>{email}</strong> does not have access permissions.
                        </p>
                        <p style="color: #94a3b8; font-size: 0.85em; margin-bottom: 30px;">
                            Please contact your administrator if this is an error.
                        </p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Sign in with another account", use_container_width=True):
                st.query_params.clear()
                if "oidc_state" in st.session_state:
                    del st.session_state.oidc_state
                st.rerun()
            st.stop()
