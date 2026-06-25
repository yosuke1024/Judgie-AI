"""
SQLAlchemy models and CRUD operations.
Adapted from the original core/db.py with Streamlit dependencies removed.
"""

import json
import os
import re
import uuid
from contextlib import contextmanager

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import DATABASE_URL


def normalize_lang_to_key(lang_name: str) -> str:
    """Normalize a language name to a safe key for use in JSON fields."""
    cleaned = lang_name.replace("-", " ")
    safe_name = re.sub(r"[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]", "", cleaned)
    safe_name = re.sub(r"\s+", "_", safe_name).strip().lower()
    if not safe_name:
        safe_name = "lang_" + str(hash(lang_name) % 1000)
    return safe_name


# --- Engine & Session ---

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ──────────────────────────────────────────────
# ORM Models
# ──────────────────────────────────────────────


class User(Base):
    """Individual user account — the identity unit."""

    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=True, unique=True)
    password_hash = Column(String, nullable=True)  # NULL = SSO-only user
    display_name = Column(String, nullable=True)
    role = Column(String, nullable=False)  # 'admin', 'team', 'observer'
    is_active = Column(Boolean, default=True, nullable=False)

    memberships = relationship("TeamMembership", back_populates="user", cascade="all, delete-orphan")


class Team(Base):
    """Team profile — the unit for submissions and evaluations."""

    __tablename__ = "teams"
    team_id = Column(String, primary_key=True)
    product_name = Column(String, nullable=True)
    team_name = Column(String, nullable=True)
    one_liner = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    memberships = relationship("TeamMembership", back_populates="team", cascade="all, delete-orphan")


class TeamMembership(Base):
    """Links a user to a team."""

    __tablename__ = "team_memberships"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(String, ForeignKey("teams.team_id"), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_user_team"),)

    user = relationship("User", back_populates="memberships")
    team = relationship("Team", back_populates="memberships")


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(String, nullable=False)
    files_json = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=func.now())


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(String, nullable=False)
    scores_json = Column(Text, nullable=False)
    impact_score = Column(Float, nullable=False)
    strengths_risks_json = Column(Text, nullable=False)
    qa_json = Column(Text)
    is_final = Column(Boolean, default=False)
    source_text = Column(Text)
    gemini_file_ids = Column(Text)
    evaluated_at = Column(DateTime, default=func.now())


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now())


class AdminChat(Base):
    __tablename__ = "admin_chats"
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    question_en = Column(Text, nullable=True)
    question_ja = Column(Text, nullable=True)
    answer_en = Column(Text, nullable=True)
    answer_ja = Column(Text, nullable=True)
    qa_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())


class TeamChat(Base):
    __tablename__ = "team_chats"
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    sender = Column(String, nullable=False)  # 'team' or 'judges'
    message_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())


class AsyncTask(Base):
    """Tracks long-running background tasks (submissions, objections, admin chat)."""

    __tablename__ = "async_tasks"
    task_id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False)
    task_type = Column(String, nullable=False)  # 'submission', 'objection', 'admin_chat'
    status = Column(String, nullable=False, default="PENDING")  # PENDING, PROCESSING, SUCCESS, FAILED
    error_message = Column(Text, nullable=True)
    result_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


# ──────────────────────────────────────────────
# Session helpers
# ──────────────────────────────────────────────


@contextmanager
def db_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ──────────────────────────────────────────────
# Schema Migrations
# ──────────────────────────────────────────────


def _table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = conn.execute(text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';"))
    return result.fetchone() is not None


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = conn.execute(text(f"PRAGMA table_info({table_name});"))
    columns = [row[1] for row in result.fetchall()]
    return column_name in columns


def init_db():
    """Create tables and run dynamic schema migrations."""
    from app.security import hash_passcode

    # --- Legacy migration: old 'users' or 'teams' table (shared passcode model) ---
    # We need to handle:
    # 1. Old 'users' table (pre-rename)
    # 2. Old 'teams' table (post-rename but still shared-passcode model with passcode/role columns)
    # In both cases, we migrate data to the new 'users' + 'teams' + 'team_memberships' model.

    with engine.begin() as conn:
        old_users_exist = _table_exists(conn, "users")
        old_teams_exist = _table_exists(conn, "teams")

        # Determine if we need migration: check if old teams table has 'passcode' column
        needs_migration = False
        legacy_table = None

        if old_teams_exist and _column_exists(conn, "teams", "passcode"):
            needs_migration = True
            legacy_table = "teams"
        elif old_users_exist and _column_exists(conn, "users", "passcode"):
            needs_migration = True
            legacy_table = "users"

        if needs_migration and legacy_table:
            # Read legacy data before dropping
            rows = conn.execute(text(f"SELECT team_id, passcode, role, product_name, team_name, one_liner, is_active FROM {legacy_table}")).fetchall()

            # Read legacy team_members if they exist
            legacy_members = []
            if _table_exists(conn, "team_members"):
                legacy_members = conn.execute(text("SELECT team_id, email FROM team_members")).fetchall()

            # Drop old tables to recreate with new schema
            conn.execute(text("DROP TABLE IF EXISTS team_members;"))
            conn.execute(text(f"DROP TABLE IF EXISTS {legacy_table};"))

            # Recreate with new schema
            Base.metadata.create_all(bind=engine)

            # Migrate data
            for row in rows:
                old_team_id, old_passcode, old_role, product_name, team_name, one_liner, is_active = row

                if old_role == "admin":
                    # Create admin as a User (skip if admin env vars will handle it)
                    pass
                else:
                    # Create team profile
                    try:
                        conn.execute(
                            text("INSERT INTO teams (team_id, product_name, team_name, one_liner, is_active) VALUES (:tid, :pn, :tn, :ol, :ia)"),
                            {"tid": old_team_id, "pn": product_name, "tn": team_name, "ol": one_liner, "ia": is_active if is_active is not None else True},
                        )
                    except Exception:
                        pass  # Team might already exist

            # Migrate team_members as Users
            for member_row in legacy_members:
                member_team_id, member_email = member_row
                try:
                    # Find which role this team had
                    team_role = "team"
                    for row in rows:
                        if row[0] == member_team_id:
                            team_role = row[2] if row[2] in ("team", "observer") else "team"
                            break

                    conn.execute(
                        text("INSERT INTO users (email, password_hash, display_name, role, is_active) VALUES (:email, NULL, NULL, :role, 1)"),
                        {"email": member_email, "role": team_role},
                    )
                    # Get the user id
                    user_row = conn.execute(text("SELECT id FROM users WHERE email = :email"), {"email": member_email}).fetchone()
                    if user_row:
                        conn.execute(
                            text("INSERT INTO team_memberships (user_id, team_id) VALUES (:uid, :tid)"),
                            {"uid": user_row[0], "tid": member_team_id},
                        )
                except Exception:
                    pass  # Skip duplicate emails
        else:
            # No migration needed — just create tables
            Base.metadata.create_all(bind=engine)

    # Additional column migrations for existing databases
    migration_statements = [
        "ALTER TABLE admin_chats ADD COLUMN qa_json TEXT;",
    ]
    for stmt in migration_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass

    # Migrate username column
    with engine.begin() as conn:
        if not _column_exists(conn, "users", "username"):
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN username TEXT;"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users (username) WHERE username IS NOT NULL;"))
            except Exception:
                pass

    # Seed default admin user and settings
    with db_session() as db:
        # Support both DEFAULT_ADMIN_ID and DEFAULT_ADMIN_EMAIL. Fallback to "admin@example.com".
        default_admin_id = os.environ.get("DEFAULT_ADMIN_ID") or os.environ.get("DEFAULT_ADMIN_EMAIL") or "admin@example.com"
        
        # Support both DEFAULT_ADMIN_PASSCODE and DEFAULT_ADMIN_PASSWORD. Fallback to "admin123".
        default_admin_pass = os.environ.get("DEFAULT_ADMIN_PASSCODE") or os.environ.get("DEFAULT_ADMIN_PASSWORD") or "admin123"

        # Seed project settings in settings table
        project_name = os.environ.get("DEFAULT_PROJECT_NAME") or os.environ.get("DEFAULT_HACKATHON_NAME") or "Default Project"
        if not get_setting("project_name"):
            set_setting("project_name", project_name, db=db)
            set_setting("re_evaluation_context_mode", "cumulative", db=db)
            set_setting("max_qa_turns", "1", db=db)
            set_setting("max_consultations", "3", db=db)
            set_setting("video_upload_enabled", "true", db=db)

        # Look up admin by either email or username/ID
        admin_user = db.query(User).filter(
            (User.email == default_admin_id) | (User.username == default_admin_id)
        ).first()

        if not admin_user:
            is_email = "@" in default_admin_id
            admin_user = User(
                email=default_admin_id if is_email else f"{default_admin_id}@example.com",
                username=None if is_email else default_admin_id,
                password_hash=hash_passcode(default_admin_pass),
                display_name="Admin",
                role="admin",
            )
            db.add(admin_user)
            db.flush()


# ──────────────────────────────────────────────
# CRUD Functions
# ──────────────────────────────────────────────


def verify_user(identifier: str, password: str) -> dict | None:
    """Verify user credentials by email or username + password. Returns user info dict if valid."""
    from app.security import verify_passcode

    with db_session() as db:
        user = db.query(User).filter(
            ((User.email == identifier) | (User.username == identifier)),
            User.is_active
        ).first()
        if not user or not user.password_hash:
            return None
        if verify_passcode(password, user.password_hash):
            # Look up team membership
            membership = db.query(TeamMembership).filter(TeamMembership.user_id == user.id).first()
            return {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "display_name": user.display_name,
                "team_id": membership.team_id if membership else None,
            }
        return None


def get_user_by_identifier(identifier: str) -> dict | None:
    """Look up a user by email or username. Returns user info dict or None."""
    with db_session() as db:
        user = db.query(User).filter((User.email == identifier) | (User.username == identifier)).first()
        if not user:
            return None
        membership = db.query(TeamMembership).filter(TeamMembership.user_id == user.id).first()
        return {
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "team_id": membership.team_id if membership else None,
        }


def get_user_by_email(email: str) -> dict | None:
    """Look up a user by email. Returns user info dict or None."""
    return get_user_by_identifier(email)


def get_consultation_count(team_id: str) -> int:
    with db_session() as db:
        return db.query(Evaluation).filter(Evaluation.team_id == team_id).count()


def save_evaluation(
    team_id: str,
    result_json: dict,
    is_final: bool = False,
    source_text: str = None,
    gemini_file_ids: list = None,
):
    with db_session() as db:
        scores_json = json.dumps(result_json.get("scores", {}))
        impact_score = result_json.get("impact_score", 0.0)

        strengths_risks = {"judges_feedback": result_json.get("judges_feedback", [])}
        for k, v in result_json.items():
            if k.startswith("product_understanding_"):
                lang_key = k.replace("product_understanding_", "")
                strengths_risks[f"summary_{lang_key}"] = v
            elif k.startswith("three_line_summary_"):
                lang_key = k.replace("three_line_summary_", "")
                strengths_risks[f"summary_{lang_key}"] = v

        file_ids_json = json.dumps(gemini_file_ids) if gemini_file_ids else None

        eval_record = Evaluation(
            team_id=team_id,
            scores_json=scores_json,
            impact_score=impact_score,
            strengths_risks_json=json.dumps(strengths_risks),
            is_final=is_final,
            source_text=source_text,
            gemini_file_ids=file_ids_json,
        )
        db.add(eval_record)


def save_objection_qa(evaluation_id: int, qa_json: dict):
    with db_session() as db:
        eval_record = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if eval_record:
            eval_record.qa_json = json.dumps(qa_json)


# --- Settings CRUD ---


def get_setting(key: str) -> str | None:
    with db_session() as db:
        setting = db.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else None


def set_setting(key: str, value: str, db=None):
    def _execute(session):
        setting = session.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(key=key, value=value))

    if db is not None:
        _execute(db)
    else:
        with db_session() as new_db:
            _execute(new_db)


def get_ai_response_languages() -> list[str]:
    val = get_setting("ai_response_languages")
    if val:
        try:
            return json.loads(val)
        except Exception:
            pass
    return ["English", "Japanese"]


def set_ai_response_languages(languages: list[str], db=None):
    set_setting("ai_response_languages", json.dumps(languages), db=db)


def is_video_upload_enabled() -> bool:
    val = get_setting("video_upload_enabled")
    return val != "false"


def set_video_upload_enabled(enabled: bool, db=None):
    set_setting("video_upload_enabled", "true" if enabled else "false", db=db)


def get_criteria():
    from app.services.templates import TEMPLATES

    val = get_setting("evaluation_criteria")
    if val:
        return json.loads(val)

    template_id = get_setting("template_id")
    if template_id:
        tpl = TEMPLATES.get(template_id)
        if tpl:
            return tpl.get("criteria", [])
    return TEMPLATES.get("hackathon", {}).get("criteria", [])


def set_criteria(criteria_list, db=None):
    set_setting("evaluation_criteria", json.dumps(criteria_list), db=db)


def get_personas():
    from app.services.templates import TEMPLATES

    val = get_setting("judges_personas")
    if val:
        personas = json.loads(val)
    else:
        template_id = get_setting("template_id")
        if template_id:
            tpl = TEMPLATES.get(template_id)
            if tpl:
                personas = tpl.get("personas", [])
            else:
                personas = []
        else:
            personas = TEMPLATES.get("hackathon", {}).get("personas", [])

    # Automatically resolve custom avatar image from assets/avatars/ if not set
    import base64

    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = current_dir
    for _ in range(5):
        if os.path.exists(os.path.join(base_dir, "assets", "avatars")):
            break
        parent = os.path.dirname(base_dir)
        if parent == base_dir:
            break
        base_dir = parent
    avatars_dir = os.path.join(base_dir, "assets", "avatars")

    for p in personas:
        if isinstance(p, dict) and not p.get("avatar_image") and p.get("name"):
            name_lower = p["name"].lower()
            for ext in [".png", ".jpg", ".jpeg"]:
                avatar_path = os.path.join(avatars_dir, f"{name_lower}{ext}")
                if os.path.exists(avatar_path):
                    try:
                        with open(avatar_path, "rb") as f:
                            encoded = base64.b64encode(f.read()).decode("utf-8")
                        mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
                        p["avatar_image"] = f"data:{mime};base64,{encoded}"
                        break
                    except Exception:
                        pass

    return personas


def set_personas(personas_list, db=None):
    set_setting("judges_personas", json.dumps(personas_list), db=db)


def get_re_evaluation_context_mode() -> str:
    val = get_setting("re_evaluation_context_mode")
    return val if val else "cumulative"


def set_re_evaluation_context_mode(mode: str):
    set_setting("re_evaluation_context_mode", mode)


def get_max_qa_turns() -> int:
    val = get_setting("max_qa_turns")
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return 1


def set_max_qa_turns(turns: int):
    set_setting("max_qa_turns", str(turns))


def get_max_consultations() -> int:
    val = get_setting("max_consultations")
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return 3


def set_max_consultations(max_consultations: int):
    set_setting("max_consultations", str(max_consultations))


def initialize_project_template(template_id: str, custom_template_data: dict = None):
    from app.services.templates import TEMPLATES

    with db_session() as db:
        selected_criteria = None
        selected_personas = None
        re_eval_mode = "cumulative"
        max_qa = 1
        max_cons = 3

        if custom_template_data:
            selected_criteria = custom_template_data.get("criteria")
            selected_personas = custom_template_data.get("personas")
            re_eval_mode = custom_template_data.get("re_evaluation_context_mode", "cumulative")
            max_qa = custom_template_data.get("max_qa_turns", 1)
            max_cons = custom_template_data.get("max_consultations", 3)
        elif template_id in TEMPLATES:
            tpl = TEMPLATES[template_id]
            selected_criteria = tpl.get("criteria")
            selected_personas = tpl.get("personas")
            re_eval_mode = tpl.get("re_evaluation_context_mode", "cumulative")
            max_qa = tpl.get("max_qa_turns", 1)
            max_cons = tpl.get("max_consultations", 3)
        else:
            raise ValueError(f"Invalid template ID: {template_id}")

        set_setting("template_id", template_id, db=db)
        set_setting("re_evaluation_context_mode", re_eval_mode, db=db)
        set_setting("max_qa_turns", str(max_qa), db=db)
        set_setting("max_consultations", str(max_cons), db=db)

        set_personas(selected_personas, db=db)
        set_criteria(selected_criteria, db=db)
        set_ai_response_languages(["English", "Japanese"], db=db)


# --- User CRUD ---


def update_admin_password(new_password: str):
    from app.security import hash_passcode

    with db_session() as db:
        admin_user = db.query(User).filter(User.role == "admin").first()
        if admin_user:
            admin_user.password_hash = hash_passcode(new_password)


def update_user_password(user_id: int, new_password: str) -> bool:
    from app.security import hash_passcode

    with db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.password_hash = hash_passcode(new_password)
            return True
        return False


def change_my_password(
    email: str = None,
    current_password: str = None,
    new_password: str = None,
) -> bool:
    from app.security import hash_passcode, verify_passcode

    with db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if user and user.password_hash and verify_passcode(current_password, user.password_hash):
            user.password_hash = hash_passcode(new_password)
            return True
        return False


def get_team_profile(team_id: str) -> dict:
    with db_session() as db:
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if team:
            return {
                "product_name": team.product_name,
                "team_name": team.team_name,
                "one_liner": team.one_liner,
            }
        return {"product_name": None, "team_name": None, "one_liner": None}


def update_team_profile(team_id: str, product_name: str, team_name: str, one_liner: str):
    with db_session() as db:
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if team:
            team.product_name = product_name
            team.team_name = team_name
            team.one_liner = one_liner


def update_team_active(team_id: str, is_active: bool) -> bool:
    with db_session() as db:
        team = db.query(Team).filter(Team.team_id == team_id).first()
        if team:
            team.is_active = is_active
            return True
        return False


# --- Session CRUD ---


def create_session(team_id: str, role: str) -> str:
    with db_session() as db:
        session_id = str(uuid.uuid4())
        db.add(Session(session_id=session_id, team_id=team_id, role=role))
        return session_id


def get_session(session_id: str) -> dict | None:
    if not session_id:
        return None
    with db_session() as db:
        record = db.query(Session).filter(Session.session_id == session_id).first()
        if record:
            return {
                "team_id": record.team_id,
                "role": record.role,
            }
        return None


def delete_session(session_id: str):
    if not session_id:
        return
    with db_session() as db:
        record = db.query(Session).filter(Session.session_id == session_id).first()
        if record:
            db.delete(record)


# --- Chat CRUD ---


def save_admin_chat(
    evaluation_id: int,
    question_en: str,
    question_ja: str,
    answer_en: str,
    answer_ja: str,
    qa_json: dict = None,
) -> AdminChat:
    with db_session() as db:
        chat = AdminChat(
            evaluation_id=evaluation_id,
            question_en=question_en,
            question_ja=question_ja,
            answer_en=answer_en,
            answer_ja=answer_ja,
            qa_json=json.dumps(qa_json) if qa_json else None,
        )
        db.add(chat)
        db.flush()
        return chat


def get_admin_chats(evaluation_id: int) -> list[dict]:
    with db_session() as db:
        chats = (
            db.query(AdminChat)
            .filter(AdminChat.evaluation_id == evaluation_id)
            .order_by(AdminChat.created_at.asc())
            .all()
        )
        result = []
        for c in chats:
            qa_data = {}
            if c.qa_json:
                try:
                    qa_data = json.loads(c.qa_json)
                except Exception:
                    pass

            if "question_english" not in qa_data and c.question_en:
                qa_data["question_english"] = c.question_en
            if "question_japanese" not in qa_data and c.question_ja:
                qa_data["question_japanese"] = c.question_ja
            if "answer_english" not in qa_data and c.answer_en:
                qa_data["answer_english"] = c.answer_en
            if "answer_japanese" not in qa_data and c.answer_ja:
                qa_data["answer_japanese"] = c.answer_ja

            result.append(
                {
                    "id": c.id,
                    "question_en": c.question_en,
                    "question_ja": c.question_ja,
                    "answer_en": c.answer_en,
                    "answer_ja": c.answer_ja,
                    "qa_json": qa_data,
                    "created_at": str(c.created_at) if c.created_at else None,
                }
            )
        return result


# --- Delete Operations ---


def delete_team(team_id: str):
    with db_session() as db:
        eval_ids = [e.id for e in db.query(Evaluation).filter(Evaluation.team_id == team_id).all()]
        if eval_ids:
            db.query(AdminChat).filter(AdminChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
        db.query(Evaluation).filter(Evaluation.team_id == team_id).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.team_id == team_id).delete(synchronize_session=False)
        db.query(Session).filter(Session.team_id == team_id).delete(synchronize_session=False)
        # Delete team memberships (users themselves are kept)
        db.query(TeamMembership).filter(TeamMembership.team_id == team_id).delete(synchronize_session=False)
        db.query(Team).filter(Team.team_id == team_id).delete(synchronize_session=False)


def delete_evaluation(evaluation_id: int):
    with db_session() as db:
        eval_record = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if eval_record:
            db.query(AdminChat).filter(AdminChat.evaluation_id == evaluation_id).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id == evaluation_id).delete(synchronize_session=False)
            db.delete(eval_record)


# ──────────────────────────────────────────────
# Async Task CRUD
# ──────────────────────────────────────────────


def create_async_task(team_id: str, task_type: str, task_id: str | None = None) -> str:
    """Create a new async task and return its task_id (UUID)."""
    if task_id is None:
        task_id = str(uuid.uuid4())
    with db_session() as db:
        task = AsyncTask(
            task_id=task_id,
            team_id=team_id,
            task_type=task_type,
            status="PENDING",
        )
        db.add(task)
    return task_id


def update_async_task(
    task_id: str,
    status: str,
    error_message: str | None = None,
    result_id: int | None = None,
):
    """Update the status of an async task."""
    with db_session() as db:
        task = db.query(AsyncTask).filter(AsyncTask.task_id == task_id).first()
        if task:
            task.status = status
            task.error_message = error_message
            task.result_id = result_id


def get_async_task(task_id: str) -> dict | None:
    """Get async task info as a dictionary."""
    db = SessionLocal()
    try:
        task = db.query(AsyncTask).filter(AsyncTask.task_id == task_id).first()
        if not task:
            return None
        return {
            "task_id": task.task_id,
            "team_id": task.team_id,
            "task_type": task.task_type,
            "status": task.status,
            "error_message": task.error_message,
            "result_id": task.result_id,
        }
    finally:
        db.close()
