"""Agent Registry (M15) — register, load, route, track capabilities."""
from __future__ import annotations

from typing import Any

from app.core.memory.store import new_id, now_iso, store
from app.core.registry.agents import AGENTS, AGENT_ORDER, Agent

# live agent status kept in the doc store so the UI sees it on reload
STATUS_COLLECTION = "agent_status"

_STATUS_TEMPLATE = {"state": "idle", "current_action": None, "tasks_done": 0, "updated_at": None}


def all_agents() -> list[dict[str, Any]]:
    """Serializable agent list for the UI (definition + live status)."""
    statuses = {s["id"]: s for s in store.list(STATUS_COLLECTION, limit=100)}
    out = []
    for agent_id in AGENT_ORDER:
        a: Agent = AGENTS[agent_id]
        status = statuses.get(agent_id, {})
        out.append(
            {
                "id": a.id, "name": a.name, "role": a.role, "layer": a.layer,
                "emoji": a.emoji, "accent": a.accent, "desk": list(a.desk),
                "tools": a.tools,
                "state": status.get("state", "idle"),
                "current_action": status.get("current_action"),
                "tasks_done": status.get("tasks_done", 0),
            }
        )
    return out


def get_agent(agent_id: str) -> Agent | None:
    return AGENTS.get(agent_id)


def set_status(agent_id: str, state: str, action: str | None = None) -> None:
    if agent_id not in AGENTS:
        return
    doc = store.get(STATUS_COLLECTION, agent_id) or {"id": agent_id, **_STATUS_TEMPLATE, "tasks_done": 0}
    doc["id"] = agent_id
    doc["state"] = state
    doc["current_action"] = action
    doc["updated_at"] = now_iso()
    if state == "finished":
        doc["tasks_done"] = int(doc.get("tasks_done", 0)) + 1
        doc["state"] = "idle"
        doc["current_action"] = None
    store.put(STATUS_COLLECTION, agent_id, doc)


def route(query: str) -> str:
    """Keyword router — picks the best agent for a message (used for direct chat)."""
    q = query.lower()
    scores = {aid: 0 for aid in AGENTS}
    for aid, a in AGENTS.items():
        for kw in a.role.lower().replace("+", " ").split():
            if len(kw) > 3 and kw in q:
                scores[aid] += 2
        if a.name.lower() in q:
            scores[aid] += 10
    scores["jarvis"] += 1  # default winner
    return max(scores, key=scores.get)


def capabilities() -> dict[str, list[str]]:
    return {aid: AGENTS[aid].tools for aid in AGENT_ORDER}
