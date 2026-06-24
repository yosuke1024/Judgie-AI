import os
import sys

import pytest

# Add the project root directory and backend directory to sys.path so the 'app' modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

# Import and mock the database engine
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models.db
import backend.app.models.db

# Setup test-specific in-memory SQLite database
test_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
test_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Replace backend.app.models.db engine and session maker with mock instances
backend.app.models.db.engine = test_engine
backend.app.models.db.SessionLocal = test_SessionLocal

# Also mock app.models.db directly to handle sys.path imports cleanly
app.models.db.engine = test_engine
app.models.db.SessionLocal = test_SessionLocal


@pytest.fixture(autouse=True)
def setup_db():
    """Create and drop database schemas for each test case."""
    app.models.db.Base.metadata.create_all(bind=test_engine)
    yield
    app.models.db.Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session_fixture():
    """Provide a clean transactional DB session for testing."""
    session = test_SessionLocal()
    try:
        yield session
    finally:
        session.close()
