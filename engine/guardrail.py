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

# Gemma 4 E2B's single strongest failure mode observed against this brief
# (see devlog): even with a rich backstory and an explicit ban in the
# persona, a "terse gruff character" instruction pulls it toward a bare
# one-word non-answer more often than not. Deliberately narrow — a real
# in-character answer that happens to be one word ("No.", "Fine.", "Stop.")
# is exactly the sparseness PRD §3's Yoda principle wants and must not be
# flagged; only content-free non-answers belong here. Not a safety concern —
# the model just went flat — so it's a separate check from `filter_reply`'s
# fourth-wall net: this one exists purely so `engine/loop.py` knows to ask
# for another take (PRD §1: the engine directs).
BLAND_DISMISSALS = {"nothing", "silence", "quiet"}


def is_bland_dismissal(text: str) -> bool:
    """True if `text` is (near enough) just one of `BLAND_DISMISSALS` and
    nothing else — a flat non-answer rather than an in-character line."""
    normalized = text.strip().lower().rstrip(".!…")
    return normalized in BLAND_DISMISSALS


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
