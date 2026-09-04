"""Voice Engine (M04).

STT: Groq Whisper API (free tier) — handles Hindi + English + Hinglish beautifully.
TTS: done client-side with the browser's Web Speech API (free, supports hi-IN).
Wake word: browser-side (Web Speech recognition of "hey jarvis") — no paid service.

If no GROQ_API_KEY is set, STT returns a helpful error and the frontend
falls back to the browser's built-in Web Speech recognition.
"""
from __future__ import annotations

import logging

import httpx

from app.config.settings import settings

log = logging.getLogger("voice.stt")

GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
STT_MODEL = "whisper-large-v3-turbo"


async def transcribe(audio_bytes: bytes, filename: str = "audio.webm", language: str | None = None) -> dict:
    """Transcribe speech → text via Groq Whisper. Auto-detects Hindi/English mix."""
    if not settings.groq_api_key:
        return {
            "error": "groq_key_missing",
            "message": "GROQ_API_KEY nahi hai .env mein — browser STT use kar rahe hain.",
        }
    files = {"file": (filename, audio_bytes)}
    data = {"model": STT_MODEL, "response_format": "json"}
    if language:
        data["language"] = language
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            GROQ_STT_URL, headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            files=files, data=data,
        )
        r.raise_for_status()
        return {"text": r.json().get("text", "")}
