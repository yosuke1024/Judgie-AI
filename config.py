import os

# 'local' or 'production'
APP_ENV = os.environ.get("APP_ENV", "local")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

if APP_ENV == "production":
    # Production database URL from environment variable
    # e.g., postgresql://user:pass@host:port/dbname
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable must be set in production")
else:
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(DATA_DIR, "judgie.db")
    DATABASE_URL = f"sqlite:///{DB_PATH}"

# App Settings
MAX_CONSULTATIONS = 3
TEAM_COUNT_FOR_SEED = 17

# Scoring Weights
SCORING_WEIGHTS = {
    "Innovation": 0.20,
    "Technical Implementation": 0.20,
    "Problem Solving & Impact": 0.20,
    "Product & UX": 0.15,
    "Working Prototype": 0.15,
    "Presentation": 0.10
}
