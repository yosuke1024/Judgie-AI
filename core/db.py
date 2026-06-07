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
                    "feedback_en": "Interesting hook, but how do you monetize? Dream analysis is a vitamin, not a painkiller.",
                    "feedback_ja": "面白い切り口ですが、どのように収益化する予定ですか？夢分析は「あれば嬉しいもの」であり、必須な解決策になりにくい。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "The concept is fun, but the database connection has no encryption for sensitive user logs. Security awareness is low.",
                    "feedback_ja": "コンセプトは楽しいですが、機密性の高いユーザーログに対するデータベースの暗号化が施されていません。セキュリティ意識が低いです。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The UI is a simple text input form. It needs to feel more dreamlike, immersive, and visually engaging.",
                    "feedback_ja": "UIが単純なテキスト入力フォームです。もっと夢のようで、没入感があり、視覚的に惹きつけられるデザインにする必要があります。"
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
                    "feedback_en": "Visualization adds distinct value, but the business model is still a bit fuzzy. The market feels small.",
                    "feedback_ja": "ビジュアル化は明確な価値を加えますが、ビジネスモデルが依然として不透明です。市場が少し小さく感じられます。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture and security.",
                    "feedback_en": "Good job patching the db connection. However, the image generation API calls are synchronous and block the main event loop.",
                    "feedback_ja": "DB接続のパッチ適用は評価できます。しかし、画像生成API呼び出しが同期処理のため、メインのイベントループをブロックしています。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "judge_persona": "Cares about user flow and delight.",
                    "feedback_en": "The generated gallery is wonderful! The color palette choice makes it look much more premium.",
                    "feedback_ja": "生成されたギャラリーは素晴らしいです！カラーパレットの選択により、非常にプレミアムな印象になりました。"
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
                    "feedback_en": "Excellent strategic shift. The API approach for clinics makes sense.",
                    "feedback_ja": "優れた戦略的シフトです。クリニック向けのAPIアプローチは非常に合理的です。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "judge_persona": "Cares about architecture.",
                    "feedback_en": "Async architecture works flawlessly. Very clean codebase now.",
                    "feedback_ja": "非同期アーキテクチャが完璧に動作しています。非常にクリーンなコードベースになりました。"
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
                    "feedback_en": "Incredible progress throughout the hackathon. This is a viable business opportunity.",
                    "feedback_ja": "ハッカソンを通じて素晴らしい進歩を遂げました。これは実現可能なビジネスチャンスです。"
                },
                {
                    "judge_name": "David", "judge_role": "Principal Software Engineer",
                    "feedback_en": "Security standards are met. Zero complaints on the repository hygiene.",
                    "feedback_ja": "セキュリティ基準が満たされています。リポジトリの衛生面において不満は一切ありません。"
                },
                {
                    "judge_name": "Lisa", "judge_role": "Head of Product Design",
                    "feedback_en": "Beautiful, responsive, dark-mode design that represents dreams perfectly.",
                    "feedback_ja": "夢の世界を完璧に表現した、美しくレスポンシブなダークモードのデザインです。"
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
                    "feedback_en": "Basic simulation works, but there is no integration pathway.",
                    "feedback_ja": "基本的なシミュレーションは動きますが、実際の統合パスが示されていません。"
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
                    "feedback_en": "Dashboard is readable, but visual density is too high.",
                    "feedback_ja": "ダッシュボードは見やすいですが、情報の密度が高すぎます。"
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
                    "feedback_en": "Extremely high market demand and very clear UX flow.",
                    "feedback_ja": "市場の需要が極めて高く、UXフローも非常に明快です。"
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

