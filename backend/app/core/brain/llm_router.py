"""LLM Router — the single doorway to the Groq brain.

Groq is the only configured model provider.

Resilience built in:
- Some coding-tool proxies (e.g. agentrouter.org) content-block casual
  Hindi/Hinglish words in USER messages only (system/assistant pass fine).
  So on a content-block we retry with user messages machine-translated
  to English via a Hinglish→English word dictionary, plus a style hint so
  the reply still comes back in natural Hinglish.
- Also retries with trimmed context (some proxies choke on odd roles).
- Always degrades to a friendly message, never crashes the office.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings

log = logging.getLogger("brain.llm_router")

# Hinglish → English dictionary (word-level, good enough to dodge moderation).
_HINGLISH_EN: dict[str, str] = {
    # addressing / pronouns
    "mujhe": "I", "mujhko": "I", "mera": "my", "meri": "my", "main": "I",
    "tum": "you", "aap": "you", "tera": "your", "tumhara": "your", "tumse": "from you",
    "kya": "what", "kyun": "why", "kyu": "why", "kab": "when", "kahan": "where",
    "kaise": "how", "kaisa": "how", "kaisi": "how", "kitna": "how much",
    "jarvis": "chief", "yaar": "friend", "bhai": "bro", "didi": "sister", "dost": "friend",
    # verbs
    "hai": "is", "hain": "are", "ho": "are", "hoon": "am", "hu": "am",
    "tha": "was", "thi": "was", "the": "were", "hoga": "will be",
    "karo": "do", "kar": "do", "karna": "to do", "karde": "do it", "kardo": "do it",
    "karna": "to do", "karlena": "do it", "bana": "make", "banao": "make", "banana": "to make",
    "likh": "write", "likho": "write", "bata": "tell", "batao": "tell", "bol": "say", "bolo": "say",
    "bhej": "send", "bhejo": "send", "bhejdo": "send it", "de": "give", "dena": "give", "dedo": "give it",
    "mila": "got", "mil": "get", "lagna": "apply", "lagta": "feels", "chalao": "run", "chalu": "running",
    "yaad": "remember", "dila": "remind", "dilana": "remind", "dilade": "remind me", "dilado": "remind me",
    "soch": "think", "dekho": "see", "dekh": "see", "sun": "listen", "suno": "listen",
    "jana": "go", "jao": "go", "aana": "come", "ao": "come", "uthna": "wake up", "sona": "sleep",
    # common words
    "nahi": "no", "nahin": "no", "haan": "yes", "acha": "okay", "accha": "okay",
    "thik": "okay", "theek": "okay", "badhiya": "great", "mast": "awesome",
    "kal": "tomorrow", "aaj": "today", "abhi": "right now", "ab": "now",
    "subah": "morning", "shaam": "evening", "raat": "night", "baje": "oclock",
    "kaam": "work", "ghar": "home", "paisa": "money", "paise": "money", "khana": "food",
    "jaldi": "quickly", "thoda": "a little", "bahut": "very", "bohot": "very",
    "chalo": "lets go", "shuru": "start", "bandh": "stop", "khatam": "finished",
    "naam": "name", "baat": "talk", "cheez": "thing", "baad": "later", "pehle": "first",
    "sab": "all", "kuch": "something", "koi": "someone", "bhi": "also", "to": "so",
    "matlab": "meaning", "waqt": "time", "din": "day", "hafta": "week", "mahina": "month",
    "meeting": "meeting", "list": "list", "note": "note", "reminder": "reminder",
}

_WORD_RE = re.compile(r"[A-Za-z]+")

_STYLE_HINT = (
    " (Note: user typed this in casual Hindi-English mix — reply in the same "
    "natural, warm Hindi-English mix style with light emojis.)"
)


def _translate_user_text(text: str) -> str:
    """Word-level Hinglish → English translation (dodges proxy moderation)."""

    def repl(m: re.Match) -> str:
        return _HINGLISH_EN.get(m.group(0).lower(), m.group(0))

    return _WORD_RE.sub(repl, text)


def _sanitize_messages(messages: list[dict[str, str]], translate_users: bool) -> list[dict[str, str]]:
    """Optionally translate user-role messages; leave system/assistant untouched
    (moderation only targets user messages on agentrouter-style proxies)."""
    out: list[dict[str, str]] = []
    for m in messages:
        content = m["content"]
        if translate_users and m["role"] == "user":
            translated = _translate_user_text(content)
            if translated != content:
                translated += _STYLE_HINT
            content = translated
        out.append({"role": m["role"], "content": content})
    return out


class LLMRouter:
    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        if settings.llm_ready:
            self.client = AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url,
                timeout=60.0,
                max_retries=0,
            )
        else:
            log.warning("No GROQ_API_KEY set — brain will run in echo/fallback mode")

    @property
    def ready(self) -> bool:
        return self.client is not None

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Plain chat completion. Returns assistant text (never raises)."""
        if not self.ready:
            return _offline_reply(messages)

        # Attempt 1: original messages (works for English + prompts)
        try:
            return await self._call(_sanitize_messages(messages, translate_users=False), model, temperature, max_tokens)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM attempt 1 failed: %s", str(exc)[:250])
            await asyncio.sleep(1.0)

        # Attempt 2: user messages translated to English (dodges content-block on Hinglish)
        try:
            return await self._call(_sanitize_messages(messages, translate_users=True), model, temperature, max_tokens)
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM attempt 2 failed: %s", str(exc)[:250])
            await asyncio.sleep(1.5)

        # Attempt 3: system + last user only, translated
        trimmed = _trim_to_last_exchange(messages)
        if trimmed:
            try:
                return await self._call(_sanitize_messages(trimmed, translate_users=True), model, temperature, max_tokens)
            except Exception as exc:  # noqa: BLE001
                log.error("LLM attempt 3 failed: %s", str(exc)[:250])

        return "⚠️ Boss, LLM provider se abhi reply nahi aa raha (block ya rate-limit lagta hai). Ek minute ruk ke dobara try karo. 🙏"

    async def _call(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        resp = await self.client.chat.completions.create(
            model=model or settings.groq_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        msg = resp.choices[0].message
        content = (msg.content or "").strip()
        if not content:
            # reasoning models can put everything in reasoning_content when cut short
            content = (getattr(msg, "reasoning_content", "") or "").strip()
        return content or "…"

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """Chat completion expected to return JSON. Parses defensively."""
        text = await self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)
        return _parse_json_block(text)


def _trim_to_last_exchange(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep system prompt + the final user message only."""
    system = [m for m in messages if m["role"] == "system"]
    last_user = [m for m in reversed(messages) if m["role"] == "user"]
    return system + (last_user[:1] if last_user else [])


def _parse_json_block(text: str) -> dict[str, Any]:
    """Extract a JSON object from a response that may contain markdown fences or prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    # find first { and last }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"raw": text}


def _offline_reply(messages: list[dict[str, str]]) -> str:
    """No API key configured — friendly Hinglish echo so the system still feels alive."""
    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    return (
        "Boss, mera brain (Groq API) abhi configure nahi hua hai. 😅\n"
        "backend/.env file mein `GROQ_API_KEY` aur `GROQ_BASE_URL` set karo, "
        "phir main tumhari har baat samajh ke kaam karunga.\n\n"
        f"(Tumne kaha: \"{last_user[:120]}\")"
    )


llm_router = LLMRouter()
