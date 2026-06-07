import streamlit as st


def t(en: str, ja: str) -> str:
    """
    Central translation helper for billingual English/Japanese UI elements.
    Reads language setting dynamically from streamlit's session state.
    """
    lang = st.session_state.get('language', 'English')
    return en if lang == 'English' else ja
