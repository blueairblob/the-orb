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
`engine/guard.py`'s affiliation heuristic — not real intent parsing (Gotchas
#1/#2's proper resolution is bigger than this pass).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from engine.guard import Guard
    from engine.world import Door, Room, WorldClock

DM_PERSONA = (
    "You are the Dungeon Master narrating a fantasy dungeon escape. Speak in "
    "sparse, deliberate, scene-setting language — never more than two or three "
    "short sentences. You are not a character in the scene; you describe it. "
    "Never break character. Never mention that you are an AI, a game, or a model."
)

# Things with no place in the cell-and-guard scene (PRD §8: no items, no
# spells, no dice, no combat yet). Deliberately narrow — generic combat/
# threat words like "attack" or "fight" are left to the guard's own
# affiliation heuristic as aggressive dialogue, not routed here.
UNGROUNDED_WORDS = {"cast", "spell", "wand", "potion", "scroll", "sword"}

# Single words, matched as whole words (like UNGROUNDED_WORDS above) — a bare
# substring match here false-positived on "look" inside "looking" (devlog
# 2026-09-09: "Have you ever thought about looking the other way?", clearly
# guard dialogue, got misrouted to the DM).
ENVIRONMENT_QUERY_WORDS = {"describe", "surroundings"}

# Multi-word phrases, matched as substrings — safe as substrings since a
# space-containing phrase can't hide inside a single unrelated word the way
# a bare word like "look" can.
#
# "look" itself deliberately isn't a bare word above (regression, real
# playtest 2026-09-14): "You look cold out here" — dialogue addressed at the
# guard, "look" used as an appearance-copula ("you appear cold"), not a
# perception command — got misrouted to narration. That's a different
# collision than the "looking" substring bug: same word, two unrelated
# senses, whole-word matching alone can't tell them apart. Anchoring "look"
# to specific environment-inspection phrasings instead catches the real
# "let me look around" intent without swallowing "you look X" dialogue.
ENVIRONMENT_QUERY_PHRASES = (
    "what do i see",
    "what does",
    "where am i",
    "what's around",
    "whats around",
    "look around",
    "take a look",
    "let me look",
    "can i look",
    "could i look",
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


# "Don't repeat unprompted" matters as much as "stay consistent": real
# testing (2026-09-18) showed a recorded detail fed back as a bare fact got
# re-narrated on every following turn, turning one line of colour into a tic.
SCENE_FACTS_HEADER = (
    "# Details you've already described — never contradict these, but don't repeat them "
    "unless they're relevant to what's being asked"
)


def _scene_fact_lines(scene_facts: Sequence[str]) -> list[str]:
    """PRD §22 Gotcha #3: whatever the DM has already improvised about the
    place is fed back as fact, so it can't describe "a single iron grate"
    one turn and "a heavy oak door" the next."""
    if not scene_facts:
        return []
    return ["", SCENE_FACTS_HEADER, *[f"- {fact}" for fact in scene_facts]]


def build_refusal_brief(
    room: Room, attempted_action: str, scene_facts: Sequence[str] = ()
) -> str:
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
            *_scene_fact_lines(scene_facts),
            "",
            "# What just happened",
            (
                f'The player just attempted something with no place here: "{attempted_action}". '
                "Gently redirect them back to what's actually real in this scene. Do not explain "
                "rules or mechanics — just narrate the mundane reality."
            ),
        ]
    )


def build_narration_brief(
    room: Room,
    door: Door,
    guard: Guard,
    premise: str,
    scene_facts: Sequence[str] = (),
    *,
    clock: WorldClock,
) -> str:
    return "\n".join(
        [
            DM_PERSONA,
            "",
            "# What the player perceives",
            (
                f"{room.description or room.name}. The door is "
                f"{'locked' if door.locked else 'unlocked'}. It is "
                f"{clock.time_of_day}."
            ),
            f"The guard beyond the door seems {guard.affiliation.band}.",
            (
                f"The player is here for {premise} — mention this only if directly "
                "relevant to what's being asked, not as a reflex."
            ),
            *_scene_fact_lines(scene_facts),
            "",
            "# Your task",
            (
                "Describe only what's asked, in sparse, scene-setting language. Do not speak as "
                "the guard — you are narrating, not conversing."
            ),
        ]
    )


def build_scene_fact_extraction_prompt(
    room: Room, scene_facts: Sequence[str], player_utterance: str, dm_reply: str
) -> str:
    """The DM-side twin of brief.build_fact_extraction_prompt (the Oracle
    fact-ledger pattern): a small, separate judgment call deciding whether
    this narration invented a lasting detail about the place. The room's own
    authored description counts as already established, so the base scene
    isn't re-recorded in different words every turn. The door's lock and
    the guard's mood are explicitly excluded — the engine owns those (PRD
    §3), and recording the model's version of them would let prose compete
    with state.

    Extractive, not abstractive: the model must *copy* the sentence, and
    engine/loop.py rejects anything that isn't verbatim in the narration.
    Real backend testing (2026-09-18) caught a paraphrasing version of this
    prompt inventing a detail the DM never said ("The iron door is etched
    with faint, swirling patterns") and recording it as canon — a missed
    fact is recoverable, a hallucinated one corrupts the ledger for good."""
    known = [room.description or room.name, *scene_facts]
    existing = "\n".join(f"- {fact}" for fact in known)
    return (
        f"# Already established about {room.name}\n{existing}\n\n"
        "# What was just said\n"
        f"Player: {player_utterance}\n"
        f"Dungeon Master: {dm_reply}\n\n"
        "# Task\n"
        "Did the Dungeon Master's narration describe a NEW, specific, lasting physical detail "
        "of this place that isn't already listed above — an object, a marking or feature of "
        "the walls or floor, the source of a sound, what lies beyond? Only things that will "
        "still be there next time: anything moving or happening right now (a shadow shifting, "
        "a sound passing) does not count. Light, air, smells and mood do not count, and "
        "neither does whether the door is locked or how the guard seems. If yes, copy that "
        "sentence from the Dungeon Master's words "
        "exactly, word for word — change nothing. If no, reply with exactly: NONE"
    )
