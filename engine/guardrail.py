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

# Speaker-specific: PRD §12's DM/guard split means "safe last-resort line"
# means different things for each. Real playtest catch (2026-09-16): the old
# single shared FALLBACK_LINE ("The guard grunts, and says nothing more.")
# was third-person narration voiced *as the guard's own line* — exactly the
# rule PERSONA itself bans the guard from breaking (only the DM narrates in
# third person). GUARD_FALLBACK_LINE stays first-person in his own terse
# voice; DM_FALLBACK_LINE keeps the third-person scene-neutral register the
# DM actually uses, worded generically so it never misdescribes whatever the
# DM was actually narrating.
GUARD_FALLBACK_LINE = "Enough talk."
DM_FALLBACK_LINE = "The moment passes without another word."


def fallback_line(speaker: str) -> str:
    return GUARD_FALLBACK_LINE if speaker == "guard" else DM_FALLBACK_LINE

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

# Same content-free "deflects instead of answering" shape as BLAND_DISMISSALS
# above, but the dismissal is a phrase rather than a single word, so it needs
# its own exact-match check rather than the first-word/padding logic below —
# a real answer that merely *ends* with one of these ("I don't care about
# your treasure. Try again.") has to stay unflagged, same as a longer reply
# containing "nothing" partway through. Real playtest catch (2026-09-16):
# "Try again." shipped bare as the whole reply to "I want out" -- deflects
# the question back at the player without answering it.
BLAND_DISMISSAL_PHRASES = {"try again"}

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
    if normalized in BLAND_DISMISSALS or normalized in BLAND_DISMISSAL_PHRASES:
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


_FIRST_PERSON = {"i", "i'm", "i've", "i'll", "i'd", "me", "my", "mine", "myself"}


def _stem(word: str) -> str:
    """Crude plural tolerance: "stones" -> "stone", "cells" -> "cell". Found
    in the R21 probe, where "The stones hold the chill" slipped past a check
    that only knew "stone"."""
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def is_room_description(
    text: str, room_name: str, room_description: str = "", player_utterance: str = ""
) -> bool:
    """True if `text` *introduces* the room to the player — names or describes
    it ("This is a cell." / "It's stone and damp.") — which PERSONA forbids the
    guard: that's the Dungeon Master's job. Stating the rule wasn't enough on
    its own, and restating it in RULE_REMINDER right before generation wasn't
    either (real playtest 2026-09-14, confirmed for "Tell me about this place"
    even with both). Driven by the room's own name and description so this
    generalises past this one scenario's "cell" — matches whole words only
    (the room name's last word, its key noun: "the cell" -> "cell"; plus the
    description's content words, minus common stopwords).

    Two exemptions (REVIEW.md R21). The room's words are ordinary ones —
    "cold", "stone" — and the original check rejected any reply containing
    them: "I've stopped feeling the cold", "It's just the cold" (asked how he
    stands it) and "Twenty years standing in this cold" were all treated as
    narrating the cell, retried, and sometimes ended in the fallback line.
    He may *follow* a topic the player raised, and speak about *himself*; he
    may not *introduce* the scene. So a room word only counts when (a) the
    player didn't just say it (`player_utterance`), and (b) it's in a
    sentence with no first-person reference. Judged sentence by sentence, so
    "I'm on watch. This cell is cold." is still caught."""
    candidates = {_stem(room_name.rsplit(maxsplit=1)[-1].lower())}
    candidates |= {
        _stem(word)
        for word in re.findall(r"[a-z']+", room_description.lower())
        if word not in _DESCRIPTION_STOPWORDS
    }
    candidates -= {_stem(word) for word in re.findall(r"[a-z']+", player_utterance.lower())}
    for sentence in re.split(r"(?<=[.!?\u2026])\s+", text):
        raw_words = set(re.findall(r"[a-z']+", sentence.lower()))
        if {_stem(word) for word in raw_words} & candidates and not raw_words & _FIRST_PERSON:
            return True
    return False


def filter_reply(text: str, speaker: str = "guard") -> str:
    """Returns `text` unchanged if it passes, else a safe fallback line for
    `speaker` ("guard" or "dm" — see `fallback_line`)."""
    stripped = text.strip()
    if not stripped:
        return fallback_line(speaker)

    lowered = stripped.lower()
    if any(marker in lowered for marker in FOURTH_WALL_MARKERS):
        return fallback_line(speaker)

    if len(stripped) > MAX_REPLY_CHARS:
        return fallback_line(speaker)

    return stripped
