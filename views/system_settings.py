import streamlit as st
import pandas as pd
from core.auth import require_login
from core.db import get_setting, set_setting, change_my_passcode

require_login(required_role='admin')

lang = st.session_state.get('language', 'English')
def t(en, ja): return en if lang == "English" else ja

st.set_page_config(page_title="System Settings - Judgie-AI", page_icon="⚙️", layout="wide")
st.title(t("⚙️ System Settings", "⚙️ システム設定"))

tab1, tab2 = st.tabs([
    t("🔑 API Key", "🔑 APIキー"),
    t("🔒 Change Password", "🔒 パスワード変更")
])

current_h_id = st.session_state.get('active_hackathon_id')
if not current_h_id:
    st.error(t("No active hackathon selected.", "アクティブなハッカソンがありません。"))
    st.stop()

# --- TAB 1: API Key ---
with tab1:
    st.markdown(f"### {t('Gemini API Configuration', 'Gemini API 設定')}")
    current_key = get_setting(current_h_id, 'gemini_api_key')
    api_key_input = st.text_input(t("Tenant Gemini 3.1 Pro API Key", "テナント用 Gemini 3.1 Pro APIキー"), type="password", value=current_key if current_key else "")
    if st.button(t("Save API Key", "APIキーを保存"), type="primary", key="save_api"):
        if api_key_input:
            set_setting(current_h_id, 'gemini_api_key', api_key_input)
            st.success(t("API Key saved for this hackathon!", "このハッカソンのAPIキーが保存されました！"))

# --- TAB 2: Change Password ---
with tab2:
    st.markdown(f"### {t('Change Password', 'パスワード変更')}")
    st.caption(t("Change your administrator password.", "管理者のパスワードを変更します。"))
    with st.form("change_admin_pass_form"):
        curr_pass = st.text_input(t("Current Password", "現在のパスワード"), type="password")
        new_pass = st.text_input(t("New Password", "新しいパスワード"), type="password")
        if st.form_submit_button(t("Update Password", "パスワードを更新"), type="primary"):
            if not curr_pass or not new_pass:
                st.error(t("All fields required.", "すべて入力してください。"))
            else:
                success = change_my_passcode(current_h_id, st.session_state.team_id, curr_pass, new_pass)
                if success:
                    st.session_state.passcode = new_pass
                    st.success(t("Password updated!", "パスワードを更新しました！"))
                else:
                    st.error(t("Incorrect current password.", "現在のパスワードが間違っています。"))
