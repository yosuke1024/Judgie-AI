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

from config import DATABASE_URL
from core.security import hash_passcode, verify_passcode
from core.templates import TEMPLATES


def normalize_lang_to_key(lang_name: str) -> str:
    # Replace hyphens with spaces first so they become underscores
    cleaned = lang_name.replace('-', ' ')
    # Generate clean key by keeping word characters and basic multilingual characters
    safe_name = re.sub(r'[^\w\s\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', '', cleaned)
    safe_name = re.sub(r'\s+', '_', safe_name).strip().lower()
    if not safe_name:
        safe_name = "lang_" + str(hash(lang_name) % 1000)
    return safe_name

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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
    __table_args__ = (UniqueConstraint('hackathon_id', 'team_id', name='uq_tenant_team'),)
    id = Column(Integer, primary_key=True, index=True)
    hackathon_id = Column(Integer, ForeignKey("hackathons.id"))
    team_id = Column(String, nullable=False)
    passcode = Column(String, nullable=False)
    role = Column(String, nullable=False) # 'superadmin', 'admin', 'team'
    product_name = Column(String)
    team_name = Column(String)
    one_liner = Column(String)

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
    message_json = Column(Text, nullable=False)  # Store JSON representation of the QA data
    created_at = Column(DateTime, default=func.now())


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
    with db_session() as db:
        yield db

def init_db():
    Base.metadata.create_all(bind=engine)
    # Run dynamic schema migrations to add columns/tables if not exists
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE admin_chats ADD COLUMN qa_json TEXT;"))
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE hackathons ADD COLUMN template_id TEXT;"))
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE hackathons ADD COLUMN re_evaluation_context_mode TEXT DEFAULT 'cumulative';"
                )
            )
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE hackathons ADD COLUMN max_qa_turns INTEGER DEFAULT 1;"))
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE hackathons ADD COLUMN max_consultations INTEGER DEFAULT 3;")
            )
    except Exception:
        pass

    with db_session() as db:
        default_admin_id = os.environ.get("DEFAULT_ADMIN_ID")
        default_admin_pass = os.environ.get("DEFAULT_ADMIN_PASSCODE")

        # If single-tenant mode is NOT enabled, seed SuperAdmin as usual
        if not default_admin_id:
            superadmin = db.query(User).filter(User.role == 'superadmin').first()
            if not superadmin:
                superadmin = User(team_id='superadmin', passcode=hash_passcode('superadmin123'), role='superadmin')
                db.add(superadmin)
        else:
            # Single-tenant mode: Auto-provision default hackathon and tenant admin
            # Only provision if there are no hackathons at all (prevent overwriting/duplicates)
            existing_h = db.query(Hackathon).first()
            if not existing_h:
                h_name = os.environ.get("DEFAULT_HACKATHON_NAME", "Default Hackathon")
                hackathon = Hackathon(
                    id=1,
                    name=h_name,
                    template_id=None,
                    re_evaluation_context_mode="cumulative",
                    max_qa_turns=1,
                    max_consultations=3
                )
                db.add(hackathon)
                db.flush()

                admin_user = User(
                    hackathon_id=hackathon.id,
                    team_id=default_admin_id,
                    passcode=hash_passcode(default_admin_pass),
                    role='admin'
                )
                db.add(admin_user)
                db.flush()

def verify_user(team_id: str, passcode: str, hackathon_id: int = None) -> dict:
    # Block SuperAdmin login if single-tenant mode is enabled
    if team_id == 'superadmin' and os.environ.get("DEFAULT_ADMIN_ID"):
        return None

    with db_session() as db:
        query = db.query(User).filter(User.team_id == team_id)
        if team_id == 'superadmin':
            user = query.filter(User.role == 'superadmin').first()
        else:
            if not hackathon_id:
                return None
            user = query.filter(User.hackathon_id == hackathon_id).first()
        if user and verify_passcode(passcode, user.passcode):
            return {'role': user.role, 'hackathon_id': user.hackathon_id}
        return None

def get_consultation_count(hackathon_id: int, team_id: str) -> int:
    with db_session() as db:
        count = db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id).count()
        return count

def save_evaluation(hackathon_id: int, team_id: str, result_json: dict, is_final: bool = False, source_text: str = None, gemini_file_ids: list = None):
    with db_session() as db:
        scores_json = json.dumps(result_json.get("scores", {}))
        impact_score = result_json.get("impact_score", 0.0)

        # Dynamic mapping for languages to support free-form languages
        # Keep backward compatibility by storing summary_<lang_key> in strengths_risks
        strengths_risks = {
            "judges_feedback": result_json.get("judges_feedback", [])
        }
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
            gemini_file_ids=file_ids_json
        )
        db.add(eval_record)

def save_objection_qa(evaluation_id: int, qa_json: dict):
    with db_session() as db:
        eval_record = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if eval_record:
            eval_record.qa_json = json.dumps(qa_json)

def get_setting(hackathon_id: int, key: str) -> str:
    if hackathon_id is None:
        return None
    with db_session() as db:
        setting = db.query(Setting).filter(Setting.hackathon_id == hackathon_id, Setting.key == key).first()
        return setting.value if setting else None

def set_setting(hackathon_id: int, key: str, value: str, db=None):
    if hackathon_id is None:
        return

    def _execute(session):
        setting = session.query(Setting).filter(Setting.hackathon_id == hackathon_id, Setting.key == key).first()
        if setting:
            setting.value = value
        else:
            setting = Setting(hackathon_id=hackathon_id, key=key, value=value)
            session.add(setting)

    if db is not None:
        _execute(db)
    else:
        with db_session() as new_db:
            _execute(new_db)

def get_ai_response_languages(hackathon_id: int) -> list[str]:
    """
    Returns the configured languages for AI responses.
    Defaults to ["English", "Japanese"] if not configured.
    """
    val = get_setting(hackathon_id, 'ai_response_languages')
    if val:
        try:
            return json.loads(val)
        except Exception:
            pass
    return ["English", "Japanese"]

def set_ai_response_languages(hackathon_id: int, languages: list[str], db=None):
    set_setting(hackathon_id, 'ai_response_languages', json.dumps(languages), db=db)


def is_video_upload_enabled(hackathon_id: int) -> bool:
    """
    Returns True if video uploads (MP4, MOV) are enabled for the hackathon.
    Defaults to True if not configured.
    """
    val = get_setting(hackathon_id, 'video_upload_enabled')
    return val != "false"


def set_video_upload_enabled(hackathon_id: int, enabled: bool, db=None):
    set_setting(hackathon_id, 'video_upload_enabled', "true" if enabled else "false", db=db)


def get_criteria(hackathon_id):
    val = get_setting(hackathon_id, 'evaluation_criteria')
    if val:
        return json.loads(val)
    return TEMPLATES["hackathon"]["criteria"]

def set_criteria(hackathon_id, criteria_list, db=None):
    set_setting(hackathon_id, 'evaluation_criteria', json.dumps(criteria_list), db=db)

def get_personas(hackathon_id):
    val = get_setting(hackathon_id, 'judges_personas')
    if val:
        return json.loads(val)
    return TEMPLATES["hackathon"]["personas"]

def set_personas(hackathon_id, personas_list, db=None):
    set_setting(hackathon_id, 'judges_personas', json.dumps(personas_list), db=db)

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

def create_hackathon(name: str, admin_id: str, admin_pass: str, template_id: str = None, custom_template_data: dict = None) -> int:
    with db_session() as db:
        hackathon = Hackathon(
            name=name,
            template_id=template_id,
            re_evaluation_context_mode="cumulative",
            max_qa_turns=1,
            max_consultations=3
        )
        db.add(hackathon)
        db.flush() # flush to get the ID

        # Create the tenant admin
        admin_user = User(
            hackathon_id=hackathon.id,
            team_id=admin_id,
            passcode=hash_passcode(admin_pass),
            role='admin'
        )
        db.add(admin_user)
        db.flush()

        # If template_id is specified directly (e.g. in legacy tests), initialize it
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
                tpl = TEMPLATES["hackathon"]
                selected_criteria = tpl.get("criteria")
                selected_personas = tpl.get("personas")
                re_eval_mode = tpl.get("re_evaluation_context_mode", "cumulative")
                max_qa = tpl.get("max_qa_turns", 1)
                max_cons = tpl.get("max_consultations", 3)

            hackathon.template_id = template_id
            hackathon.re_evaluation_context_mode = re_eval_mode
            hackathon.max_qa_turns = max_qa
            hackathon.max_consultations = max_cons

            set_personas(hackathon.id, selected_personas, db=db)
            set_criteria(hackathon.id, selected_criteria, db=db)
            set_ai_response_languages(hackathon.id, ["English", "Japanese"], db=db)

        return hackathon.id

def initialize_hackathon_template(hackathon_id: int, template_id: str, custom_template_data: dict = None):
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

def update_admin_passcode(hackathon_id: int, new_passcode: str):
    with db_session() as db:
        admin_user = db.query(User).filter(User.hackathon_id == hackathon_id, User.role == 'admin').first()
        if admin_user:
            admin_user.passcode = hash_passcode(new_passcode)

def update_team_passcode(hackathon_id: int, team_id: str, new_passcode: str) -> bool:
    with db_session() as db:
        team_user = db.query(User).filter(
            User.hackathon_id == hackathon_id,
            User.team_id == team_id,
            User.role.in_(['team', 'observer'])
        ).first()
        if team_user:
            team_user.passcode = hash_passcode(new_passcode)
            return True
        return False

def update_user_role(hackathon_id: int, team_id: str, new_role: str) -> bool:
    if new_role not in ['team', 'observer']:
        return False
    with db_session() as db:
        user = db.query(User).filter(
            User.hackathon_id == hackathon_id,
            User.team_id == team_id,
            User.role.in_(['team', 'observer'])
        ).first()
        if user:
            user.role = new_role
            return True
        return False


def change_my_passcode(hackathon_id: int = None, team_id: str = None, current_passcode: str = None, new_passcode: str = None) -> bool:
    # Robust fallback: If hackathon_id is a string, it means the older 3-argument signature
    # (team_id, current_passcode, new_passcode) was called due to hot-reload cache mismatch.
    if isinstance(hackathon_id, str):
        new_passcode = current_passcode
        current_passcode = team_id
        team_id = hackathon_id
        hackathon_id = None

    with db_session() as db:
        query = db.query(User).filter(User.team_id == team_id)
        if team_id != 'superadmin' and hackathon_id is not None:
            query = query.filter(User.hackathon_id == hackathon_id)
        user = query.first()
        if user and verify_passcode(current_passcode, user.passcode):
            user.passcode = hash_passcode(new_passcode)
            return True
        return False

def get_team_profile(hackathon_id: int, team_id: str) -> dict:
    with db_session() as db:
        user = db.query(User).filter(User.hackathon_id == hackathon_id, User.team_id == team_id).first()
        if user:
            return {'product_name': user.product_name, 'team_name': user.team_name, 'one_liner': user.one_liner}
        return {'product_name': None, 'team_name': None, 'one_liner': None}

def update_team_profile(hackathon_id: int, team_id: str, product_name: str, team_name: str, one_liner: str):
    with db_session() as db:
        user = db.query(User).filter(User.hackathon_id == hackathon_id, User.team_id == team_id).first()
        if user:
            user.product_name = product_name
            user.team_name = team_name
            user.one_liner = one_liner

def create_session(team_id: str, role: str, hackathon_id: int) -> str:
    with db_session() as db:
        session_id = str(uuid.uuid4())
        session_record = Session(session_id=session_id, team_id=team_id, role=role, hackathon_id=hackathon_id)
        db.add(session_record)
        return session_id

def get_session(session_id: str) -> dict:
    if not session_id:
        return None
    with db_session() as db:
        session_record = db.query(Session).filter(Session.session_id == session_id).first()
        if session_record:
            return {'team_id': session_record.team_id, 'role': session_record.role, 'hackathon_id': session_record.hackathon_id}
        return None

def delete_session(session_id: str):
    if not session_id:
        return
    with db_session() as db:
        session_record = db.query(Session).filter(Session.session_id == session_id).first()
        if session_record:
            db.delete(session_record)

def save_admin_chat(evaluation_id: int, question_en: str, question_ja: str, answer_en: str, answer_ja: str, qa_json: dict = None) -> AdminChat:
    with db_session() as db:
        chat = AdminChat(
            evaluation_id=evaluation_id,
            question_en=question_en,
            question_ja=question_ja,
            answer_en=answer_en,
            answer_ja=answer_ja,
            qa_json=json.dumps(qa_json) if qa_json else None
        )
        db.add(chat)
        db.flush()
        return chat

def get_admin_chats(evaluation_id: int) -> list[dict]:
    with db_session() as db:
        chats = db.query(AdminChat).filter(AdminChat.evaluation_id == evaluation_id).order_by(AdminChat.created_at.asc()).all()
        result = []
        for c in chats:
            qa_data = {}
            if c.qa_json:
                try:
                    qa_data = json.loads(c.qa_json)
                except Exception:
                    pass

            # Populate with fallback values for backward compatibility
            if "question_english" not in qa_data and c.question_en:
                qa_data["question_english"] = c.question_en
            if "question_japanese" not in qa_data and c.question_ja:
                qa_data["question_japanese"] = c.question_ja
            if "answer_english" not in qa_data and c.answer_en:
                qa_data["answer_english"] = c.answer_en
            if "answer_japanese" not in qa_data and c.answer_ja:
                qa_data["answer_japanese"] = c.answer_ja

            result.append({
                'id': c.id,
                'question_en': c.question_en,
                'question_ja': c.question_ja,
                'answer_en': c.answer_en,
                'answer_ja': c.answer_ja,
                'qa_json': qa_data,
                'created_at': c.created_at
            })
        return result

def delete_hackathon(hackathon_id: int):
    with db_session() as db:
        # 1. AdminChat (Chat history linked to evaluations)
        eval_ids = [e.id for e in db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id).all()]
        if eval_ids:
            db.query(AdminChat).filter(AdminChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)

        # 2. Evaluation
        db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id).delete(synchronize_session=False)

        # 3. Submission
        db.query(Submission).filter(Submission.hackathon_id == hackathon_id).delete(synchronize_session=False)

        # 4. Setting
        db.query(Setting).filter(Setting.hackathon_id == hackathon_id).delete(synchronize_session=False)

        # 5. Session
        db.query(Session).filter(Session.hackathon_id == hackathon_id).delete(synchronize_session=False)

        # 6. User
        db.query(User).filter(User.hackathon_id == hackathon_id).delete(synchronize_session=False)

        # 7. Hackathon
        db.query(Hackathon).filter(Hackathon.id == hackathon_id).delete(synchronize_session=False)


def delete_team(hackathon_id: int, team_id: str):
    with db_session() as db:
        # 1. AdminChat and TeamChat (Chat history linked to evaluations)
        eval_ids = [e.id for e in db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id).all()]
        if eval_ids:
            db.query(AdminChat).filter(AdminChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id.in_(eval_ids)).delete(synchronize_session=False)

        # 2. Evaluation
        db.query(Evaluation).filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id).delete(synchronize_session=False)

        # 3. Submission
        db.query(Submission).filter(Submission.hackathon_id == hackathon_id, Submission.team_id == team_id).delete(synchronize_session=False)

        # 4. Session
        db.query(Session).filter(Session.hackathon_id == hackathon_id, Session.team_id == team_id).delete(synchronize_session=False)

        # 5. User (Only delete teams/observers, do NOT delete admins/superadmins)
        db.query(User).filter(
            User.hackathon_id == hackathon_id,
            User.team_id == team_id,
            User.role.in_(['team', 'observer'])
        ).delete(synchronize_session=False)


def delete_evaluation(hackathon_id: int, evaluation_id: int):
    with db_session() as db:
        # Verify the evaluation belongs to the hackathon
        eval_record = db.query(Evaluation).filter(Evaluation.id == evaluation_id, Evaluation.hackathon_id == hackathon_id).first()
        if eval_record:
            # 1. AdminChat and TeamChat
            db.query(AdminChat).filter(AdminChat.evaluation_id == evaluation_id).delete(synchronize_session=False)
            db.query(TeamChat).filter(TeamChat.evaluation_id == evaluation_id).delete(synchronize_session=False)

            # 2. Evaluation
            db.delete(eval_record)


def seed_demo_data():
    """Seeds rich mock data for the Guest Demo Mode (Hackathon ID 9999)."""
    with db_session() as db:
        # 1. Check if demo hackathon already exists
        demo_h = db.query(Hackathon).filter(Hackathon.id == 9999).first()
        if demo_h:
            return # Already seeded

        # Create Hackathon
        demo_h = Hackathon(
            id=9999,
            name="Judgie Demo Hackathon",
            max_consultations=3
        )
        db.add(demo_h)
        db.flush()

        # Create Settings
        set_personas(9999, get_personas(None), db=db)
        set_criteria(9999, get_criteria(None), db=db)
        set_setting(9999, 'gemini_api_key', 'DEMO_MOCK_KEY', db=db)
        set_setting(9999, 'gemini_model', 'demo-mock-model', db=db)

        # Create Admin
        demo_admin = User(
            hackathon_id=9999,
            team_id="demo_admin",
            passcode=hash_passcode("demo123"),
            role="admin"
        )
        db.add(demo_admin)

        # Create Teams
        teams_data = [
            ("demo_team", "PixelCraft Labs", "DreamStream AI", "AI-driven dream analysis and visualization platform"),
            ("demo_team2", "EcoLoop", "GreenGrid", "Smart energy grid optimizer using reinforcement learning"),
            ("demo_team3", "HealthFlow", "AuraScan", "Mobile vitals assessment via edge computer vision")
        ]
        for tid, tname, pname, oliner in teams_data:
            user = User(
                hackathon_id=9999,
                team_id=tid,
                passcode=hash_passcode("demo123"),
                role="team",
                team_name=tname,
                product_name=pname,
                one_liner=oliner
            )
            db.add(user)
        db.flush()

        # Seed submissions & evaluations for demo_team (PixelCraft Labs / DreamStream AI)
        # Consultation 1 (Low Score: ~62.0)
        c1_scores = {
            "Innovation & Creativity": 3.0, "Technical Implementation": 2.5,
            "Problem Solving & Impact": 3.0, "Product & UX": 3.0,
            "Working Prototype": 3.0, "Presentation": 3.5
        }
        c1_strengths_risks = {
            "summary_en": "Initial prototype of DreamStream AI. A system to log dreams and analyze recurring themes using basic NLP.",
            "summary_ja": "DreamStream AIの初期プロトタイプ。基本的な自然言語処理を用いて夢を記録し、頻出するテーマを分析するシステム。",
            "judges_feedback": [
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "judge_persona": "Cares about market fit and monetization.",
                    "feedback_en": "The concept of dream logging is interesting from a novelty perspective, but let's talk business survival. How do you monetize this? Dream analysis is a classic wellness 'vitamin' (nice to have) rather than a 'painkiller' (must have). To make people pay monthly, you need to find a desperate user segment. Have you considered targeting high-stress professionals or linking dream patterns directly to daily productivity metrics to justify a subscription model? Even within the short duration of a hackathon, simulating a shift to B2B is the only way to increase your survival probability. Start by running closed tests in local high-stress organizations to identify the core value that users would actually pay for. This will drastically improve the credibility of your monetization slide.",
                    "feedback_ja": "夢の記録というコンセプトは目新しさの観点からは面白いですが、ビジネスの生存戦略について話しましょう。これをどうやってマネタイズしますか？夢分析は、『あれば嬉しいもの（ビタミン）』の典型であり、生活に不可欠な『鎮痛剤（ペインキラー）』ではありません。月額課金を正当化するには、切実な悩みを抱えるユーザー層を見つける必要があります。高ストレスの専門職をターゲットにするか、夢のパターンを日々の生産性指標と直接リンクさせてサブスクの価値を証明することを検討しましたか？ハッカソンのような短い期間でも、初期のB2Bへの転換などをシミュレートして検証を進めることが、生存確率を上げる唯一の道です。まずは身近な高ストレス組織でクローズドテストを行い、ユーザーが課金してでも使いたいと思えるコアバリューを明確にすることから始めましょう。そうすれば、ピッチ時のマネタイズへの説得力は全く違ったものになります。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "Looking at the codebase, the raw SQL queries used to store user logs pose a severe risk. Sensitive, highly personal dream descriptions are stored in plain text without database-level encryption. This is a privacy disaster waiting to happen. You must immediately migrate to parameterized queries using SQLAlchemy ORM to prevent SQL injection, and implement AES-256 encryption at rest for the user log columns. Additionally, the user session management logic is weak, and token expiration is not set. This makes it an easy target for session hijacking. Besides building self-documenting APIs, you must strictly meet standard security and database hygiene. By the next milestone, close these security holes and ensure data is handled over a secure pipeline.",
                    "feedback_ja": "コードベースを確認したところ、ユーザーログの保存に使われている生のSQLクエリには深刻な脆弱性があります。きわめてプライベートな夢の記述が、データベースレベルで暗号化されずに平文で保存されています。これはプライバシー保護の観点から大問題です。即座にSQLAlchemy ORMを用いたパラメータ化クエリに移行してSQLインジェクションを防ぎ、ログカラムに対して保存時のAES-256暗号化を実装してください。また、ユーザーセッションの管理ロジックも脆弱で、トークンの有効期限が設定されていません。これではセッションハイジャックの格好の標的になります。クリーンで自己文書化されたAPIを作成することに加え、セキュリティ・衛生基準をしっかりと満たす必要があります。次のチェックポイントまでに、これらのセキュリティホールを塞ぎ、安全な接続が保証された状態でデータがやりとりされる仕組みを整えてください。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "Right now, the user interface is just a generic web form with a white background. Dreams are mystical, intimate, and emotional. The visual language should reflect that. I recommend starting with a dark-mode-first theme, utilizing soft gradients, and introducing smooth transition animations when submitting a dream. A cluttered form increases cognitive load; instead, make it a single, focused text area that feels like writing in a personal diary. Typography choice is also critical—combine warm serifs with legible modern sans-serifs to create a premium feel. We expect subtle micro-animations that harmonize with the user's emotional state right after waking up. Pay attention to overall accessibility, such as color contrast and ARIA labels, to make the design truly inclusive.",
                    "feedback_ja": "現状のユーザーインターフェースは、白い背景のありふれたウェブフォームに過ぎません。夢とは神秘的で親密、そして感情的なものです。ビジュアル言語もそれを反映するべきです。デフォルトでダークモードのテーマにし、柔らかなグラデーションを活用し、夢を送信する際のスムーズな遷移アニメーションを導入することを推奨します。雑然としたフォームは認知負荷を高めるため、個人の日記帳に書き込むような、シンプルで集中できる1つのテキストエリアにしてください。フォントの選定も重要で、温かみのあるセリフ体や読みやすいモダンなサンセリフを組み合わせることで、高級感を演出できます。ユーザーが夢から醒めた直後の感情に寄り添うような、心地よいアニメーション演出を期待しています。全体的なアクセシビリティ（コントラストやARIAラベルなど）にも気を配り、どんな環境でも快適に利用できるようにデザインを洗練させていきましょう。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "judge_persona": "Cares about scope and MVP.",
                    "feedback_en": "You're trying to build a dream analyzer, a social sharing network, and a lifestyle coach all in one MVP. This is classic scope creep. For your initial validation, strip away the social and coaching features. Focus 100% on the core loop: inputting a dream and getting a single, highly accurate NLP-based theme analysis. Once you prove that users actually return to log their dreams for 7 consecutive days, only then should you prioritize secondary features. Winning a hackathon relies on product discipline—specifically, what you decide *not* to build. Discuss with your team what the absolute core problem is, and narrow down the scope of development for the next submission. Otherwise, everything will be half-baked, and you will fail to deliver the core value.",
                    "feedback_ja": "最初のMVPであるにもかかわらず、夢分析、ソーシャル共有ネットワーク、ライフスタイルコーチの機能をすべて一度に作ろうとしています。典型的なスコープクリープ（機能の膨張）です。初期検証では、ソーシャル機能やコーチング機能はすべて削ってください。夢を入力し、NLPによる正確なテーマ分析を1つ得るというコアのループに100%集中しましょう。ユーザーが実際に7日間連続で夢を記録しに戻ってくることが証明されてから、二次的な機能を優先すべきです。ハッカソンで勝つためのプロダクトマネジメントは、何を削るかで決まります。本当に解決すべき最大の課題は何かをチームで議論し、次の提出までに開発スコープを鋭く絞り込んでください。このままではすべてが中途半端になり、最も価値のある体験を提供できなくなります。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "judge_persona": "Cares about pitch and scale.",
                    "feedback_en": "Your pitch spent way too much time explaining how NLP tokenization works. As an investor, I don't care about tokenizers; I care about market size and scalability. You've framed this as a niche wellness tool, which makes the addressable market look tiny. If you want VC backing, you need to show how this database of human subconscious data can scale into a massive predictive mental health platform. Sell us the big vision first. You need to explain why dreams are critical right now, and how this could drive massive societal changes through a compelling slide deck. Put technical pride aside and restructure your slides to focus entirely on business value and the macro opportunity.",
                    "feedback_ja": "ピッチ資料で、NLPのトークン化の仕組みの説明に時間を費やしすぎています。投資家はトークナイザーには興味ありません。知りたいのは市場規模とスケーラビリティです。現状、このアプリをニッチなウェルネスツールとして位置づけているため、獲得可能な市場（TAM）が非常に小さく見えています。VCからの出資を望むなら、この人間の無意識データのデータベースが、どのように巨大な予測的メンタルヘルスプラットフォームへ拡張できるかという大きなビジョンを最初に提示してください。なぜいまこのタイミングで夢なのか、そしてこれがどのように大きな社会的変化をもたらすのかを説得力のあるスライドで説明する必要があります。技術的な誇りはおいておき、まずはビジネス価値と解決できる根本的な社会課題にフォーカスしてピッチ資料を全面的に再構成してください。"
                }
            ]
        }
        eval_c1 = Evaluation(
            hackathon_id=9999, team_id="demo_team",
            scores_json=json.dumps(c1_scores), impact_score=3.0,
            strengths_risks_json=json.dumps(c1_strengths_risks),
            is_final=False, source_text="Demo Team Consultation 1 Source Code"
        )
        db.add(eval_c1)

        # Consultation 2 (Mid Score: ~74.0 with Objection QA)
        c2_scores = {
            "Innovation & Creativity": 3.5, "Technical Implementation": 3.5,
            "Problem Solving & Impact": 3.5, "Product & UX": 3.5,
            "Working Prototype": 4.0, "Presentation": 4.0
        }
        c2_strengths_risks = {
            "summary_en": "DreamStream AI V2. Added dream visualization using generated imagery and fixed database security issues.",
            "summary_ja": "DreamStream AI V2。画像生成による夢のビジュアル化を追加し、データベースのセキュリティ問題を修正。",
            "judges_feedback": [
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "judge_persona": "Cares about market fit and monetization.",
                    "feedback_en": "Using generative AI to visualize dreams is a major improvement. It creates a hook that users will naturally want to share on social media, driving organic, low-cost user acquisition. However, the business model is still fuzzy. Direct consumer subscription for dream visualization is a tough sell in this economy. Have you considered a B2B model, such as partnering with corporate wellness platforms, or integration with premium meditation apps? Don't cling to B2C monetization; a pivot to partnering with medical institutions or sleep clinics based on the collected data could be highly viable. Work more on price packaging and target personas to increase LTV. This visualization feature will serve as a powerful demo for B2B pitches.",
                    "feedback_ja": "生成AIを使って夢を視覚化するのは素晴らしい改善です。ユーザーが自然とSNSにシェアしたくなる強力なフックになり、低コストで有機的なユーザー獲得が期待できます。しかし、ビジネスモデルは依然として不透明です。この経済状況下で一般ユーザーに夢の可視化サブスクを売るのは困難です。企業のウェルネスプラットフォームと提携するB2Bモデルや、有料マインドフルネスアプリとの統合を検討したことはありますか？B2Cでの収益化に固執せず、蓄積したデータをもとに医療機関や睡眠クリニックと提携するビジネスモデルへのピボット（方向転換）も視野に入れると良いでしょう。顧客単価（LTV）を高めるための価格設計やターゲット選定をもう少し詰めてみてください。この機能があれば、B2B向けのピッチでも強力なデモとして機能するはずです。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "Excellent job addressing the security issues; the parameterized queries and the transition to SQLite encryption are solid. However, the image generation API calls are synchronous and block the main event loop. If more than three users request dream visualizations at the same time, the server will hang. You need to implement an asynchronous architecture with a task queue (like Celery and Redis) to process image generation in the background. Additionally, the API key is hardcoded in the config file; move it to environment variables immediately. Do not forget to mask credentials in your log handling. I also recommend adding Trace IDs to your structured JSON logs to trace issues easily when they arise.",
                    "feedback_ja": "セキュリティ問題への対処はお見事です。パラメータ化クエリと暗号化への移行は堅実です。しかし、画像生成APIの呼び出しが同期的に行われており、メインのイベントループをブロックしています。同時に3人以上のユーザーが夢のビジュアル化をリクエストすると、サーバーはハングします。画像生成をバックグラウンドで処理するために、CeleryとRedisのようなタスクキューを用いた非同期アーキテクチャを導入してください。さらに、APIキーが設定ファイルにハードコードされているため、すぐに環境変数へ切り替えるべきです。エラーログ出力処理での機密情報のマスキングも忘れないでください。システム障害時のトレースを容易にするために、構造化ログ（JSON等）に各リクエスト固有のTrace IDを付与して出力する仕組みも推奨します。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The generated gallery is visually striking, and the dark mode theme is a huge step forward. But there is a glaring issue with the wait state. When the user requests an image, the screen stays frozen for 8 to 12 seconds with no feedback. This is when users close the app thinking it crashed. You must implement a beautiful loading skeleton screen or a micro-animation with progressive updates (e.g., 'Analyzing colors...', 'Painting dreamscape...') to manage expectations. In addition, the card layout showing the dream gallery has too many text details competing with the images. Reduce font sizes and increase padding to let the generated visuals stand out. A premium experience is only achieved when UI and UX work together seamlessly.",
                    "feedback_ja": "生成されたギャラリーは視覚的に非常に魅力的で、ダークモードへの変更は大きな前進です。しかし、待機時の画面設計に深刻な問題があります。画像生成をリクエストした際、画面が8〜12秒間フィードバックなしで完全に静止します。これではアプリがフリーズしたと勘違いして閉じられてしまいます。美しいスケルトンスクリーンや、「色彩を解析中...」「夢の世界を描画中...」といった進捗を示すマイクロアニメーションを実装してください。また、生成された夢の画像を一覧表示するカードデザインですが、情報レイアウトが煩雑になっています。文字情報のフォントサイズを下げ、余白を増やすことで、生成画像自体が最も目立つようにデザインを洗練させてください。UIとUXがシームレスに噛み合ってこそ、プレミアムな体験が完成します。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "judge_persona": "Cares about scope and MVP.",
                    "feedback_en": "Adding dream visualization using image generation is a high-value feature that directly solves the engagement issue. But let's track the metrics. Do users who get visual dreams have higher retention than those who only get text? I advise creating a simple telemetry funnel to track conversion from text input to image generation, and see if this visual feature actually increases day-3 retention before you commit to optimizing it further. Do not add highly personalized features at this stage of the hackathon. For now, prioritize image generation stability and basic event logging for retention tracking. Instead of adding new scope, spend time proving that the current feature actually delivers value.",
                    "feedback_ja": "画像生成によるビジュアル化は、エンゲージメント低下という課題を直接解決する高価値な機能です。ただ、数値を計測しましょう。ビジュアル化された夢を受け取ったユーザーは、テキストのみのユーザーよりも継続率（リテンション）が高いでしょうか？テキスト入力から画像生成までの遷移ファネルを計測し、このビジュアル機能が実際に3日後リテンションの向上に寄与しているかを確かめてから、さらなる最適化に進むことを勧めます。ハッカソンの時間内で高度なパーソナライズ機能をこれ以上追加するのはお勧めしません。現時点では、画像生成の安定性とリテンション分析用の最小限のイベント収集（テレメトリ）を最優先で開発すべきです。機能を追加する代わりに、既存の機能がユーザーにとって本当に価値があるのかという証明に時間を割いてください。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "judge_persona": "Cares about pitch and scale.",
                    "feedback_en": "You've built a product that deeply resonates with human emotions, which is rare in a tech hackathon. The demo is highly polished, but you must demonstrate unit economics. Generating images via external APIs incurs real costs. If a free user triggers image generation 20 times a day, your business model scales into a financial deficit. Show a tiered approach: text-only analysis on a free tier, and high-res image generation restricted to a premium subscription. Investors will not back a startup where scaling correlates with growing losses. Add a slide detailing API cost estimations and how premium subscriptions will cover it. This will make your business plan highly convincing.",
                    "feedback_ja": "技術系ハッカソンでは珍しい、ユーザーの感情に深く共鳴するプロダクトを構築できています。デモの完成度は高いですが、ユニットエコノミクス（1ユニットあたりの採算）を示す必要があります。外部APIを使った画像生成には原価がかかります。無料ユーザーが1日に20回画像生成を行うと、利用されるほど赤字になります。フリープランはテキスト分析のみ、プレミアムプランで高解像度画像生成といった階層化戦略を示し、採算性があることを証明してください。投資家は、拡大すればするほど赤字が膨らむモデルには投資しません。ピッチ資料には、API利用料の見積もりと、課金ユーザーがそれをどのように回収するかという具体的な数値を明記したスライドを追加してください。そうすれば、ピッチ全体の現実味が格段に上がります。"
                }
            ]
        }
        c2_qa = {
            "user_objection": "We believe dream analysis can be a painkiller for sleep clinics and therapy. Can you re-evaluate the market impact?",
            "qa_summary_en": "The panel acknowledges the potential B2B pivot to sleep clinics, which transforms the app from a wellness tool to a clinical utility.",
            "qa_summary_ja": "睡眠クリニックへのB2Bピボットの可能性について、審査員団は合意しました。これにより、アプリは単なるウェルネスツールから臨床的な実用ツールへと昇華されます。",
            "judges_responses": [
                {
                    "judge_name": "Alex",
                    "response_en": "Great pivot! Targeting clinics changes the monetization completely. I increase my impact score potential.",
                    "response_ja": "素晴らしいピボットです！クリニックをターゲットにすることで収益化手段がガラリと変わります。インパクトの評価を上げます。"
                },
                {
                    "judge_name": "David",
                    "response_en": "Good explanation, but ensure HIPAA/GDPR compliance for clinic integration.",
                    "response_ja": "納得の説明です。ただし、クリニック統合の際はHIPAA/GDPRコンプライアンスを徹底してください。"
                }
            ]
        }
        eval_c2 = Evaluation(
            hackathon_id=9999, team_id="demo_team",
            scores_json=json.dumps(c2_scores), impact_score=3.5,
            strengths_risks_json=json.dumps(c2_strengths_risks),
            qa_json=json.dumps(c2_qa),
            is_final=False, source_text="Demo Team Consultation 2 Source Code"
        )
        db.add(eval_c2)

        # Consultation 3 (High Score: ~82.0)
        c3_scores = {
            "Innovation & Creativity": 4.0, "Technical Implementation": 4.0,
            "Problem Solving & Impact": 4.0, "Product & UX": 4.0,
            "Working Prototype": 4.0, "Presentation": 4.5
        }
        c3_strengths_risks = {
            "summary_en": "DreamStream AI V3. Refined UI/UX with async task queueing for image generation and initial drafts of sleep clinic API.",
            "summary_ja": "DreamStream AI V3。画像生成のための非同期タスクキューイングによるUI/UXの洗練、および睡眠クリニックAPIの初期ドラフトの実装。",
            "judges_feedback": [
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "judge_persona": "Cares about market fit.",
                    "feedback_en": "This B2B pivot is excellent execution. By providing an API for sleep clinics to monitor their patients' sleep-onset anxiety through visual logs, you've unlocked a massive market. The transition from B2C novelty to B2B infrastructure is a textbook example of finding product-market fit. Shifting from low-barrier consumer wellness subscriptions to high-ticket enterprise contracts with sleep clinics will bring massive business stability. I highly praise this rapid business evolution during the hackathon. As next steps, draft a clear strategy for low-friction pilot onboarding and define your expected customer acquisition cost (CAC).",
                    "feedback_ja": "このB2Bへのピボットは素晴らしい実行力です。睡眠クリニックが患者の入眠時不安を視覚的なログを通じてモニタリングするためのAPIを提供することで、巨大な市場が開かれました。B2CのエンタメアプリからB2Bのインフラへと移行したことは、プロダクトマーケットフィット（PMF）を見出すための教科書的な好例です。初期のウェルネス向けの課金から、睡眠クリニックを対象とした高単価な年間契約や月額サブスクへとシフトすることで、事業の安定性が格段に高まります。ハッカソン期間中にこれだけのビジネスモデルの進化を遂げたことを強く評価します。次のステップとして、主要なクリニックの導入障壁を下げるための無料トライアルの提供方法や、顧客獲得コスト（CAC）の最適化についても具体的な計画を策定してください。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture.",
                    "feedback_en": "The async architecture using Celery and Redis is flawless. Image generation tasks are now handled in the background, and the UI remains perfectly responsive. I also see that you added integration tests for the clinic webhook calls, which shows great engineering hygiene. The code is highly modularized. However, since the clinics will be handling sensitive medical/health logs, you must secure webhook payloads with signature verification and use TLS for all communications. Ensure all keys and secrets are loaded from environment variables. Overall, the system design is highly robust and getting ready for a production release.",
                    "feedback_ja": "CeleryとRedisを使用した非同期アーキテクチャの導入は完璧です。画像生成タスクはバックグラウンドで処理され、UIは遅延なく完全にレスポンシブな状態を維持しています。また、クリニック向けのWebhook呼び出しに対する結合テストが追加されており、優れたエンジニアリング衛生が保たれています。コードのモジュール構造も非常に綺麗です。ただし、クリニックが扱うデータは機密性の高い医療・ヘルスデータですので、暗号化通信（HTTPS/TLS）やWebhook呼び出し時のシグネチャ検証（署名チェック）は必須です。APIキーとシークレットは、必ず環境変数から取得するように制限を強めてください。全体として、非常に高い設計思想でコーディングされており、プロダクションへの準備が整いつつあります。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The loading state skeleton screen you implemented is beautiful, and the card-flip transition to reveal the generated dream image feels extremely premium and satisfying. For the clinic admin portal, make sure the patient dashboard maintains this level of visual clarity and doesn't get cluttered with too many technical metrics. Clinicians need to scan patient timelines rapidly, so displaying emotional trends in an intuitive graph would be a great enhancement. Verify the contrast ratios of your palette against WCAG 2.1 accessibility standards. Incorporating inclusive UI controls, like font scaling and screen reader compatibility, will elevate this tool for clinical users.",
                    "feedback_ja": "実装されたローディング用のスケルトンスクリーンは見事で、生成された夢画像が表示される際のカード反転（フリップ）アニメーションは、極めて高級感がありユーザーを満足させます。クリニックの管理者向けポータルでも、この高いビジュアル品質を維持し、情報が煩雑にならないように注意してください。医師や技師が患者のログを素早く確認できるよう、直感的なダッシュボードUIにし、夢の感情の起伏をタイムライン形式で表示するような工夫を施すとさらに良いでしょう。また、配色におけるコントラスト比を検証し、アクセシビリティ基準（WCAG 2.1）を満たしているか確認してください。文字サイズ調整機能や読み上げ対応など、医療用ツールとしての包摂的なデザインを意識すると完璧です。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "judge_persona": "Cares about scope and MVP.",
                    "feedback_en": "You've successfully prioritized the sleep clinic API over the social feed, which was the right decision. The scope is now sharp and aligned with your B2B validation goals. Now, I recommend focusing on a small cohort of 3 clinics to run a pilot test. Collect feedback on their actual usage patterns before building out any complex enterprise billing features. Don't worry about building a flawless product during the hackathon. Focus first on the core requirement: log reliability and frictionless sharing for clinicians and patients. Creating a brief developer API integration guide in Markdown will yield significant points during the jury review.",
                    "feedback_ja": "ソーシャルフィードよりも睡眠クリニック向けAPIの実装を優先したことは、正しい意思決定でした。製品のスコープが明確になり、B2B検証の目標に合致しています。次のステップとして、3つのクリニックに絞って試験導入（パイロット）を行うことを勧めます。複雑な課金機能を作る前に、彼らの実際の使用パターンからフィードバックを集めてください。ハッカソン期間内で完璧なプロダクトを作ろうとする必要はありません。クリニックの医師や患者が最も価値を感じる「ログの正確性と共有のしやすさ」というコア要件を満たすことが先決です。APIの接続マニュアルや開発者向けの統合用ドキュメントをMarkdownで簡潔に用意しておくと、デモ時や審査員の評価に非常に有利になります。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "judge_persona": "Cares about pitch and scale.",
                    "feedback_en": "The addition of a concrete B2B sales narrative has made your pitch 10x stronger. You showed a clear understanding of the customer acquisition cost (CAC) and the lifetime value (LTV) of clinic subscriptions. My only advice now is to prepare a slide detailing the regulatory pathway (like HIPAA) to show you are ready for enterprise deployment. Healthcare ventures are inherently bound by regulatory compliance, and addressing this early on will drastically lower the psychological barrier for potential investors. Briefly highlighting your proprietary advantages, such as custom emotion annotation pipelines, will secure your pitch's winning status.",
                    "feedback_ja": "具体的なB2Bの販売ストーリーを加えたことで、ピッチ全体の説得力が10倍向上しました。顧客獲得コスト（CAC）とクリニック契約の生涯価値（LTV）についての明確な理解が示されています。アドバイスとしては、エンタープライズへの導入準備ができていることを示すために、HIPAAなどの法規制クリアのロードマップを記載したスライドを1枚用意しておくと完璧です。医療分野への進出は規制がつきものですので、そこに対する認識が最初からあることをアピールできると、投資家の心理的ハードルは大幅に下がります。また、競合に対する技術的な優位性（独自のデータアノテーション手法や感情抽出ロジック）についても、簡潔に言及できると完璧なプレゼンになります。"
                }
            ]
        }
        eval_c3 = Evaluation(
            hackathon_id=9999, team_id="demo_team",
            scores_json=json.dumps(c3_scores), impact_score=4.0,
            strengths_risks_json=json.dumps(c3_strengths_risks),
            is_final=False, source_text="Demo Team Consultation 3 Source Code"
        )
        db.add(eval_c3)

        # Final Submission (Top Score: ~89.0 with Admin Chat)
        final_scores = {
            "Innovation & Creativity": 4.5, "Technical Implementation": 4.5,
            "Problem Solving & Impact": 4.0, "Product & UX": 4.5,
            "Working Prototype": 4.5, "Presentation": 4.5
        }
        final_strengths_risks = {
            "summary_en": "DreamStream AI Final. Complete integration with mock clinic database, fully secure AES-256 local dream logs storage, and polished mobile-first interface.",
            "summary_ja": "DreamStream AI 最終提出。模擬クリニックデータベースとの完全な統合、AES-256による完全に保護されたローカル夢ログストレージ、洗練されたモバイルファーストインターフェースの提供。",
            "judges_feedback": [
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Incredible progress. You have taken a simple consumer novelty and turned it into a viable B2B business during the course of this hackathon. The mock clinic integration proves you can build infrastructure. You have validated the pricing, monetization model, and target audience. Outstanding execution! With this level of completion, you should spin this out of the hackathon and pitch for seed funding immediately. The alignment between problem, product, and monetization is incredibly robust. Your team exhibits stellar execution capabilities, and as a serial entrepreneur, I'm ready to write a check. Hat's off to an outstanding submission!",
                    "feedback_ja": "素晴らしい進歩です。ハッカソンの短い期間中に、単なるB2Cのエンタメアプリから実用的なB2Bビジネスへと見事に昇華させました。模擬クリニックとのデータベース統合は、インフラ構築能力を証明しています。価格設定、マネタイズモデル、ターゲット層のすべてが実証されています。抜群の実行力です！この完成度であれば、ハッカソンの枠を超えてすぐにシードの資金調達を開始すべきです。顧客の課題解決に向けたアプローチが一貫しており、ピッチからプロダクト、ビジネス設計までのラインが極めて強固です。チームのバランスも良く、起業家として明日にも投資の意思決定を下したいと思わせる素晴らしいクオリティに脱帽しました。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "The codebase is a model for hackathon submissions. Security standards are fully met with AES-256 encryption at rest for sensitive dream logs, and credentials are securely managed. The implementation of clean, self-documenting REST APIs with comprehensive unit test coverage makes this codebase production-ready. Outstanding architecture. The CI/CD pipelines are fully set up, ensuring all code modifications compile error-free with automatic lint checks. Error handling is explicit, and logging includes Trace IDs, making telemetry highly actionable. To maintain such exceptional engineering hygiene in a time crunch is a testament to your technical team's caliber.",
                    "feedback_ja": "このコードベースはハッカソン提出物のモデルケースと言えます。機密性の高い夢ログに対するAES-256の保存時暗号化、厳格なシークレット管理により、セキュリティ基準が完璧に満たされています。テストカバレッジを備えたクリーンで自己文書化されたREST APIの実装は、今すぐプロダクション環境に移行できる品質です。見事なアーキテクチャ設計です。CI/CDパイプラインも完全に整備されており、自動テストとリントエラーのチェックが完璧に行われています。例外処理も徹底しており、Trace IDがログに付与されているため本番での追跡性も問題ありません。これほど優れた技術衛生とクオリティを短期間で維持できたことは、技術チームの並外れた能力を示しています。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "Beautiful, responsive, dark-mode design that represents dreams perfectly. The accessibility scores are close to 100 with clear contrast and ARIA labels. The micro-interactions and transitions create a truly premium, seamless user journey. You have created an experience that is both medically functional and emotionally delightful. Every UI component is cleanly encapsulated in the design system, ensuring consistent styling. The skeleton loading states and reveal animations provide excellent user satisfaction. As a product designer, I am thoroughly impressed and find this interface close to flawless.",
                    "feedback_ja": "夢の世界観を完璧に表現した、美しくレスポンシブなダークモードデザインです。明快なコントラスト設計や適切なARIAラベル付与により、アクセシビリティスコアは100に近いです。マイクロインタラクションとアニメーションが、極めてプレミアムでシームレスな体験を実現しています。医学的な実用性と感情的な心地よさを見事に両立させました。各コンポーネントが機能的にモジュール化されており、デザインシステムが崩れることなく綺麗に統一されています。待機時のスケルトンスクリーンや、結果発表時の演出はユーザーに感動を与えます。プロダクトデザイナーとして誇らしく思える仕上がりであり、文句のつけようがありません。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "feedback_en": "The product focus is razor-sharp. You resisted the temptation of scope creep and polished the features that actually matter to your B2B customers—the secure logs and the clinic integration. The metrics deck and integration roadmap you submitted demonstrate a mature product mindset. Ready for deployment. The speed at which you validated user feedback and iterated on your product schema during this hackathon is exemplary. There is no dead weight in the application; every feature direct contributes to core value. As a PM, I applaud your execution and prioritization discipline.",
                    "feedback_ja": "製品のフォーカスが極めて鋭いです。スコープクリープの誘惑に打ち勝ち、B2B顧客にとって真に重要な機能（セキュアなログ保存とクリニック連携）のみを磨き上げました。提出された指標（メトリクス）予測と統合ロードマップは、成熟したプロダクト思考を示しています。デプロイの準備は完了しています。ユーザーテストからの学習サイクルをハッカソン期間中に完了させ、フィードバックを元に製品仕様を磨き上げた姿勢は模範的です。無駄な機能が一切なく、すべての行コードが価値提供に直結しています。プロダクトマネージャーとして、素晴らしいロードマップの実行とチームの優先順位付けの判断力を賞賛します。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "This is a winning pitch. You framed the problem perfectly, demonstrated a working B2B API integration, and showed a clear path to profitability. The quality of your presentation materials matches the stellar quality of your codebase. You answered every technical and business question with absolute confidence. I would write a check tomorrow. The slide deck was beautifully structured, highlighting the sleep medicine industry growth, regulatory roadmaps, and quantifiable clinic ROI. A phenomenal synergy between deep engineering and sharp business model; this is by far the best submission.",
                    "feedback_ja": "これは間違いなく最優秀のピボットとピッチです。課題の設定が完璧で、動作するB2B API連携のデモを示し、収益化への明確な道筋を証明しました。プレゼンテーションのクオリティは、素晴らしいコードベースの品質と見事に合致しています。技術・ビジネスのあらゆる質問に自信を持って回答していました。明日にも出資したいレベルです。スライドの構成は明快で、睡眠医療の市場の伸び、HIPAA規制への適合方針、そこでクリニックが獲得できる経済的価値が数値で明快に示されていました。技術力とビジネスモデルの双方が高次元で融合した、今回のハッカソンで圧倒的なベスト submission です。"
                }
            ]
        }
        eval_final = Evaluation(
            hackathon_id=9999, team_id="demo_team",
            scores_json=json.dumps(final_scores), impact_score=4.5,
            strengths_risks_json=json.dumps(final_strengths_risks),
            is_final=True, source_text="Demo Team Final Submission Source Code"
        )
        db.add(eval_final)
        db.flush()

        # Seed Admin Chat for the final evaluation
        admin_chat = AdminChat(
            evaluation_id=eval_final.id,
            question_en="Explain the security measures implemented in the final repository for storing user generated dream descriptions.",
            question_ja="ユーザーが生成した夢の記述を保存するために、最終リポジトリに実装されたセキュリティ対策を説明してください。",
            answer_en="The project implements AES-256 encryption at rest for the `dream_content` database column and uses strict session tokens with short expiry to prevent session hijacking.",
            answer_ja="プロジェクトは、`dream_content`データベースカラムに対してAES-256による保存時暗号化を実装しており、セッションハイジャックを防ぐために有効期限の短い厳格なセッションキーを使用しています。"
        )
        db.add(admin_chat)

        # Seed evaluations for demo_team2 (EcoLoop / GreenGrid)
        # Consultation 1 (Low Score: ~58.0)
        t2_c1_scores = {
            "Innovation & Creativity": 3.0, "Technical Implementation": 3.0,
            "Problem Solving & Impact": 2.5, "Product & UX": 2.5,
            "Working Prototype": 3.0, "Presentation": 3.0
        }
        t2_c1_strengths_risks = {
            "summary_en": "Initial grid optimization simulation setup.",
            "summary_ja": "スマートグリッド最適化の初期シミュレーションセットアップ。",
            "judges_feedback": [
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "The simulator core runs, but it relies on static CSV data for grid state. There is no real-time data streaming pipeline. For a grid optimizer, we need to see how you plan to handle high-frequency sensor streams and model drift. In its current form, this is a static data analysis tool rather than a deployable grid infrastructure. The database schema also decouples sensor logs from configuration tables too loosely. Design a real-time transport layer using WebSockets, and implement buffering and auto-retry logic in code when dealing with volatile inputs. Establishing this pipeline is key.",
                    "feedback_ja": "シミュレータのコアは動いていますが、静的なCSVデータに依存しています。リアルタイムのデータストリーミング用パイプラインがありません。グリッド最適化システムとして、高頻度のセンサーデータやモデルドリフトにどう対処するかの設計が必要です。このままでは、静的なデータ分析ツールであり、現場での運用に耐えうるインフラになりません。データベーススキーマ設計においても、センサーログと構成パラメータの関連付けが疎結合すぎます。WebSocketを用いたリアルタイム通信を設計し、ストリーミングデータが入ってきた際のエラーバッファリングや自動リトライの仕組みをコードレベルで設計してください。まずはデータ入力のパイプラインを確立することが先決です。"
                },
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Who is the customer? National grids are notoriously difficult to sell to. The sales cycles are measured in years. If you want this to survive, target micro-grids, local renewable farms, or EV charging stations where you can run quick PoCs. These segments face urgent pain points like peak constraints and battery degradation. Use the hackathon period to target independent energy providers and outline exactly how you minimize their operating expenses. Focus on a sharp, niche market where you can secure a pilot tomorrow rather than presenting unrealistic national scale plans.",
                    "feedback_ja": "顧客は誰ですか？国家規模の電力網（送電事業者）への営業は極めて困難で、サイクルに数年かかります。生き残りたいなら、迅速なPoCが可能なマイクログリッド、地方の再生可能エネルギー発電所、またはEV充電ステーションをターゲットにすべきです。これらの顧客セグメントであれば、彼らが今抱えている「ピーク電力制限」や「バッテリー劣化」などの具体的な課題にすぐアプローチできます。ハッカソン中だからこそ、ターゲットをニッチな独立系エネルギー業者に絞り込み、彼らにとっての価値（電気代削減や稼働率向上）をどう定量化できるか検証を進めるべきです。大風呂敷を広げた計画ではなく、明日にも契約を取れる「小さく鋭い」市場から始めてください。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "The configuration page has over 30 unorganized input fields for physical parameters. This is a UX nightmare for grid operators. Use sensible defaults and group them into progressive disclosure panels. In this raw form, it's impossible to tell which parameters are critical to grid stability. Establish a clear visual hierarchy. Add instant validation to input fields so users receive immediate feedback when values drift outside safe thresholds. Redesign this interface to minimize operator cognitive fatigue and accidental input errors.",
                    "feedback_ja": "設定ページに整理されていない入力フィールドが30以上も並んでいます。これはオペレーターにとってUXの悪夢です。妥当なデフォルト値を設定し、折りたたみ式パネル等で段階的に開示するUIに整理してください。現在の無機質なフォーム表示では、どのパラメータがグリッドの安全性にクリティカルな影響を与えるのか一目で分かりません。もっと視覚的なヒエラルキーを意識してください。インプットデータにバリデーションをかけ、許容範囲外の数値が入った場合は即座にエラーフィードバックを出す仕組みも必要です。オペレータが監視する画面なのですから、心理的な負担とミスを最小限に抑える機能的なデザインに再設計してください。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "feedback_en": "The core purpose of this tool is unclear. Are you optimizing for peak shaving, grid health, or consumer cost reduction? Focus on one specific user scenario (e.g., peak demand mitigation) before attempting a general solution. Building an engine that does everything during a hackathon is impossible and dilutes your value proposition. For this prototype, focus 100% on battery charging controls during sudden renewable fluctuations. Prove this single use case works exceptionally well, and hide all other irrelevant features from the client interface.",
                    "feedback_ja": "このツールの核心となる目的が不明確です。ピークカット、電力網の健全性維持、それとも消費者のコスト削減のどれに最適化していますか？一般的な最適化を目指す前に、まずは特定のユースケース（ピーク時の負荷軽減など）にフォーカスしてください。ハッカソンで何でもできるジェネラルな最適化エンジンを作るのは不可能です。それはプロダクトのフォーカスがぼやけている証拠です。今回のプロトタイプでは「再生可能エネルギーの出力急変時のバッテリー充放電制御」だけに目的を100%絞り込み、その単一のユースケースで圧倒的な成果を示すことに特化すべきです。無駄なパラメータはすべてダッシュボードから隠しましょう。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "Your pitch is missing the macro trend. Why does smart grid optimization matter 'right now'? High renewable penetration makes grids unstable, and grids are seeking software solutions. Frame your presentation around this global transition. No matter how advanced your optimization algorithms are, investors won't write checks if you don't connect them to macro social and financial tailwinds. Start your pitch's first minute with high-impact data on grid stability challenges and position your product as the timely solution to this crisis.",
                    "feedback_ja": "ピッチ資料にマクロな潮流（トレンド）の記述が欠けています。なぜスマートグリッドの最適化が『今』重要なのでしょうか？再生可能エネルギーの急増によって電力網が不安定化しており、世界がソフトウェアでの解決を求めています。このグローバルな規制緩和とエネルギーシフトを軸にピッチを構成してください。あなたが実装したアルゴリズムが技術的にどれほど難解であっても、それが生み出すマクロな社会的・経済的価値が投資家に伝わらなければ資金は集まりません。プレゼンの最初の1分で、気候変動対策と電力インフラ崩壊の危機をデータで示し、そこに対する唯一の解として自分たちのプロダクトを位置づけてください。"
                }
            ]
        }
        eval_t2_c1 = Evaluation(
            hackathon_id=9999, team_id="demo_team2",
            scores_json=json.dumps(t2_c1_scores), impact_score=2.8,
            strengths_risks_json=json.dumps(t2_c1_strengths_risks),
            is_final=False, source_text="Demo Team 2 Consultation 1"
        )
        db.add(eval_t2_c1)

        # Consultation 2 (Mid Score: ~71.0)
        t2_c2_scores = {
            "Innovation & Creativity": 3.5, "Technical Implementation": 3.5,
            "Problem Solving & Impact": 3.5, "Product & UX": 3.5,
            "Working Prototype": 3.5, "Presentation": 3.5
        }
        t2_c2_strengths_risks = {
            "summary_en": "Improved reinforcement learning algorithm and real-time dashboard UI.",
            "summary_ja": "強化学習アルゴリズムの改善とリアルタイムダッシュボードUIの追加。",
            "judges_feedback": [
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "The live monitoring dashboard is readable and displays all necessary real-time parameters, but the visual density is too high. Graphs, progress bars, and raw numbers are competing for attention. Use clearer layout hierarchies, reduce non-essential borders, and use color purely to draw attention to critical threshold breaches. In its current form, key metrics (like critical alerts or remaining capacity) are buried in telemetry noise. Apply micro-animations and whitespace to create a 'calm UI' where operators only react when anomalies occur.",
                    "feedback_ja": "リアルタイム監視ダッシュボードは必要十分なパラメータを表示できていますが、視覚的な情報密度が高すぎます。グラフやプログレスバー、生の数値が互いに注意を引き合っています。レイアウトの階層構造を整理し、不要な枠線を減らし、危険な閾値を超えた警告にのみ色を使うようにしてください。現在のダッシュボードは、コントロールルームで本当に見たい情報（異常アラートやバッテリー残量など）がノイズに埋もれてしまっています。グラスモーフィズムや余白を意識し、オペレータが何もないときは安心でき、異常時だけ瞬時に行動に移せるような「静かなデザイン」へと洗練させてください。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "PPO reinforcement learning model shows good convergence. However, I noticed that the WebSocket connection that feeds the dashboard lacks automatic reconnection logic. If the server drops for a second, the frontend hangs indefinitely. Implement exponential backoff reconnection. Furthermore, since the RL inference runs on the main thread, high-frequency data spikes cause noticeable visual lag in your UI rendering. Move your inference loops to Web Workers or separate processes to keep the UI smooth. Audit your packages to prune unused dependencies and keep the build clean.",
                    "feedback_ja": "PPO強化学習モデルは良好な収束を示しています。しかし、ダッシュボードにデータを流すWebSocket接続に自動再接続ロジックがありません。サーバーが一瞬切断されるとフロントエンドがハングします。指数バックオフを伴う再接続処理を入れてください。また、強化学習の推論ロジックがメインのスレッドで動いているため、データ受信時の処理遅延によりUI描画にカクつき（遅延）が生じています。推論処理をWeb Workerや別プロセスへ逃がし、UIのレスポンシブさを維持する工夫が必要です。コード全体の依存関係を見直し、使われていないライブラリを削除してパッケージサイズを軽量に保つこともエンジニアリング上の重要なステップです。"
                },
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Focusing on localized corporate micro-grids is a smart pivot. It makes the monetization story much more credible. You need to show a clear ROI projection: how many thousands of dollars does a corporate campus save on electricity bills by deploying GreenGrid? For a business to pay thousands in subscription fees, you must prove savings that are multiples of that price. Use your simulation engine to project peak saving efficacy and generate cost reduction curves. Presenting these concrete figures to address the customer's cash flow concerns will win deals.",
                    "feedback_ja": "ローカルな企業向けマイクログリッドにフォーカスしたのは賢いピボットです。収益化のストーリーが格段に現実的になりました。次は具体的なROI（投資対効果）の予測を示す必要があります。GreenGridを導入することで、企業のキャンパスが電気代を年間何ドル削減できるのかを数値化してください。企業がこのソフトに月額数千ドルを支払うためには、その数倍の電気代削減が保証されなければなりません。例えば、シミュレータを使って「GreenGrid導入によるピークカット実績とコスト削減モデル」のシミュレーション結果をピッチ資料に明記してください。顧客が直面している財布の痛みを和らげる具体的数字こそが、ピッチを成約に導きます。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "The technical demo is impressive, but your pitch is getting bogged down in reinforcement learning algorithms. Investors care about the unit economics and market size. Frame the pitch around grid stability risks under high renewable penetration and how GreenGrid captures that value. Technical advantages are fine, but keep it to one slide. Focus the rest of your time explaining the total addressable market (TAM) of micro-grids and your go-to-market channels to scale rapidly. Shift from an academic engineering tone to a business leadership perspective to attract VC interest.",
                    "feedback_ja": "技術デモは素晴らしいですが、ピッチが強化学習のアルゴリズム説明に終始してしまっています。投資家が知りたいのはユニットエコノミクスと市場規模です。再生可能エネルギー導入拡大に伴うグリッドの不安定化リスクと、GreenGridが提供する経済的価値を軸にピッチを再構成してください。技術的な優位性を説明することは重要ですが、それはスライド1枚で十分です。残りの時間は、ターゲットとする企業マイクログリッドの市場がどれだけ大きく（TAM）、どのような販売チャネルで急速にスケールできるかを説明することに割いてください。技術防衛やアルゴリズムの詳細説明よりも、市場性（マーケット性）にフォーカスしてピッチしてください。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "feedback_en": "The team made good progress in usability, but you added a manual overriding feature for safety that goes against the AI optimization premise. If human intervention is required for basic scaling, it defeats the automated optimization. Define strict guardrails so the AI can operate autonomously within safe bounds. Restrict manual overrides to extreme emergencies and ensure audit logs track these events. Instead of relying on manual tweaks, visualize the AI's confidence levels and decision pathways to build trust with the operators so they can safely leave the engine in autopilot.",
                    "feedback_ja": "使いやすさの面で進歩が見られます。しかし、安全性のために追加した『手動オーバーライド（強制介入）』機能は、AI最適化の前提と矛盾しています。基本調整に人間が介在しなければならないなら、自動最適化の意味がありません。AIが安全な範囲内で完全に自律動作できるよう、厳格なガードレール（境界条件）を定義してください。手動介入は、極端な緊急事態のみに制限し、そのためのログ記録や権限管理（監査ログ）を実装する必要があります。何でも手動で直せるようにする代わりに、AIの意思決定プロセスを視覚化（説明可能AI）して、オペレータが安心して自動制御を眺めていられるプロダクト設計に磨き上げてください。"
                }
            ]
        }
        eval_t2_c2 = Evaluation(
            hackathon_id=9999, team_id="demo_team2",
            scores_json=json.dumps(t2_c2_scores), impact_score=3.5,
            strengths_risks_json=json.dumps(t2_c2_strengths_risks),
            is_final=False, source_text="Demo Team 2 Consultation 2"
        )
        db.add(eval_t2_c2)

        # Seed evaluation for demo_team3 (HealthFlow / AuraScan)
        # Final Submission only (Score: ~85.0)
        t3_final_scores = {
            "Innovation & Creativity": 4.5, "Technical Implementation": 4.0,
            "Problem Solving & Impact": 4.5, "Product & UX": 4.0,
            "Working Prototype": 4.0, "Presentation": 4.5
        }
        t3_final_strengths_risks = {
            "summary_en": "AuraScan Final submission. Runs image processing locally using WASM and gives immediate stress levels evaluation.",
            "summary_ja": "AuraScan最終提出。WASMを使用してローカルで画像処理を実行し、即座にストレスレベル評価を提供します。",
            "judges_feedback": [
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Extremely high market demand for contactless health screening. By targeting corporate wellness programs first, you have a clear, low-friction go-to-market strategy. The self-serve onboarding flow is well thought out. The HR manager portal to track employee wellness indices visually is highly persuasive. During this hackathon, you successfully proved that you can deliver an enterprise-ready product with low onboarding friction. You have significant potential to spin this off as a health-tech startup.",
                    "feedback_ja": "非接触ヘルススクリーニングに対する市場の需要は極めて高いです。まず企業のウェルネスプログラムをターゲットにする戦略は、障壁が低く賢明なアプローチです。セルフサーブ型のオンボーディングフローもよく考えられています。B2B顧客である人事担当者が従業員のメンタルヘルス改善を視覚的にトラッキングできる管理者用画面も説得力があります。このハッカソン期間中に、ユーザー獲得コストを抑えながら迅速に企業に導入可能なプロダクトとしての整合性を見事に証明しました。このままヘルスケアテックのスタートアップとして立ち上げられる高いポテンシャルを感じます。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "Running the computer vision models entirely client-side using WebAssembly (WASM) is a brilliant architectural decision. It completely solves privacy concerns (no biometric data sent to servers) and minimizes server infrastructure costs. Code quality is high with clean separation of logic. Client-side performance is tuned well, rendering stably on standard mobile browsers. Unit test coverage is comprehensive, validating the core vital computation algorithms. Security, performance, and maintainability are in perfect harmony.",
                    "feedback_ja": "WASMを使用してコンピュータビジョンモデルを完全にクライアント側で実行する設計は、素晴らしいアーキテクチャの決定です。生体データをサーバーに送信しないためプライバシー懸念を完璧に解決し、サーバーコストも最小化できます。コードのモジュール化も美しく高品質です。クライアント側のパフォーマンスもよくチューニングされており、スマートフォンのブラウザでも安定して動作します。単体テストの網羅性も高く、バイタル計算エンジンの正確性が実証されています。セキュリティ, パフォーマンス, コードの保守性のすべてが非常に高い水準で調和した、エンジニアとしてお手本のような提出コードです。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "The mobile-first UX is exceptionally clean. The face alignment guide overlay during scanning is highly intuitive. The glassmorphic design and subtle pulse animations give a soothing, clinical-yet-friendly aesthetic that perfectly suits a health app. Warm and cool tones are balanced beautifully to avoid inducing user anxiety, and page transitions are seamless. The typography feels medical yet accessible, and results are structured cleanly. Inclusive accessibility patterns are well observed; a truly excellent design.",
                    "feedback_ja": "モバイルファーストのUXは非常によく洗練されています。スキャン中の顔位置合わせ用ガイド（オーバーレイ）は極めて直感的です。グラスモーフィズムデザインと微細なパルスアニメーションが、健康的で親しみやすい美しさを醸し出しており、ヘルスケアアプリに完璧にマッチしています。ユーザーに心理的なストレスを与えないような暖色と寒色のバランス、そしてスムーズな遷移演出は見事です。フォントも清潔感があり、スキャン結果の表示も情報整理が行き届いています。アクセシビリティも十分に考慮されており、完璧なデザイン評価に値します。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "Outstanding presentation and demo execution. You clearly demonstrated the value proposition within the first minute and handled technical questions with absolute confidence. The ROI story for HR managers (reducing burnout/absenteeism) is highly compelling. The demo video captured the instantaneous measurement loop perfectly. The growth potential, TAM calculations, and competitive moat were laid out with solid logical backing. From a VC perspective, this is a top-tier pitch ready for immediate funding evaluation.",
                    "feedback_ja": "プレゼンテーションとデモの実行は圧巻でした。最初の1分で明確なバリュープロポジションを示し、投資家に対する技術的な質問に対しても確固たる自信で回答していました。HR担当者向けのROIストーリー（燃え尽き症候群や欠勤率の低下）は極めて説得力があります。デモ動画でも、アプリが実際に一瞬でストレス値を測定する様子が完璧に収録されていました。ビジネスの成長ポテンシャル、市場規模（TAM）の計算、競合に対する優位性がスライド上に論理的に配置されていました。VCから見ても、即座に出資検討を始めたくなる一流のピッチでした。"
                },
                {
                    "judge_name": "Sarah", "judge_role": "Senior Product Manager",
                    "feedback_en": "The product focus is sharp, and you've streamlined the vital scanning flow to a simple 1-click action. You successfully executed a complete user test cycle during the hackathon, which shows great product discipline. Just make sure the offline sync syncs health logs securely once connection is re-established. Stripping out unnecessary features to prioritize scan reliability and core accuracy was an excellent PM call. The roadmap for production deployment is highly realistic, with clear post-hackathon iteration stages.",
                    "feedback_ja": "製品のフォーカスが非常に鋭く、バイタル測定の流れがシンプルな1クリックの動作に合理化されています。ハッカソン期間中に完全なユーザーテストのサイクルを実行できたことは、優れたプロダクト管理能力を示しています。オフラインからオンラインに復帰した際、健康ログが安全に同期される点だけ注意してください。不要な機能を削ぎ落とし、スキャンのしやすさと測定結果の信頼性というコア要件に100%フォーカスした判断はPMとして見事です。プロダクトのリリースに向けた開発ロードマップも堅実であり、次の開発優先順位も明確になっています。"
                }
            ]
        }
        eval_t3_final = Evaluation(
            hackathon_id=9999, team_id="demo_team3",
            scores_json=json.dumps(t3_final_scores), impact_score=4.2,
            strengths_risks_json=json.dumps(t3_final_strengths_risks),
            is_final=True, source_text="Demo Team 3 Final Submission"
        )
        db.add(eval_t3_final)

