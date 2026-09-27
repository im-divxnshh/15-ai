"""Embeddings — GLM (OpenAI-compatible) or a zero-dependency local fallback.

The local fallback is a hashing bag-of-words vector. It's not semantic,
but it keeps memory search 100% free and functional with zero API keys.
If the GLM provider errors, we permanently switch to local at runtime.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re

from openai import AsyncOpenAI

from app.config.settings import settings

log = logging.getLogger("memory.embeddings")

LOCAL_DIM = 512
_WORD_RE = re.compile(r"[a-zA-Zऀ-ॿ]{2,}")


class Embeddings:
    def __init__(self) -> None:
        self.provider = settings.embeddings_provider
        if self.provider == "glm" and not settings.llm_ready:
            self.provider = "local"
        if self.provider == "glm":
            self._client = AsyncOpenAI(api_key=settings.glm_api_key, base_url=settings.glm_base_url)
        log.info("embeddings provider: %s", self.provider)

    def _fallback_to_local(self, reason: str) -> None:
        log.warning("embeddings: glm failed (%s) — switching to local provider permanently", reason)
        self.provider = "local"

    @property
    def dim(self) -> int:
        if self.provider == "local":
            return LOCAL_DIM
        return -1  # unknown until first call; real dim returned by provider

    async def embed(self, text: str) -> list[float]:
        text = text.strip() or " "
        if self.provider == "glm":
            try:
                resp = await self._client.embeddings.create(model=settings.embeddings_model, input=[text])
                return resp.data[0].embedding
            except Exception as exc:  # noqa: BLE001
                self._fallback_to_local(str(exc)[:120])
        return self._embed_local(text)

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        if self.provider == "glm":
            try:
                resp = await self._client.embeddings.create(model=settings.embeddings_model, input=texts)
                return [d.embedding for d in resp.data]
            except Exception as exc:  # noqa: BLE001
                self._fallback_to_local(str(exc)[:120])
        return [self._embed_local(t) for t in texts]

    # -- local (free, zero-dependency) ---------------------------------------
    @staticmethod
    def _embed_local(text: str) -> list[float]:
        vec = [0.0] * LOCAL_DIM
        words = _WORD_RE.findall(text.lower())
        for w in words:
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            idx = h % LOCAL_DIM
            sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


embeddings = Embeddings()
