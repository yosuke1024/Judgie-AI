import streamlit as st

from core.i18n import t
from core.ui_utils import get_avatar_html


def render_judge_feedback_tab(feedback_data: dict, avatar_map: dict, lang: str):
    """
    Renders judge feedback cards, scores breakdown for each judge, and detailed evaluations.
    Supports dynamic multilingual rendering based on configured languages.
    """
    from core.db import normalize_lang_to_key
    judges = feedback_data.get('judges_feedback', [])
    if not judges:
        st.write(t("No specific judges feedback provided.", "審査員からの詳細なフィードバックはありません。"))
        return

    for j in judges:
        j_name = j.get('judge_name', 'Judge')
        j_icon = avatar_map.get(j_name, '🧑‍⚖️')
        j_role = j.get('judge_role', 'Expert Panelist')
        j_persona = j.get('judge_persona', '')

        # Determine language-specific feedback key dynamically
        lang_key = normalize_lang_to_key(lang)
        feedback_text = j.get(f'feedback_{lang_key}')
        if feedback_text is None:
            fallback_keys = ['feedback_en', 'feedback_ja']
            for fk in fallback_keys:
                feedback_text = j.get(fk)
                if feedback_text:
                    break
            if not feedback_text:
                for k, v in j.items():
                    if k.startswith("feedback_"):
                        feedback_text = v
                        break
            if not feedback_text:
                feedback_text = f"No detailed feedback available in {lang}."

        with st.expander(f"{j_name} - {j_role}", expanded=True):
            # Render avatar and persona summary
            avatar_html = get_avatar_html(j_name, j_icon, size=40)
            st.markdown(
                f'<div style="display: flex; align-items: center; margin-bottom: 10px;">'
                f'  {avatar_html}'
                f'  <div>'
                f'    <strong style="font-size: 1.1em;">{j_name}</strong><br>'
                f'    <span style="font-size: 0.8em; color: gray;">{j_persona}</span>'
                f'  </div>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Display individual judge scores if present
            j_scores = j.get('judge_scores', [])
            if j_scores:
                score_html = '<div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; padding: 10px; background-color: rgba(255,255,255,0.05); border-radius: 5px;">'
                for s_item in j_scores:
                    c_name = s_item.get('criteria_name', '')
                    s_val = s_item.get('score', 0)
                    color = "#4CAF50" if s_val >= 4 else "#FF9800" if s_val >= 3 else "#F44336"
                    score_html += f'<div style="flex: 1; min-width: 120px;"><div style="font-size: 0.75em; color: gray;">{c_name}</div><div style="font-weight: bold; color: {color};">{s_val} / 5.0</div></div>'
                score_html += '</div>'
                st.markdown(score_html, unsafe_allow_html=True)

            st.write(feedback_text)
