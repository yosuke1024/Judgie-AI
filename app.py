import os

import streamlit as st

from core.auth import init_session, verify_ip_address
from core.db import init_db, seed_demo_data
from core.i18n import t
from core.oidc import enforce_oidc_gateway

# Enforce IP address firewall if ALLOWED_IPS is set in environment/secrets
verify_ip_address()

# Enforce OIDC Gateway if enabled in environment
if os.environ.get("OIDC_ENABLED") == "true":
    enforce_oidc_gateway()

st.set_page_config(page_title="Judgie-AI | Project Evaluation Platform", page_icon="⚖️", layout="wide")


# Initialize DB and Session
init_db()
seed_demo_data()
init_session()

# Global Language Setting
if 'language' not in st.session_state:
    st.session_state.language = 'English'

with st.sidebar:
    st.session_state.language = st.radio("Language / 言語", ["English", "日本語"])
    if st.session_state.logged_in:
        st.markdown("---")
        st.markdown(f"**Logged in as:** `{st.session_state.team_id}` ({st.session_state.role})")
        if st.button("Logout", use_container_width=True):
            from core.auth import logout
            logout()

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; font-size: 0.85em; color: #888888; margin-top: 15px;'>
            <a href='https://github.com/yosuke1024/Judgie-AI' target='_blank' style='color: #38bdf8; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; justify-content: center; gap: 4px; margin-bottom: 5px;'>
                <svg height="16" width="16" viewBox="0 0 16 16" style="fill: #38bdf8; vertical-align: middle;"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
                GitHub Repository
            </a>
            <br>
            Built with ❤️ by <a href='https://pixapps.ai' target='_blank' style='color: #38bdf8; text-decoration: none; font-weight: bold;'>PixApps.ai</a>
        </div>
        """,
        unsafe_allow_html=True
    )

# Check if SuperAdmin should be disabled (Single-tenant mode)
super_admin_disabled = os.environ.get("DEFAULT_ADMIN_ID") is not None

# Define Pages
login_page = st.Page("views/login.py", title="Login", icon="🔑")
super_login_page = st.Page("views/super_login.py", title="Super Admin Login", icon="🌍")
leaderboard_page = st.Page("views/leaderboard.py", title="Leaderboard", icon="🏆")
team_page = st.Page("views/team_view.py", title="Team Dashboard", icon="🧑‍💻")
admin_page = st.Page("views/admin_center.py", title="Admin Command Center", icon="👑")
settings_page = st.Page("views/system_settings.py", title="System Settings", icon="⚙️")
superadmin_page = st.Page("views/superadmin_center.py", title="Super Admin Console", icon="🌍")
manual_page = st.Page("views/user_manual.py", title=t("User Manual", "ユーザーマニュアル"), icon="📖")

# Dynamic Navigation based on role
pages = []
if not st.session_state.logged_in:
    if st.query_params.get("admin") == "true" and not super_admin_disabled:
        pages = [super_login_page, manual_page]
    else:
        pages = [login_page, manual_page]
elif st.session_state.role == 'superadmin' and not super_admin_disabled:
    pages = [superadmin_page, manual_page]
elif st.session_state.role == 'admin':
    pages = [admin_page, team_page, leaderboard_page, settings_page, manual_page]
elif st.session_state.role == 'team':
    pages = [team_page, leaderboard_page, manual_page]
elif st.session_state.role == 'observer':
    pages = [team_page, leaderboard_page, manual_page]
else:
    # Fallback in case a superadmin session is active but now disabled
    pages = [login_page, manual_page]

pg = st.navigation(pages)
pg.run()

# Force restore query parameter after navigation routing is done
if st.session_state.get('logged_in') and st.session_state.get('sid'):
    st.query_params['sid'] = st.session_state.sid
