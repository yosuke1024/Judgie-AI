import streamlit as st
from core.auth import login
from core.i18n import t

st.title(t("🌍 Super Admin Console Access", "🌍 スーパー管理者 ログイン"))
st.markdown(t("Platform administration login.", "プラットフォーム管理用の専用ログイン画面です。"))

with st.container(border=True):
    st.subheader("Super Admin Authentication")
    team_id = "superadmin"
    passcode = st.text_input(t("Passcode", "パスコード"), type="password")
    
    if st.button(t("Log In", "ログイン"), type="primary", use_container_width=True):
        if not passcode:
            st.warning(t("Please enter the passcode.", "パスコードを入力してください。"))
        elif login(team_id, passcode, tenant_id=None):
            st.success(t("Login successful! Redirecting...", "ログイン成功！リダイレクト中..."))
            st.query_params.clear()
            st.rerun()
        else:
            st.error(t("Invalid Passcode.", "パスコードが間違っています。"))
            
st.markdown("---")
if st.button(t("← Back to Normal Login", "← 通常のログイン画面に戻る")):
    st.query_params.clear()
    st.rerun()
