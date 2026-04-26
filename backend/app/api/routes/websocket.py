"""WebSocket endpoint streaming live agent events for a task.

Auth: token is passed via query string `?token=<jwt>` since browsers
cannot set custom Authorization headers on WebSocket upgrade.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.exceptions import InvalidTokenError
from app.core.security import decode_token
from app.db.models import Task, User
from app.db.session import async_session_factory
from app.queue.redis_client import subscribe_to_task_updates

logger = structlog.get_logger()
router = APIRouter()


async def _authenticate_ws(token: str | None) -> str | None:
    """Return the authenticated user_id, or None on failure."""
    if not token:
        return None
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        return None
    return payload.get("sub")


@router.websocket("/tasks/{task_id}")
async def task_websocket(
    websocket: WebSocket,
    task_id: str,
    token: str | None = Query(default=None),
) -> None:
    user_id = await _authenticate_ws(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Ownership check â users can only watch their own tasks.
    async with async_session_factory() as db:
        task = await db.get(Task, task_id)
        if not task or task.user_id != user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()
    logger.info("WebSocket connected", task_id=task_id, user_id=user_id)

    try:
        async for event in subscribe_to_task_updates(task_id):
            await websocket.send_json(event)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", task_id=task_id)
    except Exception as exc:
        logger.exception("WebSocket error", task_id=task_id, error=str(exc))
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except RuntimeError:
            pass
