"""Tasks API — the user's task list (reminders, to-dos)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.memory.store import new_id, now_iso, store

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskCreate(BaseModel):
    title: str
    due: str | None = None
    priority: str = "normal"


class TaskPatch(BaseModel):
    status: str | None = None  # open | done


@router.get("")
async def list_tasks(status: str | None = None, limit: int = 100) -> dict:
    tasks = store.list("tasks", limit=limit)
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return {"tasks": tasks}


@router.post("")
async def create_task(req: TaskCreate) -> dict:
    task_id = new_id()
    task = {"id": task_id, "title": req.title, "due": req.due,
            "priority": req.priority, "status": "open",
            "created_at": now_iso(), "completed_at": None}
    store.put("tasks", task_id, task)
    return task


@router.patch("/{task_id}")
async def update_task(task_id: str, req: TaskPatch) -> dict:
    task = store.get("tasks", task_id)
    if not task:
        raise HTTPException(404, "task not found")
    if req.status:
        task["status"] = req.status
        task["completed_at"] = now_iso() if req.status == "done" else None
    store.put("tasks", task_id, task)
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> dict:
    ok = store.delete("tasks", task_id)
    if not ok:
        raise HTTPException(404, "task not found")
    return {"deleted": True}


@router.get("/runtime")
async def runtime_tasks(limit: int = 50) -> dict:
    """Background agent tasks (from the runtime queue)."""
    return {"tasks": store.list("runtime_tasks", limit=limit)}
