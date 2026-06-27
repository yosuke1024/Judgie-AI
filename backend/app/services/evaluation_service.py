import json
import logging

from app.models.db import Evaluation, TeamChat, db_session, get_ai_response_languages, normalize_lang_to_key
from app.services.gemini import object_to_judges, translate_text

logger = logging.getLogger(__name__)


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


def minimize_evaluation_context(strengths_risks_json_str: str) -> dict:
    """
    Minimizes the evaluation feedback context by removing unnecessary metadata
    (like judge personas, roles, emojis, avatar images) to optimize LLM token usage.
    """
    if not strengths_risks_json_str:
        return {}
    try:
        raw_feedback = json.loads(strengths_risks_json_str)
    except Exception:
        return {}

    judges_feedback = raw_feedback.get("judges_feedback", [])
    minimized_feedback = []

    for j in judges_feedback:
        minimized_j = {
            "judge_name": j.get("judge_name"),
            "judge_scores": j.get("judge_scores", []),
        }
        # Copy only translation feedback keys (e.g., feedback_en, feedback_ja)
        # Exclude judge_persona, judge_role, judge_emoji, judge_avatar_image
        for key, val in j.items():
            if key.startswith("feedback_"):
                minimized_j[key] = val
        minimized_feedback.append(minimized_j)

    minimized_context = {"judges_feedback": minimized_feedback}

    # Also carry over product understanding summaries if available
    for key, val in raw_feedback.items():
        if key.startswith("summary_"):
            minimized_context[key] = val

    return minimized_context


def submit_team_objection(eval_id: int, prev_eval_json: str, objection_text: str) -> dict:
    """
    Executes a chat session turn with the AI expert panel in response to the team's objection.
    Inserts both user objection and panel's answer as separate records in TeamChat table.
    """
    # 1. Translate the user's objection into all configured languages
    languages = get_ai_response_languages()
    try:
        translated = translate_text(objection_text, languages)
        translated["user_objection"] = objection_text
    except Exception as e:
        logger.warning(f"Translation failed: {e}")
        translated = {"user_objection": objection_text}
        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            translated[f"user_objection_{lang_key}"] = objection_text

    # 2. Retrieve the entire chat history for this evaluation
    with db_session() as db:
        chats = db.query(TeamChat).filter(TeamChat.evaluation_id == eval_id).order_by(TeamChat.created_at.asc()).all()
        chat_history = []
        for c in chats:
            chat_history.append({"sender": c.sender, "message_json": c.message_json})

    # Append the new user objection to the chat history in memory for the LLM context
    chat_history.append({"sender": "team", "message_json": json.dumps(translated)})

    # Minimize previous evaluation context to protect against token overflow
    minimized_prev = minimize_evaluation_context(prev_eval_json)
    minimized_prev_json = json.dumps(minimized_prev) if minimized_prev else "{}"

    # 3. Call Gemini with the full Q&A discussion history
    qa_result = object_to_judges("", None, minimized_prev_json, chat_history)

    # Defensive programming: sanitize Gemini responses
    qa_result = sanitize_objection_response(qa_result)

    # 4. Insert both user message and AI response to TeamChat table in a single transaction
    with db_session() as db:
        user_msg = TeamChat(evaluation_id=eval_id, sender="team", message_json=json.dumps(translated))
        db.add(user_msg)
        db.flush()

        ai_msg = TeamChat(evaluation_id=eval_id, sender="judges", message_json=json.dumps(qa_result))
        db.add(ai_msg)

    return qa_result


def sanitize_objection_response(data: dict) -> dict:
    """
    Sanitizes LLM panel objection debate responses.
    Supports dynamic multilingual keys based on configured languages.
    """
    languages = get_ai_response_languages()
    from app.models.db import get_personas

    personas = get_personas()
    persona_map = {p["name"].lower(): p for p in personas}

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

        j_name = r.get("judge_name", "Judge")
        p_data = persona_map.get(j_name.lower(), {})

        normalized_r = {
            "judge_name": j_name,
            "judge_role": r.get("judge_role") or p_data.get("role") or "Expert Panelist",
            "judge_emoji": p_data.get("avatar") or r.get("judge_emoji") or r.get("avatar") or "🤖",
            "judge_avatar_image": p_data.get("avatar_image") or r.get("judge_avatar_image") or r.get("avatar_image"),
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
