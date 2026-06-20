import os
import sys

import pytest

# Add the project root directory to sys.path so the 'core' module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Define Mock classes for Streamlit APIs
class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError as e:
            raise AttributeError(name) from e


class MockContext:
    def __init__(self):
        self.ip_address = None


class MockStreamlit:
    def __init__(self):
        self.session_state = MockSessionState()
        self.query_params = {}
        self.secrets = {}
        self.context = MockContext()

    def error(self, msg):
        pass

    def success(self, msg):
        pass

    def warning(self, msg):
        pass

    def info(self, msg):
        pass

    def stop(self):
        raise SystemExit("Streamlit Stop")

    def rerun(self):
        raise SystemExit("Streamlit Rerun")


# Inject the mock streamlit module into sys.modules before any imports occur
mock_st = MockStreamlit()
sys.modules["streamlit"] = mock_st

# Import core.db and mock the database engine
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import core.db  # noqa: E402

# Setup test-specific in-memory SQLite database
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
test_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Replace core.db engine and session maker with mock instances
core.db.engine = test_engine
core.db.SessionLocal = test_SessionLocal


@pytest.fixture(autouse=True)
def setup_db():
    """Create and drop database schemas for each test case."""
    core.db.Base.metadata.create_all(bind=test_engine)
    yield
    core.db.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session_fixture():
    """Provide a clean transactional DB session for testing."""
    session = test_SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def mock_streamlit():
    """Clear Streamlit mock state for each test run."""
    mock_st.session_state.clear()
    mock_st.query_params.clear()
    mock_st.secrets.clear()
    return mock_st
