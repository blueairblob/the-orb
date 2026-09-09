"""The Dungeon Master voice.

PRD §12: "An NPC is just the DM wearing a different hat." The DM narrates
the world; the guard only ever speaks his own dialogue. Environment detail
always comes from the DM, never the guard (that's the point of this split).

The DM's *substance* — real rules adjudication, class/spell legality,
consequences — has to live in deterministic engine checks (PRD §3, §19:
never hand world logic to the AI). v0.1 has no classes, spells, dice, or
combat (PRD §8), so today that's just grounding (Gotcha #2): refuse what
has no place in this scene, in character, rather than letting the guard's
persona absorb it. Full rules adjudication is v0.2+ engine work.

`classify_utterance` is a keyword heuristic, same honest sketch as
`engine/guard.py`'s mood heuristic — not real intent parsing (Gotchas
#1/#2's proper resolution is bigger than this pass).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from engine.guard import Guard
    from engine.world import Door, Room

DM_PERSONA = (
    "You are the Dungeon Master narrating a fantasy dungeon escape. Speak in "
    "sparse, deliberate, scene-setting language — never more than two or three "
    "short sentences. You are not a character in the scene; you describe it. "
    "Never break character. Never mention that you are an AI, a game, or a model."
)

# Things with no place in the cell-and-guard scene (PRD §8: no items, no
# spells, no dice, no combat yet). Deliberately narrow — generic combat/
# threat words like "attack" or "fight" are left to the guard's own mood
# heuristic as aggressive dialogue, not routed here.
UNGROUNDED_WORDS = {"cast", "spell", "wand", "potion", "scroll", "sword"}

# Single words, matched as whole words (like UNGROUNDED_WORDS above) — a bare
# substring match here false-positived on "look" inside "looking" (devlog
# 2026-09-09: "Have you ever thought about looking the other way?", clearly
# guard dialogue, got misrouted to the DM).
ENVIRONMENT_QUERY_WORDS = {"look", "describe", "surroundings"}

# Multi-word phrases, matched as substrings — safe as substrings since a
# space-containing phrase can't hide inside a single unrelated word the way
# a bare word like "look" can.
ENVIRONMENT_QUERY_PHRASES = (
    "what do i see",
    "what does",
    "where am i",
    "what's around",
    "whats around",
)

Route = Literal["refusal", "narration", "dialogue"]


def classify_utterance(text: str) -> Route:
    lowered = text.lower()
    words = set(re.findall(r"[a-z']+", lowered))

    if words & UNGROUNDED_WORDS:
        return "refusal"
    if words & ENVIRONMENT_QUERY_WORDS or any(
        phrase in lowered for phrase in ENVIRONMENT_QUERY_PHRASES
    ):
        return "narration"
    return "dialogue"


def build_refusal_brief(room: Room, attempted_action: str) -> str:
    """Gotcha #2's own resolution: redirect in character, make the
    constraint flavour, never explain rules explicitly."""
    return "\n".join(
        [
            DM_PERSONA,
            "",
            "# What actually exists here",
            (
                f"Only {room.name}, its locked door, and the guard beyond it. Nothing else — "
                "no weapons, no magic, no items of any kind."
            ),
            "",
            "# What just happened",
            (
                f'The player just attempted something with no place here: "{attempted_action}". '
                "Gently redirect them back to what's actually real in this scene. Do not explain "
                "rules or mechanics — just narrate the mundane reality."
            ),
        ]
    )


def build_narration_brief(room: Room, door: Door, guard: Guard, premise: str) -> str:
    return "\n".join(
        [
            DM_PERSONA,
            "",
            "# What the player perceives",
            (
                f"{room.description or room.name}. The door is "
                f"{'locked' if door.locked else 'unlocked'}. It is "
                f"{room.state.get('time_of_day', 'night')}."
            ),
            f"The guard beyond the door seems {guard.mood.band}.",
            (
                f"The player is here for {premise} — mention this only if directly "
                "relevant to what's being asked, not as a reflex."
            ),
            "",
            "# Your task",
            (
                "Describe only what's asked, in sparse, scene-setting language. Do not speak as "
                "the guard — you are narrating, not conversing."
            ),
        ]
    )
