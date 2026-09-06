"""Guardrail filter (PRD §17): checks the LLM's reply before it's spoken.

Deliberately simple — the bounded architecture (brief, capabilities, object
model) is the main defence against bad output; this is a last-resort net,
not the primary mechanism. "On a trip, fall back to a safe pre-written line."
"""

from __future__ import annotations

FOURTH_WALL_MARKERS = (
    "as an ai",
    "language model",
    "i'm just a",
    "i am just a",
    "i cannot",
    "as a large language",
)

MAX_REPLY_CHARS = 240

FALLBACK_LINE = "The guard grunts, and says nothing more."


def filter_reply(text: str) -> str:
    """Returns `text` unchanged if it passes, else a safe fallback line."""
    stripped = text.strip()
    if not stripped:
        return FALLBACK_LINE

    lowered = stripped.lower()
    if any(marker in lowered for marker in FOURTH_WALL_MARKERS):
        return FALLBACK_LINE

    if len(stripped) > MAX_REPLY_CHARS:
        return FALLBACK_LINE

    return stripped
