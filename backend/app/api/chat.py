"""Chat API — talk to the office."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.security.security import audit
from app.services.tools.registry import tool_registry
from app.core.runtime.orchestrator import orchestrator

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    text: str
    agent: str | None = None  # talk directly to one agent


class ChatResponse(BaseModel):
    reply: str
    agent: str
    intent: str
    tools_used: list[str]
    memory_used: list[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    response = await orchestrator.chat(req.text, direct_agent=req.agent)
    audit.log("user", "chat", {"agent": response.agent, "intent": response.intent.value})
    return ChatResponse(
        reply=response.text,
        agent=response.agent,
        intent=response.intent.value,
        tools_used=[t.get("tool", "") for t in response.tool_results],
        memory_used=response.memory_used,
    )


@router.get("/tools")
async def tools() -> dict:
    return {"tools": tool_registry.available()}
