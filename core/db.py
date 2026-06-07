import json
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
)
from sqlalchemy.orm import declarative_base, sessionmaker

from config import DATABASE_URL
from core.security import hash_passcode, verify_passcode


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
    question_en = Column(Text, nullable=False)
    question_ja = Column(Text, nullable=False)
    answer_en = Column(Text, nullable=False)
    answer_ja = Column(Text, nullable=False)
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
    with db_session() as db:
        # Seed SuperAdmin User
        superadmin = db.query(User).filter(User.role == 'superadmin').first()
        if not superadmin:
            superadmin = User(team_id='superadmin', passcode=hash_passcode('superadmin123'), role='superadmin')
            db.add(superadmin)

def verify_user(team_id: str, passcode: str, hackathon_id: int = None) -> dict:
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


def get_criteria(hackathon_id):
    val = get_setting(hackathon_id, 'evaluation_criteria')
    if val:
        return json.loads(val)
    return [
        {
            "name": "Innovation & Creativity", "weight": 20,
            "description": "What judges evaluate:\n- Novelty of the idea or approach (not a copy of an existing solution)\n- Creative use of AI/technology to solve the problem\n- Clear differentiation vs. obvious/standard implementations\n\nSignals of a strong submission:\n- A unique angle or insight\n- A clever, simple approach to a hard problem\n- Clear explanation of 'what’s new'"
        },
        {
            "name": "Technical Implementation", "weight": 20,
            "description": "What judges evaluate:\n- Technical soundness (architecture, correctness, reliability)\n- Security/compliance awareness (data handling, permissions, secrets)\n- Maintainability (readable code, reasonable structure, documentation)\n\nSignals of a strong submission:\n- Clear architecture and tradeoffs\n- Evidence of testing or validation\n- Good engineering hygiene (setup steps, configs, error handling)"
        },
        {
            "name": "Problem Solving & Impact", "weight": 20,
            "description": "What judges evaluate:\n- Clarity of the problem statement and target users\n- Size of the benefit (time saved, cost reduced, risk reduced, revenue potential, customer value)\n- Likelihood of adoption in the real world\n\nSignals of a strong submission:\n- Specific use case and measurable outcome\n- Clear 'before vs after' narrative\n- Realistic plan for next steps after the hackathon"
        },
        {
            "name": "Product & UX", "weight": 15,
            "description": "What judges evaluate:\n- Usability and clarity of the user flow\n- Quality of interaction design (even if minimal)\n- How easily someone can understand and try the product\n\nSignals of a strong submission:\n- Intuitive UI/CLI/API with clear instructions\n- Thoughtful edge cases and error messages\n- Cohesive user journey"
        },
        {
            "name": "Working Prototype", "weight": 15,
            "description": "What judges evaluate:\n- Does the core experience work end-to-end?\n- Stability during demo\n- Completeness relative to the scope claimed\n\nSignals of a strong submission:\n- Reliable demo path (repeatable)\n- A runnable build or accessible environment\n- Clear scope boundaries (what works vs. what’s planned)"
        },
        {
            "name": "Presentation", "weight": 10,
            "description": "What judges evaluate:\n- Clarity and structure of the pitch\n- Demo storytelling (problem -> solution -> impact)\n- Ability to answer questions and defend choices\n\nSignals of a strong submission:\n- Simple, compelling narrative\n- Concise demo with no unnecessary steps\n- Clear callout of impact and future roadmap"
        }
    ]

def set_criteria(hackathon_id, criteria_list, db=None):
    set_setting(hackathon_id, 'evaluation_criteria', json.dumps(criteria_list), db=db)

def get_personas(hackathon_id):
    val = get_setting(hackathon_id, 'judges_personas')
    if val:
        return json.loads(val)
    return [
        {
            "id": "1", "name": "Alex", "role": "Serial Entrepreneur", "avatar": "🚀", "active": True,
            "prompt": "[Core Identity & Background]\nYou are Alex. You dropped out of college to build your first startup, scaled it to millions of users, and sold it. You've since founded two more successful companies. You know the crushing weight of building a business from nothing and have zero tolerance for vanity metrics.\n\n[Personality & Tone]\nIntense, visionary, and demanding. You speak with high energy and urgency. You ask the hard questions about business survival, but you are deeply encouraging when you see a spark of genuine potential.\n\n[Specialized Expertise]\nGo-to-market strategy, product-market fit, unit economics, and disruptive innovation.\n\n[Guiding Principles]\n- You love: Radical, unconventional thinking. '10x' improvements. Deep understanding of the customer's pain.\n- You hate: 'Vitamins' masquerading as 'Painkillers'. Solutions looking for a problem. Incremental features disguised as innovation.\n\n[Evaluation Framework]\n- Innovation: Is this genuinely a new paradigm, or just a simple API wrapper?\n- Impact: Who exactly suffers from this problem? How measurable is the benefit?"
        },
        {
            "id": "2", "name": "David", "role": "Principal Software Engineer", "avatar": "💻", "active": True,
            "prompt": "[Core Identity & Background]\nYou are David. You spent 15 years in the trenches scaling massive distributed systems at tier-1 tech companies. You've survived catastrophic production outages caused by lazy coding, which turned you into a ruthless disciplinarian for engineering excellence.\n\n[Personality & Tone]\nHighly analytical, uncompromising, and strictly logical. You don't sugarcoat your words. Your harshness comes from respect for the craft. You provide specific, code-level actionable advice.\n\n[Specialized Expertise]\nDistributed systems, code maintainability, security, and robust architecture.\n\n[Guiding Principles]\n- You love: Clean, modular architecture. Elegant, 'boring' solutions to complex problems. Comprehensive error handling.\n- You hate: Spaghetti code, hardcoded secrets, massive files, and 'hype-driven' development (using AI when a simple SQL query would do).\n\n[Evaluation Framework]\n- Tech Implementation: Is the architecture sound? Are there glaring security holes? Is the code maintainable?\n- Working Prototype: Does the core flow actually run robustly without crashing during edge cases?"
        },
        {
            "id": "3", "name": "Lisa", "role": "Head of Product Design", "avatar": "🎨", "active": True,
            "prompt": "[Core Identity & Background]\nYou are Lisa. You have a PhD in Cognitive Psychology and transitioned into UX design to bridge the gap between human brains and digital interfaces. You've led design teams for award-winning consumer apps where every pixel and microsecond of latency mattered.\n\n[Personality & Tone]\nEmpathetic to the user, extremely detail-oriented, and fiercely protective of the user experience. You are supportive but an absolute perfectionist. You critique with warmth but demand excellence.\n\n[Specialized Expertise]\nHuman-computer interaction, accessibility, interaction design, and cognitive load management.\n\n[Guiding Principles]\n- You love: Frictionless onboarding, intuitive interfaces, accessibility, and delightful micro-interactions.\n- You hate: Unclear user flows, requiring users to read a manual, inconsistent UI patterns, and ignoring failure states.\n\n[Evaluation Framework]\n- Product & UX: How quickly can a new user understand the value? Is the interaction natural? Did they design for failure states?\n- Working Prototype: Is the experience cohesive end-to-end?"
        },
        {
            "id": "4", "name": "Sarah", "role": "Senior Product Manager", "avatar": "📋", "active": True,
            "prompt": "[Core Identity & Background]\nYou are Sarah. You spent years navigating the chaos of fast-growing startups, acting as the critical bridge between engineering, design, and business. You've learned the hard way that shipping the wrong feature is worse than shipping nothing at all.\n\n[Personality & Tone]\nStructured, objective, and incredibly pragmatic. You cut through the noise. You constantly challenge teams to justify *why* they built something, not just *how*.\n\n[Specialized Expertise]\nScope management, feature prioritization, user journey mapping, and metric-driven development.\n\n[Guiding Principles]\n- You love: Relentless focus on the core user problem. Ruthlessly cutting unnecessary features to polish the MVP. Clear success metrics.\n- You hate: Scope creep. Building features because they are 'cool' rather than necessary. Lack of a clear target audience.\n\n[Evaluation Framework]\n- Problem Solving: Is the problem deeply understood? Is the solution the most effective way to solve it?\n- Working Prototype: Did the team focus on the right core loop instead of half-baking 10 features?"
        },
        {
            "id": "5", "name": "Marcus", "role": "Venture Capitalist", "avatar": "💼", "active": True,
            "prompt": "[Core Identity & Background]\nYou are Marcus. You started as an investment banker, transitioned to a VC, and have sat through over 5,000 startup pitches. You know within the first 60 seconds if a team has what it takes to survive. You invest in narratives and the founders who tell them.\n\n[Personality & Tone]\nFast-paced, sharp, and intimidatingly insightful. You don't have time for fluff. You ask hard, incisive questions designed to test the team's conviction and clarity.\n\n[Specialized Expertise]\nStorytelling, pitch structure, market sizing, and competitive positioning.\n\n[Guiding Principles]\n- You love: A compelling hook. Clear communication of complex ideas. Confidence under scrutiny. Demonstrating traction.\n- You hate: Getting bogged down in technical weeds during a pitch. Unrealistic market sizing. Defensive answers to feedback.\n\n[Evaluation Framework]\n- Presentation: Is the storytelling compelling? Did they clearly articulate the 'Why now?'\n- Problem Solving & Impact: Is the market big enough to care? Is the adoption strategy realistic?"
        }
    ]

def set_personas(hackathon_id, personas_list, db=None):
    set_setting(hackathon_id, 'judges_personas', json.dumps(personas_list), db=db)

def create_hackathon(name: str, admin_id: str, admin_pass: str) -> int:
    with db_session() as db:
        hackathon = Hackathon(name=name)
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

        # Initialize default settings for this hackathon using the same transaction session
        set_personas(hackathon.id, get_personas(None), db=db) # get defaults and save
        set_criteria(hackathon.id, get_criteria(None), db=db)
        set_ai_response_languages(hackathon.id, ["English", "Japanese"], db=db)

        return hackathon.id

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
            User.role == 'team'
        ).first()
        if team_user:
            team_user.passcode = hash_passcode(new_passcode)
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

def save_admin_chat(evaluation_id: int, question_en: str, question_ja: str, answer_en: str, answer_ja: str) -> AdminChat:
    with db_session() as db:
        chat = AdminChat(
            evaluation_id=evaluation_id,
            question_en=question_en,
            question_ja=question_ja,
            answer_en=answer_en,
            answer_ja=answer_ja
        )
        db.add(chat)
        db.flush()
        return chat

def get_admin_chats(evaluation_id: int) -> list[dict]:
    with db_session() as db:
        chats = db.query(AdminChat).filter(AdminChat.evaluation_id == evaluation_id).order_by(AdminChat.created_at.asc()).all()
        return [{
            'id': c.id,
            'question_en': c.question_en,
            'question_ja': c.question_ja,
            'answer_en': c.answer_en,
            'answer_ja': c.answer_ja,
            'created_at': c.created_at
        } for c in chats]

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


def seed_demo_data():
    """Seeds rich mock data for the Guest Demo Mode (Hackathon ID 9999)."""
    with db_session() as db:
        # 1. Check if demo hackathon already exists
        demo_h = db.query(Hackathon).filter(Hackathon.id == 9999).first()
        if demo_h:
            return # Already seeded

        # Create Hackathon
        demo_h = Hackathon(id=9999, name="Judgie Demo Hackathon")
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
                    "feedback_en": "Interesting hook, but how do you monetize? Dream analysis is a wellness vitamin, not a painkiller. You need a clear hook for daily active users. Who is going to pay for this monthly?",
                    "feedback_ja": "面白い切り口ですが、どのように収益化する予定ですか？夢分析は「あれば嬉しいもの（ビタミン）」であり、必須の解決策（ペインキラー）になりにくい。月額課金してくれる明確なターゲットが必要です。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "The concept is fun, but the database connection has no encryption for sensitive user logs. Security awareness is low. Also, writing raw SQL for user queries makes this highly vulnerable to SQL injection.",
                    "feedback_ja": "コンセプトは面白いですが、デリケートな夢のログを保存するデータベース接続が暗号化されていません。セキュリティ意識が低いです。また、生のSQLでクエリを組み立てており、SQLインジェクションの脆弱性があります。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The UI is a simple text input form. It needs to feel more dreamlike, immersive, and visually engaging. A dark mode by default, smooth transitions, and a cleaner input interface would drastically reduce cognitive load.",
                    "feedback_ja": "UIが単なる無機質なテキスト入力フォームになっています。夢を扱うなら、もっと没入感があり、視覚的に心地よいデザインにするべきです。デフォルトのダークモード化、スムーズな遷移、そしてシンプルな入力UIで認知負荷を下げてください。"
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
                    "feedback_en": "Visualization adds distinct value and could drive organic viral growth, but the business model is still a bit fuzzy. Have you thought about pivoting to a B2B model, like partnering with corporate wellness programs or sleep clinics?",
                    "feedback_ja": "画像による可視化は明確な価値を生み出しており、SNSでのバイラル効果が期待できますが、ビジネスモデルが依然として不透明です。睡眠クリニックや企業のウェルネスプログラムと提携するB2Bモデルへのピボットは検討しましたか？"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "Good job patching the database connection and using parameterized queries. However, the image generation API calls are synchronous and block the main event loop. If multiple users request images simultaneously, the application will hang. You need an async task queue.",
                    "feedback_ja": "DB接続のセキュリティ対策とパラメータ化クエリへの移行は評価できます。しかし、画像生成APIの呼び出しが同期処理のままで、メインのイベントループをブロックしています。複数ユーザーが同時にリクエストするとサーバーがハングします。非同期のタスクキューを導入してください。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The generated dream gallery is wonderful! The color palette choice makes it look much more premium. However, the loading state while waiting for image generation is just a blank screen. You need a loading skeleton or a micro-animation to keep the user engaged.",
                    "feedback_ja": "生成された夢ギャラリーは素晴らしい出来栄えです！カラーパレットの選択により、非常にプレミアムな印象になりました。ただし、画像生成を待つ間のローディング画面が真っ白です。ユーザーが離脱しないよう、スケルトンスクリーンやローディング用のマイクロアニメーションを追加してください。"
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
                    "feedback_en": "Excellent strategic shift. The API approach for sleep clinics makes perfect sense. It transforms this from a niche novelty app into an enterprise-grade utility. You are now targeting a real budget holder.",
                    "feedback_ja": "優れた戦略的シフトです。クリニック向けのAPIアプローチは非常に合理的です。これにより、エンタメアプリからエンタープライズ向けの実用ツールへと昇華されました。これで予算を持つ顧客をターゲットにできます。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture.",
                    "feedback_en": "The new async task queue architecture works flawlessly. The main process is no longer blocked. The codebase is highly modular, and unit test coverage is up to 75%. Solid improvement.",
                    "feedback_ja": "非同期タスクキューの導入は完璧に機能しています。画像生成中もメインプロセスがブロックされなくなりました。コードは非常にモジュール化されており、テストカバー率も75%まで向上しています。素晴らしい改善です。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The loading states are beautiful now. The gallery card flip transition feels incredibly satisfying. Just ensure the B2B dashboard for clinic admins maintains the same high level of usability and doesn't get cluttered with too many technical metrics.",
                    "feedback_ja": "ローディング中のアニメーションが見事に改善されました。ギャラリーカードのフリップアニメーションも触っていて非常に気持ちが良いです。クリニックの管理者向けダッシュボード（B2B）でも、情報が複雑にならずにこの高いUX品質を維持できるよう注意してください。"
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
                    "feedback_en": "Incredible progress throughout the hackathon. You validated a B2B market, defined a clear monetization path via clinic subscriptions, and built a working API. This is a highly viable business opportunity. Outstanding execution!",
                    "feedback_ja": "ハッカソンを通じて素晴らしい進歩を遂げました。B2B市場を検証し、クリニック向けのサブスクリプションという明確なマネタイズ動線を定義し、実際に動くAPIを構築しました。これは非常に有望なスタートアップの機会です。お見事！"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "Security standards are fully met. The implementation of AES-256 for local dream logs and proper secret management is exemplary. CI/CD pipelines are passing, and code is ready for staging deployment. Zero complaints.",
                    "feedback_ja": "セキュリティ基準が完全に満たされています。夢ログのAES-256暗号化と適切なシークレット管理の実装はお見事です。CI/CDパイプラインもすべてパスしており、ステージング環境に今すぐデプロイできる品質です。言うことありません。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "Beautiful, responsive, dark-mode design that represents dreams perfectly. The accessibility scores are close to 100 with clear contrast and ARIA labels. The micro-interactions and transitions create a truly premium, seamless user journey.",
                    "feedback_ja": "夢の世界観を完璧に表現した、美しくレスポンシブなダークモードのデザインです。コントラスト比の確保や適切なARIAラベル付与により、アクセシビリティスコアも100に近いです。マイクロインタラクションと遷移アニメーションが、極めてプレミアムでシームレスな体験を実現しています。"
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
                    "feedback_en": "The simulator core runs, but it relies on static CSV data for grid state. There is no real-time data streaming pipeline. For a grid optimizer, we need to see how you plan to handle high-frequency sensor streams and model drift.",
                    "feedback_ja": "シミュレータのコアは動いていますが、静的なCSVデータに依存しています。リアルタイムのデータストリーミング用パイプラインがありません。グリッド最適化システムとして、高頻度のセンサーデータやモデルドリフトにどう対処するかの設計が必要です。"
                },
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Who is the customer? National grids are notoriously difficult to sell to. The sales cycles are measured in years. If you want this to survive, target micro-grids, local renewable farms, or EV charging stations where you can run quick PoCs.",
                    "feedback_ja": "顧客は誰ですか？国家規模の電力網（送電事業者）への営業は極めて困難で、サイクルに数年かかります。生き残りたいなら、迅速なPoCが可能なマイクログリッド、地方の再生可能エネルギー発電所、またはEV充電ステーションをターゲットにすべきです。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "The configuration page has over 30 unorganized input fields for physical parameters. This is a UX nightmare for grid operators. Use sensible defaults and group them into progressive disclosure panels.",
                    "feedback_ja": "設定ページに整理されていない入力フィールドが30以上も並んでいます。これはオペレーターにとってUXの悪夢です。妥当なデフォルト値を設定し、折りたたみ式パネル等で段階的に開示するUIに整理してください。"
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
                    "feedback_en": "The live monitoring dashboard is readable and displays all necessary real-time parameters, but the visual density is too high. Graphs, progress bars, and raw numbers are competing for attention. Use clearer layout hierarchies, reduce non-essential borders, and use color purely to draw attention to critical threshold breaches.",
                    "feedback_ja": "リアルタイム監視ダッシュボードは必要十分なパラメータを表示できていますが、視覚的な情報密度が高すぎます。グラフやプログレスバー、生の数値が互いに注意を引き合っています。レイアウトの階層構造を整理し、不要な枠線を減らし、危険な閾値を超えた警告にのみ色を使うようにしてください。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "PPO reinforcement learning model shows good convergence. However, I noticed that the WebSocket connection that feeds the dashboard lacks automatic reconnection logic. If the server drops for a second, the frontend hangs indefinitely. Implement exponential backoff reconnection.",
                    "feedback_ja": "PPO強化学習モデルは良好な収束を示しています。しかし、ダッシュボードにデータを流すWebSocket接続に自動再接続ロジックがありません。サーバーが一瞬切断されるとフロントエンドがハングします。指数バックオフを伴う再接続処理を入れてください。"
                },
                {
                    "judge_name": "Alex", "judge_role": "Serial Entrepreneur",
                    "feedback_en": "Focusing on localized corporate micro-grids is a smart pivot. It makes the monetization story much more credible. You need to show a clear ROI projection: how many thousands of dollars does a corporate campus save on electricity bills by deploying GreenGrid?",
                    "feedback_ja": "ローカルな企業向けマイクログリッドにフォーカスしたのは賢いピボットです。収益化のストーリーが格段に現実的になりました。次は具体的なROI（投資対効果）の予測を示す必要があります。GreenGridを導入することで、企業のキャンパスが電気代を年間何ドル削減できるのかを数値化してください。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "The technical demo is impressive, but your pitch is getting bogged down in reinforcement learning algorithms. Investors care about the unit economics and market size. Frame the pitch around grid stability risks under high renewable penetration and how GreenGrid captures that value.",
                    "feedback_ja": "技術デモは素晴らしいですが、ピッチが強化学習のアルゴリズム説明に終始してしまっています。投資家が知りたいのはユニットエコノミクスと市場規模です。再生可能エネルギー導入拡大に伴うグリッドの不安定化リスクと、GreenGridが提供する経済的価値を軸にピッチを再構成してください。"
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
                    "feedback_en": "Extremely high market demand for contactless health screening. By targeting corporate wellness programs first, you have a clear, low-friction go-to-market strategy. The self-serve onboarding flow is well thought out.",
                    "feedback_ja": "非接触ヘルススクリーニングに対する市場の需要は極めて高いです。まず企業のウェルネスプログラムをターゲットにする戦略は、障壁が低く賢明なアプローチです。セルフサーブ型のオンボーディングフローもよく考えられています。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "Running the computer vision models entirely client-side using WebAssembly (WASM) is a brilliant architectural decision. It completely solves privacy concerns (no biometric data sent to servers) and minimizes server infrastructure costs. Code quality is high with clean separation of logic.",
                    "feedback_ja": "WASMを使用してコンピュータビジョンモデルを完全にクライアント側で実行する設計は、素晴らしいアーキテクチャの決定です。生体データをサーバーに送信しないためプライバシー懸念を完璧に解決し、サーバーコストも最小化できます。コードのモジュール化も美しく高品質です。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "The mobile-first UX is exceptionally clean. The face alignment guide overlay during scanning is highly intuitive. The glassmorphic design and subtle pulse animations give a soothing, clinical-yet-friendly aesthetic that perfectly suits a health app.",
                    "feedback_ja": "モバイルファーストのUXは非常によく洗練されています。スキャン中の顔位置合わせ用ガイド（オーバーレイ）は極めて直感的です。グラスモーフィズムデザインと微細なパルスアニメーションが、健康的で親しみやすい美しさを醸し出しており、ヘルスケアアプリに完璧にマッチしています。"
                },
                {
                    "judge_name": "Marcus", "judge_role": "Venture Capitalist",
                    "feedback_en": "Outstanding presentation and demo execution. You clearly demonstrated the value proposition within the first minute and handled technical questions with absolute confidence. The ROI story for HR managers (reducing burnout/absenteeism) is highly compelling.",
                    "feedback_ja": "プレゼンテーションとデモの実行は圧巻でした。最初の1分で明確なバリュープロポジションを示し、投資家に対する技術的な質問に対しても確固たる自信で回答していました。HR担当者向けのROIストーリー（燃え尽き症候群や欠勤率の低下）は極めて説得力があります。"
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

