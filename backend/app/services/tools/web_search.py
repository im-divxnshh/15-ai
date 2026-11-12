"""Compatibility public-search wrapper. Sources must come from a real tool."""
from app.core.runtime.tools import dispatch

async def web_search(query: str, max_results: int = 5) -> list[dict]:
    result = await dispatch('public-search', 'drake', 'web_search', {'query': query})
    if not result.get('ok'):
        raise RuntimeError(result.get('error', 'Search unavailable'))
    if 'results' in result:
        return result['results'][:max_results]
    return [{'title': url, 'url': url, 'snippet': 'Public source; content has not been fetched.'} for url in result.get('urls', [])[:max_results]]
