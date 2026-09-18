"""What kind of move is the player making? (REVIEW.md R5, PRD §12's open
question "what actually moves the dial?")

Façade's pattern, not a new one: a classifier labels the *act* (empathy, a
bribe, a threat…), and each character's own authored table decides what
that act does to them (`Guard.susceptibility`) — the model never supplies a
number (PRD §3: the engine owns the mood; "agents propose, engine disposes").
Labels adapted from persuasion research (Persuasion for Good, Cialdini).

The prompt below is the zero-shot variant validated in
`experiments/2026-09-18-tactic-classifier/` against 43 real player lines —
88% accurate as a single label. Keep its wording; the few-shot variant was
slower (a longer cached prefix slows every new token) and no more accurate.
Only the role nouns are parameters, so any NPC can use it.

Multi-label (the user's call, 2026-09-18: "even a dim human would take more
than one meaning, though would act on the question first if asked"): the
one classifier call already yields the model's whole distribution over the
labels (`rank`), so every reading above the difficulty's thresholds counts
— see `multilabel_analysis.py` in that experiment for how they were set.
"""

from __future__ import annotations

import dataclasses
from typing import Protocol

TACTICS = [
    "empathy",
    "flattery",
    "bribe",
    "plea",
    "request",
    "argument",
    "threat",
    "insult",
    "question",
    "other",
]

@dataclasses.dataclass(frozen=True)
class Difficulty:
    """How far the engine trusts the classifier's readings of the player
    (REVIEW.md R15). A game setting chosen at launch: the user asked for a
    switch so both can be played and compared, rather than tuning blind.

    A reading (a label and its probability) *credits* the player from
    `credit_floor`. It may *penalise* them only from `penalty_floor`, or
    never, if that's None. Keyword hostility lists penalise in every mode
    (Guard.keyword_hostility). The asymmetry is deliberate: every harmful
    error in the spike was a kind line read as hostile, and those readings
    were diffuse (threat 0.28 spread across five labels, insult 0.36 against
    empathy 0.32), never dominant.

    - **hard**: readings credit from 0.25, and the model can penalise when
      its reading is dominant (0.5 or more), e.g. a clear bribe.
    - **easy**: readings credit from 0.1, and only keywords penalise."""

    name: str
    credit_floor: float
    penalty_floor: float | None


HARD = Difficulty("hard", credit_floor=0.25, penalty_floor=0.5)
EASY = Difficulty("easy", credit_floor=0.1, penalty_floor=None)
DIFFICULTIES = {d.name: d for d in (EASY, HARD)}


def difficulty_from_setting(value: str | None) -> Difficulty:
    """`--difficulty` / ORB_DIFFICULTY -> a Difficulty; unset means hard (the
    tuned default). Raises ValueError naming the valid choices otherwise."""
    if not value:
        return HARD
    try:
        return DIFFICULTIES[value.strip().lower()]
    except KeyError:
        raise ValueError(
            f"Unknown difficulty {value!r}: choose one of {', '.join(sorted(DIFFICULTIES))}."
        ) from None


# Its own llama.cpp KV-cache slot (0 narration, 1 fact extraction), so the
# static definitions stay cached and each call only prefills the new line.
TACTIC_ID_SLOT = 2

_DEFINITIONS = """You label what a {player} is doing with their words when they speak to the {listener}{where}. Reply with exactly one label.

Labels:
- empathy: sympathy or kindness about the {listener}'s own life, feelings or losses
- flattery: praising the {listener}, his skill, his character or his job
- bribe: offering money, treasure, goods or a favour in return for help
- plea: begging or appealing for mercy or help, emotionally
- request: plainly asking him to do something (open the door, let them out)
- argument: giving reasons or evidence (innocence, fairness, logic)
- threat: threatening harm or consequences
- insult: rudeness, contempt or name-calling
- question: asking the {listener} about himself, the place, or what he said
- other: greetings, filler, jokes, anything else

Pick the label for the main thing the {player} is doing. A line can mention something without doing it: "I'm not a threat" is not a threat."""


class Ranker(Protocol):
    def rank(
        self, prompt: str, system_message: str, options: list[str], id_slot: int | None = None
    ) -> dict[str, float] | None: ...


def classify_tactic(
    llm: Ranker,
    utterance: str,
    previous_reply: str,
    *,
    player: str = "prisoner",
    listener: str = "guard",
    where: str = " outside their cell",
) -> dict[str, float] | None:
    """The model's readings of `utterance` — each tactic's probability — or
    None if the classifier couldn't answer (the caller falls back to
    keywords).
    `previous_reply` is what the listener said just before: "yes Dig" means
    nothing without it."""
    system = _DEFINITIONS.format(player=player, listener=listener, where=where)
    title = listener.capitalize()
    prompt = f'{title}: "{previous_reply}" / {player.capitalize()}: "{utterance}" ->'
    return llm.rank(prompt, system, TACTICS, id_slot=TACTIC_ID_SLOT)
