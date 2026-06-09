import os

# 'local' or 'production'
APP_ENV = os.environ.get("APP_ENV", "local")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

if APP_ENV == "production":
    # Production database URL from environment variable
    # e.g., postgresql://user:pass@host:port/dbname or sqlite:////app/data/judgie.db
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
    # Ensure data directory exists and is writable (fall back to /tmp on read-only filesystems like Streamlit Cloud)
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
