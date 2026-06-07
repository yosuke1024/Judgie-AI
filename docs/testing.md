# Testing Guide

This project uses `pytest` for running automated tests to ensure code quality and robustness. 
We focus on testing the core business logic located in the `core/` directory.

---

## 1. Setup

Before running tests, install the development and testing dependencies in your virtual environment:

```bash
# Activate your virtual environment (adjust according to your shell)
source venv/bin/activate

# Install development and testing dependencies
pip install -r requirements-dev.txt
```

---

## 2. Running Tests

### Run all tests
Execute the following command in the root directory:

```bash
pytest
```

### Run a specific test file
To run a specific test file, specify its path:

```bash
pytest tests/test_security.py
```

---

## 3. Test Coverage

We use `pytest-cov` to measure how much of the codebase is covered by tests.

### Show coverage summary in terminal
Run the following command to calculate coverage for the `core/` package:

```bash
pytest --cov=core tests/
```

### Generate HTML coverage report
To generate a visual HTML report detailing which lines are tested, run:

```bash
pytest --cov=core --cov-report=html tests/
```

This will create an `htmlcov/` directory in the project root. Open `htmlcov/index.html` in your browser to view the detailed coverage report file by file.

---

## 4. Test Design & Mocking Strategy

To make tests fast, reliable, and runnable without external service configurations, we employ the following strategies:

- **In-Memory SQLite Database**:
  Database operations (`core/db.py`) are tested using an in-memory SQLite database (`sqlite:///:memory:`). This is configured in `tests/conftest.py` to prevent modifying any local files during testing.
- **Streamlit Mocking**:
  Streamlit-specific APIs, such as `st.session_state` and `st.query_params`, are replaced with mock objects. This allows testing Streamlit-dependent logic outside the Streamlit server lifecycle.
- **Gemini API Mocking**:
  All interactions with the Google Generative AI API (`core/gemini.py`) are mocked using `pytest-mock`. Tests do not make network requests and will work without a Gemini API key.
