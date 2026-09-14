"""Guardrail filter (PRD §17): checks the LLM's reply before it's spoken.

Deliberately simple — the bounded architecture (brief, capabilities, object
model) is the main defence against bad output; this is a last-resort net,
not the primary mechanism. "On a trip, fall back to a safe pre-written line."
"""

from __future__ import annotations

import re

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

# How many words a reply can have and still count as a padded version of a
# bare BLAND_DISMISSALS word ("Nothing worth mentioning.", "Nothing matters
# now.") rather than a real, if terse, answer — both real failures were 3
# words, a little headroom added. Matched only against the *first* word, not
# a substring, so "Another word. Nothing here." (a real answer that merely
# mentions "nothing" partway through) isn't caught — same shape of miss as
# the exact-match version already accepted, just widened past bare matches.
BLAND_DISMISSAL_MAX_WORDS = 4

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
    """True if `text` is (near enough) just one of `BLAND_DISMISSALS`, or a
    short padded variant of one ("Nothing worth mentioning.", "Nothing
    matters now.") — both real non-answers to real substantive questions
    (real playtest 2026-09-14), not the sparse-but-real short answer PRD
    §3's Yoda principle wants and must not flag ("No.", "Fine.", "Stop.",
    or a longer reply that just happens to contain one of these words)."""
    normalized = _normalize(text)
    if normalized in BLAND_DISMISSALS:
        return True
    words = normalized.split()
    return bool(words) and words[0] in BLAND_DISMISSALS and len(words) <= BLAND_DISMISSAL_MAX_WORDS


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


# Common enough in ordinary dialogue that matching them as "room
# description" would false-positive constantly — excluded from the
# room_description content-word set below.
_DESCRIPTION_STOPWORDS = {"a", "an", "the", "is", "are", "it", "this", "that", "in", "of", "and"}


def is_room_description(text: str, room_name: str, room_description: str = "") -> bool:
    """True if `text` names or describes the room directly (e.g. "This is a
    cell." or "It's stone and damp.") — PERSONA already forbids the guard
    from describing his surroundings (that's the Dungeon Master's job), but
    stating the rule wasn't enough on its own, and restating it in
    RULE_REMINDER right before generation wasn't either (real playtest
    2026-09-14, confirmed for "Tell me about this place" even with both).
    Driven by the room's own name and description so this generalises past
    this one scenario's "cell" rather than being hardcoded to it — matches
    whole words only (the room name's own last word, its key noun: "the
    cell" -> "cell"; plus room_description's own content words, minus
    common stopwords), so a guard line that happens to share unrelated
    ordinary vocabulary doesn't false-positive."""
    candidates = {room_name.rsplit(maxsplit=1)[-1].lower()}
    candidates |= {
        word
        for word in re.findall(r"[a-z']+", room_description.lower())
        if word not in _DESCRIPTION_STOPWORDS
    }
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & candidates)


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
