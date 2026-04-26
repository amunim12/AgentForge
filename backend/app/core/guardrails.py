"""Input validation and output sanitization for agent-facing content.

The Pydantic schemas already enforce length/type constraints. Guardrails
sit on top of that to catch content the schema can't see: credential
leakage attempts, obvious prompt-injection markers, and oversized agent
output before it reaches a client.

Keep these checks fast and side-effect-free â they run on the request
hot path.
"""
from __future__ import annotations

import re

from app.core.exceptions import AgentForgeError
from fastapi import status


class GuardrailViolation(AgentForgeError):
    status_code = status.HTTP_400_BAD_REQUEST
    public_message = "Input rejected by content guardrails."


# Patterns that indicate credential leakage or injection attempts.
# Matched case-insensitive against the raw user description.
_BLOCKED_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:password|secret|api[\s_-]?key|access[\s_-]?token)\s*[:=]", re.I),
    re.compile(r"-----BEGIN\s+[A-Z ]*PRIVATE KEY-----"),
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"\b(?:DROP|DELETE|TRUNCATE)\s+TABLE\b", re.I),
    # Naive prompt-injection markers â not a complete defense, just a tripwire.
    re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b", re.I),
    re.compile(r"\bsystem\s*prompt\s*[:=]", re.I),
)

_MAX_OUTPUT_CHARS = 16_000
_REDACT_TOKEN = "[redacted]"


def validate_task_input(description: str) -> None:
    """Raise GuardrailViolation if the description trips a blocked pattern.

    Length is already enforced by the Pydantic schema; we only check
    patterns here so this stays a single-pass scan.
    """
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(description):
            raise GuardrailViolation()


def sanitize_agent_output(text: str) -> str:
    """Truncate over-long agent output and redact obvious credential leaks.

    Agents occasionally echo example credentials in code samples â strip
    those before they reach a client or the vector store.
    """
    if not text:
        return text
    cleaned = _BLOCKED_PATTERNS[0].sub(_REDACT_TOKEN, text)
    if len(cleaned) > _MAX_OUTPUT_CHARS:
        cleaned = cleaned[:_MAX_OUTPUT_CHARS] + "\n\n[output truncated by guardrails]"
    return cleaned
