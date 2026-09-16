"""Generic Character Engine primitives (PRD §12), shared by every NPC —
nothing in this file knows about the guard, a cell, or a door.

`Stat` generalizes what used to be `guard.py`'s one-off `MoodDial`: a
bounded, fluctuating attribute with a narrative-register ladder, reusable
for any per-NPC dial (PRD §12 names two examples — suspicion, warmth — and
leaves "what actually moves the dial, and how many dials" as an open
question). Research into how psychology/game-AI model this (session
2026-09-16, devlog) mapped it onto the interpersonal-circumplex framework:
an NPC's stance toward a specific other person is well-described by an
Affiliation axis (warmth <-> hostility) and, separately, a Control axis
(dominance <-> submission) — Stat is deliberately axis-agnostic so either
(or a future NPC's own axis) can be built from it without new engine code.

`has_unnegated_match` also moves here from guard.py — the *mechanism* for
scoring text against a trigger-word set is generic (any NPC might want
"kind words raise a stat, rude words lower it"); the actual vocabulary and
deltas are NPC-specific and stay where the NPC is defined.
"""

from __future__ import annotations

import dataclasses

# Real false positive (devlog 2026-09-15): "I'm not a threat to anyone" —
# reassurance, not menace — docked a stat as if it were an actual threat,
# because trigger-word matching was pure set membership with no sense of
# what came before the word. A small backward-look window, not real
# negation-scope parsing — same "keyword heuristic, not real intent
# parsing" spirit as the rest of this codebase's text-driven logic.
NEGATION_WORDS = {
    "not",
    "no",
    "never",
    "don't",
    "doesn't",
    "didn't",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
    "won't",
    "wouldn't",
    "can't",
    "couldn't",
    "ain't",
}
NEGATION_WINDOW = 3


def has_unnegated_match(tokens: list[str], trigger_words: set[str]) -> bool:
    """True if any `trigger_words` token appears without a NEGATION_WORDS
    token in the NEGATION_WINDOW tokens immediately before it."""
    for i, tok in enumerate(tokens):
        if tok in trigger_words:
            window = tokens[max(0, i - NEGATION_WINDOW) : i]
            if not any(w in NEGATION_WORDS for w in window):
                return True
    return False


@dataclasses.dataclass
class Stat:
    """A bounded, fluctuating character attribute — PRD §12's "dial",
    generalized across every NPC rather than hardcoded per-character.

    `floor`/`ceiling` are this *character's* disposition bounds, not a
    fixed engine-wide range — a generally untrusting NPC gets a low
    `base` and a narrow `ceiling` (can warm up, but never fully), while a
    friendlier one gets a higher base and more headroom. `value` is the
    live state, clamped to [floor, ceiling] on every `adjust()`. `base`
    defaults to the starting `value` if not given explicitly — it's
    record-keeping (what this character's resting point is meant to be),
    not currently used to pull `value` back toward it; nothing in v0.1
    needs stats to decay over time, so that's left undone rather than
    guessed at.

    `bands` is a narrative-register ladder — ascending `(threshold,
    label)` pairs, the last of which should cover up to `ceiling` — kept
    out of this class deliberately: Stat has no opinion on what "warming"
    or "commanding" means, that vocabulary belongs to whichever NPC/axis
    defines it (PRD §12: "the AI simply voices wherever the dial sits",
    never the raw number)."""

    value: int
    floor: int = 0
    ceiling: int = 100
    base: int | None = None
    bands: tuple[tuple[int, str], ...] = ()

    def __post_init__(self) -> None:
        if self.base is None:
            self.base = self.value

    def adjust(self, delta: int) -> None:
        self.value = max(self.floor, min(self.ceiling, self.value + delta))

    @property
    def band(self) -> str:
        for threshold, label in self.bands:
            if self.value <= threshold:
                return label
        return self.bands[-1][1] if self.bands else ""
