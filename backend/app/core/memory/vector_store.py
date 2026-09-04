"""Vector store — Neon Postgres + pgvector when configured, in-memory cosine otherwise."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.config.settings import settings
from app.core.memory.embeddings import embeddings

log = logging.getLogger("memory.vector")


class LocalVectorStore:
    """Zero-dependency fallback: keeps vectors in RAM (rebuilt from doc store on boot)."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def upsert(self, content: str, vector: list[float], meta: dict[str, Any]) -> str:
        item_id = meta.get("id") or str(uuid.uuid4())
        self.items = [i for i in self.items if i["id"] != item_id]
        self.items.append({"id": item_id, "content": content, "vector": vector, "meta": meta})
        return item_id

    async def search(self, query_vec: list[float], limit: int = 5, kind: str | None = None) -> list[dict[str, Any]]:
        scored = []
        for item in self.items:
            if kind and item["meta"].get("kind") != kind:
                continue
            score = _cosine(query_vec, item["vector"])
            if score > 0.05:
                scored.append({"id": item["id"], "content": item["content"], "meta": item["meta"], "score": round(score, 4)})
        scored.sort(key=lambda x: -x["score"])
        return scored[:limit]

    async def count(self) -> int:
        return len(self.items)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5 or 1.0
    nb = sum(y * y for y in b) ** 0.5 or 1.0
    return dot / (na * nb)


class NeonVectorStore:
    """Neon Postgres with pgvector. Created lazily on first use."""

    def __init__(self) -> None:
        self._pool = None
        self._dim: int | None = None

    async def _ensure(self) -> None:
        if self._pool is not None:
            return
        import asyncpg

        self._pool = await asyncpg.create_pool(settings.neon_url, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            # figure out real embedding dim from a probe vector
            probe = await embeddings.embed("dimension probe")
            self._dim = len(probe)
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    kind TEXT DEFAULT 'note',
                    agent TEXT DEFAULT 'jarvis',
                    embedding vector({self._dim}),
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS memories_embedding_idx ON memories USING ivfflat (embedding vector_cosine_ops)")
        log.info("Neon vector store ready (dim=%s)", self._dim)

    async def upsert(self, content: str, vector: list[float], meta: dict[str, Any]) -> str:
        await self._ensure()
        item_id = meta.get("id") or str(uuid.uuid4())
        vec_str = "[" + ",".join(str(v) for v in vector) + "]"
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memories (id, content, kind, agent, embedding, created_at)
                VALUES ($1, $2, $3, $4, $5::vector, $6)
                ON CONFLICT (id) DO UPDATE SET content = $2, embedding = $5::vector
                """,
                item_id, content, meta.get("kind", "note"), meta.get("agent", "jarvis"),
                vec_str, datetime.now(timezone.utc),
            )
        return item_id

    async def search(self, query_vec: list[float], limit: int = 5, kind: str | None = None) -> list[dict[str, Any]]:
        await self._ensure()
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, content, kind, agent, created_at,
                       1 - (embedding <=> $1::vector) AS score
                FROM memories
                WHERE ($2::text IS NULL OR kind = $2)
                ORDER BY embedding <=> $1::vector
                LIMIT $3
                """,
                vec_str, kind, limit,
            )
        return [
            {
                "id": r["id"], "content": r["content"], "score": round(float(r["score"]), 4),
                "meta": {"kind": r["kind"], "agent": r["agent"], "created_at": str(r["created_at"])},
            }
            for r in rows
        ]

    async def count(self) -> int:
        await self._ensure()
        async with self._pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM memories")


def get_vector_store():
    if settings.neon_ready:
        try:
            return NeonVectorStore()
        except Exception:  # noqa: BLE001
            log.exception("Neon init failed, falling back to local vectors")
    return LocalVectorStore()


vector_store = get_vector_store()
