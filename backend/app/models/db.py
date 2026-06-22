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
from sqlalchemy.orm import declarative_base, sessionmaker

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

class Hackathon(Base):
    __tablename__ = "hackathons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    template_id = Column(String, nullable=True)
    re_evaluation_context_mode = Column(String, default="cumulative", nullable=False)
    max_qa_turns = Column(Integer, default=1, nullable=False)
    max_consultations = Column(Integer, default=3, nullable=False)
    created_at = Column(DateTime, default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("hackathon_id", "team_id", name="uq_tenant_team"),)
    id = Column(Integer, primary_key=True, index=True)
    hackathon_id = Column(Integer, ForeignKey("hackathons.id"))
    team_id = Column(String, nullable=False)
    passcode = Column(String, nullable=False)
    role = Column(String, nullable=False)  # 'superadmin', 'admin', 'team', 'observer'
    email = Column(String, nullable=True)
    product_name = Column(String)
    team_name = Column(String)
    one_liner = Column(String)
    is_active = Column(Boolean, default=True, nullable=False)


class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    hackathon_id = Column(Integer, ForeignKey("hackathons.id"))
    team_id = Column(String, nullable=False)
    files_json = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, default=func.now())


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    hackathon_id = Column(Integer, ForeignKey("hackathons.id"))
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
    hackathon_id = Column(Integer, ForeignKey("hackathons.id"), primary_key=True)
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False)
    role = Column(String, nullable=False)
    hackathon_id = Column(Integer)
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

def init_db():
    """Create tables and run dynamic schema migrations."""
    Base.metadata.create_all(bind=engine)

    migration_statements = [
        "ALTER TABLE admin_chats ADD COLUMN qa_json TEXT;",
        "ALTER TABLE hackathons ADD COLUMN template_id TEXT;",
        "ALTER TABLE hackathons ADD COLUMN re_evaluation_context_mode TEXT DEFAULT 'cumulative';",
        "ALTER TABLE hackathons ADD COLUMN max_qa_turns INTEGER DEFAULT 1;",
        "ALTER TABLE hackathons ADD COLUMN max_consultations INTEGER DEFAULT 3;",
        "ALTER TABLE users ADD COLUMN email TEXT;",
        "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1;",
    ]
    for stmt in migration_statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass

    # Seed SuperAdmin or single-tenant admin
    from app.security import hash_passcode

    with db_session() as db:
        default_admin_id = os.environ.get("DEFAULT_ADMIN_ID")
        default_admin_pass = os.environ.get("DEFAULT_ADMIN_PASSCODE")

        if not default_admin_id:
            superadmin = db.query(User).filter(User.role == "superadmin").first()
            if not superadmin:
                superadmin = User(
                    team_id="superadmin",
                    passcode=hash_passcode("superadmin123"),
                    role="superadmin",
                )
                db.add(superadmin)
        else:
            existing_h = db.query(Hackathon).first()
            if not existing_h:
                h_name = os.environ.get("DEFAULT_HACKATHON_NAME", "Default Hackathon")
                hackathon = Hackathon(
                    id=1,
                    name=h_name,
                    template_id=None,
                    re_evaluation_context_mode="cumulative",
                    max_qa_turns=1,
                    max_consultations=3,
                )
                db.add(hackathon)
                db.flush()
                admin_user = User(
                    hackathon_id=hackathon.id,
                    team_id=default_admin_id,
                    passcode=hash_passcode(default_admin_pass),
                    role="admin",
                )
                db.add(admin_user)
                db.flush()


# ──────────────────────────────────────────────
# CRUD Functions
# ──────────────────────────────────────────────

def verify_user(team_id: str, passcode: str, hackathon_id: int = None) -> dict | None:
    """Verify user credentials and return role/hackathon_id if valid."""
    from app.security import verify_passcode

    if team_id == "superadmin" and os.environ.get("DEFAULT_ADMIN_ID"):
        return None

    with db_session() as db:
        query = db.query(User).filter(User.team_id == team_id, User.is_active == True)
        if team_id == "superadmin":
            user = query.filter(User.role == "superadmin").first()
        else:
            if not hackathon_id:
                return None
            user = query.filter(User.hackathon_id == hackathon_id).first()
        if user and verify_passcode(passcode, user.passcode):
            return {"role": user.role, "hackathon_id": user.hackathon_id, "email": user.email}
        return None


def get_consultation_count(hackathon_id: int, team_id: str) -> int:
    with db_session() as db:
        return (
            db.query(Evaluation)
            .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id)
            .count()
        )


def save_evaluation(
    hackathon_id: int,
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
            hackathon_id=hackathon_id,
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

def get_setting(hackathon_id: int, key: str) -> str | None:
    if hackathon_id is None:
        return None
    with db_session() as db:
        setting = db.query(Setting).filter(
            Setting.hackathon_id == hackathon_id, Setting.key == key
        ).first()
        return setting.value if setting else None


def set_setting(hackathon_id: int, key: str, value: str, db=None):
    if hackathon_id is None:
        return

    def _execute(session):
        setting = session.query(Setting).filter(
            Setting.hackathon_id == hackathon_id, Setting.key == key
        ).first()
        if setting:
            setting.value = value
        else:
            session.add(Setting(hackathon_id=hackathon_id, key=key, value=value))

    if db is not None:
        _execute(db)
    else:
        with db_session() as new_db:
            _execute(new_db)


def get_ai_response_languages(hackathon_id: int) -> list[str]:
    val = get_setting(hackathon_id, "ai_response_languages")
    if val:
        try:
            return json.loads(val)
        except Exception:
            pass
    return ["English", "Japanese"]


def set_ai_response_languages(hackathon_id: int, languages: list[str], db=None):
    set_setting(hackathon_id, "ai_response_languages", json.dumps(languages), db=db)


def is_video_upload_enabled(hackathon_id: int) -> bool:
    val = get_setting(hackathon_id, "video_upload_enabled")
    return val != "false"


def set_video_upload_enabled(hackathon_id: int, enabled: bool, db=None):
    set_setting(hackathon_id, "video_upload_enabled", "true" if enabled else "false", db=db)


def get_criteria(hackathon_id):
    from app.services.templates import TEMPLATES

    val = get_setting(hackathon_id, "evaluation_criteria")
    if val:
        return json.loads(val)
    if hackathon_id is not None:
        with db_session() as db:
            h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
            if h:
                if h.template_id:
                    tpl = TEMPLATES.get(h.template_id)
                    if tpl:
                        return tpl.get("criteria", [])
                return []
    return TEMPLATES.get("hackathon", {}).get("criteria", [])


def set_criteria(hackathon_id, criteria_list, db=None):
    set_setting(hackathon_id, "evaluation_criteria", json.dumps(criteria_list), db=db)


def get_personas(hackathon_id):
    from app.services.templates import TEMPLATES

    val = get_setting(hackathon_id, "judges_personas")
    if val:
        personas = json.loads(val)
    else:
        if hackathon_id is not None:
            with db_session() as db:
                h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
                if h:
                    if h.template_id:
                        tpl = TEMPLATES.get(h.template_id)
                        if tpl:
                            personas = tpl.get("personas", [])
                    else:
                        personas = []
                else:
                    personas = TEMPLATES.get("hackathon", {}).get("personas", [])
        else:
            personas = TEMPLATES.get("hackathon", {}).get("personas", [])

    # Automatically resolve custom avatar image from assets/avatars/ if not set
    import base64
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
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


def set_personas(hackathon_id, personas_list, db=None):
    set_setting(hackathon_id, "judges_personas", json.dumps(personas_list), db=db)


def get_re_evaluation_context_mode(hackathon_id: int) -> str:
    if hackathon_id is None:
        return "cumulative"
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        return h.re_evaluation_context_mode if h else "cumulative"


def set_re_evaluation_context_mode(hackathon_id: int, mode: str):
    if hackathon_id is None:
        return
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        if h:
            h.re_evaluation_context_mode = mode


def get_max_qa_turns(hackathon_id: int) -> int:
    if hackathon_id is None:
        return 1
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        return h.max_qa_turns if h else 1


def set_max_qa_turns(hackathon_id: int, turns: int):
    if hackathon_id is None:
        return
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        if h:
            h.max_qa_turns = turns


def get_max_consultations(hackathon_id: int) -> int:
    if hackathon_id is None:
        return 3
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        return h.max_consultations if h and h.max_consultations is not None else 3


def set_max_consultations(hackathon_id: int, max_consultations: int):
    if hackathon_id is None:
        return
    with db_session() as db:
        h = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        if h:
            h.max_consultations = max_consultations


# --- Hackathon CRUD ---

def create_hackathon(
    name: str, admin_id: str, admin_pass: str,
    template_id: str = None, custom_template_data: dict = None,
) -> int:
    from app.security import hash_passcode
    from app.services.templates import TEMPLATES

    with db_session() as db:
        hackathon = Hackathon(
            name=name, template_id=template_id,
            re_evaluation_context_mode="cumulative", max_qa_turns=1, max_consultations=3,
        )
        db.add(hackathon)
        db.flush()

        admin_user = User(
            hackathon_id=hackathon.id, team_id=admin_id,
            passcode=hash_passcode(admin_pass), role="admin",
        )
        db.add(admin_user)
        db.flush()

        if template_id:
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
                tpl = TEMPLATES.get("hackathon", {})
                selected_criteria = tpl.get("criteria")
                selected_personas = tpl.get("personas")

            hackathon.template_id = template_id
            hackathon.re_evaluation_context_mode = re_eval_mode
            hackathon.max_qa_turns = max_qa
            hackathon.max_consultations = max_cons

            set_personas(hackathon.id, selected_personas, db=db)
            set_criteria(hackathon.id, selected_criteria, db=db)
            set_ai_response_languages(hackathon.id, ["English", "Japanese"], db=db)

        return hackathon.id


def initialize_hackathon_template(hackathon_id: int, template_id: str, custom_template_data: dict = None):
    from app.services.templates import TEMPLATES

    with db_session() as db:
        hackathon = db.query(Hackathon).filter(Hackathon.id == hackathon_id).first()
        if not hackathon:
            raise ValueError(f"Hackathon ID {hackathon_id} not found.")

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

        hackathon.template_id = template_id
        hackathon.re_evaluation_context_mode = re_eval_mode
        hackathon.max_qa_turns = max_qa
        hackathon.max_consultations = max_cons

        set_personas(hackathon_id, selected_personas, db=db)
        set_criteria(hackathon_id, selected_criteria, db=db)
        set_ai_response_languages(hackathon_id, ["English", "Japanese"], db=db)


# --- User / Team CRUD ---

def update_admin_passcode(hackathon_id: int, new_passcode: str):
    from app.security import hash_passcode

    with db_session() as db:
        admin_user = db.query(User).filter(
            User.hackathon_id == hackathon_id, User.role == "admin"
        ).first()
        if admin_user:
            admin_user.passcode = hash_passcode(new_passcode)


def update_team_passcode(hackathon_id: int, team_id: str, new_passcode: str) -> bool:
    from app.security import hash_passcode

    with db_session() as db:
        team_user = (
            db.query(User)
            .filter(
                User.hackathon_id == hackathon_id,
                User.team_id == team_id,
                User.role.in_(["team", "observer"]),
            )
            .first()
        )
        if team_user:
            team_user.passcode = hash_passcode(new_passcode)
            return True
        return False


def update_user_role(hackathon_id: int, team_id: str, new_role: str) -> bool:
    if new_role not in ["team", "observer"]:
        return False
    with db_session() as db:
        user = (
            db.query(User)
            .filter(
                User.hackathon_id == hackathon_id,
                User.team_id == team_id,
                User.role.in_(["team", "observer"]),
            )
            .first()
        )
        if user:
            user.role = new_role
            return True
        return False


def update_user_active(hackathon_id: int, team_id: str, is_active: bool) -> bool:
    with db_session() as db:
        user = (
            db.query(User)
            .filter(
                User.hackathon_id == hackathon_id,
                User.team_id == team_id,
                User.role.in_(["team", "observer"]),
            )
            .first()
        )
        if user:
            user.is_active = is_active
            return True
        return False


def change_my_passcode(
    hackathon_id: int = None, team_id: str = None,
    current_passcode: str = None, new_passcode: str = None,
) -> bool:
    from app.security import hash_passcode, verify_passcode

    if isinstance(hackathon_id, str):
        new_passcode = current_passcode
        current_passcode = team_id
        team_id = hackathon_id
        hackathon_id = None

    with db_session() as db:
        query = db.query(User).filter(User.team_id == team_id)
        if team_id != "superadmin" and hackathon_id is not None:
            query = query.filter(User.hackathon_id == hackathon_id)
        user = query.first()
        if user and verify_passcode(current_passcode, user.passcode):
            user.passcode = hash_passcode(new_passcode)
            return True
        return False


def get_team_profile(hackathon_id: int, team_id: str) -> dict:
    with db_session() as db:
        user = db.query(User).filter(
            User.hackathon_id == hackathon_id, User.team_id == team_id
        ).first()
        if user:
            return {
                "product_name": user.product_name,
                "team_name": user.team_name,
                "one_liner": user.one_liner,
            }
        return {"product_name": None, "team_name": None, "one_liner": None}


def update_team_profile(hackathon_id: int, team_id: str, product_name: str, team_name: str, one_liner: str):
    with db_session() as db:
        user = db.query(User).filter(
            User.hackathon_id == hackathon_id, User.team_id == team_id
        ).first()
        if user:
            user.product_name = product_name
            user.team_name = team_name
            user.one_liner = one_liner


# --- Session CRUD ---

def create_session(team_id: str, role: str, hackathon_id: int) -> str:
    with db_session() as db:
        session_id = str(uuid.uuid4())
        db.add(Session(session_id=session_id, team_id=team_id, role=role, hackathon_id=hackathon_id))
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
                "hackathon_id": record.hackathon_id,
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
    evaluation_id: int, question_en: str, question_ja: str,
    answer_en: str, answer_ja: str, qa_json: dict = None,
) -> AdminChat:
    with db_session() as db:
        chat = AdminChat(
            evaluation_id=evaluation_id,
            question_en=question_en, question_ja=question_ja,
            answer_en=answer_en, answer_ja=answer_ja,
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

            result.append({
                "id": c.id,
                "question_en": c.question_en,
                "question_ja": c.question_ja,
                "answer_en": c.answer_en,
                "answer_ja": c.answer_ja,
                "qa_json": qa_data,
                "created_at": str(c.created_at) if c.created_at else None,
            })
        return result


# --- Delete Operations ---

def delete_hackathon(hackathon_id: int):
    with db_session() as db:
        eval_ids = [e.id for e in db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id).all()]
        if eval_ids:
            db.query(AdminChat).filter(AdminChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
        db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id).delete(synchronize_session=False)
        db.query(Submission).filter(Submission.hackathon_id == hackathon_id).delete(synchronize_session=False)
        db.query(Setting).filter(Setting.hackathon_id == hackathon_id).delete(synchronize_session=False)
        db.query(Session).filter(Session.hackathon_id == hackathon_id).delete(synchronize_session=False)
        db.query(User).filter(User.hackathon_id == hackathon_id).delete(synchronize_session=False)
        db.query(Hackathon).filter(Hackathon.id == hackathon_id).delete(synchronize_session=False)


def delete_team(hackathon_id: int, team_id: str):
    with db_session() as db:
        eval_ids = [
            e.id for e in db.query(Evaluation)
            .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id)
            .all()
        ]
        if eval_ids:
            db.query(AdminChat).filter(AdminChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
        db.query(Evaluation).filter(
            Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id
        ).delete(synchronize_session=False)
        db.query(Submission).filter(
            Submission.hackathon_id == hackathon_id, Submission.team_id == team_id
        ).delete(synchronize_session=False)
        db.query(Session).filter(
            Session.hackathon_id == hackathon_id, Session.team_id == team_id
        ).delete(synchronize_session=False)
        db.query(User).filter(
            User.hackathon_id == hackathon_id, User.team_id == team_id,
            User.role.in_(["team", "observer"]),
        ).delete(synchronize_session=False)


def delete_evaluation(hackathon_id: int, evaluation_id: int):
    with db_session() as db:
        eval_record = (
            db.query(Evaluation)
            .filter(Evaluation.id == evaluation_id, Evaluation.hackathon_id == hackathon_id)
            .first()
        )
        if eval_record:
            db.query(AdminChat).filter(AdminChat.evaluation_id == evaluation_id).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id == evaluation_id).delete(synchronize_session=False)
            db.delete(eval_record)
