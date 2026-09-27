"""Memory API — search / remember / stats."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.memory.manager import memory
from app.core.memory.store import store

router = APIRouter(prefix="/api/memory", tags=["memory"])


class RememberRequest(BaseModel):
    content: str
    kind: str = "note"


@router.get("/search")
async def search(q: str, limit: int = 10) -> dict:
    hits = await memory.search(q, limit=limit)
    return {"results": hits}


@router.post("/remember")
async def remember(req: RememberRequest) -> dict:
    doc_id = await memory.remember(req.content, kind=req.kind)
    return {"saved": True, "id": doc_id}


@router.get("/stats")
async def stats() -> dict:
    return await memory.stats()


@router.get("/facts")
async def facts() -> dict:
    return {"facts": memory.all_facts()}


@router.get("/history")
async def history(limit: int = 50) -> dict:
    return {"turns": store.list("conversations", limit=limit)}
