"""
Chat router: team Q&A (objections) and admin private queries.
Both POST endpoints run LLM calls asynchronously via BackgroundTasks.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.auth.deps import CurrentUser, get_current_user, require_role
from app.models.db import (
    Evaluation,
    SessionLocal,
    TeamChat,
    create_async_task,
    get_admin_chats,
    get_ai_response_languages,
    get_max_qa_turns,
    normalize_lang_to_key,
    save_admin_chat,
    update_async_task,
)
from app.schemas.schemas import (
    AdminChatResponse,
    AdminQuestion,
    AsyncTaskResponse,
    ChatMessage,
    TeamObjection,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Team Q&A (Objections) ──


@router.get("/team/{eval_id}", response_model=list[ChatMessage])
def get_team_chat_history(
    eval_id: int,
    user: CurrentUser = Depends(get_current_user),
):
    """Get team Q&A chat history for an evaluation."""
    db = SessionLocal()
    try:
        chats = db.query(TeamChat).filter(TeamChat.evaluation_id == eval_id).order_by(TeamChat.created_at.asc()).all()
        result = []
        for c in chats:
            try:
                msg_data = json.loads(c.message_json)
            except Exception:
                msg_data = c.message_json
            result.append(
                ChatMessage(
                    id=c.id,
                    sender=c.sender,
                    message_json=msg_data,
                    created_at=str(c.created_at) if c.created_at else None,
                )
            )
        return result
    finally:
        db.close()


def _run_team_objection(task_id: str, eval_id: int, prev_eval_json: str, objection_text: str):
    """Background task: process team objection via AI judges panel."""
    update_async_task(task_id, "PROCESSING")
    try:
        from app.services.evaluation_service import submit_team_objection as svc_submit

        svc_submit(eval_id, prev_eval_json, objection_text)
        update_async_task(task_id, "SUCCESS")
    except Exception as e:
        update_async_task(task_id, "FAILED", error_message=str(e))


@router.post("/team/{eval_id}", response_model=AsyncTaskResponse, status_code=202)
def submit_team_objection(
    eval_id: int,
    req: TeamObjection,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(get_current_user),
):
    """Submit a team objection/question to the AI judges panel (async)."""
    if user.role != "team":
        raise HTTPException(status_code=403, detail="Only teams can submit objections")

    # Check Q&A turn limit
    max_turns = get_max_qa_turns()
    db = SessionLocal()
    try:
        team_turns = db.query(TeamChat).filter(TeamChat.evaluation_id == eval_id, TeamChat.sender == "team").count()
    finally:
        db.close()

    if max_turns != -1 and team_turns >= max_turns:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum Q&A turns ({max_turns}) reached",
        )

    # Get previous evaluation JSON for context
    db = SessionLocal()
    try:
        eval_record = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
        if not eval_record:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        prev_eval_json = eval_record.strengths_risks_json
    finally:
        db.close()

    # Create async task and schedule background work
    task_id = create_async_task(user.team_id, "objection")
    background_tasks.add_task(_run_team_objection, task_id, eval_id, prev_eval_json, req.objection_text)

    return JSONResponse(
        status_code=202,
        content={"task_id": task_id, "status": "PENDING", "result_id": None, "error_message": None},
    )


# ── Admin Private Chat ──


@router.get("/admin/{eval_id}", response_model=list[AdminChatResponse])
def get_admin_chat_history(
    eval_id: int,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Get admin private chat history for an evaluation."""
    chats = get_admin_chats(eval_id)
    return [AdminChatResponse(**c) for c in chats]


def _run_admin_chat(
    task_id: str, eval_id: int, source_text: str, gemini_file_ids: str, prev_json_str: str, question: str
):
    """Background task: process admin private chat question via Gemini."""
    update_async_task(task_id, "PROCESSING")
    try:
        from app.services.gemini import admin_chat_about_submission

        res_json = admin_chat_about_submission(
            source_text,
            gemini_file_ids,
            prev_json_str,
            question,
        )

        # Map dynamic keys to static columns for backward compatibility
        languages = get_ai_response_languages()
        q_en = question
        q_ja = question
        a_en = ""
        a_ja = ""

        for lang in languages:
            lang_key = normalize_lang_to_key(lang)
            if lang_key in ["english", "en", "英語"]:
                q_en = res_json.get(f"question_{lang_key}", question)
                a_en = res_json.get(f"answer_{lang_key}", "")
            elif lang_key in ["japanese", "ja", "日本語"]:
                q_ja = res_json.get(f"question_{lang_key}", question)
                a_ja = res_json.get(f"answer_{lang_key}", "")

        save_admin_chat(
            evaluation_id=eval_id,
            question_en=q_en,
            question_ja=q_ja,
            answer_en=a_en,
            answer_ja=a_ja,
            qa_json=res_json,
        )

        update_async_task(task_id, "SUCCESS")

    except Exception as e:
        update_async_task(task_id, "FAILED", error_message=str(e))


@router.post("/admin/{eval_id}", response_model=AsyncTaskResponse, status_code=202)
def submit_admin_question(
    eval_id: int,
    req: AdminQuestion,
    background_tasks: BackgroundTasks,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Submit an admin question about a team's submission (async)."""
    db = SessionLocal()
    try:
        eval_record = db.query(Evaluation).filter(Evaluation.id == eval_id).first()
        if not eval_record:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        source_text = eval_record.source_text
        gemini_file_ids = eval_record.gemini_file_ids
        prev_json_str = eval_record.strengths_risks_json
    finally:
        db.close()

    if not source_text and not gemini_file_ids:
        raise HTTPException(
            status_code=400,
            detail="No source data available for this submission",
        )

    # Create async task and schedule background work
    task_id = create_async_task(user.team_id, "admin_chat")
    background_tasks.add_task(
        _run_admin_chat,
        task_id,
        eval_id,
        source_text,
        gemini_file_ids,
        prev_json_str,
        req.question,
    )

    return JSONResponse(
        status_code=202,
        content={"task_id": task_id, "status": "PENDING", "result_id": None, "error_message": None},
    )
