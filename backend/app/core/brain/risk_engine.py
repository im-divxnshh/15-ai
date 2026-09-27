"""Risk Engine — scores planned actions; high risk => needs user approval."""
from __future__ import annotations

import re

from app.core.brain.models import Plan, RiskAssessment

# Actions that are ALWAYS considered risky (regex on the action text).
_DANGER_PATTERNS = [
    (r"\b(delete|remove|drop|erase|format|wipe)\b", 70),
    (r"\b(deploy|publish|release|push)\b", 45),
    (r"\b(send|email|mail|post|tweet)\b", 40),
    (r"\b(buy|purchase|pay|spend|invest|transfer)\b", 60),
    (r"\b(password|credential|secret|token|api[_ ]?key)\b", 80),
    (r"\b(uninstall|reset|restart|shutdown|kill)\b", 55),
]

_SAFE_WORDS = re.compile(r"\b(status|show|list|read|search|find|check|summar|explain|remind|note|journal)\b")


class RiskEngine:
    async def assess(self, plan: Plan) -> RiskAssessment:
        if not plan.steps:
            return RiskAssessment()

        # Fast path: purely informational actions never need approval.
        all_text = " ".join(s.action.lower() for s in plan.steps)
        if _SAFE_WORDS.search(all_text) and not any(
            p for p, _ in _DANGER_PATTERNS if p.search(all_text)
        ):
            return RiskAssessment(score=0, level="safe", needs_approval=False)

        score = 0
        reasons: list[str] = []
        for s in plan.steps:
            text = f"{s.action} {s.tool or ''}".lower()
            for pattern, pts in _DANGER_PATTERNS:
                if re.search(pattern, text):
                    score = max(score, pts)
                    reasons.append(f"step {s.step}: risky action '{s.action[:60]}'")
            if s.needs_approval:
                score = max(score, 50)
                reasons.append(f"step {s.step}: planner flagged approval")

        level = "safe" if score < 20 else "low" if score < 40 else "medium" if score < 70 else "high"
        return RiskAssessment(
            score=score,
            level=level,
            reasons=reasons,
            needs_approval=score >= 40,
        )


risk_engine = RiskEngine()
