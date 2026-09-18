"""The guard — the Character Engine's first NPC (PRD §12, the "Tamagotchi model").

PRD §12 explicitly leaves "what actually moves the dial?" as an open,
unsketched question. `adjust_affiliation_from_text` below is a first sketch,
not a final answer: a small, transparent keyword heuristic. The natural
upgrade — have the LLM *propose* a delta via structured output and let the
engine clamp/apply it (Gotcha #31: "agents propose, engine disposes") — is
flagged in the devlog as the v0.2 direction, not built here.
"""

from __future__ import annotations

import dataclasses
import re

from engine.character import Stat, has_unnegated_match
from engine.world import Thing, add_fact

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

# Narrative register ladder for the guard's Affiliation stat (see
# engine/character.py's Stat.bands) — unchanged values from the old
# MoodDial.band, just relocated: Stat itself carries no opinion on what
# these labels mean, only this NPC does. Ascending (threshold, label); the
# last entry's threshold must cover up to the stat's ceiling.
AFFILIATION_BANDS: tuple[tuple[int, str], ...] = (
    (15, "hostile"),
    (40, "gruff and suspicious"),
    (65, "wary but listening"),
    (85, "warming"),
    (100, "ready to help"),
)

# Reverted back down after a real test: widening this to 24 (and the brief's
# window to 16) was meant to fix the guard forgetting an offer from a dozen
# turns back, but a live session showed it made verbatim self-repetition
# *worse*, not better (devlog). A small-model prompting reference the user
# shared makes the same case directly: "forgetting old chats is in character
# for a low-level NPC... giving him real long-term memory tends to break
# believability, and risks overloading the small model's context." Kept
# slightly above what recent_memory's default shows, not equal to it — see
# that default below.
MAX_MEMORY = 12


@dataclasses.dataclass
class Guard(Thing):
    """An NPC running the Character Engine (PRD §12), pointed at a single
    person rather than the whole scene."""

    # PRD §12 lists two dials (suspicion, warmth) but leaves the driving
    # mechanism unsketched; research into psychology/game-AI models of NPC
    # disposition (devlog 2026-09-16) mapped "warmth <-> hostility" onto the
    # interpersonal circumplex's Affiliation axis — this *is* trust, not a
    # separate number from it (see engine/character.py's Stat for the
    # generic primitive this is built on, shared by every future NPC). A
    # second axis, Control (dominance <-> submission), is deliberately not
    # built yet — no scene currently needs it to gate or flavor anything,
    # same "defer until there's a concrete signal" call already made for
    # Thing.capabilities.
    affiliation: Stat = dataclasses.field(
        default_factory=lambda: Stat(value=40, floor=0, ceiling=100, bands=AFFILIATION_BANDS)
    )
    memory: list[str] = dataclasses.field(default_factory=list)
    unlock_threshold: int = 75
    lockout_threshold: int = 10
    secret_reveal_threshold: int = 65
    # Engine-owned state machine flag (PRD §8 v0.1 must-have: "conversation
    # flags, what he has let slip"). Before this existed, brief.py re-offered
    # the *same* "you may reveal this" option to the model every single
    # turn once eligible, with no memory of whether it had happened — a
    # direct gap against PRD §22 Gotcha #3 ("the moment the AI invents
    # something, the engine writes it to state and feeds it back forever").
    # Set by maybe_reveal_secret() below, never by the model itself.
    secret_revealed: bool = False
    # PRD §22 Gotcha #3's general case, beyond the one pre-scripted
    # `secret` above: durable facts the actor spontaneously *invents*
    # during narration (a name, a person, a place, an event from his
    # past) — nothing the engine knew about in advance. Recorded via
    # add_established_fact(), fed back into every future brief so the
    # actor is bound by its own earlier word rather than free to
    # reinvent it (PRD's own example: "rolling green hills" then "a dark
    # forest" — contradiction, illusion dead). Newest-first, matching the
    # "Oracle" fact-ledger pattern this was modelled on (see devlog).
    # No cap — v0.1 sessions are short (10-30 turns to unlock/lockout),
    # so the bloat problem PRD §22 Gotcha #6 flags as "unsolved" doesn't
    # bite at this scale; revisit if that ever changes.
    established_facts: list[str] = dataclasses.field(default_factory=list)
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

    def own_lines(self, speaker: str, limit: int = 6) -> list[str]:
        """Just `speaker`'s own most recent lines, unprefixed — for a
        verbatim-repeat check (see guardrail.is_repeated_reply), distinct
        from recent_memory's full back-and-forth."""
        prefix = f"{speaker}: "
        lines = [entry[len(prefix):] for entry in self.memory if entry.startswith(prefix)]
        return lines[-limit:]

    def _is_repeat(self, utterance: str) -> bool:
        recent_player_lines = [
            line.split(": ", 1)[1]
            for line in self.memory
            if line.startswith("player: ")
        ]
        return utterance.strip().lower() in {line.strip().lower() for line in recent_player_lines}

    def adjust_affiliation_from_text(self, utterance: str) -> int:
        """Sketch heuristic for PRD §12's open question. Returns the delta
        applied, so callers/tests can observe it."""
        was_repeat = self._is_repeat(utterance)
        lowered = utterance.lower()
        tokens = re.findall(r"[a-z']+", lowered)

        delta = 0
        if has_unnegated_match(tokens, KIND_WORDS):
            delta += KIND_DELTA
        if has_unnegated_match(tokens, RUDE_WORDS) or any(
            phrase in lowered for phrase in RUDE_PHRASES
        ):
            delta += RUDE_DELTA
        if has_unnegated_match(tokens, THREAT_WORDS) or any(
            phrase in lowered for phrase in THREAT_PHRASES
        ):
            delta += THREAT_DELTA
        if was_repeat:
            delta += REPEAT_DELTA

        self.affiliation.adjust(delta)
        return delta

    def check_thresholds(self) -> str | None:
        """Returns 'unlock', 'lockout', or None."""
        if self.affiliation.value >= self.unlock_threshold:
            return "unlock"
        if self.affiliation.value <= self.lockout_threshold:
            return "lockout"
        return None

    def maybe_reveal_secret(self) -> bool:
        """Engine-owned state transition, not a same-turn choice the model
        re-decides from scratch every eligible turn. Once flipped, stays
        flipped permanently — matches Gotcha #3's "bound thereafter", not
        reversible if affiliation later drops back below threshold. Returns
        True only on the call that actually flips it, so callers
        (engine/loop.py) can tell "just became eligible" from "already was"
        and time the brief's framing accordingly (see build_guard_brief)."""
        if not self.secret_revealed and self.affiliation.value >= self.secret_reveal_threshold:
            self.secret_revealed = True
            return True
        return False

    def add_established_fact(self, fact: str) -> bool:
        """Records a new durable fact the actor just improvised (PRD §22
        Gotcha #3). Deduped case/whitespace-insensitively — returns False
        without re-adding if this fact (or near enough) is already
        recorded. Newest-first, matching build_guard_brief's ordering."""
        return add_fact(self.established_facts, fact)
