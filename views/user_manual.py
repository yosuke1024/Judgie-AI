import os

import streamlit as st

from core.i18n import t

# Title and header
st.title(t("📖 User Manual", "📖 ユーザーマニュアル"))
st.caption(t("Guide on how to use Judgie-AI for all roles.", "Judgie-AIの全ロール向けの使い方ガイドです。"))

# Determine the manual file based on language
manual_file = (
    "docs/user_manual_en.md" if st.session_state.get("language", "English") == "English" else "docs/user_manual_ja.md"
)

if not os.path.exists(manual_file):
    st.error(
        t(
            f"Manual file not found at: `{manual_file}`. Please contact system administrator.",
            f"マニュアルファイルが見つかりません: `{manual_file}`。システム管理者へ連絡してください。",
        )
    )
else:
    try:
        with open(manual_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Display manual content
        st.markdown(content, unsafe_allow_html=True)
    except Exception as e:
        st.error(t(f"Error loading manual: {str(e)}", f"マニュアルの読み込み中にエラーが発生しました: {str(e)}"))
