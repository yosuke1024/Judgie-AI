import streamlit as st

from core.auth import login
from core.db import Hackathon, SessionLocal
from core.i18n import t

st.title(t("⚖️ Judgie-AI Login", "⚖️ Judgie-AI ログイン"))
st.markdown(t("Welcome to the AI-powered Project Evaluation Platform. Please log in.", "AIプロジェクト評価プラットフォームへようこそ。ログインしてください。"))

with st.container():
    st.subheader(t("Login", "ログイン"))

    db = SessionLocal()
    try:
        hackathons = db.query(Hackathon).order_by(Hackathon.id.desc()).all()
    finally:
        db.close()

    # Auto-seed demo data if no hackathons exist yet to prevent crash and show demo option
    if not hackathons:
        from core.db import seed_demo_data
        seed_demo_data()
        db = SessionLocal()
        try:
            hackathons = db.query(Hackathon).order_by(Hackathon.id.desc()).all()
        finally:
            db.close()

    # Exclude demo hackathon (ID: 9999) from the active login hackathons
    active_hackathons = [h for h in hackathons if h.id != 9999]

    if not active_hackathons:
        st.warning(t("No projects available yet. Please ask your super admin.", "現在参加できるプロジェクトがありません。"))
    elif len(active_hackathons) == 1:
        single_h = active_hackathons[0]
        tenant_id = single_h.id
        st.markdown(f"**{t('Project', 'プロジェクト')}:** {single_h.name}")

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
    else:
        h_options = {h.id: f"{h.name} (ID: {h.id})" for h in active_hackathons}

        # Determine pre-selected index based on URL query param
        tenant_param = st.query_params.get("tenant", "")
        default_index = 0
        if tenant_param.isdigit():
            tid = int(tenant_param)
            keys = list(h_options.keys())
            if tid in keys:
                default_index = keys.index(tid)

        tenant_id = st.selectbox(
            t("Select Project", "参加するプロジェクトを選択"),
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

    st.markdown("---")
    st.subheader(t("✨ Demo Experience", "✨ デモ体験"))
    st.markdown(t("Try Judgie-AI immediately without credentials or Gemini API keys. Safe read-only mode.", "ログイン情報やAPIキーの設定不要で、すぐにデモ画面を体験できます（安全な閲覧専用モード）。"))

    col_demo1, col_demo2 = st.columns(2)
    with col_demo1:
        if st.button(t("Try as Team (Participant)", "一般参加者として体験"), use_container_width=True):
            from core.db import seed_demo_data
            seed_demo_data()
            if login("demo_team", "demo123", tenant_id=9999):
                st.success(t("Redirecting to team dashboard...", "チームダッシュボードへリダイレクト中..."))
                st.rerun()
    with col_demo2:
        if st.button(t("Try as Admin (Host)", "管理者・ホストとして体験"), use_container_width=True):
            from core.db import seed_demo_data
            seed_demo_data()
            if login("demo_admin", "demo123", tenant_id=9999):
                st.success(t("Redirecting to admin console...", "管理コンソールへリダイレクト中..."))
                st.rerun()

    import os
    super_admin_disabled = os.environ.get("DEFAULT_ADMIN_ID") is not None
    if not super_admin_disabled:
        st.markdown("---")
        col_sa1, col_sa2 = st.columns([3, 1])
        with col_sa2:
            if st.button(t("🌍 Super Admin Login", "🌍 スーパー管理者"), key="go_to_super_admin", use_container_width=True):
                st.query_params["admin"] = "true"
                st.rerun()

