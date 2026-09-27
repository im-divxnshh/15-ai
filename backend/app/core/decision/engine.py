"""Decision Engine (M13) — pros/cons + risk + score for any decision."""
from __future__ import annotations

from app.core.brain.llm_router import llm_router

DECISION_PROMPT = """You are the Decision Engine. Evaluate the decision and return ONLY JSON:
{
  "summary": "one-line verdict",
  "pros": ["..."],
  "cons": ["..."],
  "risks": ["..."],
  "score": 0-100,          // 100 = strongly recommended
  "recommendation": "go" | "no-go" | "maybe"
}
Be honest and practical. Indian-context aware (cost in rupees where relevant)."""


class DecisionEngine:
    async def evaluate(self, question: str, context: str = "") -> dict:
        user = f"Decision to evaluate: {question}"
        if context:
            user += f"\n\nContext:\n{context}"
        return await llm_router.chat_json(
            [{"role": "system", "content": DECISION_PROMPT}, {"role": "user", "content": user}],
            temperature=0.3,
            max_tokens=600,
        )


decision_engine = DecisionEngine()
