import os
import tempfile

from app.models.db import is_video_upload_enabled, save_evaluation
from app.services.file_handler import extract_text_from_zip
from app.services.gemini import analyze_submission, upload_to_gemini, wait_for_files_active


def process_submission(
    hackathon_id: int, team_id: str, uploaded_files: list, prev_evaluations_json: str, is_final: bool
) -> dict:
    """
    Handles the entire submission workflow: extraction, Gemini upload, polling, and parsing.
    Includes defensive fallback structures to protect against LLM schema malformations.
    """
    video_enabled = is_video_upload_enabled(hackathon_id)

    text_content = ""
    gemini_media_files = []

    # Extract text from ZIP and upload media files to Gemini
    for uf in uploaded_files:
        if uf.name.endswith(".zip"):
            text_content += extract_text_from_zip(uf)
        elif uf.name.endswith((".mp4", ".mov", ".pdf")):
            ext = os.path.splitext(uf.name)[1]
            if ext.lower() in (".mp4", ".mov") and not video_enabled:
                raise ValueError(
                    "Video uploads (MP4, MOV) are disabled for this project. / "
                    "このプロジェクトでは動画のアップロードは無効化されています。"
                )

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
        is_final=is_final,
    )

    # Defensive programming: ensure the JSON structure conforms to what UI expects
    from app.models.db import get_ai_response_languages

    languages = get_ai_response_languages(hackathon_id)
    result_json = sanitize_evaluation_response(result_json, hackathon_id, languages)

    # Save the normalized evaluation to database
    g_file_names = [f.name for f in gemini_media_files] if gemini_media_files else []
    save_evaluation(
        hackathon_id, team_id, result_json, is_final=is_final, source_text=text_content, gemini_file_ids=g_file_names
    )

    return result_json


def sanitize_evaluation_response(data: dict, hackathon_id: int, languages: list[str] = None) -> dict:
    """
    Sanitizes LLM response to ensure essential keys and safe fallback structures are present.
    """
    if languages is None:
        languages = ["English", "Japanese"]
    from app.models.db import normalize_lang_to_key, get_personas

    personas = get_personas(hackathon_id)
    persona_map = {p["name"].lower(): p for p in personas}

    if not isinstance(data, dict):
        data = {}

    sanitized = {
        "scores": data.get("scores", {}),
        "impact_score": float(data.get("impact_score", 0.0)),
        "judges_feedback": data.get("judges_feedback", []),
    }

    # Compatibility mapping for legacy keys
    compat_map = {
        "english": "en",
        "japanese": "ja",
        "日本語": "ja",
        "英語": "en",
        "spanish": "es",
        "french": "fr",
        "german": "de",
        "korean": "ko",
        "chinese": "zh",
        "vietnamese": "vi",
        "thai": "th",
        "indonesian": "id",
    }

    # Dynamically populate product_understanding and action_items for each language
    for lang in languages:
        lang_key = normalize_lang_to_key(lang)

        pu_val = data.get(f"product_understanding_{lang_key}")
        if pu_val is None and lang_key in compat_map:
            pu_val = data.get(f"product_understanding_{compat_map[lang_key]}")
        sanitized[f"product_understanding_{lang_key}"] = pu_val or f"No product understanding provided in {lang}."

        action_items_key = f"action_items_{lang_key}"
        items = data.get(action_items_key)
        if items is None and lang_key in compat_map:
            items = data.get(f"action_items_{compat_map[lang_key]}")
        if not isinstance(items, list):
            items = [str(items)] if items else []
        sanitized[action_items_key] = items

    if not isinstance(sanitized["judges_feedback"], list):
        sanitized["judges_feedback"] = []

    # Normalize judges feedback list
    normalized_feedback = []
    for j in sanitized["judges_feedback"]:
        if not isinstance(j, dict):
            continue
        j_name = j.get("judge_name", "Judge")
        p_data = persona_map.get(j_name.lower(), {})

        normalized_j = {
            "judge_name": j_name,
            "judge_role": j.get("judge_role") or p_data.get("role") or "Expert Panelist",
            "judge_persona": j.get("judge_persona") or (p_data.get("prompt", "")[:120] + "...") or "",
            "judge_scores": j.get("judge_scores", []),
            "judge_emoji": p_data.get("avatar") or j.get("judge_emoji") or j.get("avatar") or "🤖",
            "judge_avatar_image": p_data.get("avatar_image") or j.get("judge_avatar_image") or j.get("avatar_image"),
        }
        if not isinstance(normalized_j["judge_scores"], list):
            normalized_j["judge_scores"] = []

        # Dynamically populate feedback for each language
        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            fb_val = j.get(f"feedback_{lang_key}")
            if fb_val is None and lang_key in compat_map:
                fb_val = j.get(f"feedback_{compat_map[lang_key]}")
            normalized_j[f"feedback_{lang_key}"] = fb_val or f"No detailed feedback in {lang}."

        normalized_feedback.append(normalized_j)

    sanitized["judges_feedback"] = normalized_feedback
    return sanitized
