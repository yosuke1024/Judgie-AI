"""
Submissions router: file upload and AI evaluation.
"""

import json
import os
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.deps import CurrentUser, get_current_user
from app.models.db import (
    get_ai_response_languages,
    get_consultation_count,
    get_max_consultations,
    get_re_evaluation_context_mode,
    is_video_upload_enabled,
    save_evaluation,
)

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("/upload")
async def upload_submission(
    files: list[UploadFile] = File(...),
    is_final: bool = Form(False),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Upload files for AI evaluation.
    Accepts ZIP, MP4, MOV, PDF files.
    """
    if user.role not in ("team",):
        raise HTTPException(status_code=403, detail="Only teams can submit")

    hackathon_id = user.hackathon_id
    team_id = user.team_id

    if not hackathon_id:
        raise HTTPException(status_code=400, detail="No active hackathon")

    # Check consultation limit
    max_cons = get_max_consultations(hackathon_id)
    current_count = get_consultation_count(hackathon_id, team_id)
    if max_cons != -1 and current_count >= max_cons and not is_final:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum consultations ({max_cons}) reached",
        )

    video_enabled = is_video_upload_enabled(hackathon_id)

    # Process files
    from app.services.file_handler import extract_text_from_zip
    from app.services.gemini import analyze_submission, upload_to_gemini, wait_for_files_active

    text_content = ""
    gemini_media_files = []

    for uf in files:
        file_bytes = await uf.read()
        filename = uf.filename or ""

        if filename.endswith(".zip"):
            import io
            text_content += extract_text_from_zip(io.BytesIO(file_bytes))
        elif filename.endswith((".mp4", ".mov", ".pdf")):
            ext = os.path.splitext(filename)[1].lower()
            if ext in (".mp4", ".mov") and not video_enabled:
                raise HTTPException(
                    status_code=400,
                    detail="Video uploads are disabled for this project",
                )

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".pdf": "application/pdf"}
            mime_type = mime_map.get(ext, "application/octet-stream")

            g_file = upload_to_gemini(hackathon_id, tmp_path, mime_type=mime_type)
            gemini_media_files.append(g_file)
            os.unlink(tmp_path)

    # Wait for Gemini file processing
    if gemini_media_files:
        wait_for_files_active(hackathon_id, gemini_media_files)

    # Build previous evaluations context
    prev_evaluations_json = ""
    context_mode = get_re_evaluation_context_mode(hackathon_id)
    if context_mode == "cumulative" and current_count > 0:
        from app.models.db import Evaluation, SessionLocal
        db = SessionLocal()
        try:
            prev_evals = (
                db.query(Evaluation)
                .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id)
                .order_by(Evaluation.id.asc())
                .all()
            )
            if prev_evals:
                prev_data = []
                for pe in prev_evals:
                    prev_data.append({
                        "scores": json.loads(pe.scores_json),
                        "feedback": json.loads(pe.strengths_risks_json),
                    })
                prev_evaluations_json = json.dumps(prev_data)
        finally:
            db.close()

    # Analyze via Gemini
    try:
        result_json = analyze_submission(
            hackathon_id,
            text_content,
            gemini_media_files,
            previous_evaluations_json=prev_evaluations_json,
            is_final=is_final,
        )
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            raise HTTPException(
                status_code=429,
                detail="Gemini API rate limit reached (token quota exceeded). Please wait a moment or configure a paid API key."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Gemini evaluation failed: {err_msg}"
            )

    # Sanitize response
    from app.services.submission_service import sanitize_evaluation_response
    languages = get_ai_response_languages(hackathon_id)
    result_json = sanitize_evaluation_response(result_json, languages)

    # Save to DB
    g_file_names = [f.name for f in gemini_media_files] if gemini_media_files else []
    save_evaluation(
        hackathon_id, team_id, result_json,
        is_final=is_final, source_text=text_content, gemini_file_ids=g_file_names,
    )

    return result_json
