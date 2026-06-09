from core.db import Evaluation, db_session, save_objection_qa, get_ai_response_languages, normalize_lang_to_key
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
    qa_result = sanitize_objection_response(qa_result, hackathon_id)

    # Cache user objection text in the database object
    qa_result['user_objection'] = objection_text

    save_objection_qa(eval_id, qa_result)
    return qa_result

def sanitize_objection_response(data: dict, hackathon_id: int = None) -> dict:
    """
    Sanitizes LLM panel objection debate responses.
    Supports dynamic multilingual keys based on configured languages.
    """
    if hackathon_id is not None:
        languages = get_ai_response_languages(hackathon_id)
    else:
        languages = ["English", "Japanese"]

    if not isinstance(data, dict):
        data = {}

    sanitized = {}

    # Map dynamic qa_summary keys for each configured language
    for lang in languages:
        lang_key = normalize_lang_to_key(lang)
        default_summary = "Objection evaluated by the expert panel."
        if lang_key in ["japanese", "ja", "日本語"]:
            default_summary = "審査員パネルによって異議が精査されました。"
        sanitized[f"qa_summary_{lang_key}"] = data.get(f"qa_summary_{lang_key}", default_summary)

    # Retain legacy/fallback keys for backward compatibility
    sanitized["qa_summary_en"] = data.get("qa_summary_en", "Objection evaluated by the expert panel.")
    sanitized["qa_summary_ja"] = data.get("qa_summary_ja", "審査員パネルによって異議が精査されました。")

    raw_responses = data.get("judges_responses", [])
    if not isinstance(raw_responses, list):
        raw_responses = []

    normalized_responses = []
    for r in raw_responses:
        if not isinstance(r, dict):
            continue
        
        normalized_r = {
            "judge_name": r.get("judge_name", "Judge"),
        }

        # Map dynamic response keys for each configured language
        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            default_resp = "No detailed response in this language."
            if lang_key in ["japanese", "ja", "日本語"]:
                default_resp = "日本語の回答がありません。"
            elif lang_key in ["english", "en", "英語"]:
                default_resp = "No detailed response in English."
            
            normalized_r[f"response_{lang_key}"] = r.get(f"response_{lang_key}", default_resp)

        # Retain legacy/fallback keys for backward compatibility
        normalized_r["response_en"] = r.get("response_en", "No detailed response in English.")
        normalized_r["response_ja"] = r.get("response_ja", "日本語の回答がありません。")

        normalized_responses.append(normalized_r)

    sanitized["judges_responses"] = normalized_responses
    return sanitized

