"""Context Engine (M12) — build / compress / retrieve the context window."""
from __future__ import annotations

from app.core.memory.manager import memory

MAX_CONTEXT_CHARS = 6000


class ContextEngine:
    async def build(self, query: str, history_limit: int = 6) -> str:
        """Assemble memory hits + recent facts + trimmed history into one context block."""
        memory_ctx, _ = await memory.recall_context(query, limit=5)
        facts = memory.all_facts()[:10]
        history = memory.get_history(limit=history_limit)

        parts: list[str] = []
        if facts:
            parts.append("Known facts:\n" + "\n".join(f"- {f.get('key')}: {f.get('value')}" for f in facts))
        if memory_ctx:
            parts.append(f"Relevant memories:\n{memory_ctx}")
        if history:
            hist_text = "\n".join(f"[{h['role']}] {h['content'][:150]}" for h in history)
            parts.append(f"Recent conversation:\n{hist_text}")

        context = "\n\n".join(parts)
        return self.compress(context)

    @staticmethod
    def compress(text: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        """Cheap compression: keep head + tail when too long (recent + oldest anchors)."""
        if len(text) <= max_chars:
            return text
        half = max_chars // 2
        return text[:half] + "\n...[compressed]...\n" + text[-half:]


context_engine = ContextEngine()
