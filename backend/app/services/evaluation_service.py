import json

from app.models.db import Evaluation, TeamChat, db_session, get_ai_response_languages, normalize_lang_to_key
from app.services.gemini import object_to_judges


def get_team_evaluations(team_id: str) -> list[dict]:
    """
    Safely retrieves and formats all evaluations for the specified team.
    """
    with db_session() as db:
        evaluations = db.query(Evaluation).filter(Evaluation.team_id == team_id).order_by(Evaluation.id.asc()).all()
        eval_rows = []
        for e in evaluations:
            eval_rows.append(
                {
                    "id": e.id,
                    "team_id": e.team_id,
                    "scores_json": e.scores_json,
                    "impact_score": e.impact_score,
                    "strengths_risks_json": e.strengths_risks_json,
                    "qa_json": e.qa_json,
                    "is_final": e.is_final,
                    "source_text": e.source_text,
                    "gemini_file_ids": e.gemini_file_ids,
                    "evaluated_at": e.evaluated_at,
                }
            )
        return eval_rows


def get_team_chats(evaluation_id: int) -> list[dict]:
    """
    Retrieves all chat messages for a specific evaluation ID.
    """
    with db_session() as db:
        chats = (
            db.query(TeamChat).filter(TeamChat.evaluation_id == evaluation_id).order_by(TeamChat.created_at.asc()).all()
        )
        chat_list = []
        for c in chats:
            try:
                msg_data = json.loads(c.message_json)
            except Exception:
                msg_data = c.message_json
            chat_list.append({"id": c.id, "sender": c.sender, "message_json": msg_data, "created_at": c.created_at})
        return chat_list


def submit_team_objection(hackathon_id: int, eval_id: int, prev_eval_json: str, objection_text: str) -> dict:
    """
    Executes a chat session turn with the AI expert panel in response to the team's objection.
    Inserts both user objection and panel's answer as separate records in TeamChat table.
    """
    # 1. Translate the user's objection into all configured languages
    languages = get_ai_response_languages(hackathon_id)
    try:
        from app.services.gemini import translate_text
        translated = translate_text(hackathon_id, objection_text, languages)
        translated["user_objection"] = objection_text
    except Exception as e:
        print(f"Translation failed: {e}")
        translated = {"user_objection": objection_text}
        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            translated[f"user_objection_{lang_key}"] = objection_text

    # 2. Insert user message to TeamChat table
    with db_session() as db:
        user_msg = TeamChat(
            evaluation_id=eval_id, sender="team", message_json=json.dumps(translated)
        )
        db.add(user_msg)
        db.flush()

        # 3. Retrieve the entire chat history for this evaluation
        chats = db.query(TeamChat).filter(TeamChat.evaluation_id == eval_id).order_by(TeamChat.created_at.asc()).all()
        chat_history = []
        for c in chats:
            chat_history.append({"sender": c.sender, "message_json": c.message_json})

    # 4. Call Gemini with the full Q&A discussion history
    qa_result = object_to_judges(hackathon_id, "", None, prev_eval_json, chat_history)

    # Defensive programming: sanitize Gemini responses
    qa_result = sanitize_objection_response(qa_result, hackathon_id)

    # 5. Insert AI response to TeamChat table
    with db_session() as db:
        ai_msg = TeamChat(evaluation_id=eval_id, sender="judges", message_json=json.dumps(qa_result))
        db.add(ai_msg)

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
