"""
Submissions router: file upload and AI evaluation (async via BackgroundTasks).
"""

import json
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.auth.deps import CurrentUser, get_current_user
from app.models.db import (
    create_async_task,
    get_ai_response_languages,
    get_consultation_count,
    get_max_consultations,
    get_re_evaluation_context_mode,
    is_video_upload_enabled,
    save_evaluation,
    update_async_task,
)
from app.schemas.schemas import AsyncTaskResponse

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _run_submission_evaluation(
    task_id: str,
    team_id: str,
    saved_files: list[dict],
    is_final: bool,
    current_count: int,
):
    """Background task: process files and run AI evaluation."""
    from app.services.file_handler import extract_text_from_zip
    from app.services.gemini import analyze_submission, upload_to_gemini, wait_for_files_active
    from app.services.submission_service import sanitize_evaluation_response

    update_async_task(task_id, "PROCESSING")

    try:
        text_content = ""
        gemini_media_files = []

        for file_info in saved_files:
            path = file_info["path"]
            filename = file_info["filename"]

            if filename.endswith(".zip"):
                import io

                with open(path, "rb") as f:
                    text_content += extract_text_from_zip(io.BytesIO(f.read()))
            elif filename.endswith((".mp4", ".mov", ".pdf")):
                ext = os.path.splitext(filename)[1].lower()
                mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".pdf": "application/pdf"}
                mime_type = mime_map.get(ext, "application/octet-stream")
                g_file = upload_to_gemini(path, mime_type=mime_type)
                gemini_media_files.append(g_file)

        # Wait for Gemini file processing
        if gemini_media_files:
            wait_for_files_active(gemini_media_files)

        # Build previous evaluations context
        prev_evaluations_json = ""
        context_mode = get_re_evaluation_context_mode()
        if context_mode == "cumulative" and current_count > 0:
            from app.models.db import Evaluation, SessionLocal

            db = SessionLocal()
            try:
                prev_evals = (
                    db.query(Evaluation).filter(Evaluation.team_id == team_id).order_by(Evaluation.id.asc()).all()
                )
                if prev_evals:
                    prev_data = []
                    for pe in prev_evals:
                        prev_data.append(
                            {
                                "scores": json.loads(pe.scores_json),
                                "feedback": json.loads(pe.strengths_risks_json),
                            }
                        )
                    prev_evaluations_json = json.dumps(prev_data)
            finally:
                db.close()

        # Analyze via Gemini
        result_json = analyze_submission(
            text_content,
            gemini_media_files,
            previous_evaluations_json=prev_evaluations_json,
            is_final=is_final,
        )

        # Sanitize response
        languages = get_ai_response_languages()
        result_json = sanitize_evaluation_response(result_json, languages)

        # Save to DB
        g_file_names = [f.name for f in gemini_media_files] if gemini_media_files else []
        save_evaluation(
            team_id,
            result_json,
            is_final=is_final,
            source_text=text_content,
            gemini_file_ids=g_file_names,
        )

        update_async_task(task_id, "SUCCESS")

    except Exception as e:
        err_msg = str(e)
        update_async_task(task_id, "FAILED", error_message=err_msg)

    finally:
        # Clean up temporary files
        for file_info in saved_files:
            try:
                os.unlink(file_info["path"])
            except OSError:
                pass


@router.post("/upload", response_model=AsyncTaskResponse, status_code=202)
async def upload_submission(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    is_final: bool = Form(False),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Upload files for AI evaluation (async).
    Accepts ZIP, MP4, MOV, PDF files.
    Returns 202 Accepted with a task_id for polling.
    """
    if user.role not in ("team",):
        raise HTTPException(status_code=403, detail="Only teams can submit")

    team_id = user.team_id

    # Check consultation limit
    max_cons = get_max_consultations()
    current_count = get_consultation_count(team_id)
    if max_cons != -1 and current_count >= max_cons and not is_final:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum consultations ({max_cons}) reached",
        )

    video_enabled = is_video_upload_enabled()

    # Save uploaded files to temp directory for background processing
    saved_files: list[dict] = []
    for uf in files:
        file_bytes = await uf.read()
        filename = uf.filename or ""

        if filename.endswith((".zip", ".mp4", ".mov", ".pdf")):
            ext = os.path.splitext(filename)[1].lower()

            if ext in (".mp4", ".mov") and not video_enabled:
                # Clean up already saved files
                for f in saved_files:
                    try:
                        os.unlink(f["path"])
                    except OSError:
                        pass
                raise HTTPException(
                    status_code=400,
                    detail="Video uploads are disabled for this project",
                )

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                saved_files.append({"path": tmp.name, "filename": filename})

    # Create async task
    task_id = create_async_task(team_id, "submission")

    # Schedule background work
    background_tasks.add_task(
        _run_submission_evaluation,
        task_id,
        team_id,
        saved_files,
        is_final,
        current_count,
    )

    return JSONResponse(
        status_code=202,
        content={"task_id": task_id, "status": "PENDING", "result_id": None, "error_message": None},
    )
