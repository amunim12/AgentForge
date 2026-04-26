"""Tavily web-search tool exposed to the Executor agent."""
from __future__ import annotations

import asyncio

import structlog
from langchain_core.tools import tool
from tavily import TavilyClient

from app.core.config import settings

logger = structlog.get_logger()

_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def _format_results(raw: dict) -> str:
    results = raw.get("results", []) or []
    if not results:
        return "No results found."

    lines: list[str] = []
    answer = raw.get("answer")
    if answer:
        lines.append(f"Summary: {answer}\n")
    for i, item in enumerate(results, start=1):
        title = item.get("title", "(untitled)")
        url = item.get("url", "")
        content = (item.get("content") or "").strip().replace("\n", " ")
        if len(content) > 500:
            content = content[:500] + "â¦"
        lines.append(f"[{i}] {title}\n    URL: {url}\n    {content}")
    return "\n\n".join(lines)


@tool
async def web_search(query: str, max_results: int = 5) -> str:
    """Search the live web for up-to-date information.

    Use this whenever you need facts that may have changed after the model's \
    training cutoff, or when the task asks about recent events, current prices, \
    news, or specific real-world entities.

    Args:
        query: A specific, well-formed search query. Prefer concrete nouns and \
               dates; avoid vague questions.
        max_results: How many results to return (1â10).

    Returns:
        A numbered list of results with titles, URLs, and content snippets.
    """
    bounded = max(1, min(int(max_results), 10))

    def _run() -> dict:
        return _get_client().search(
            query=query,
            max_results=bounded,
            search_depth="advanced",
            include_answer=True,
        )

    try:
        raw = await asyncio.to_thread(_run)
    except Exception as exc:
        logger.warning("Tavily search failed", error=str(exc), query=query)
        return f"Web search failed: {exc}"

    return _format_results(raw)
