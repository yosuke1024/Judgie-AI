import json

from app.models.db import (
    AdminChat,
    Evaluation,
    TeamChat,
    User,
    change_my_passcode,
    create_session,
    delete_evaluation,
    delete_session,
    delete_team,
    get_admin_chats,
    get_ai_response_languages,
    get_consultation_count,
    get_criteria,
    get_max_consultations,
    get_personas,
    get_session,
    get_setting,
    get_team_profile,
    init_db,
    initialize_project_template,
    is_video_upload_enabled,
    save_admin_chat,
    save_evaluation,
    save_objection_qa,
    set_ai_response_languages,
    set_criteria,
    set_max_consultations,
    set_personas,
    set_setting,
    set_video_upload_enabled,
    update_admin_passcode,
    update_team_passcode,
    update_team_profile,
    verify_user,
)
from app.security import hash_passcode, verify_passcode


def test_init_db(db_session_fixture):
    # Test init_db. Ensure the superadmin user is created by default.
    init_db()
    superadmin = db_session_fixture.query(User).filter(User.role == "superadmin").first()
    assert superadmin is not None
    assert superadmin.team_id == "superadmin"


def test_verify_user(db_session_fixture):
    init_db()

    # 1. Superadmin authentication
    assert verify_user("superadmin", "superadmin123") == {"role": "superadmin", "email": None}
    assert verify_user("superadmin", "wrongpass") is None

    # 2. Team user authentication
    team_user = User(team_id="teamA", passcode=hash_passcode("teampass"), role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    assert verify_user("teamA", "teampass") == {"role": "team", "email": None}
    assert verify_user("teamA", "wrongpass") is None


def test_settings(db_session_fixture):
    set_setting("theme", "dark")
    assert get_setting("theme") == "dark"
    assert get_setting("nonexistent") is None


def test_criteria(db_session_fixture):
    # Save and retrieve evaluation criteria lists
    test_criteria_list = [{"name": "Coding", "weight": 50, "description": "Clean code"}]

    # Test default criteria fallback
    default_criteria = get_criteria()
    assert len(default_criteria) > 0
    assert default_criteria[0]["name"] == "Innovation & Creativity"

    set_criteria(test_criteria_list)
    criteria = get_criteria()
    assert len(criteria) == 1
    assert criteria[0]["name"] == "Coding"


def test_personas(db_session_fixture):
    # Retrieve and configure judge personas
    test_personas_list = [{"id": "1", "name": "Test Judge", "active": True, "prompt": "Evaluate code"}]

    # Test default fallback for personas
    default_personas = get_personas()
    assert len(default_personas) > 0
    assert default_personas[0]["name"] == "Alex"

    set_personas(test_personas_list)
    personas = get_personas()
    assert len(personas) == 1
    assert personas[0]["name"] == "Test Judge"


def test_evaluation_flow(db_session_fixture):
    init_db()

    result_data = {
        "scores": {"Innovation & Creativity": 4.5},
        "impact_score": 4.2,
        "three_line_summary_en": "Good product",
        "three_line_summary_ja": "良いプロダクト",
        "judges_feedback": [{"judge_name": "Alex", "feedback_en": "Great"}],
    }

    # Save evaluation
    save_evaluation("teamA", result_data, is_final=True, source_text="print('hello')", gemini_file_ids=["file1"])

    # Verify saved content
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "teamA").first()
    assert eval_rec is not None
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
    assert get_consultation_count("teamA") == 1
    assert get_consultation_count("teamB") == 0


def test_update_admin_passcode(db_session_fixture):
    # Seed admin user
    admin_user = User(team_id="admin1", passcode=hash_passcode("pass123"), role="admin")
    db_session_fixture.add(admin_user)
    db_session_fixture.commit()

    update_admin_passcode("newpass")
    assert verify_user("admin1", "newpass") is not None
    assert verify_user("admin1", "pass123") is None


def test_update_team_passcode(db_session_fixture):
    # Create a registered team user
    team_user = User(team_id="teamA", passcode=hash_passcode("teampass"), role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    # Verify that the update succeeds
    assert update_team_passcode("teamA", "newteampass") is True
    assert verify_user("teamA", "newteampass") is not None
    assert verify_user("teamA", "teampass") is None

    # Verify that the update fails for a non-existent team ID
    assert update_team_passcode("nonexistent", "somepass") is False


def test_change_my_passcode(db_session_fixture):
    init_db()
    admin_user = User(team_id="admin1", passcode=hash_passcode("pass123"), role="admin")
    db_session_fixture.add(admin_user)
    db_session_fixture.commit()

    # 1. Update admin passcode
    assert (
        change_my_passcode(team_id="admin1", current_passcode="pass123", new_passcode="changedpass")
        is True
    )
    assert verify_user("admin1", "changedpass") is not None

    # 2. Mismatched passcode error
    assert (
        change_my_passcode(team_id="admin1", current_passcode="wrong", new_passcode="another")
        is False
    )


def test_team_profile(db_session_fixture):
    # Set up team user
    team_user = User(team_id="teamA", passcode="teampass", role="team")
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    profile = get_team_profile("teamA")
    assert profile["product_name"] is None

    update_team_profile("teamA", "My Product", "Awesome Team", "We build cool stuff")

    profile_updated = get_team_profile("teamA")
    assert profile_updated["product_name"] == "My Product"
    assert profile_updated["team_name"] == "Awesome Team"
    assert profile_updated["one_liner"] == "We build cool stuff"

    # Non-existent team profile
    assert get_team_profile("nonexistent") == {"product_name": None, "team_name": None, "one_liner": None}


def test_session_management(db_session_fixture):
    # Create session
    sid = create_session("admin1", "admin")
    assert sid is not None

    # Retrieve session
    sdata = get_session(sid)
    assert sdata["team_id"] == "admin1"
    assert sdata["role"] == "admin"

    # Non-existent session
    assert get_session("nonexistent-sid") is None
    assert get_session("") is None

    # Delete session
    delete_session(sid)
    assert get_session(sid) is None


def test_admin_chat(db_session_fixture):
    # Save chat log
    save_admin_chat(123, "Q?", "質問?", "A!", "回答!")

    # Retrieve and verify
    chats = get_admin_chats(123)
    assert len(chats) == 1
    assert chats[0]["question_en"] == "Q?"
    assert chats[0]["question_ja"] == "質問?"
    assert chats[0]["answer_en"] == "A!"
    assert chats[0]["answer_ja"] == "回答!"


def test_ai_response_languages(db_session_fixture):
    # 1. Default languages when not set
    assert get_ai_response_languages() == ["English", "Japanese"]

    # 2. Set custom languages
    custom_langs = ["English", "Japanese", "Spanish", "French"]
    set_ai_response_languages(custom_langs)
    assert get_ai_response_languages() == custom_langs


def test_single_project_seeding(db_session_fixture, monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("DEFAULT_ADMIN_ID", "railway_admin")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSCODE", "railway_pass123")
    monkeypatch.setenv("DEFAULT_HACKATHON_NAME", "Railway Hackathon")

    # Run init_db
    init_db()

    # Verify default project and admin user are created
    assert get_setting("project_name") == "Railway Hackathon"

    admin_user = db_session_fixture.query(User).filter(User.team_id == "railway_admin").first()
    assert admin_user is not None
    assert admin_user.role == "admin"
    assert verify_passcode("railway_pass123", admin_user.passcode) is True


def test_initialize_project_template(db_session_fixture):
    # Initialize with hackathon template
    initialize_project_template("hackathon")

    assert get_setting("template_id") == "hackathon"
    assert get_setting("re_evaluation_context_mode") == "cumulative"
    assert get_setting("max_qa_turns") == "1"
    assert get_setting("max_consultations") == "3"

    # Check criteria and personas are initialized
    criteria = get_criteria()
    assert len(criteria) > 0
    assert criteria[0]["name"] == "Innovation & Creativity"

    personas = get_personas()
    assert len(personas) > 0
    assert personas[0]["name"] == "Alex"


def test_max_consultations(db_session_fixture):
    # Check default
    assert get_max_consultations() == 3

    # Set to custom value
    set_max_consultations(5)
    assert get_max_consultations() == 5

    # Set to unlimited
    set_max_consultations(-1)
    assert get_max_consultations() == -1


def test_video_upload_enabled(db_session_fixture):
    # Check default (should be True)
    assert is_video_upload_enabled() is True

    # Set to False
    set_video_upload_enabled(False)
    assert is_video_upload_enabled() is False

    # Set to True
    set_video_upload_enabled(True)
    assert is_video_upload_enabled() is True


def test_delete_team_cascades(db_session_fixture):
    init_db()

    # Create two team users
    team1 = User(team_id="team1", passcode="pass1", role="team")
    team2 = User(team_id="team2", passcode="pass2", role="team")
    db_session_fixture.add(team1)
    db_session_fixture.add(team2)
    db_session_fixture.commit()

    # Submission for team1
    from app.models.db import Submission

    sub1 = Submission(team_id="team1", files_json="[]")
    db_session_fixture.add(sub1)
    db_session_fixture.commit()

    # Evaluation for team1
    result_data = {
        "scores": {"Innovation & Creativity": 4.0},
        "impact_score": 4.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "概要",
        "judges_feedback": [],
    }
    save_evaluation("team1", result_data, is_final=True, source_text="code", gemini_file_ids=["fileA"])
    eval_rec = (
        db_session_fixture.query(Evaluation)
        .filter(Evaluation.team_id == "team1")
        .first()
    )
    assert eval_rec is not None
    eval_id = eval_rec.id

    # Chats for team1
    save_admin_chat(eval_id, "Q", "問", "A", "答")
    team_chat = TeamChat(evaluation_id=eval_id, sender="team", message_json="{}")
    db_session_fixture.add(team_chat)
    db_session_fixture.commit()

    # Session for team1
    create_session("team1", "team")

    # Verify everything exists before deletion
    assert db_session_fixture.query(User).filter(User.team_id == "team1").first() is not None
    assert db_session_fixture.query(User).filter(User.team_id == "team2").first() is not None
    assert (
        db_session_fixture.query(Submission)
        .filter(Submission.team_id == "team1")
        .first()
        is not None
    )
    assert (
        db_session_fixture.query(Evaluation)
        .filter(Evaluation.team_id == "team1")
        .first()
        is not None
    )
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval_id).first() is not None
    assert db_session_fixture.query(TeamChat).filter(TeamChat.evaluation_id == eval_id).first() is not None

    # Delete team1
    delete_team("team1")

    # Verify team1 data is gone
    db_session_fixture.expire_all()
    assert db_session_fixture.query(User).filter(User.team_id == "team1").first() is None
    assert (
        db_session_fixture.query(Submission)
        .filter(Submission.team_id == "team1")
        .first()
        is None
    )
    assert (
        db_session_fixture.query(Evaluation)
        .filter(Evaluation.team_id == "team1")
        .first()
        is None
    )
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval_id).first() is None
    assert db_session_fixture.query(TeamChat).filter(TeamChat.evaluation_id == eval_id).first() is None

    # Verify team2 is NOT deleted
    assert db_session_fixture.query(User).filter(User.team_id == "team2").first() is not None


def test_delete_evaluation_cascades(db_session_fixture):
    init_db()

    result_data = {
        "scores": {"Innovation & Creativity": 4.0},
        "impact_score": 4.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "概要",
        "judges_feedback": [],
    }

    # Save two evaluations
    save_evaluation("team1", result_data, is_final=False, source_text="code1", gemini_file_ids=[])
    save_evaluation("team1", result_data, is_final=True, source_text="code2", gemini_file_ids=[])

    evals = (
        db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "team1").all()
    )
    assert len(evals) == 2
    eval1_id = evals[0].id
    eval2_id = evals[1].id

    # Add chats to eval1
    save_admin_chat(eval1_id, "Q", "問", "A", "答")
    team_chat = TeamChat(evaluation_id=eval1_id, sender="team", message_json="{}")
    db_session_fixture.add(team_chat)
    db_session_fixture.commit()

    # Verify eval1 and chats exist
    assert db_session_fixture.query(Evaluation).filter(Evaluation.id == eval1_id).first() is not None
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval1_id).first() is not None
    assert db_session_fixture.query(TeamChat).filter(TeamChat.evaluation_id == eval1_id).first() is not None

    # Delete eval1
    delete_evaluation(eval1_id)

    # Verify eval1 and its chats are gone
    db_session_fixture.expire_all()
    assert db_session_fixture.query(Evaluation).filter(Evaluation.id == eval1_id).first() is None
    assert db_session_fixture.query(AdminChat).filter(AdminChat.evaluation_id == eval1_id).first() is None
    assert db_session_fixture.query(TeamChat).filter(TeamChat.evaluation_id == eval1_id).first() is None

    # Verify eval2 is still present
    assert db_session_fixture.query(Evaluation).filter(Evaluation.id == eval2_id).first() is not None


def test_update_user_active(db_session_fixture):
    from app.models.db import update_user_active
    init_db()

    # Register a team
    team_user = User(
        team_id="active_team",
        passcode=hash_passcode("teampass"),
        role="team",
    )
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    # Initial state should be active (default True)
    assert team_user.is_active is True

    # Disable team
    success = update_user_active("active_team", False)
    assert success is True
    db_session_fixture.expire_all()

    user_in_db = db_session_fixture.query(User).filter(User.team_id == "active_team").first()
    assert user_in_db.is_active is False

    # Enable team again
    success = update_user_active("active_team", True)
    assert success is True
    db_session_fixture.expire_all()
    user_in_db = db_session_fixture.query(User).filter(User.team_id == "active_team").first()
    assert user_in_db.is_active is True


def test_verify_user_inactive(db_session_fixture):
    from app.models.db import update_user_active, verify_user
    init_db()

    team_user = User(
        team_id="verify_team",
        passcode=hash_passcode("teampass"),
        role="team",
    )
    db_session_fixture.add(team_user)
    db_session_fixture.commit()

    # Should succeed when active
    verified = verify_user("verify_team", "teampass")
    assert verified is not None
    assert verified["role"] == "team"

    # Disable team
    update_user_active("verify_team", False)

    # Should fail when inactive
    verified_inactive = verify_user("verify_team", "teampass")
    assert verified_inactive is None
