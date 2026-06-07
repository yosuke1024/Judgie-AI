import os
import tempfile

from core.db import save_evaluation
from core.file_handler import extract_text_from_zip
from core.gemini import analyze_submission, upload_to_gemini, wait_for_files_active


def process_submission(hackathon_id: int, team_id: str, uploaded_files: list, prev_evaluations_json: str, is_final: bool) -> dict:
    """
    Handles the entire submission workflow: extraction, Gemini upload, polling, and parsing.
    Includes defensive fallback structures to protect against LLM schema malformations.
    """
    text_content = ""
    gemini_media_files = []

    # Extract text from ZIP and upload media files to Gemini
    for uf in uploaded_files:
        if uf.name.endswith(".zip"):
            text_content += extract_text_from_zip(uf)
        elif uf.name.endswith((".mp4", ".mov", ".pdf")):
            ext = os.path.splitext(uf.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(uf.read())
                tmp_path = tmp.name

            mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".pdf": "application/pdf"}
            mime_type = mime_map.get(ext.lower(), "application/octet-stream")

            g_file = upload_to_gemini(hackathon_id, tmp_path, mime_type=mime_type)
            gemini_media_files.append(g_file)
            os.unlink(tmp_path)

    # Wait for Gemini file active status if media files exist
    if gemini_media_files:
        wait_for_files_active(hackathon_id, gemini_media_files)

    # Analyze via Gemini model
    result_json = analyze_submission(
        hackathon_id,
        text_content,
        gemini_media_files,
        previous_evaluations_json=prev_evaluations_json,
        is_final=is_final
    )

    # Defensive programming: ensure the JSON structure conforms to what UI expects
    result_json = sanitize_evaluation_response(result_json)

    # Save the normalized evaluation to database
    g_file_names = [f.name for f in gemini_media_files] if gemini_media_files else []
    save_evaluation(hackathon_id, team_id, result_json, is_final=is_final, source_text=text_content, gemini_file_ids=g_file_names)

    return result_json

def sanitize_evaluation_response(data: dict) -> dict:
    """
    Sanitizes LLM response to ensure essential keys and safe fallback structures are present.
    """
    if not isinstance(data, dict):
        data = {}

    sanitized = {
        "product_understanding_en": data.get("product_understanding_en", "No product understanding provided."),
        "product_understanding_ja": data.get("product_understanding_ja", "プロダクトの理解が提供されていません。"),
        "action_items_en": data.get("action_items_en", []),
        "action_items_ja": data.get("action_items_ja", []),
        "scores": data.get("scores", {}),
        "impact_score": float(data.get("impact_score", 0.0)),
        "judges_feedback": data.get("judges_feedback", [])
    }

    # Ensure lists are strictly lists
    if not isinstance(sanitized["action_items_en"], list):
        sanitized["action_items_en"] = [str(sanitized["action_items_en"])] if sanitized["action_items_en"] else []
    if not isinstance(sanitized["action_items_ja"], list):
        sanitized["action_items_ja"] = [str(sanitized["action_items_ja"])] if sanitized["action_items_ja"] else []
    if not isinstance(sanitized["judges_feedback"], list):
        sanitized["judges_feedback"] = []

    # Normalize judges feedback list
    normalized_feedback = []
    for j in sanitized["judges_feedback"]:
        if not isinstance(j, dict):
            continue
        normalized_j = {
            "judge_name": j.get("judge_name", "Judge"),
            "judge_role": j.get("judge_role", "Expert Panelist"),
            "judge_persona": j.get("judge_persona", ""),
            "judge_scores": j.get("judge_scores", []),
            "feedback_en": j.get("feedback_en", "No detailed feedback in English."),
            "feedback_ja": j.get("feedback_ja", "日本語のフィードバックがありません。")
        }
        if not isinstance(normalized_j["judge_scores"], list):
            normalized_j["judge_scores"] = []

        normalized_feedback.append(normalized_j)

    sanitized["judges_feedback"] = normalized_feedback
    return sanitized
