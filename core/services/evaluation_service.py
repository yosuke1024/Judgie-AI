import json
from core.db import db_session, Evaluation, save_objection_qa
from core.gemini import object_to_judges

def get_team_evaluations(team_id: str) -> list[dict]:
    """
    Safely retrieves and formats all evaluations for the specified team.
    """
    with db_session() as db:
        evaluations = db.query(Evaluation).filter(Evaluation.team_id == team_id).order_by(Evaluation.id.asc()).all()
        eval_rows = []
        for e in evaluations:
            eval_rows.append({
                'id': e.id,
                'team_id': e.team_id,
                'scores_json': e.scores_json,
                'impact_score': e.impact_score,
                'strengths_risks_json': e.strengths_risks_json,
                'qa_json': e.qa_json,
                'is_final': e.is_final,
                'source_text': e.source_text,
                'gemini_file_ids': e.gemini_file_ids,
                'evaluated_at': e.evaluated_at
            })
        return eval_rows

def submit_team_objection(hackathon_id: int, eval_id: int, prev_eval_json: str, objection_text: str) -> dict:
    """
    Executes a one-shot AI debate in response to the team's objection and updates the DB.
    Includes robust schema verification for LLM responses.
    """
    qa_result = object_to_judges(hackathon_id, "", None, prev_eval_json, objection_text)
    
    # Defensive programming: sanitize Gemini responses
    qa_result = sanitize_objection_response(qa_result)
    
    # Cache user objection text in the database object
    qa_result['user_objection'] = objection_text
    
    save_objection_qa(eval_id, qa_result)
    return qa_result

def sanitize_objection_response(data: dict) -> dict:
    """
    Sanitizes LLM panel objection debate responses.
    """
    if not isinstance(data, dict):
        data = {}
        
    sanitized = {
        "qa_summary_en": data.get("qa_summary_en", "Objection evaluated by the expert panel."),
        "qa_summary_ja": data.get("qa_summary_ja", "審査員パネルによって異議が精査されました。"),
        "judges_responses": data.get("judges_responses", [])
    }
    
    if not isinstance(sanitized["judges_responses"], list):
        sanitized["judges_responses"] = []
        
    normalized_responses = []
    for r in sanitized["judges_responses"]:
        if not isinstance(r, dict):
            continue
        normalized_r = {
            "judge_name": r.get("judge_name", "Judge"),
            "response_en": r.get("response_en", "No detailed response in English."),
            "response_ja": r.get("response_ja", "日本語の回答がありません。")
        }
        normalized_responses.append(normalized_r)
        
    sanitized["judges_responses"] = normalized_responses
    return sanitized
