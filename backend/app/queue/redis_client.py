"""Pub/sub for real-time agent events.

Upstash Redis is REST-based and has no native pub/sub, so we use an
in-process asyncio broker as the WebSocket transport (agent pipeline and
WebSocket handler share the FastAPI process). Events are additionally
persisted to a Redis Stream per task for audit and replay.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from upstash_redis.asyncio import Redis

from app.core.config import settings

logger = structlog.get_logger()

TASK_CHANNEL_PREFIX = "task:updates:"
STREAM_MAX_LEN = 1000
TERMINAL_EVENTS: frozenset[str] = frozenset({"task_complete", "task_failed"})

_redis_client: Redis | None = None


def get_redis() -> Redis:
    """Lazy-create the Upstash REST client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis(
            url=settings.UPSTASH_REDIS_REST_URL,
            token=settings.UPSTASH_REDIS_REST_TOKEN,
        )
    return _redis_client


# --------------------------------------------------------------------------
# In-process broker: one asyncio.Queue per subscriber, indexed by task_id.
# --------------------------------------------------------------------------
class _Broker:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = (
            defaultdict(list)
        )
        self._lock = asyncio.Lock()

    async def publish(self, task_id: str, message: dict[str, Any]) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(task_id, []))
        for q in queues:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                logger.warning("Subscriber queue full, dropping event", task_id=task_id)

    async def subscribe(self, task_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers[task_id].append(q)
        return q

    async def unsubscribe(
        self, task_id: str, q: asyncio.Queue[dict[str, Any]]
    ) -> None:
        async with self._lock:
            if task_id in self._subscribers:
                try:
                    self._subscribers[task_id].remove(q)
                except ValueError:
                    pass
                if not self._subscribers[task_id]:
                    del self._subscribers[task_id]


_broker = _Broker()


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
async def publish_task_update(task_id: str, message: dict[str, Any]) -> None:
    """Broadcast an agent event to all WebSocket subscribers for a task.

    Also persists to a Redis Stream for audit; Redis failures are logged
    but never raised, so the agent pipeline is not blocked by infra issues.
    """
    await _broker.publish(task_id, message)
    try:
        stream_key = f"{TASK_CHANNEL_PREFIX}{task_id}"
        await get_redis().xadd(
            stream_key,
            {"payload": json.dumps(message)},
            maxlen=STREAM_MAX_LEN,
            approximate=True,
        )
    except Exception as exc:  # pragma: no cover â best-effort persistence
        logger.warning(
            "Failed to persist task event to Redis stream",
            task_id=task_id,
            error=str(exc),
        )


async def subscribe_to_task_updates(
    task_id: str,
) -> AsyncGenerator[dict[str, Any], None]:
    """Async generator yielding agent events for a task until terminal event."""
    queue = await _broker.subscribe(task_id)
    try:
        while True:
            message = await queue.get()
            yield message
            if message.get("type") in TERMINAL_EVENTS:
                break
    finally:
        await _broker.unsubscribe(task_id, queue)


async def close_redis() -> None:
    """Release the Upstash HTTP client on shutdown."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.close()
        except Exception:  # pragma: no cover
            pass
        _redis_client = None
