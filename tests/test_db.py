import json

from core.db import (
    AdminChat,
    Evaluation,
    Hackathon,
    Session,
    Setting,
    User,
    change_my_passcode,
    create_hackathon,
    create_session,
    delete_hackathon,
    delete_session,
    get_admin_chats,
    get_ai_response_languages,
    get_consultation_count,
    get_criteria,
    get_personas,
    get_session,
    get_setting,
    get_team_profile,
    init_db,
    save_admin_chat,
    save_evaluation,
    save_objection_qa,
    set_ai_response_languages,
    set_criteria,
    set_personas,
    set_setting,
    update_admin_passcode,
    update_team_passcode,
    update_team_profile,
    verify_user,
)
from core.security import hash_passcode, verify_passcode


def test_init_db(db_session_fixture):
    # Test init_db. Ensure the superadmin user is created.
    init_db()
    superadmin = db_session_fixture.query(User).filter(User.role == 'superadmin').first()
    assert superadmin is not None
    assert superadmin.team_id == 'superadmin'

def test_verify_user(db_session_fixture):
    init_db()

    # Create a hackathon and set up users
    hid = create_hackathon("Hack1", "admin1", "pass123")

    # 1. Superadmin authentication
    assert verify_user("superadmin", "superadmin123") == {'role': 'superadmin', 'hackathon_id': None}
    assert verify_user("superadmin", "wrongpass") is None

    # 2. Tenant admin authentication
    assert verify_user("admin1", "pass123", hackathon_id=hid) == {'role': 'admin', 'hackathon_id': hid}
    assert verify_user("admin1", "wrongpass", hackathon_id=hid) is None
    assert verify_user("admin1", "pass123") is None

    # 3. Non-existent user
    assert verify_user("nonexistent", "pass", hackathon_id=hid) is None

def test_settings(db_session_fixture):
    # Retrieve and save setting variables
    set_setting(1, "theme", "dark")
    assert get_setting(1, "theme") == "dark"
    assert get_setting(2, "theme") is None
    assert get_setting(None, "theme") is None

    # Safeguard when passing None
    set_setting(None, "theme", "dark")

def test_criteria(db_session_fixture):
    # Save and retrieve evaluation criteria lists
    test_criteria_list = [{"name": "Coding", "weight": 50, "description": "Clean code"}]

    # Test default criteria fallback (when None is passed)
    default_criteria = get_criteria(999)
    assert len(default_criteria) > 0
    assert default_criteria[0]["name"] == "Innovation & Creativity"

    set_criteria(1, test_criteria_list)
    criteria = get_criteria(1)
    assert len(criteria) == 1
    assert criteria[0]["name"] == "Coding"

def test_personas(db_session_fixture):
    # Retrieve and configure judge personas
    test_personas_list = [{"id": "1", "name": "Test Judge", "active": True, "prompt": "Evaluate code"}]

    # Test default fallback for personas
    default_personas = get_personas(999)
    assert len(default_personas) > 0
    assert default_personas[0]["name"] == "Alex"

    set_personas(1, test_personas_list)
    personas = get_personas(1)
    assert len(personas) == 1
    assert personas[0]["name"] == "Test Judge"

def test_evaluation_flow(db_session_fixture):
    # Save evaluations and objection Q&A
    hid = create_hackathon("Hack1", "admin1", "pass123", template_id="hackathon")

    result_data = {
        "scores": {"Innovation & Creativity": 4.5},
        "impact_score": 4.2,
        "three_line_summary_en": "Good product",
        "three_line_summary_ja": "良いプロダクト",
        "judges_feedback": [{"judge_name": "Alex", "feedback_en": "Great"}]
    }

    # Save evaluation
    save_evaluation(hid, "teamA", result_data, is_final=True, source_text="print('hello')", gemini_file_ids=["file1"])

    # Verify saved content
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "teamA").first()
    assert eval_rec is not None
    assert eval_rec.hackathon_id == hid
    assert eval_rec.impact_score == 4.2
    assert eval_rec.is_final is True
    assert eval_rec.source_text == "print('hello')"
    assert "file1" in eval_rec.gemini_file_ids

    eval_id = eval_rec.id

    # Save user objection QA
    qa_data = {"user_objection": "But it is good", "answer": "OK"}
    save_objection_qa(eval_id, qa_data)

    # Re-retrieve from DB and assert
    db_session_fixture.expire_all()
    eval_rec_updated = db_session_fixture.query(Evaluation).filter(Evaluation.id == eval_id).first()
    assert eval_rec_updated.qa_json is not None
    qa_json_loaded = json.loads(eval_rec_updated.qa_json)
    assert qa_json_loaded["user_objection"] == "But it is good"

    # Check consultation counts
    assert get_consultation_count(hid, "teamA") == 1
    assert get_consultation_count(hid, "teamB") == 0

def test_update_admin_passcode(db_session_fixture):
    hid = create_hackathon("Hack1", "admin1", "pass123")
    update_admin_passcode(hid, "newpass")
    assert verify_user("admin1", "newpass", hackathon_id=hid) is not None
    assert verify_user("admin1", "pass123", hackathon_id=hid) is None

def test_update_team_passcode(db_session_fixture):
    hid = create_hackathon("Hack1", "admin1", "pass123")

    # Create a registered team user
    team_user = User(hackathon_id=hid, team_id="teamA", passcode=hash_passcode("teampass"), role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    # Verify that the update succeeds with the correct team ID and hackathon ID
    assert update_team_passcode(hid, "teamA", "newteampass") is True
    assert verify_user("teamA", "newteampass", hackathon_id=hid) is not None
    assert verify_user("teamA", "teampass", hackathon_id=hid) is None

    # Verify that the update fails for a non-existent team ID
    assert update_team_passcode(hid, "nonexistent", "somepass") is False

    # Verify that the update is not applied if a different hackathon ID is specified
    assert update_team_passcode(999, "teamA", "anotherpass") is False

def test_change_my_passcode(db_session_fixture):
    init_db()
    hid = create_hackathon("Hack1", "admin1", "pass123")

    # 1. Update admin passcode
    assert change_my_passcode(hackathon_id=hid, team_id="admin1", current_passcode="pass123", new_passcode="changedpass") is True
    assert verify_user("admin1", "changedpass", hackathon_id=hid) is not None

    # 2. Mismatched passcode error
    assert change_my_passcode(hackathon_id=hid, team_id="admin1", current_passcode="wrong", new_passcode="another") is False

    # 3. Test compatibility fallback signature (using 3 arguments instead of 4)
    # change_my_passcode(team_id, current_passcode, new_passcode)
    assert change_my_passcode("admin1", "changedpass", "compatpass") is True

    db_session_fixture.expire_all()
    user = db_session_fixture.query(User).filter(User.team_id == "admin1").first()
    assert verify_passcode("compatpass", user.passcode) is True

def test_team_profile(db_session_fixture):
    # Create and update team profiles
    hid = create_hackathon("Hack1", "admin1", "pass123")

    # Set up team user
    team_user = User(hackathon_id=hid, team_id="teamA", passcode="teampass", role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    profile = get_team_profile(hid, "teamA")
    assert profile["product_name"] is None

    update_team_profile(hid, "teamA", "My Product", "Awesome Team", "We build cool stuff")

    profile_updated = get_team_profile(hid, "teamA")
    assert profile_updated["product_name"] == "My Product"
    assert profile_updated["team_name"] == "Awesome Team"
    assert profile_updated["one_liner"] == "We build cool stuff"

    # Non-existent team profile
    assert get_team_profile(hid, "nonexistent") == {'product_name': None, 'team_name': None, 'one_liner': None}

def test_session_management(db_session_fixture):
    hid = create_hackathon("Hack1", "admin1", "pass123")

    # Create session
    sid = create_session("admin1", "admin", hid)
    assert sid is not None

    # Retrieve session
    sdata = get_session(sid)
    assert sdata["team_id"] == "admin1"
    assert sdata["role"] == "admin"
    assert sdata["hackathon_id"] == hid

    # Non-existent session
    assert get_session("nonexistent-sid") is None
    assert get_session("") is None

    # Delete session
    delete_session(sid)
    assert get_session(sid) is None

    # Safeguards for None or empty strings
    delete_session(None)
    delete_session("")

def test_admin_chat(db_session_fixture):
    # 1. Save chat log in legacy format (qa_json=None)
    save_admin_chat(123, "Q?", "質問?", "A!", "回答!")

    # Retrieve and verify legacy compatibility fallback in qa_json
    chats = get_admin_chats(123)
    assert len(chats) == 1
    assert chats[0]["question_en"] == "Q?"
    assert chats[0]["question_ja"] == "質問?"
    assert chats[0]["answer_en"] == "A!"
    assert chats[0]["answer_ja"] == "回答!"
    assert chats[0]["qa_json"]["question_english"] == "Q?"
    assert chats[0]["qa_json"]["question_japanese"] == "質問?"
    assert chats[0]["qa_json"]["answer_english"] == "A!"
    assert chats[0]["qa_json"]["answer_japanese"] == "回答!"

    # 2. Save with multi-language qa_json dictionary
    mock_qa = {
        "question_english": "What logic?",
        "answer_english": "Some logic",
        "question_spanish": "Que logica?",
        "answer_spanish": "Alguna logica"
    }
    save_admin_chat(123, "What logic?", "どんなロジック？", "Some logic", "いくつかのロジック", qa_json=mock_qa)

    chats_all = get_admin_chats(123)
    assert len(chats_all) == 2
    assert chats_all[1]["qa_json"]["question_spanish"] == "Que logica?"
    assert chats_all[1]["qa_json"]["answer_spanish"] == "Alguna logica"

    assert len(get_admin_chats(999)) == 0

def test_delete_hackathon(db_session_fixture):
    init_db()

    # 1. Create a tenant (Hackathon)
    hid = create_hackathon("HackToDelete", "del_admin", "pass123", template_id="hackathon")

    # 2. Create related dummy data
    # Team user
    team_user = User(hackathon_id=hid, team_id="teamDel", passcode="teampass", role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    # Submission
    from core.db import Submission
    submission = Submission(hackathon_id=hid, team_id="teamDel", files_json="[]")
    db_session_fixture.add(submission)
    db_session_fixture.commit()

    # Evaluation data
    result_data = {
        "scores": {"Innovation & Creativity": 4.0},
        "impact_score": 4.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "概要",
        "judges_feedback": []
    }
    save_evaluation(hid, "teamDel", result_data, is_final=True, source_text="code", gemini_file_ids=["fileX"])
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.hackathon_id == hid).first()
    assert eval_rec is not None
    eval_id = eval_rec.id

    # Chat history
    save_admin_chat(eval_id, "Q", "問", "A", "答")

    # Session
    create_session("teamDel", "team", hid)

    # Verify each data exists
    assert db_session_fixture.query(Hackathon).filter(Hackathon.id == hid).first() is not None
    assert db_session_fixture.query(User).filter(User.hackathon_id == hid).count() == 2 # admin + team
    assert db_session_fixture.query(Setting).filter(Setting.hackathon_id == hid).count() > 0
    assert db_session_fixture.query(Submission).filter(Submission.hackathon_id == hid).first() is not None
    assert db_session_fixture.query(Evaluation).filter(Evaluation.hackathon_id == hid).first() is not None
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval_id).first() is not None
    assert db_session_fixture.query(Session).filter(Session.hackathon_id == hid).first() is not None

    # 3. Delete the tenant
    delete_hackathon(hid)

    # 4. Verify that all associated data has been deleted
    db_session_fixture.expire_all()
    assert db_session_fixture.query(Hackathon).filter(Hackathon.id == hid).first() is None
    assert db_session_fixture.query(User).filter(User.hackathon_id == hid).count() == 0
    assert db_session_fixture.query(Setting).filter(Setting.hackathon_id == hid).count() == 0
    assert db_session_fixture.query(Submission).filter(Submission.hackathon_id == hid).first() is None
    assert db_session_fixture.query(Evaluation).filter(Evaluation.hackathon_id == hid).first() is None
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval_id).first() is None
    assert db_session_fixture.query(Session).filter(Session.hackathon_id == hid).first() is None

def test_ai_response_languages(db_session_fixture):
    # Test setting and getting languages
    hid = create_hackathon("Hack1", "admin1", "pass123", template_id="hackathon")

    # 1. Default languages when not set
    assert get_ai_response_languages(hid) == ["English", "Japanese"]

    # 2. Set custom languages
    custom_langs = ["English", "Japanese", "Spanish", "French"]
    set_ai_response_languages(hid, custom_langs)
    assert get_ai_response_languages(hid) == custom_langs

    # 3. Key normalization test
    from core.db import normalize_lang_to_key
    assert normalize_lang_to_key("English") == "english"
    assert normalize_lang_to_key("日本語") == "日本語"
    assert normalize_lang_to_key("Spanish") == "spanish"
    assert normalize_lang_to_key("French") == "french"
    assert normalize_lang_to_key("Korean") == "korean"


def test_seed_demo_data(db_session_fixture):
    from core.db import seed_demo_data
    seed_demo_data()

    # Verify hackathon
    demo_h = db_session_fixture.query(Hackathon).filter(Hackathon.id == 9999).first()
    assert demo_h is not None
    assert demo_h.name == "Judgie Demo Hackathon"

    # Verify users
    admin_u = db_session_fixture.query(User).filter(User.hackathon_id == 9999, User.team_id == "demo_admin").first()
    assert admin_u is not None
    assert admin_u.role == "admin"

    team_u = db_session_fixture.query(User).filter(User.hackathon_id == 9999, User.team_id == "demo_team").first()
    assert team_u is not None
    assert team_u.role == "team"
    assert team_u.team_name == "PixelCraft Labs"

    # Verify evaluations
    evals = db_session_fixture.query(Evaluation).filter(Evaluation.hackathon_id == 9999).all()
    assert len(evals) == 7  # 4 for demo_team, 2 for demo_team2, 1 for demo_team3


def test_single_tenant_mode(db_session_fixture, monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("DEFAULT_ADMIN_ID", "railway_admin")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSCODE", "railway_pass123")
    monkeypatch.setenv("DEFAULT_HACKATHON_NAME", "Railway Hackathon")

    # Re-run init_db in single-tenant mode
    init_db()

    # 1. Verify SuperAdmin is NOT created
    superadmin = db_session_fixture.query(User).filter(User.role == 'superadmin').first()
    assert superadmin is None

    # 2. Verify default hackathon and admin user are created
    hackathon = db_session_fixture.query(Hackathon).filter(Hackathon.id == 1).first()
    assert hackathon is not None
    assert hackathon.name == "Railway Hackathon"

    admin_user = db_session_fixture.query(User).filter(User.hackathon_id == 1, User.team_id == "railway_admin").first()
    assert admin_user is not None
    assert admin_user.role == "admin"
    assert verify_passcode("railway_pass123", admin_user.passcode) is True

    # 3. Verify SuperAdmin login is blocked in verify_user
    assert verify_user("superadmin", "superadmin123") is None

    # 4. Verify admin login succeeds
    assert verify_user("railway_admin", "railway_pass123", hackathon_id=1) == {'role': 'admin', 'hackathon_id': 1}


def test_initialize_hackathon_template(db_session_fixture):
    # Create hackathon without a template
    hid = create_hackathon("HackEmpty", "empty_admin", "pass123", template_id=None)

    db_session_fixture.expire_all()
    hackathon = db_session_fixture.query(Hackathon).filter(Hackathon.id == hid).first()
    assert hackathon.template_id is None

    # Initialize with startup_pitch template
    from core.db import initialize_hackathon_template
    initialize_hackathon_template(hid, "startup_pitch")

    db_session_fixture.expire_all()
    hackathon_updated = db_session_fixture.query(Hackathon).filter(Hackathon.id == hid).first()
    assert hackathon_updated.template_id == "startup_pitch"
    assert hackathon_updated.re_evaluation_context_mode == "independent"
    assert hackathon_updated.max_qa_turns == 3

    # Check criteria and personas are initialized
    criteria = get_criteria(hid)
    assert len(criteria) > 0
    assert criteria[0]["name"] == "Market Opportunity"

    personas = get_personas(hid)
    assert len(personas) > 0
    assert personas[0]["name"] == "Marcus"
