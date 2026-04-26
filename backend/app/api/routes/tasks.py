"""Task CRUD + agent-pipeline kickoff endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import run_agent_pipeline
from app.api.deps import get_current_user, get_db
from app.api.middleware.rate_limit import limiter
from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.guardrails import validate_task_input
from app.db.models import Task, TaskStatus, User
from app.schemas.task import TaskCreate, TaskListRead, TaskRead

router = APIRouter()


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.RATE_LIMIT_TASK_CREATE)
async def create_task(
    request: Request,
    payload: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    validate_task_input(payload.description)
    task = Task(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        user_id=current_user.id,
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Kick off the Planner â Executor â Critic pipeline in the background.
    background_tasks.add_task(run_agent_pipeline, task.id, task.description)
    return task


@router.get("/", response_model=list[TaskListRead])
async def list_tasks(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    skip = max(skip, 0)
    limit = max(1, min(limit, 100))
    result = await db.execute(
        select(Task)
        .where(Task.user_id == current_user.id)
        .order_by(Task.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise NotFoundError("Task not found")
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    task = await db.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise NotFoundError("Task not found")
    await db.delete(task)
    await db.commit()


@router.post("/{task_id}/cancel", response_model=TaskRead)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = await db.get(Task, task_id)
    if not task or task.user_id != current_user.id:
        raise NotFoundError("Task not found")
    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        return task
    task.status = TaskStatus.FAILED
    task.error_message = "Cancelled by user"
    task.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(task)
    return task
