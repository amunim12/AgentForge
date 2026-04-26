"""E2B sandboxed Python-code execution tool."""
from __future__ import annotations

import asyncio

import structlog
from langchain_core.tools import tool

from app.core.config import settings

logger = structlog.get_logger()

_MAX_OUTPUT_CHARS = 4000


def _truncate(text: str, limit: int = _MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\nâ¦[truncated {len(text) - limit} chars]"


def _run_in_sandbox(code: str) -> str:
    """Synchronous E2B execution â called via asyncio.to_thread."""
    # Import inside the function so a missing/misconfigured e2b install does
    # not break module import at application startup.
    try:
        from e2b_code_interpreter import Sandbox
    except ImportError as exc:
        return f"Code executor unavailable: {exc}"

    try:
        with Sandbox(api_key=settings.E2B_API_KEY) as sandbox:
            execution = sandbox.run_code(code)
    except Exception as exc:
        logger.warning("E2B sandbox error", error=str(exc))
        return f"Sandbox error: {exc}"

    stdout = ""
    stderr = ""
    try:
        logs = getattr(execution, "logs", None)
        if logs is not None:
            stdout = "\n".join(getattr(logs, "stdout", []) or [])
            stderr = "\n".join(getattr(logs, "stderr", []) or [])
    except Exception:
        pass

    error_obj = getattr(execution, "error", None)
    error_text = ""
    if error_obj is not None:
        error_text = getattr(error_obj, "traceback", None) or str(error_obj)

    results_text = ""
    try:
        results = getattr(execution, "results", None) or []
        result_reprs: list[str] = []
        for r in results:
            text = getattr(r, "text", None) or str(r)
            if text:
                result_reprs.append(text)
        results_text = "\n".join(result_reprs)
    except Exception:
        pass

    sections: list[str] = []
    if stdout:
        sections.append(f"stdout:\n{_truncate(stdout)}")
    if stderr:
        sections.append(f"stderr:\n{_truncate(stderr)}")
    if results_text:
        sections.append(f"results:\n{_truncate(results_text)}")
    if error_text:
        sections.append(f"error:\n{_truncate(error_text)}")

    if not sections:
        return "(no output)"
    return "\n\n".join(sections)


@tool
async def code_executor(code: str) -> str:
    """Execute Python code inside a secure E2B sandbox.

    Use this for calculations, data manipulation, text processing, or verifying \
    a claim with deterministic logic. The sandbox is ephemeral â files do not \
    persist across calls. Standard scientific libraries (numpy, pandas, \
    matplotlib) are pre-installed.

    Args:
        code: Valid Python 3 source code. Use print() to surface values you \
              want to observe.

    Returns:
        A string containing the combined stdout / stderr / result repr / error \
        traceback sections, each capped to a reasonable length.
    """
    return await asyncio.to_thread(_run_in_sandbox, code)
