"""
Application configuration for FastAPI backend.
Reads from environment variables with sensible defaults for local development.
"""

import os

# 'local' or 'production'
APP_ENV = os.environ.get("APP_ENV", "local")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# --- Database ---
if APP_ENV == "production":
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set in production")

    # If DATABASE_URL is SQLite, ensure target directory exists
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        if db_path.startswith("/"):
            db_dir = os.path.dirname(db_path)
        else:
            db_dir = os.path.dirname(os.path.join(BASE_DIR, db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
else:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        test_file = os.path.join(DATA_DIR, ".write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        DB_PATH = os.path.join(DATA_DIR, "judgie.db")
    except (IOError, OSError):
        DB_PATH = "/tmp/judgie.db"
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# --- JWT Auth ---
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "720"))  # 12 hours

# --- OIDC Auth ---
OIDC_ENABLED = os.environ.get("OIDC_ENABLED", "false").lower() == "true"
OIDC_ISSUER = os.environ.get("OIDC_ISSUER", "https://accounts.google.com")
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "")
OIDC_REDIRECT_URI = os.environ.get("OIDC_REDIRECT_URI", "http://localhost:5173/login/callback")
OIDC_ALLOWED_DOMAINS = [d.strip() for d in os.environ.get("OIDC_ALLOWED_DOMAINS", "").split(",") if d.strip()]
OIDC_ALLOWED_EMAILS = [e.strip() for e in os.environ.get("OIDC_ALLOWED_EMAILS", "").split(",") if e.strip()]

# --- CORS ---
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

# --- App Settings ---
MAX_CONSULTATIONS = 3
TEAM_COUNT_FOR_SEED = 17

SCORING_WEIGHTS = {
    "Innovation": 0.20,
    "Technical Implementation": 0.20,
    "Problem Solving & Impact": 0.20,
    "Product & UX": 0.15,
    "Working Prototype": 0.15,
    "Presentation": 0.10,
}

# --- Templates directory ---
# Resolve dynamically to support both local dev and Docker context
_HERE = os.path.abspath(__file__)
_DIR = _HERE
TEMPLATES_DIR = None
for _ in range(5):
    _DIR = os.path.dirname(_DIR)
    _potential = os.path.join(_DIR, "templates")
    if os.path.exists(_potential) and os.path.isdir(_potential):
        TEMPLATES_DIR = _potential
        break

if not TEMPLATES_DIR:
    TEMPLATES_DIR = os.path.join(os.path.dirname(BASE_DIR), "templates")

# --- LLM Providers ---
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()
LLM_MODEL = os.environ.get("LLM_MODEL")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
