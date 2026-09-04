"""Agents API — the office roster + live status."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.registry import registry

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("")
async def list_agents() -> dict:
    return {"agents": registry.all_agents()}


@router.get("/capabilities")
async def capabilities() -> dict:
    return {"capabilities": registry.capabilities()}


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    agents = {a["id"]: a for a in registry.all_agents()}
    if agent_id not in agents:
        raise HTTPException(404, f"agent '{agent_id}' not found")
    return agents[agent_id]
