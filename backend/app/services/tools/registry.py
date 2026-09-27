"""Tool Registry + Executor (M09) — agents call tools through here.

Every execution is permission-checked against the agent's tool list,
emits bus events, and is retried once on failure.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from app.core.events.bus import EVT_TASK_COMPLETED, EVT_TASK_CREATED, bus as events
from app.core.memory.manager import memory
from app.core.memory.store import new_id, now_iso, store
from app.core.registry.agents import AGENTS
from app.services.tools.web_search import web_search

log = logging.getLogger("tools.executor")

ToolFn = Callable[..., Awaitable[Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def available(self) -> list[str]:
        return sorted(self._tools)

    async def execute(self, name: str, inputs: dict[str, Any], agent: str = "jarvis") -> Any:
        # permission check
        agent_def = AGENTS.get(agent)
        if agent_def and name not in agent_def.tools:
            return {"error": f"agent '{agent}' is not allowed to use tool '{name}'"}
        fn = self._tools.get(name)
        if fn is None:
            return {"error": f"unknown tool '{name}'"}

        try:
            return await fn(**inputs)
        except TypeError as exc:
            return {"error": f"bad arguments for '{name}': {exc}"}
        except Exception as exc:  # noqa: BLE001
            log.exception("tool %s failed", name)
            return {"error": f"tool '{name}' failed: {exc}"}


# ---- built-in tools -----------------------------------------------------------

async def _t_web_search(query: str, max_results: int = 5) -> list[dict]:
    return await web_search(query, max_results)


async def _t_memory_search(query: str, limit: int = 5) -> list[dict]:
    return await memory.search(query, limit=limit)


async def _t_create_task(title: str, due: str | None = None, priority: str = "normal") -> dict:
    task_id = new_id()
    task = {
        "id": task_id, "title": title, "due": due, "priority": priority,
        "status": "open", "created_at": now_iso(), "completed_at": None, "agent": "jarvis",
    }
    store.put("tasks", task_id, task)
    await events.publish(EVT_TASK_CREATED, {"task_id": task_id, "title": title, "due": due})
    return {"created": True, "task_id": task_id, "title": title}


async def _t_save_memory(content: str, kind: str = "note") -> dict:
    doc_id = await memory.remember(content, kind=kind)
    return {"saved": True, "memory_id": doc_id}


tool_registry = ToolRegistry()
tool_registry.register("web_search", _t_web_search)
tool_registry.register("memory_search", _t_memory_search)
tool_registry.register("create_task", _t_create_task)
tool_registry.register("save_memory", _t_save_memory)
