import pytest
import os
import streamlit as st
from unittest.mock import MagicMock
from core.auth import (
    verify_ip_address, init_session, login, logout, require_login
)

@pytest.fixture(autouse=True)
def clear_env():
    # Clear ALLOWED_IPS environment variable before each test run
    if "ALLOWED_IPS" in os.environ:
        del os.environ["ALLOWED_IPS"]
    yield

def test_verify_ip_address_allowed(mock_streamlit):
    # Should proceed without errors when ALLOWED_IPS is not set
    verify_ip_address()
    
    # Case where the client IP is whitelisted
    os.environ["ALLOWED_IPS"] = "192.168.1.1,10.0.0.1"
    st.context.ip_address = "192.168.1.1"
    
    verify_ip_address() # Should not raise any errors

def test_verify_ip_address_denied(mock_streamlit):
    os.environ["ALLOWED_IPS"] = "192.168.1.1"
    st.context.ip_address = "203.0.113.1"
    
    # Access should be denied, causing Streamlit execution to stop
    with pytest.raises(SystemExit) as excinfo:
        verify_ip_address()
        
    assert "Streamlit Stop" in str(excinfo.value)

def test_init_session_new(mock_streamlit):
    # Test initial unauthenticated state setup
    init_session()
    
    assert st.session_state.logged_in is False
    assert st.session_state.role is None

def test_init_session_auto_login(mocker, mock_streamlit):
    # Test automatic login when 'sid' is present in query parameters and session is valid
    st.query_params['sid'] = 'valid-session-id'
    
    mock_session_data = {
        'role': 'team',
        'team_id': 'teamA',
        'hackathon_id': 1
    }
    mocker.patch("core.auth.get_session", return_value=mock_session_data)
    
    init_session()
    
    assert st.session_state.logged_in is True
    assert st.session_state.role == 'team'
    assert st.session_state.team_id == 'teamA'
    assert st.session_state.active_hackathon_id == 1
    assert st.session_state.sid == 'valid-session-id'

def test_login_success(mocker, mock_streamlit):
    # Mock verify_user response
    mocker.patch("core.auth.verify_user", return_value={'role': 'admin', 'hackathon_id': 1})
    mocker.patch("core.auth.create_session", return_value='new-sid')
    
    res = login("admin1", "pass123", tenant_id=1)
    
    assert res is True
    assert st.session_state.logged_in is True
    assert st.session_state.role == 'admin'
    assert st.session_state.sid == 'new-sid'
    assert st.query_params['sid'] == 'new-sid'

def test_login_failed(mocker, mock_streamlit):
    mocker.patch("core.auth.verify_user", return_value=None)
    init_session()
    
    res = login("admin1", "wrongpass")
    
    assert res is False
    assert st.session_state.logged_in is False

def test_logout(mocker, mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.sid = 'active-sid'
    
    mock_delete = mocker.patch("core.auth.delete_session")
    
    with pytest.raises(SystemExit) as excinfo:
        logout()
        
    assert "Streamlit Rerun" in str(excinfo.value)
    mock_delete.assert_called_once_with('active-sid')
    assert st.session_state.logged_in is False
    assert st.session_state.sid is None

def test_require_login_authorized(mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.role = 'admin'
    
    # Should proceed normally when authenticated with matching role
    require_login('admin')

def test_require_login_not_logged_in(mock_streamlit):
    st.session_state.logged_in = False
    
    with pytest.raises(SystemExit):
        require_login()

def test_require_login_wrong_role(mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.role = 'team'
    
    with pytest.raises(SystemExit):
        require_login('admin')
