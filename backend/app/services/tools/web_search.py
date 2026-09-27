"""Web search tool — powered by the GLM brain (same key, same endpoint).

No Tavily, no extra API — the LLM answers search-style queries directly
with fresh-ish knowledge. Keeps the whole system on ONE key.
"""
from __future__ import annotations

import logging

from app.core.brain.llm_router import llm_router

log = logging.getLogger("tools.web_search")

SEARCH_PROMPT = """You are the web-search agent. Answer the query with concrete, specific,
up-to-date information. Structure: direct answer first, then 3-5 key facts as bullet points.
If you are not sure about current/live data (prices, today's news), say so honestly
instead of inventing numbers. Answer in the language of the query."""


async def web_search(query: str, max_results: int = 5) -> list[dict]:
    """LLM-powered search: returns a single rich 'result' the brain can use as fact."""
    text = await llm_router.chat(
        [
            {"role": "system", "content": SEARCH_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0.3,
        max_tokens=900,
    )
    return [{"title": query, "url": "llm://glm", "snippet": text}]
