from app.models.db import Evaluation, save_evaluation
from app.services.evaluation_service import get_team_evaluations, sanitize_objection_response, submit_team_objection


def test_get_team_evaluations(db_session_fixture):
    # Set up test data
    result_data = {
        "scores": {"Innovation": 4.0},
        "impact_score": 4.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "サマリー",
        "judges_feedback": [],
    }
    save_evaluation("teamA", result_data, is_final=False)
    save_evaluation("teamA", result_data, is_final=True)
    save_evaluation("teamB", result_data, is_final=False)  # Different team

    evals = get_team_evaluations("teamA")
    assert len(evals) == 2
    assert evals[0]["is_final"] is False
    assert evals[1]["is_final"] is True


def test_sanitize_objection_response():
    # 1. Normal case
    input_data = {
        "qa_summary_en": "Objection reviewed",
        "qa_summary_ja": "精査されました",
        "judges_responses": [{"judge_name": "Alex", "response_en": "Eng response", "response_ja": "日本語回答"}],
    }
    res = sanitize_objection_response(input_data)
    assert res["qa_summary_en"] == "Objection reviewed"
    assert res["judges_responses"][0]["judge_name"] == "Alex"

    # 2. Missing values or incorrect formats
    bad_input = {"judges_responses": "invalid_type_not_list"}
    res_bad = sanitize_objection_response(bad_input)
    assert res_bad["qa_summary_en"] == "Objection evaluated by the expert panel."  # Default value
    assert res_bad["judges_responses"] == []

    # 3. Non-dict input format
    res_none = sanitize_objection_response(None)
    assert res_none["qa_summary_en"] == "Objection evaluated by the expert panel."
    assert res_none["judges_responses"] == []

    # 4. Invalid types for specific items inside judges_responses list
    bad_responses = {
        "judges_responses": [
            "not_a_dict",
            {"judge_name": "David"},  # Partial missing keys
        ]
    }
    res_mixed = sanitize_objection_response(bad_responses)
    assert len(res_mixed["judges_responses"]) == 1
    assert res_mixed["judges_responses"][0]["judge_name"] == "David"
    assert res_mixed["judges_responses"][0]["response_en"] == "No detailed response in English."


def test_sanitize_objection_response_multilingual(db_session_fixture):
    # Set up multilingual AI response settings
    from app.models.db import set_ai_response_languages

    set_ai_response_languages(["English", "Japanese", "Korean"])

    input_data = {
        "qa_summary_english": "English summary",
        "qa_summary_japanese": "日本語の要約",
        "qa_summary_korean": "한국어 요약",
        "judges_responses": [
            {
                "judge_name": "Marcus",
                "response_english": "Marcus response in English",
                "response_japanese": "Marcus response in Japanese",
                "response_korean": "Marcus response in Korean",
            }
        ],
    }

    res = sanitize_objection_response(input_data)

    # Check that the dynamic keys are correctly sanitized and preserved
    assert res["qa_summary_english"] == "English summary"
    assert res["qa_summary_japanese"] == "日本語の要約"
    assert res["qa_summary_korean"] == "한국어 요약"

    # Check fallback/legacy keys are also set
    assert res["qa_summary_en"] == "Objection evaluated by the expert panel."
    assert res["qa_summary_ja"] == "審査員パネルによって異議が精査されました。"

    # Check judges responses dynamic and static keys
    judges = res["judges_responses"]
    assert len(judges) == 1
    assert judges[0]["judge_name"] == "Marcus"
    assert judges[0]["response_english"] == "Marcus response in English"
    assert judges[0]["response_japanese"] == "Marcus response in Japanese"
    assert judges[0]["response_korean"] == "Marcus response in Korean"

    # Fallback response values
    assert judges[0]["response_en"] == "No detailed response in English."
    assert judges[0]["response_ja"] == "日本語の回答がありません。"


def test_submit_team_objection(mocker, db_session_fixture):
    # Pre-save target evaluation records
    result_data = {
        "scores": {},
        "impact_score": 3.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "サマリー",
        "judges_feedback": [],
    }
    save_evaluation("teamA", result_data, is_final=False)
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "teamA").first()
    eval_id = eval_rec.id

    # Mock object_to_judges API
    mock_llm_response = {
        "qa_summary_en": "Objection accepted",
        "qa_summary_ja": "受け入れられました",
        "judges_responses": [{"judge_name": "Lisa", "response_en": "I agree"}],
    }
    mocker.patch("app.services.evaluation_service.object_to_judges", return_value=mock_llm_response)

    # Execute
    res = submit_team_objection(eval_id=eval_id, prev_eval_json='{"scores": {}}', objection_text="Please reconsider")

    assert res["qa_summary_en"] == "Objection accepted"

    # Verify DB update in TeamChat table
    db_session_fixture.expire_all()
    from app.services.evaluation_service import get_team_chats

    chats = get_team_chats(eval_id)
    assert len(chats) == 2

    assert chats[0]["sender"] == "team"
    assert chats[0]["message_json"]["user_objection"] == "Please reconsider"

    assert chats[1]["sender"] == "judges"
    assert chats[1]["message_json"]["qa_summary_en"] == "Objection accepted"


def test_minimize_evaluation_context():
    from app.services.evaluation_service import minimize_evaluation_context

    raw_json = """{
        "judges_feedback": [
            {
                "judge_name": "Marcus",
                "judge_role": "Technical Architect",
                "judge_persona": "Marcus cares about tech stack...",
                "judge_scores": [{"criteria_name": "Tech", "score": 4.5}],
                "judge_emoji": "💻",
                "feedback_en": "Good tech selection",
                "feedback_ja": "良い技術選定"
            }
        ],
        "summary_ja": "プロダクトサマリー日本語",
        "summary_en": "Product summary English"
    }"""

    minimized = minimize_evaluation_context(raw_json)

    assert "judges_feedback" in minimized
    assert len(minimized["judges_feedback"]) == 1

    j = minimized["judges_feedback"][0]
    assert j["judge_name"] == "Marcus"
    assert j["judge_scores"] == [{"criteria_name": "Tech", "score": 4.5}]
    assert j["feedback_en"] == "Good tech selection"
    assert j["feedback_ja"] == "良い技術選定"

    # Check that metadata fields are omitted
    assert "judge_role" not in j
    assert "judge_persona" not in j
    assert "judge_emoji" not in j

    # Check summaries are preserved
    assert minimized["summary_ja"] == "プロダクトサマリー日本語"
    assert minimized["summary_en"] == "Product summary English"


def test_submit_team_objection_error_does_not_consume_turn(mocker, db_session_fixture):
    # Pre-save target evaluation records
    result_data = {
        "scores": {},
        "impact_score": 3.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "サマリー",
        "judges_feedback": [],
    }
    save_evaluation("teamB", result_data, is_final=False)
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "teamB").first()
    eval_id = eval_rec.id

    # Mock object_to_judges API to raise an exception
    mocker.patch(
        "app.services.evaluation_service.object_to_judges",
        side_effect=Exception("API connection failed (503 Unavailable)"),
    )

    # Execute and assert Exception is raised
    import pytest
    with pytest.raises(Exception, match="API connection failed"):
        submit_team_objection(eval_id=eval_id, prev_eval_json='{"scores": {}}', objection_text="Please reconsider")

    # Verify DB update in TeamChat table: no messages should be saved
    db_session_fixture.expire_all()
    from app.services.evaluation_service import get_team_chats

    chats = get_team_chats(eval_id)
    assert len(chats) == 0
