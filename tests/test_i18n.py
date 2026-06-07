import streamlit as st

from core.i18n import t


def test_t_default_english(mock_streamlit):
    # Fallback to English when session_state has no language set
    assert t("Hello", "こんにちは") == "Hello"

def test_t_english(mock_streamlit):
    st.session_state['language'] = 'English'
    assert t("Hello", "こんにちは") == "Hello"

def test_t_japanese(mock_streamlit):
    st.session_state['language'] = 'Japanese'
    assert t("Hello", "こんにちは") == "こんにちは"
