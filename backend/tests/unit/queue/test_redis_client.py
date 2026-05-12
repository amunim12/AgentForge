"""Unit tests for the in-process event broker and publish_task_update."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.queue.redis_client import (
    TERMINAL_EVENTS,
    _Broker,
    publish_task_update,
    subscribe_to_task_updates,
)


# ---------------------------------------------------------------------------
# _Broker unit tests
# ---------------------------------------------------------------------------
class TestBroker:
    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(self) -> None:
        broker = _Broker()
        q = await broker.subscribe("task-1")
        await broker.publish("task-1", {"type": "agent_start"})

        msg = q.get_nowait()
        assert msg == {"type": "agent_start"}

    @pytest.mark.asyncio
    async def test_publish_delivers_to_multiple_subscribers(self) -> None:
        broker = _Broker()
        q1 = await broker.subscribe("task-2")
        q2 = await broker.subscribe("task-2")

        await broker.publish("task-2", {"type": "ping"})

        assert q1.get_nowait() == {"type": "ping"}
        assert q2.get_nowait() == {"type": "ping"}

    @pytest.mark.asyncio
    async def test_publish_does_not_deliver_to_different_task(self) -> None:
        broker = _Broker()
        q = await broker.subscribe("task-A")
        await broker.publish("task-B", {"type": "other"})

        assert q.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self) -> None:
        broker = _Broker()
        q = await broker.subscribe("task-3")
        await broker.unsubscribe("task-3", q)

        # After unsubscribe, publishing should not deliver to the old queue.
        await broker.publish("task-3", {"type": "late"})
        assert q.empty()

    @pytest.mark.asyncio
    async def test_unsubscribe_cleans_up_empty_task_entry(self) -> None:
        broker = _Broker()
        q = await broker.subscribe("task-4")
        await broker.unsubscribe("task-4", q)

        # Internal dict should not hold an empty list for the task key.
        async with broker._lock:
            assert "task-4" not in broker._subscribers

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_queue_is_safe(self) -> None:
        broker = _Broker()
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        # Unsubscribing a queue that was never subscribed must not raise.
        await broker.unsubscribe("task-X", q)

    @pytest.mark.asyncio
    async def test_queue_full_drops_event_gracefully(self) -> None:
        broker = _Broker()
        # Subscribe with a queue of capacity 1, then overflow it.
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1)
        async with broker._lock:
            broker._subscribers["task-5"].append(q)

        await broker.publish("task-5", {"type": "first"})
        # Second publish should not raise; the event is silently dropped.
        await broker.publish("task-5", {"type": "dropped"})

        assert q.get_nowait() == {"type": "first"}
        assert q.empty()


# ---------------------------------------------------------------------------
# subscribe_to_task_updates — terminal event exits the generator
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_subscribe_yields_events_until_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.queue import redis_client as rc_module

    broker = _Broker()
    monkeypatch.setattr(rc_module, "_broker", broker)

    events_to_send = [
        {"type": "agent_start", "agent": "planner"},
        {"type": "agent_done", "agent": "planner"},
        {"type": "task_complete", "result": "done", "score": 0.9},
    ]

    async def _feed() -> None:
        await asyncio.sleep(0)  # yield to let the generator subscribe first
        for evt in events_to_send:
            await broker.publish("task-gen", evt)

    received: list[dict[str, Any]] = []

    async def _collect() -> None:
        async for event in subscribe_to_task_updates("task-gen"):
            received.append(event)

    await asyncio.gather(_feed(), _collect())

    assert len(received) == 3
    assert received[-1]["type"] == "task_complete"


@pytest.mark.asyncio
async def test_subscribe_stops_at_task_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.queue import redis_client as rc_module

    broker = _Broker()
    monkeypatch.setattr(rc_module, "_broker", broker)

    async def _feed() -> None:
        await asyncio.sleep(0)
        await broker.publish("task-fail", {"type": "agent_start", "agent": "planner"})
        await broker.publish("task-fail", {"type": "task_failed", "error": "oops"})
        # This event arrives after terminal — generator should have exited.
        await broker.publish("task-fail", {"type": "should_not_arrive"})

    received: list[dict[str, Any]] = []

    async def _collect() -> None:
        async for event in subscribe_to_task_updates("task-fail"):
            received.append(event)

    await asyncio.gather(_feed(), _collect())

    assert len(received) == 2
    assert received[-1]["type"] == "task_failed"
    assert not any(e["type"] == "should_not_arrive" for e in received)


@pytest.mark.asyncio
async def test_subscribe_unregisters_queue_on_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.queue import redis_client as rc_module

    broker = _Broker()
    monkeypatch.setattr(rc_module, "_broker", broker)

    async def _feed() -> None:
        await asyncio.sleep(0)
        await broker.publish("task-cleanup", {"type": "task_complete"})

    await asyncio.gather(_feed(), _exhaust("task-cleanup"))

    # After the generator exits, the subscriber entry should be gone.
    async with broker._lock:
        assert "task-cleanup" not in broker._subscribers


async def _exhaust(task_id: str) -> None:
    async for _ in subscribe_to_task_updates(task_id):
        pass


# ---------------------------------------------------------------------------
# Terminal events constant
# ---------------------------------------------------------------------------
def test_terminal_events_contains_expected_types() -> None:
    assert "task_complete" in TERMINAL_EVENTS
    assert "task_failed" in TERMINAL_EVENTS
    assert "agent_start" not in TERMINAL_EVENTS
    assert "agent_done" not in TERMINAL_EVENTS


# ---------------------------------------------------------------------------
# publish_task_update — Redis persistence is best-effort; broker always receives
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_publish_task_update_delivers_to_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.queue import redis_client as rc_module

    broker = _Broker()
    monkeypatch.setattr(rc_module, "_broker", broker)

    # Stub Redis so xadd is a no-op.
    fake_redis = AsyncMock()
    fake_redis.xadd = AsyncMock(return_value="0-0")
    monkeypatch.setattr(rc_module, "_redis_client", fake_redis)

    q = await broker.subscribe("task-pub")
    await publish_task_update("task-pub", {"type": "agent_start", "agent": "planner"})

    msg = q.get_nowait()
    assert msg["type"] == "agent_start"


@pytest.mark.asyncio
async def test_publish_task_update_continues_when_redis_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis failure must not prevent the broker from receiving the event."""
    from app.queue import redis_client as rc_module

    broker = _Broker()
    monkeypatch.setattr(rc_module, "_broker", broker)

    fake_redis = MagicMock()
    fake_redis.xadd = MagicMock(side_effect=RuntimeError("connection refused"))
    monkeypatch.setattr(rc_module, "_redis_client", fake_redis)

    q = await broker.subscribe("task-redis-fail")

    # publish_task_update calls get_redis() which returns _redis_client; the
    # xadd call is awaited in a try/except that swallows the error.
    # The broker.publish happens first regardless.
    try:
        await publish_task_update("task-redis-fail", {"type": "event"})
    except Exception:
        pass  # Redis error is swallowed; what matters is the broker received it.

    assert not q.empty()
