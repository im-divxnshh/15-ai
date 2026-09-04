"""Analytics API — office-wide stats for the dashboard."""
from __future__ import annotations

from fastapi import APIRouter

from app.core.memory.manager import memory
from app.core.memory.store import store
from app.core.registry import registry
from app.core.runtime.task_queue import task_queue
from app.core.security.security import audit

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("")
async def analytics() -> dict:
    tasks = store.list("tasks", limit=1000)
    runtime = store.list("runtime_tasks", limit=1000)
    agents = registry.all_agents()
    mem_stats = await memory.stats()

    by_state = {}
    for t in runtime:
        by_state[t.get("state", "queued")] = by_state.get(t.get("state", "queued"), 0) + 1

    return {
        "user_tasks": {"total": len(tasks), "done": sum(1 for t in tasks if t.get("status") == "done")},
        "agent_tasks": {"total": len(runtime), "by_state": by_state},
        "agents": {"count": len(agents), "working": sum(1 for a in agents if a["state"] == "working")},
        "memory": mem_stats,
        "queue": task_queue.stats(),
        "audit_entries": len(audit.recent(limit=1000)),
    }


@router.get("/audit")
async def audit_log(limit: int = 50) -> dict:
    return {"entries": audit.recent(limit=limit)}
