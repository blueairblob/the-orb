"""The guard — the Character Engine's first NPC (PRD §12, the "Tamagotchi model").

PRD §12 explicitly leaves "what actually moves the dial?" as an open,
unsketched question. `adjust_mood_from_text` below is a first sketch, not a
final answer: a small, transparent keyword heuristic. The natural upgrade —
have the LLM *propose* a mood delta via structured output and let the engine
clamp/apply it (Gotcha #31: "agents propose, engine disposes") — is flagged
in the devlog as the v0.2 direction, not built here.
"""

from __future__ import annotations

import dataclasses
import re

from engine.world import Thing

KIND_WORDS = {
    "please",
    "friend",
    "sorry",
    "thanks",
    "thank",
    "kind",
    "understand",
    "appreciate",
}
RUDE_WORDS = {"idiot", "stupid", "hate", "pathetic", "useless"}
RUDE_PHRASES = {"shut up"}
THREAT_WORDS = {"kill", "hurt", "die", "regret", "threat"}
THREAT_PHRASES = {"or else"}

KIND_DELTA = 3
RUDE_DELTA = -4
THREAT_DELTA = -8
REPEAT_DELTA = -2

MAX_MEMORY = 12


@dataclasses.dataclass
class MoodDial:
    """A single trust/suspicion dial, 0-100 (PRD §12 lists two — suspicion,
    warmth — but with the driving mechanism unsketched, v0.1 keeps one and
    documents the simplification rather than guessing at a second)."""

    value: int = 40
    minimum: int = 0
    maximum: int = 100

    def adjust(self, delta: int) -> None:
        self.value = max(self.minimum, min(self.maximum, self.value + delta))

    @property
    def band(self) -> str:
        """Narrative register, never the raw number (PRD §12: "the AI simply
        voices wherever the dial currently sits")."""
        if self.value <= 15:
            return "hostile"
        if self.value <= 40:
            return "gruff and suspicious"
        if self.value <= 65:
            return "wary but listening"
        if self.value <= 85:
            return "warming"
        return "ready to help"


@dataclasses.dataclass
class Guard(Thing):
    """An NPC running the Character Engine (PRD §12), pointed at a single
    person rather than the whole scene."""

    mood: MoodDial = dataclasses.field(default_factory=MoodDial)
    memory: list[str] = dataclasses.field(default_factory=list)
    unlock_threshold: int = 75
    lockout_threshold: int = 10
    # PRD §12's own example, verbatim — drives are what make an NPC feel
    # alive underneath the conversation, not just a mood number.
    drives: list[str] = dataclasses.field(
        default_factory=lambda: [
            "bored",
            "cold",
            "wants his watch to end",
            "secretly a little soft on prisoners",
        ]
    )
    # Private canon (PRD §3: reality is permanent) the actor performs *from*,
    # never recites. A generic engine-level fallback — the actual character's
    # story belongs in the scenario that names him (see `engine/scenario.py`),
    # same pattern as `description` overriding `Thing`'s default there.
    backstory: str = "Long years on this watch, most of them cold and uneventful."
    # The one thing behind his "secretly soft on prisoners" drive — the brief
    # only clears him to let it show once trust is real (see `engine/brief.py`).
    secret: str = "He never says why, but he goes gentle on prisoners who remind him of someone."

    def remember(self, speaker: str, line: str) -> None:
        self.memory.append(f"{speaker}: {line}")
        self.memory[:] = self.memory[-MAX_MEMORY:]

    def recent_memory(self, turns: int = 6) -> list[str]:
        return self.memory[-turns:]

    def _is_repeat(self, utterance: str) -> bool:
        recent_player_lines = [
            line.split(": ", 1)[1]
            for line in self.memory
            if line.startswith("player: ")
        ]
        return utterance.strip().lower() in {line.strip().lower() for line in recent_player_lines}

    def adjust_mood_from_text(self, utterance: str) -> int:
        """Sketch heuristic for PRD §12's open question. Returns the delta
        applied, so callers/tests can observe it."""
        was_repeat = self._is_repeat(utterance)
        lowered = utterance.lower()
        words = set(re.findall(r"[a-z']+", lowered))

        delta = 0
        if words & KIND_WORDS:
            delta += KIND_DELTA
        if words & RUDE_WORDS or any(phrase in lowered for phrase in RUDE_PHRASES):
            delta += RUDE_DELTA
        if words & THREAT_WORDS or any(phrase in lowered for phrase in THREAT_PHRASES):
            delta += THREAT_DELTA
        if was_repeat:
            delta += REPEAT_DELTA

        self.mood.adjust(delta)
        return delta

    def check_thresholds(self) -> str | None:
        """Returns 'unlock', 'lockout', or None."""
        if self.mood.value >= self.unlock_threshold:
            return "unlock"
        if self.mood.value <= self.lockout_threshold:
            return "lockout"
        return None
