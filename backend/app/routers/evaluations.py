"""
Evaluations router: scores, scoreboard, deletion.
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, get_current_user, require_role
from app.models.db import (
    Evaluation,
    SessionLocal,
    User,
    delete_evaluation,
    get_criteria,
)
from app.schemas.schemas import EvaluationResponse, ScoreboardEntry

router = APIRouter(prefix="/api/evaluations", tags=["evaluations"])


@router.get("/team/{team_id}", response_model=list[EvaluationResponse])
def get_team_evaluations(
    team_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get all evaluations for a specific team."""
    # Teams can only see their own evaluations
    if user.role == "team" and user.team_id != team_id:
        raise HTTPException(status_code=403, detail="Access denied")

    hackathon_id = user.hackathon_id
    db = SessionLocal()
    try:
        evaluations = (
            db.query(Evaluation)
            .filter(Evaluation.hackathon_id == hackathon_id, Evaluation.team_id == team_id)
            .order_by(Evaluation.id.asc())
            .all()
        )
        return [
            EvaluationResponse(
                id=e.id,
                team_id=e.team_id,
                scores_json=e.scores_json,
                impact_score=e.impact_score,
                strengths_risks_json=e.strengths_risks_json,
                qa_json=e.qa_json,
                is_final=e.is_final,
                source_text=e.source_text,
                gemini_file_ids=e.gemini_file_ids,
                evaluated_at=str(e.evaluated_at) if e.evaluated_at else None,
            )
            for e in evaluations
        ]
    finally:
        db.close()


@router.get("/scoreboard", response_model=list[ScoreboardEntry])
def get_scoreboard(user: CurrentUser = Depends(get_current_user)):
    """Get the live scoreboard for the current hackathon."""
    hackathon_id = user.hackathon_id
    if not hackathon_id:
        raise HTTPException(status_code=400, detail="No active hackathon")

    criteria = get_criteria(hackathon_id)
    active_criteria = [c for c in criteria if c.get("active", True)]
    total_weight = sum(c["weight"] for c in active_criteria) if active_criteria else 1

    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.role == "team", User.hackathon_id == hackathon_id, User.is_active)
            .order_by(User.team_id)
            .all()
        )

        all_teams = {
            u.team_id: {
                "product_name": u.product_name,
                "team_name": u.team_name,
                "one_liner": u.one_liner,
            }
            for u in users
        }
        team_ids = list(all_teams.keys())

        evaluations = (
            db.query(Evaluation)
            .filter(Evaluation.team_id.in_(team_ids))
            .all()
        ) if team_ids else []

        # Build eval dict: latest per team
        eval_dict = {}
        for tid in team_ids:
            team_evals = [e for e in evaluations if e.team_id == tid]
            if team_evals:
                latest = max(team_evals, key=lambda x: x.id)
                eval_dict[tid] = {
                    "scores_json": latest.scores_json,
                    "is_final": latest.is_final,
                    "consults": len(team_evals),
                }

        result = []
        for tid, info in all_teams.items():
            entry = ScoreboardEntry(
                team_id=tid,
                product_name=info["product_name"],
                team_name=info["team_name"],
                one_liner=info["one_liner"],
            )

            if tid in eval_dict:
                ed = eval_dict[tid]
                scores = json.loads(ed["scores_json"])
                total_score = sum(
                    scores.get(c["name"], 0) * 20.0 * (c["weight"] / total_weight)
                    for c in active_criteria
                )
                entry.total_score = round(total_score, 1)
                entry.consults = ed["consults"]
                entry.status = "Final" if ed["is_final"] else f"In Progress ({ed['consults']}/3)"
                entry.scores_json = ed["scores_json"]

            result.append(entry)

        result.sort(key=lambda x: x.total_score, reverse=True)
        return result
    finally:
        db.close()


@router.delete("/{evaluation_id}")
def delete_evaluation_endpoint(
    evaluation_id: int,
    user: CurrentUser = Depends(require_role("admin")),
):
    """Delete an evaluation and its chat history."""
    delete_evaluation(user.hackathon_id, evaluation_id)
    return {"message": f"Evaluation {evaluation_id} deleted"}
