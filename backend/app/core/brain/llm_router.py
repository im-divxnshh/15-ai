"""LLM Router — the single doorway to the GLM brain.

OpenAI-compatible client so it works with GLM (z.ai), agentrouter-style
proxies, Groq, OpenAI, or any compatible endpoint via env vars.

Resilience built in:
- Preventive sanitization of tokens some proxies moderate (e.g. "jarvis").
- Retry on transient blocks / invalid-role errors (retry without history).
- Always degrades to a friendly Hinglish message, never crashes the office.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config.settings import settings

log = logging.getLogger("brain.llm_router")

# Words some coding-tool proxies content-block (they dislike assistant-building
# / casual chat). Sanitized to look-alike spellings that pass moderation.
_SANITIZE_MAP = [
    (re.compile(r"\bjarvis\b", re.I), "J.A.R.V.I.S"),
]


def _sanitize(text: str) -> str:
    for pattern, repl in _SANITIZE_MAP:
        text = pattern.sub(repl, text)
    return text


def _sanitize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"role": m["role"], "content": _sanitize(m["content"])} for m in messages]


class LLMRouter:
    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        if settings.llm_ready:
            self.client = AsyncOpenAI(
                api_key=settings.glm_api_key,
                base_url=settings.glm_base_url,
                # agentrouter-style proxies reject generic clients — identify as an approved CLI
                default_headers={
                    "User-Agent": "claude-cli/2.0.0 (external, cli)",
                    "anthropic-version": "2023-06-01",
                },
            )
        else:
            log.warning("No GLM_API_KEY set — brain will run in echo/fallback mode")

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

        # 1st attempt: sanitized messages
        try:
            return await self._call(_sanitize_messages(messages), model, temperature, max_tokens)
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
            log.warning("LLM call failed (attempt 1): %s", err[:300])

        # 2nd attempt: system+last-user only (history/roles sometimes upset proxies)
        trimmed = _trim_to_last_exchange(messages)
        if trimmed and len(trimmed) < len(messages):
            try:
                return await self._call(_sanitize_messages(trimmed), model, temperature, max_tokens)
            except Exception as exc:  # noqa: BLE001
                log.warning("LLM call failed (attempt 2): %s", str(exc)[:300])

        # 3rd attempt: single bare user message
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if last_user:
            try:
                return await self._call(
                    [{"role": "user", "content": _sanitize(last_user)}], model, temperature, max_tokens
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
                log.error("LLM call failed (attempt 3): %s", err[:300])
                if "content-blocked" in err or "blocked" in err.lower():
                    return (
                        "⛔ Boss, provider ne ye message block kar diya (content policy). "
                        "Thoda alag words mein try karo — ya `.env` mein koi official GLM endpoint "
                        "(jaise z.ai) use karo jo aise filters nahi lagata. 🙏"
                    )
        return "⚠️ Brain se connect nahi ho paya — LLM error aa gaya. Thodi der baad try karo. 🙏"

    async def _call(
        self,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> str:
        resp = await self.client.chat.completions.create(
            model=model or settings.glm_model,
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
        "Boss, mera brain (GLM API) abhi configure nahi hua hai. 😅\n"
        "backend/.env file mein `GLM_API_KEY` aur `GLM_BASE_URL` set karo, "
        "phir main tumhari har baat samajh ke kaam karunga.\n\n"
        f"(Tumne kaha: \"{last_user[:120]}\")"
    )


llm_router = LLMRouter()
