import pytest
import json
from core.db import create_hackathon, save_evaluation, Evaluation
from core.services.evaluation_service import (
    get_team_evaluations, submit_team_objection, sanitize_objection_response
)

def test_get_team_evaluations(db_session_fixture):
    # Set up test data
    hid = create_hackathon("Hack1", "admin1", "pass123")
    
    result_data = {
        "scores": {"Innovation": 4.0},
        "impact_score": 4.0,
        "three_line_summary_en": "summary",
        "three_line_summary_ja": "サマリー",
        "judges_feedback": []
    }
    save_evaluation(hid, "teamA", result_data, is_final=False)
    save_evaluation(hid, "teamA", result_data, is_final=True)
    save_evaluation(hid, "teamB", result_data, is_final=False) # Different team
    
    evals = get_team_evaluations("teamA")
    assert len(evals) == 2
    assert evals[0]["is_final"] is False
    assert evals[1]["is_final"] is True

def test_sanitize_objection_response():
    # 1. Normal case
    input_data = {
        "qa_summary_en": "Objection reviewed",
        "qa_summary_ja": "精査されました",
        "judges_responses": [
            {
                "judge_name": "Alex",
                "response_en": "Eng response",
                "response_ja": "日本語回答"
            }
        ]
    }
    res = sanitize_objection_response(input_data)
    assert res["qa_summary_en"] == "Objection reviewed"
    assert res["judges_responses"][0]["judge_name"] == "Alex"
    
    # 2. Missing values or incorrect formats
    bad_input = {
        "judges_responses": "invalid_type_not_list"
    }
    res_bad = sanitize_objection_response(bad_input)
    assert res_bad["qa_summary_en"] == "Objection evaluated by the expert panel." # Default value
    assert res_bad["judges_responses"] == []
    
    # 3. Non-dict input format
    res_none = sanitize_objection_response(None)
    assert res_none["qa_summary_en"] == "Objection evaluated by the expert panel."
    assert res_none["judges_responses"] == []
    
    # 4. Invalid types for specific items inside judges_responses list
    bad_responses = {
        "judges_responses": [
            "not_a_dict",
            {"judge_name": "David"} # Partial missing keys
        ]
    }
    res_mixed = sanitize_objection_response(bad_responses)
    assert len(res_mixed["judges_responses"]) == 1
    assert res_mixed["judges_responses"][0]["judge_name"] == "David"
    assert res_mixed["judges_responses"][0]["response_en"] == "No detailed response in English."

def test_submit_team_objection(mocker, db_session_fixture):
    hid = create_hackathon("Hack1", "admin1", "pass123")
    
    # Pre-save target evaluation records
    result_data = {
        "scores": {}, "impact_score": 3.0,
        "three_line_summary_en": "summary", "three_line_summary_ja": "サマリー",
        "judges_feedback": []
    }
    save_evaluation(hid, "teamA", result_data, is_final=False)
    eval_rec = db_session_fixture.query(Evaluation).filter(Evaluation.team_id == "teamA").first()
    eval_id = eval_rec.id
    
    # Mock object_to_judges API
    mock_llm_response = {
        "qa_summary_en": "Objection accepted",
        "qa_summary_ja": "受け入れられました",
        "judges_responses": [{"judge_name": "Lisa", "response_en": "I agree"}]
    }
    mocker.patch("core.services.evaluation_service.object_to_judges", return_value=mock_llm_response)
    
    # Execute
    res = submit_team_objection(
        hackathon_id=hid,
        eval_id=eval_id,
        prev_eval_json='{"scores": {}}',
        objection_text="Please reconsider"
    )
    
    assert res["qa_summary_en"] == "Objection accepted"
    assert res["user_objection"] == "Please reconsider"
    
    # Verify DB update
    db_session_fixture.expire_all()
    eval_rec_updated = db_session_fixture.query(Evaluation).filter(Evaluation.id == eval_id).first()
    assert eval_rec_updated.qa_json is not None
    qa_loaded = json.loads(eval_rec_updated.qa_json)
    assert qa_loaded["user_objection"] == "Please reconsider"
    assert qa_loaded["qa_summary_en"] == "Objection accepted"
