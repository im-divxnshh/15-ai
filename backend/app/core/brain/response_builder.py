"""Response Builder — composes the final human reply from everything the brain knows."""
from __future__ import annotations

from app.core.brain.llm_router import llm_router
from app.core.brain.models import Classification, Plan, Reasoning
from app.core.brain.prompts import ANSWER_PROMPT, system_prompt

JARVIS_PROMPT = """You are JARVIS — the master orchestrator of the 15-AI office.
Elite, calm, strategic — but with warmth. You talk to the user like a trusted chief-of-staff
who is also a friend. You know every agent in your office and what they're working on."""


class ResponseBuilder:
    async def build(
        self,
        text: str,
        classification: Classification,
        plan: Plan | None = None,
        reasoning: Reasoning | None = None,
        tool_results: list[dict] | None = None,
        memory_context: str = "",
        history: list[dict] | None = None,
        agent_name: str = "JARVIS",
        agent_prompt: str = JARVIS_PROMPT,
    ) -> str:
        parts = [f"User message: {text}"]
        if reasoning:
            parts.append(f"Reasoning: {reasoning.model_dump_json()}")
        if plan and plan.steps:
            parts.append(f"Plan: {plan.model_dump_json()}")
        if tool_results:
            parts.append(f"Tool results (use these as facts): {tool_results}")
        if memory_context:
            parts.append(f"Memory context: {memory_context}")

        messages: list[dict] = [
            {"role": "system", "content": system_prompt(agent_name, agent_prompt) + "\n\n" + ANSWER_PROMPT},
        ]
        if history:
            messages.extend(history[-8:])
        messages.append({"role": "user", "content": "\n\n".join(parts)})

        return await llm_router.chat(messages, temperature=0.75)


response_builder = ResponseBuilder()
