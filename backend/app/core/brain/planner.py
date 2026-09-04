"""Planner — turns a user goal into a short list of agent/tool steps."""
from __future__ import annotations

import logging

from app.core.brain.llm_router import llm_router
from app.core.brain.models import Classification, Plan, PlanStep
from app.core.brain.prompts import PLAN_PROMPT

log = logging.getLogger("brain.planner")


class Planner:
    async def plan(self, text: str, classification: Classification, context: str = "") -> Plan:
        if classification.intent in ("chat", "emotional"):
            return Plan(goal=text, steps=[], respond_directly=True)

        user_block = f"User message: {text}"
        if context:
            user_block += f"\n\nRelevant memory context:\n{context}"

        data = await llm_router.chat_json(
            [
                {"role": "system", "content": PLAN_PROMPT},
                {"role": "user", "content": user_block},
            ],
            temperature=0.1,
            max_tokens=600,
        )

        steps = []
        for s in data.get("steps", []) or []:
            try:
                steps.append(
                    PlanStep(
                        step=int(s.get("step", len(steps) + 1)),
                        agent=s.get("agent", "jarvis"),
                        action=s.get("action", ""),
                        tool=s.get("tool"),
                        tool_input=s.get("tool_input") or {},
                        needs_approval=bool(s.get("needs_approval", False)),
                    )
                )
            except Exception:  # noqa: BLE001
                continue

        return Plan(
            goal=data.get("goal", text),
            steps=steps,
            respond_directly=bool(data.get("respond_directly", not steps)),
        )


planner = Planner()
