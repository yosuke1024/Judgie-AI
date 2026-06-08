import os

import streamlit as st

from core.db import create_session, delete_session, get_session, verify_user


def verify_ip_address():
    """
    Checks the connection's source IP address against an ALLOWED_IPS whitelist.
    Stops Streamlit execution immediately with an error if the client IP is unauthorized.
    Supports native Streamlit 1.56.0+ context API and older websocket header fallbacks.
    """
    allowed_ips_str = os.environ.get("ALLOWED_IPS")
    if not allowed_ips_str:
        try:
            allowed_ips_str = st.secrets.get("ALLOWED_IPS", "")
        except Exception:
            allowed_ips_str = ""
    if not allowed_ips_str:
        return

    allowed_ips = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()]
    if not allowed_ips:
        return

    client_ip = None

    # 1. Streamlit 1.56.0+ Native Context API (Safe & Supported)
    try:
        if hasattr(st, "context") and hasattr(st.context, "ip_address"):
            client_ip = st.context.ip_address
    except Exception:
        pass

    # 2. Streamlit >= 1.14.0 and < 1.56.0 Internal Websocket API (Legacy fallback)
    if not client_ip:
        try:
            from streamlit.web.server.websocket_headers import _get_websocket_headers
            headers = _get_websocket_headers()
            if headers:
                x_forwarded_for = headers.get("X-Forwarded-For")
                if x_forwarded_for:
                    client_ip = x_forwarded_for.split(",")[0].strip()
        except Exception:
            pass

    # Default local fallback
    if not client_ip:
        client_ip = "127.0.0.1"

    if client_ip not in allowed_ips:
        st.error(f"🚫 Access Denied. Your IP address ({client_ip}) is not authorized to access this application.")
        st.stop()

def init_session():
    """Initialize required session state variables."""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'team_id' not in st.session_state:
        st.session_state.team_id = None
    if 'active_hackathon_id' not in st.session_state:
        st.session_state.active_hackathon_id = None
    if 'sid' not in st.session_state:
        st.session_state.sid = None

    url_sid = st.query_params.get('sid')

    # Auto-login via URL query parameter if not already logged in
    if url_sid and not st.session_state.logged_in:
        session_data = get_session(url_sid)
        if session_data:
            st.session_state.logged_in = True
            st.session_state.role = session_data['role']
            st.session_state.team_id = session_data['team_id']
            st.session_state.active_hackathon_id = session_data['hackathon_id']
            st.session_state.sid = url_sid

    # If logged in but URL parameter is missing (e.g. after page navigation), restore it
    if st.session_state.logged_in and st.session_state.sid:
        if st.query_params.get('sid') != st.session_state.sid:
            st.query_params['sid'] = st.session_state.sid

def login(team_id, passcode, tenant_id=None):
    """Attempt to login and set session state."""
    user_info = verify_user(team_id, passcode, hackathon_id=tenant_id)
    if user_info:
        st.session_state.logged_in = True
        st.session_state.role = user_info['role']
        st.session_state.team_id = team_id

        active_h_id = user_info['hackathon_id']
        if not active_h_id and user_info['role'] == 'admin':
            from core.db import Hackathon, SessionLocal
            db = SessionLocal()
            try:
                hackathon = db.query(Hackathon).order_by(Hackathon.id.desc()).first()
                active_h_id = hackathon.id if hackathon else None
            finally:
                db.close()

        st.session_state.active_hackathon_id = active_h_id

        # Persist session to DB and URL
        sid = create_session(team_id, user_info['role'], active_h_id)
        st.session_state.sid = sid
        st.query_params['sid'] = sid

        return True
    return False

def logout():
    """Clear session state and logout."""
    # Delete persistent session if exists
    sid = st.session_state.get('sid') or st.query_params.get('sid')
    if sid:
        delete_session(sid)
    st.query_params.clear()

    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.team_id = None
    st.session_state.active_hackathon_id = None
    st.session_state.sid = None

    # Clear OIDC state variables
    for key in ['oidc_verified', 'oidc_email', 'oidc_state']:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()

def require_login(required_role=None):
    """
    Protect pages. Must be called at the top of every page.
    If not logged in, redirects to app.py.
    If required_role is set, redirects if the user doesn't have the role.
    """
    init_session()

    if not st.session_state.logged_in:
        st.warning("Please log in to access this page.")
        st.stop() # Stops execution of the rest of the page

    if required_role and st.session_state.role != required_role:
        st.error(f"Access Denied. This page requires {required_role} privileges.")
        st.stop()
