import streamlit as st
from core.auth import login
from core.db import SessionLocal, Hackathon
from core.i18n import t

st.title(t("⚖️ Judgie-AI Login", "⚖️ Judgie-AI ログイン"))
st.markdown(t("Welcome to the AI-powered Hackathon Platform. Please log in.", "AIハッカソンプラットフォームへようこそ。ログインしてください。"))

with st.container():
    st.subheader(t("Login", "ログイン"))
    
    db = SessionLocal()
    try:
        hackathons = db.query(Hackathon).order_by(Hackathon.id.desc()).all()
    finally:
        db.close()
        
    if not hackathons:
        st.warning(t("No hackathons available yet. Please ask your super admin.", "現在参加できるハッカソンがありません。"))
        st.stop()
        
    h_options = {h.id: f"{h.name} (ID: {h.id})" for h in hackathons}
    
    # Determine pre-selected index based on URL query param
    tenant_param = st.query_params.get("tenant", "")
    default_index = 0
    if tenant_param.isdigit():
        tid = int(tenant_param)
        keys = list(h_options.keys())
        if tid in keys:
            default_index = keys.index(tid)
            
    tenant_id = st.selectbox(
        t("Select Hackathon", "参加するハッカソンを選択"), 
        options=list(h_options.keys()), 
        format_func=lambda x: h_options[x],
        index=default_index
    )
    team_id = st.text_input(t("Team ID / Admin ID", "チームID / 管理者ID"), placeholder="e.g. team01 or admin")
    passcode = st.text_input(t("Passcode", "パスコード"), type="password")
    
    if st.button(t("Log In", "ログイン"), type="primary", use_container_width=True):
        if not team_id or not passcode:
            st.warning(t("Please enter all fields.", "すべての項目を入力してください。"))
        elif login(team_id, passcode, tenant_id=tenant_id):
            st.success(t("Login successful! Redirecting...", "ログイン成功！リダイレクト中..."))
            st.rerun()
        else:
            st.error(t("Invalid ID or Passcode.", "IDまたはパスコードが間違っています。"))
