"""Memory Manager (M02) — the brain's one-stop memory facade.

Layers:
- Long-term memory    → vector store (Neon pgvector / local)  "remember everything"
- Conversation memory → doc store (Firestore / local JSON)    recent chat history
- Facts & profile     → doc store                             stable facts about the user
"""
from __future__ import annotations

import logging

from app.core.events.bus import EVT_MEMORY_SAVED, bus as events
from app.core.memory.embeddings import embeddings
from app.core.memory.store import new_id, now_iso, store
from app.core.memory.vector_store import vector_store

log = logging.getLogger("memory.manager")

HISTORY_LIMIT = 20


class MemoryManager:
    # -- long-term semantic memory ------------------------------------------
    async def remember(self, content: str, kind: str = "note", agent: str = "jarvis") -> str:
        vec = await embeddings.embed(content)
        doc_id = new_id()
        await vector_store.upsert(content, vec, {"id": doc_id, "kind": kind, "agent": agent, "created_at": now_iso()})
        await events.publish(EVT_MEMORY_SAVED, {"content": content[:120], "kind": kind, "agent": agent})
        return doc_id

    async def recall_context(self, query: str, limit: int = 5) -> tuple[str, list[str]]:
        """Return (joined context string, list of hit contents) for the brain."""
        vec = await embeddings.embed(query)
        hits = await vector_store.search(vec, limit=limit)
        if not hits:
            return "", []
        lines = [f"- {h['content']}" for h in hits]
        return "\n".join(lines), [h["content"] for h in hits]

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        vec = await embeddings.embed(query)
        return await vector_store.search(vec, limit=limit)

    # -- conversation memory ---------------------------------------------------
    async def save_conversation_turn(self, role: str, text: str, agent: str = "jarvis") -> None:
        store.put(
            "conversations",
            new_id(),
            {"role": role, "text": text, "agent": agent, "created_at": now_iso()},
        )

    def get_history(self, limit: int = HISTORY_LIMIT) -> list[dict]:
        turns = store.list("conversations", limit=limit)
        turns.reverse()  # oldest first
        # normalize roles: anything that isn't "user" (jarvis, agents) speaks as "assistant"
        return [
            {"role": "user" if t["role"] == "user" else "assistant", "content": t["text"]}
            for t in turns
        ]

    # -- facts / profile ---------------------------------------------------------
    def save_fact(self, key: str, value: str) -> None:
        store.put("facts", key, {"key": key, "value": value, "updated_at": now_iso()})

    def get_fact(self, key: str) -> str | None:
        doc = store.get("facts", key)
        return doc["value"] if doc else None

    def all_facts(self) -> list[dict]:
        return store.list("facts", limit=100)

    # -- stats ----------------------------------------------------------------
    async def stats(self) -> dict:
        try:
            vector_count = await vector_store.count()
        except Exception:  # noqa: BLE001
            vector_count = 0
        return {
            "vector_memories": vector_count,
            "conversation_turns": len(store.list("conversations", limit=1000)),
            "facts": len(store.list("facts", limit=1000)),
        }


memory = MemoryManager()
