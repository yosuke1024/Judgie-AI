import streamlit as st

from core.auth import require_login
from core.db import change_my_passcode, get_setting, set_setting
from core.i18n import t

require_login(required_role='admin')

st.set_page_config(page_title="System Settings - Judgie-AI", page_icon="⚙️", layout="wide")
st.title(t("⚙️ System Settings", "⚙️ システム設定"))

tab1, tab2 = st.tabs([
    t("🤖 Gemini Configuration", "🤖 Gemini設定"),
    t("🔒 Change Password", "🔒 パスワード変更")
])

current_h_id = st.session_state.get('active_hackathon_id')
is_demo = (current_h_id == 9999)
if not current_h_id:
    st.error(t("No active project selected.", "アクティブなプロジェクトがありません。"))
    st.stop()

# --- TAB 1: Gemini Config ---
with tab1:
    st.markdown(f"### {t('Gemini API Configuration', 'Gemini API 設定')}")
    current_key = get_setting(current_h_id, 'gemini_api_key')

    # Label is generic now since model can be changed
    api_key_input = st.text_input(t("Tenant Gemini API Key", "テナント用 Gemini APIキー"), type="password", value=current_key if current_key else "", disabled=is_demo)

    if st.button(t("Save & Validate API Key", "APIキーを検証して保存"), type="primary", key="save_api", disabled=is_demo):
        if api_key_input:
            with st.spinner(t("Validating key and fetching available models...", "キーの有効性を検証し、利用可能なモデルを取得中...")):
                try:
                    import json

                    from core.gemini import list_available_gemini_models

                    # Connection test by calling model listing
                    models = list_available_gemini_models(current_h_id, api_key_override=api_key_input)
                    if models:
                        set_setting(current_h_id, 'gemini_api_key', api_key_input)
                        set_setting(current_h_id, 'gemini_available_models', json.dumps(models))
                        st.success(t("API Key verified and saved successfully!", "APIキーの検証に成功し、設定が保存されました！"))
                        st.rerun()
                    else:
                        st.error(t("No supported models returned. Please check the key.", "対応するモデルが見つかりませんでした。キーを確認してください。"))
                except Exception as e:
                    st.error(t(f"Failed to validate API Key: {str(e)}", f"APIキーの検証に失敗しました。入力が正しいか確認してください: {str(e)}"))
        else:
            st.warning(t("Please enter an API key.", "APIキーを入力してください。"))

    if current_key:
        st.divider()
        st.markdown(f"### {t('Model & Plan Settings', 'モデルとプランの設定')}")

        # 1. Billing Tier configuration
        current_tier = get_setting(current_h_id, 'gemini_api_tier') or "Free Tier"
        api_tier = st.radio(
            t("API Key Plan Type", "APIキーのプランタイプ"),
            options=["Free Tier", "Paid Tier / Pay-as-you-go"],
            index=0 if current_tier == "Free Tier" else 1,
            horizontal=True,
            disabled=is_demo
        )

        if api_tier == "Free Tier":
            st.info(t(
                "⚠️ **Free Tier Active:** API Rate limits are very strict. Recommended models: `gemini-3.5-flash` or `gemini-3.1-flash-lite`.",
                "⚠️ **無料プラン:** 同時リクエスト制限が厳しいため、評価エラーを防ぐために軽量・高速な `gemini-3.5-flash` または `gemini-3.1-flash-lite` の利用をお勧めします。"
            ))
        else:
            st.success(t(
                "✨ **Paid Tier Active:** Higher rate limits. Recommended models: `gemini-3.5-flash` (fast/value) or `gemini-3.1-pro` (high-accuracy reasoning).",
                "✨ **有料プラン:** 制限が緩和されており、本番プロジェクト運用に適しています。`gemini-3.5-flash` (高速) または `gemini-3.1-pro` (高精度・コード審査向き) が推奨されます。"
            ))

        # 2. Dynamic model selection
        import json
        models_val = get_setting(current_h_id, 'gemini_available_models')
        if models_val:
            try:
                available_models = json.loads(models_val)
            except Exception:
                available_models = ["gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
        else:
            available_models = ["gemini-3.5-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite", "gemini-2.5-flash"]

        current_model = get_setting(current_h_id, 'gemini_model') or "gemini-2.5-flash"

        default_idx = 0
        if current_model in available_models:
            default_idx = available_models.index(current_model)
        elif "gemini-3.5-flash" in available_models:
            default_idx = available_models.index("gemini-3.5-flash")

        model_input = st.selectbox(
            t("Select Gemini Model", "Geminiモデルの選択"),
            options=available_models,
            index=default_idx,
            disabled=is_demo
        )

        if st.button(t("Save Model Settings", "モデル設定を保存"), type="primary", key="save_model_settings", disabled=is_demo):
            set_setting(current_h_id, 'gemini_model', model_input)
            set_setting(current_h_id, 'gemini_api_tier', api_tier)
            st.success(t("Model and plan settings updated!", "モデルおよびプラン設定が更新されました！"))
            st.rerun()

# --- TAB 2: Change Password ---
with tab2:
    st.markdown(f"### {t('Change Password', 'パスワード変更')}")
    st.caption(t("Change your administrator password.", "管理者のパスワードを変更します。"))
    if is_demo:
        st.caption(t("💡 Password change is disabled in Demo Mode.", "💡 デモモードではパスワード変更は無効化されています。"))
    with st.form("change_admin_pass_form"):
        curr_pass = st.text_input(t("Current Password", "現在のパスワード"), type="password", disabled=is_demo)
        new_pass = st.text_input(t("New Password", "新しいパスワード"), type="password", disabled=is_demo)
        if st.form_submit_button(t("Update Password", "パスワードを更新"), type="primary", disabled=is_demo):
            if not curr_pass or not new_pass:
                st.error(t("All fields required.", "すべて入力してください。"))
            else:
                success = change_my_passcode(current_h_id, st.session_state.team_id, curr_pass, new_pass)
                if success:
                    st.session_state.passcode = new_pass
                    st.success(t("Password updated!", "パスワードを更新しました！"))
                else:
                    st.error(t("Incorrect current password.", "現在のパスワードが間違っています。"))
