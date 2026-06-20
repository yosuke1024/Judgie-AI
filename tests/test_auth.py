import os

import pytest
import streamlit as st

from core.auth import init_session, login, login_by_email, logout, require_login, verify_ip_address


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

    verify_ip_address()  # Should not raise any errors


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
    st.query_params["sid"] = "valid-session-id"

    mock_session_data = {"role": "team", "team_id": "teamA", "hackathon_id": 1}
    mocker.patch("core.auth.get_session", return_value=mock_session_data)

    init_session()

    assert st.session_state.logged_in is True
    assert st.session_state.role == "team"
    assert st.session_state.team_id == "teamA"
    assert st.session_state.active_hackathon_id == 1
    assert st.session_state.sid == "valid-session-id"


def test_login_success(mocker, mock_streamlit):
    # Mock verify_user response
    mocker.patch("core.auth.verify_user", return_value={"role": "admin", "hackathon_id": 1})
    mocker.patch("core.auth.create_session", return_value="new-sid")

    res = login("admin1", "pass123", tenant_id=1)

    assert res is True
    assert st.session_state.logged_in is True
    assert st.session_state.role == "admin"
    assert st.session_state.sid == "new-sid"
    assert st.query_params["sid"] == "new-sid"


def test_login_failed(mocker, mock_streamlit):
    mocker.patch("core.auth.verify_user", return_value=None)
    init_session()

    res = login("admin1", "wrongpass")

    assert res is False
    assert st.session_state.logged_in is False


def test_logout(mocker, mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.sid = "active-sid"
    st.session_state.oidc_verified = True
    st.session_state.oidc_email = "test@example.com"
    st.session_state.oidc_state = "some-state"

    mock_delete = mocker.patch("core.auth.delete_session")

    with pytest.raises(SystemExit) as excinfo:
        logout()

    assert "Streamlit Rerun" in str(excinfo.value)
    mock_delete.assert_called_once_with("active-sid")
    assert st.session_state.logged_in is False
    assert st.session_state.sid is None
    assert st.session_state.oidc_verified is True
    assert st.session_state.oidc_email == "test@example.com"
    assert st.session_state.oidc_state == "some-state"


def test_require_login_authorized(mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.role = "admin"

    # Should proceed normally when authenticated with matching role
    require_login("admin")


def test_require_login_not_logged_in(mock_streamlit):
    st.session_state.logged_in = False

    with pytest.raises(SystemExit):
        require_login()


def test_require_login_wrong_role(mock_streamlit):
    st.session_state.logged_in = True
    st.session_state.role = "team"

    with pytest.raises(SystemExit):
        require_login("admin")


def test_login_by_email_success(mocker, mock_streamlit):
    # Mocking User class and db_session query
    mock_user = mocker.MagicMock()
    mock_user.team_id = "teamA"
    mock_user.role = "team"
    mock_user.hackathon_id = 1
    mock_user.email = "user@example.com"

    mock_db = mocker.MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    # Mock the context manager db_session
    mocker.patch("core.db.db_session", return_value=mocker.MagicMock(__enter__=mocker.MagicMock(return_value=mock_db)))
    mocker.patch("core.auth.create_session", return_value="new-sid")

    res = login_by_email("user@example.com")

    assert res is True
    assert st.session_state.logged_in is True
    assert st.session_state.role == "team"
    assert st.session_state.team_id == "teamA"
    assert st.session_state.active_hackathon_id == 1
    assert st.session_state.sid == "new-sid"


def test_login_by_email_not_found(mocker, mock_streamlit):
    mock_db = mocker.MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    mocker.patch("core.db.db_session", return_value=mocker.MagicMock(__enter__=mocker.MagicMock(return_value=mock_db)))

    res = login_by_email("unknown@example.com")

    assert res is False
    assert st.session_state.get("logged_in") is not True


def test_login_blocked_when_oidc_enabled(mocker, mock_streamlit):
    # Enable OIDC
    os.environ["OIDC_ENABLED"] = "true"

    try:
        res = login("admin", "pass123", tenant_id=1)
        assert res is False
        assert st.session_state.get("logged_in") is not True
    finally:
        del os.environ["OIDC_ENABLED"]

