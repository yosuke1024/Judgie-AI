import streamlit as st
from core.db import init_db
from core.auth import init_session, verify_ip_address

# Enforce IP address firewall if ALLOWED_IPS is set in environment/secrets
verify_ip_address()

st.set_page_config(page_title="Judgie-AI | Hackathon Platform", page_icon="⚖️", layout="wide")

# Initialize DB and Session
init_db()
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

# Define Pages
login_page = st.Page("views/login.py", title="Login", icon="🔑")
super_login_page = st.Page("views/super_login.py", title="Super Admin Login", icon="🌍")
leaderboard_page = st.Page("views/leaderboard.py", title="Leaderboard", icon="🏆")
team_page = st.Page("views/team_view.py", title="Team Dashboard", icon="🧑‍💻")
admin_page = st.Page("views/admin_center.py", title="Admin Command Center", icon="👑")
settings_page = st.Page("views/system_settings.py", title="System Settings", icon="⚙️")
superadmin_page = st.Page("views/superadmin_center.py", title="Super Admin Console", icon="🌍")

# Dynamic Navigation based on role
pages = []
if not st.session_state.logged_in:
    if st.query_params.get("admin") == "true":
        pages = [super_login_page]
    else:
        pages = [login_page]
elif st.session_state.role == 'superadmin':
    pages = [superadmin_page]
elif st.session_state.role == 'admin':
    pages = [admin_page, team_page, leaderboard_page, settings_page]
elif st.session_state.role == 'team':
    pages = [team_page, leaderboard_page]

pg = st.navigation(pages)
pg.run()

# Force restore query parameter after navigation routing is done
if st.session_state.get('logged_in') and st.session_state.get('sid'):
    st.query_params['sid'] = st.session_state.sid
