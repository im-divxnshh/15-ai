"""Legacy local hashing vectors; no remote embedding provider.

The active NOVA runtime uses durable keyword recall in runtime/repository.py.
These compatibility vectors are lexical, not semantic embeddings.
"""
from __future__ import annotations
import hashlib
import math
import re
LOCAL_DIM = 512
_WORD_RE = re.compile(r"[a-zA-Zऀ-ॿ]{2,}")

class Embeddings:
    provider = "local"
    @property
    def dim(self): return LOCAL_DIM
    async def embed(self, text): return self._embed_local(text.strip() or " ")
    async def embed_many(self, texts): return [self._embed_local(t) for t in texts]

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
