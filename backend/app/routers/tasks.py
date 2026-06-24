"""
Tasks router: async task status polling endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import CurrentUser, get_current_user
from app.models.db import get_async_task
from app.schemas.schemas import AsyncTaskResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=AsyncTaskResponse)
def get_task_status(
    task_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get the current status of an async task."""
    task = get_async_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Why: Ensure users can only poll their own tasks to prevent information leakage.
    # Admins can poll any task since they need visibility into all team activities.
    if user.role != "admin" and task["team_id"] != user.team_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this task")

    return AsyncTaskResponse(**task)
