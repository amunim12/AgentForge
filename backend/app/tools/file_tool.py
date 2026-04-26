"""In-process scratch-notebook tool for agents.

Instead of exposing real filesystem access (which would be a sandbox escape
vector), the "file" tool writes to a per-process in-memory notebook keyed by
virtual filename. Agents use this to stash intermediate artifacts across
tool calls inside a single executor run.
"""
from __future__ import annotations

import threading
from typing import Literal

from langchain_core.tools import tool

_lock = threading.Lock()
_MAX_FILE_CHARS = 32_000
_MAX_FILES = 32

# Module-level in-memory store. Replaced at each `reset_notebook()` call.
_notebook: dict[str, str] = {}


def reset_notebook() -> None:
    """Clear the notebook between executor runs."""
    with _lock:
        _notebook.clear()


def snapshot_notebook() -> dict[str, str]:
    with _lock:
        return dict(_notebook)


Action = Literal["read", "write", "append", "list", "delete"]


@tool
def file_tool(
    action: Action,
    name: str = "",
    content: str = "",
) -> str:
    """Read, write, append to, or list entries in the per-task scratch notebook.

    The notebook is an in-memory key-value store for intermediate text \
    artifacts. It does NOT persist to disk and is reset at the end of each \
    task run. Use it to stash research notes, outlines, or large tool outputs \
    you plan to reference later in the same task.

    Args:
        action: One of "read", "write", "append", "list", "delete".
        name: Virtual filename (required for read/write/append/delete).
        content: Text to write or append (required for write/append).

    Returns:
        The requested content, a confirmation, or an error string.
    """
    with _lock:
        if action == "list":
            if not _notebook:
                return "(notebook is empty)"
            lines = [f"- {k} ({len(v)} chars)" for k, v in _notebook.items()]
            return "\n".join(lines)

        if not name:
            return "Error: 'name' is required for this action."

        if action == "read":
            value = _notebook.get(name)
            if value is None:
                return f"Error: no entry named {name!r}."
            return value

        if action == "delete":
            if name in _notebook:
                del _notebook[name]
                return f"Deleted {name!r}."
            return f"Error: no entry named {name!r}."

        if action in ("write", "append"):
            if not content:
                return "Error: 'content' is required for write/append."
            if action == "write":
                if len(_notebook) >= _MAX_FILES and name not in _notebook:
                    return f"Error: notebook capacity reached ({_MAX_FILES} entries)."
                _notebook[name] = content[:_MAX_FILE_CHARS]
                return f"Wrote {len(_notebook[name])} chars to {name!r}."

            # append
            existing = _notebook.get(name, "")
            combined = (existing + content)[:_MAX_FILE_CHARS]
            if name not in _notebook and len(_notebook) >= _MAX_FILES:
                return f"Error: notebook capacity reached ({_MAX_FILES} entries)."
            _notebook[name] = combined
            return f"Appended to {name!r} (total {len(combined)} chars)."

        return f"Error: unknown action {action!r}."
