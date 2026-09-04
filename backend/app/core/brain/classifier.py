"""Classifier — what does the user want, in which language, how urgent?"""
from __future__ import annotations

import logging

from app.core.brain.llm_router import llm_router
from app.core.brain.models import Classification, Intent, Priority
from app.core.brain.prompts import CLASSIFY_PROMPT

log = logging.getLogger("brain.classifier")

# Cheap keyword pre-filter — skips an LLM call for obvious cases.
_HINGLISH_WORDS = {
    "kya", "kaise", "kaisa", "hai", "hain", "nahi", "nahin", "haan", "yaar", "bhai",
    "kar", "karo", "karna", "karde", "mera", "meri", "tum", "aap", "mujhe", "bata",
    "batao", "acha", "thik", "theek", "chalo", "matlab", "bhai", "didi", "boss",
}
_TASK_WORDS = {
    "remind", "reminder", "schedule", "book", "create", "make", "build", "write",
    "research", "find", "search", "prepare", "plan", "setup", "set up", "send",
    "yaad", "dila", "bana", "likh", "dhundh", "kraudh", "cron", "automate",
}


def quick_classify(text: str) -> Classification | None:
    t = text.lower().strip()
    if not t:
        return None
    words = set(t.split())
    hinglish_hits = len(words & _HINGLISH_WORDS)
    task_hits = sum(1 for w in _TASK_WORDS if w in t)
    language = "hinglish" if hinglish_hits and any(c.isascii() for c in t) else ("hindi" if hinglish_hits else "english")
    if task_hits >= 1 and len(t.split()) > 2:
        return Classification(intent=Intent.TASK, language=language, urgency=Priority.NORMAL, confidence=0.6)
    return None


class Classifier:
    async def classify(self, text: str) -> Classification:
        quick = quick_classify(text)
        if quick and quick.confidence >= 0.6 and len(text) < 25:
            return quick

        data = await llm_router.chat_json(
            [
                {"role": "system", "content": CLASSIFY_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=200,
        )
        try:
            return Classification(
                intent=Intent(data.get("intent", "chat")),
                language=data.get("language", "english"),
                sentiment=data.get("sentiment", "neutral"),
                urgency=Priority(int(data.get("urgency", 1))),
                confidence=float(data.get("confidence", 0.7)),
            )
        except Exception:  # noqa: BLE001
            log.exception("classifier parse failed, falling back")
            return quick or Classification(language="english")


classifier = Classifier()
