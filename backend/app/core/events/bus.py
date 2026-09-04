"""Event Bus (M07) — in-process pub/sub + Socket.IO broadcast.

Every interesting thing that happens (task created, agent started,
memory saved...) is published here and pushed live to the 2D office UI.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("events.bus")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._sio_emit: Callable[..., Any] | None = None

    # -- Socket.IO wiring (set by main.py at startup) --
    def attach_socketio(self, emit: Callable[..., Any]) -> None:
        self._sio_emit = emit

    # -- pub/sub --
    def subscribe(self, event: str, handler: Callable[..., Any]) -> None:
        self._subs[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., Any]) -> None:
        if handler in self._subs[event]:
            self._subs[event].remove(handler)

    async def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        envelope = {"event": event, "data": payload, "ts": _now()}

        # local subscribers
        for handler in list(self._subs[event]):
            try:
                result = handler(payload)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                log.exception("event handler failed for %s", event)

        # push to connected UI clients
        if self._sio_emit is not None:
            try:
                result = self._sio_emit("office_event", envelope)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001
                log.exception("socket emit failed for %s", event)


# Canonical event names
EVT_TASK_CREATED = "TaskCreated"
EVT_TASK_COMPLETED = "TaskCompleted"
EVT_TASK_FAILED = "TaskFailed"
EVT_AGENT_STARTED = "AgentStarted"
EVT_AGENT_FINISHED = "AgentFinished"
EVT_AGENT_THINKING = "AgentThinking"
EVT_MEMORY_SAVED = "MemorySaved"
EVT_APPROVAL_REQUESTED = "ApprovalRequested"
EVT_APPROVAL_RESOLVED = "ApprovalResolved"
EVT_CHAT_MESSAGE = "ChatMessage"
EVT_SYSTEM = "SystemEvent"

bus = EventBus()
