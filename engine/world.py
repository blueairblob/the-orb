"""The object model — the engine's spine (PRD §4).

Everything in the world is a `Thing`. Specialised subclasses (`Room`, `Door`,
and `Guard` in `engine/guard.py`) add nothing structural — just different
capabilities and state filled in. No ORM, no networking, no server: this is
the direct rebuttal of the Evennia finding in
`docs/decisions/0002-evennia-evaluation.md` — a Django+Twisted multiplayer
stack for a single-player, on-device engine was declined, and this is what
"build it fresh" produces instead. Testable, debuggable, plain Python.

Deliberately excludes distance/direction (PRD §5) — v0.1 has no map to
navigate (PRD §8: "Explicitly NOT in scope").
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

# Word-set overlap above which two facts count as the same detail. Real
# testing (2026-09-18) recorded both "A shadow shifts just beyond the bars"
# and "...beyond the iron bars" — an exact-match dedupe let near-identical
# retellings pile up (overlap 0.875). A genuine extension ("grew up in
# Oakhaven" vs "grew up in Oakhaven, where he learned to keep quiet", 0.5)
# must stay a separate fact.
NEAR_DUPLICATE_OVERLAP = 0.8


def _fact_words(fact: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", fact.lower()))


def _is_near_duplicate(a: str, b: str) -> bool:
    words_a, words_b = _fact_words(a), _fact_words(b)
    if not words_a or not words_b:
        return False
    return len(words_a & words_b) / len(words_a | words_b) >= NEAR_DUPLICATE_OVERLAP


def add_fact(ledger: list[str], fact: str) -> bool:
    """Adds `fact` to a newest-first fact ledger (PRD §22 Gotcha #3: once
    improvised, a detail is canon). Returns False if blank or already
    recorded — including a near-identical retelling of an existing fact (see
    NEAR_DUPLICATE_OVERLAP); the first wording wins, since it's the one the
    model has already been bound to. Shared by every ledger — the guard's
    facts about himself and the world's facts about the place."""
    normalized = fact.strip()
    if not normalized:
        return False
    if any(_is_near_duplicate(normalized, existing) for existing in ledger):
        return False
    ledger.insert(0, normalized)
    return True


@dataclasses.dataclass
class Thing:
    """Base class for everything in the world (PRD §4).

    The five layers from the PRD map directly onto fields here:
    state, relationships, capabilities, existence, position.
    """

    id: str
    name: str
    description: str = ""
    state: dict[str, Any] = dataclasses.field(default_factory=dict)
    relationships: dict[str, Thing] = dataclasses.field(default_factory=dict)
    capabilities: set[str] = dataclasses.field(default_factory=set)
    exists: bool = True
    location: Thing | None = None

    def has_capability(self, capability: str) -> bool:
        """Capabilities *are* the rules (PRD §4) — the engine checks this,
        never the AI."""
        return capability in self.capabilities

    def destroy(self) -> None:
        """Crosses the existence threshold — the thing is simply gone."""
        self.exists = False
        self.location = None


@dataclasses.dataclass
class Room(Thing):
    """A place things can be located in."""

    def contents(self, world: World) -> list[Thing]:
        return [thing for thing in world.things.values() if thing.location is self]


@dataclasses.dataclass
class Door(Thing):
    """A lockable, openable connector between places."""

    capabilities: set[str] = dataclasses.field(
        default_factory=lambda: {"lockable", "openable"}
    )
    state: dict[str, Any] = dataclasses.field(default_factory=lambda: {"locked": True})

    @property
    def locked(self) -> bool:
        return bool(self.state.get("locked", True))

    def unlock(self) -> None:
        self.state["locked"] = False

    def lock(self) -> None:
        self.state["locked"] = True


@dataclasses.dataclass
class WorldClock:
    """Ticks in minutes. PRD §5: "quietly powers half the engine." Kept
    minimal for v0.1 — just enough for a time-of-day flavour hook; no
    persistent-effect durations are needed yet (no items, no combat, §8)."""

    minutes: int = 0

    def advance(self, minutes: int) -> None:
        self.minutes += minutes

    @property
    def time_of_day(self) -> str:
        hour = (self.minutes // 60) % 24
        if 5 <= hour < 8:
            return "dawn"
        if 8 <= hour < 18:
            return "day"
        if 18 <= hour < 21:
            return "dusk"
        return "night"


@dataclasses.dataclass
class World:
    """Holds every `Thing` and the clock. The brief-builder (`engine/brief.py`)
    walks this graph fresh every turn — it is never hand-written (PRD §4)."""

    things: dict[str, Thing] = dataclasses.field(default_factory=dict)
    clock: WorldClock = dataclasses.field(default_factory=WorldClock)
    # Scene canon the DM has improvised while narrating (an iron grate, a
    # drip in the corner, what lies beyond the wall) — the PRD's own
    # flagship example of Gotcha #3 is a DM detail, not an NPC's. Lives on
    # the world rather than any one Thing because it describes the place.
    # Flavour on top of engine state, never a substitute for it: the door's
    # lock and the guard's mood are excluded at extraction time
    # (dm.build_scene_fact_extraction_prompt), since the engine owns those.
    established_facts: list[str] = dataclasses.field(default_factory=list)

    def add(self, thing: Thing) -> Thing:
        self.things[thing.id] = thing
        return thing

    def add_established_fact(self, fact: str) -> bool:
        return add_fact(self.established_facts, fact)
