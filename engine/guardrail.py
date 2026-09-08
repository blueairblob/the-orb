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

# The model sometimes wraps its whole reply in literal quote marks (seen
# repeatedly in real sessions: '"Silence."', '"What do you want?"') — without
# stripping these first, a quoted bland dismissal slips past the check below
# undetected (rstrip only trims .!…, never the quote outside that), so
# engine/loop.py never retries it. Straight and curly, since the model isn't
# consistent about which it uses.
_WRAPPING_QUOTES = "\"'‘’“”"


def _normalize(text: str) -> str:
    return text.strip().strip(_WRAPPING_QUOTES).strip().lower().rstrip(".!…")


def is_bland_dismissal(text: str) -> bool:
    """True if `text` is (near enough) just one of `BLAND_DISMISSALS` and
    nothing else — a flat non-answer rather than an in-character line."""
    return _normalize(text) in BLAND_DISMISSALS


def is_repeated_reply(text: str, prior_lines: list[str]) -> bool:
    """True if `text` is (near enough) verbatim one of the speaker's own
    recent lines — an echo of a past turn, not a fresh reaction to this one.
    Widening the guard's memory window was meant to fix real amnesia
    (forgetting an offer made a dozen lines back) but turned out to make him
    *more* prone to literally repeating himself verbatim once — devlog: "Move
    slow." recurred four times in one session, for four different prompts.
    Same shape as is_bland_dismissal: a narrow, last-resort check so
    engine/loop.py knows to ask for another take, not a rewrite."""
    normalized = _normalize(text)
    return any(normalized == _normalize(prior) for prior in prior_lines)


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
