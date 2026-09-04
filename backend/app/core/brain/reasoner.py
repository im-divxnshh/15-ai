"""Reasoner — the thinking pass before answering."""
from __future__ import annotations

from app.core.brain.llm_router import llm_router
from app.core.brain.models import Plan, Reasoning
from app.core.brain.prompts import REASON_PROMPT


class Reasoner:
    async def reason(
        self,
        text: str,
        plan: Plan | None,
        tool_results: list[dict] | None = None,
        memory_context: str = "",
    ) -> Reasoning:
        parts = [f"User message: {text}"]
        if plan:
            parts.append(f"Plan: {plan.model_dump_json()}")
        if tool_results:
            parts.append(f"Tool results: {tool_results}")
        if memory_context:
            parts.append(f"Memory context: {memory_context}")

        data = await llm_router.chat_json(
            [
                {"role": "system", "content": REASON_PROMPT},
                {"role": "user", "content": "\n\n".join(parts)},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        return Reasoning(
            thinking=data.get("thinking", ""),
            key_points=data.get("key_points", []) or [],
            risks=data.get("risks", []) or [],
        )


reasoner = Reasoner()
