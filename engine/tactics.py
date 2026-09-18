"""What kind of move is the player making? (REVIEW.md R5, PRD §12's open
question "what actually moves the dial?")

Façade's pattern, not a new one: a classifier labels the *act* (empathy, a
bribe, a threat…), and each character's own authored table decides what
that act does to them (`Guard.susceptibility`) — the model never supplies a
number (PRD §3: the engine owns the mood; "agents propose, engine disposes").
Labels adapted from persuasion research (Persuasion for Good, Cialdini).

The prompt below is the zero-shot variant validated in
`experiments/2026-09-18-tactic-classifier/` against 43 real player lines —
88% accurate alone, no harmful errors once combined with the keyword
hostility override and CONFIDENCE_FLOOR (see `Guard.resolve_tactic`). Keep
its wording; the few-shot variant was slower (a longer cached prefix slows
every new token) and no more accurate. Only the two role nouns are
parameters, so any NPC can use it.
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

# Below this, a label counts as neutral ("other"). In the spike every
# dangerous error — a kind line read as hostile, which would *punish*
# sympathy — scored 0.15-0.35; at 0.4 the kept labels were 95% accurate.
CONFIDENCE_FLOOR = 0.4


@dataclasses.dataclass(frozen=True)
class Difficulty:
    """How much the engine trusts the classifier's reading of the player
    (REVIEW.md R15). A game setting, chosen at launch — the user asked for a
    switch so both can be played and compared, rather than tuning blind.

    - **hard**: the classifier's labels count for or against the player,
      but only above CONFIDENCE_FLOOR.
    - **easy**: the classifier can only *credit* the player. Its labels that
      would lower the mood are ignored — only the keyword lists penalise
      (hostility, which they read precisely) — and crediting labels count
      from a lower floor. Every harmful spike error was a model label that
      penalised a kind line, and in live play real sympathy was often read
      correctly but unsurely ("Wow, look I am really sorry" -> empathy
      0.28), which hard's floor turns neutral.

    Checked on the spike's 43 labelled lines: neither mode gave undeserved
    credit or a harmful penalty; easy differs mainly in not charging for
    bribes."""

    name: str
    confidence_floor: float
    model_can_penalise: bool


HARD = Difficulty("hard", CONFIDENCE_FLOOR, model_can_penalise=True)
EASY = Difficulty("easy", 0.2, model_can_penalise=False)
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


class Chooser(Protocol):
    def choose(
        self, prompt: str, system_message: str, options: list[str], id_slot: int | None = None
    ) -> tuple[str, float | None] | None: ...


def classify_tactic(
    llm: Chooser,
    utterance: str,
    previous_reply: str,
    *,
    player: str = "prisoner",
    listener: str = "guard",
    where: str = " outside their cell",
) -> tuple[str, float | None] | None:
    """The model's label and confidence for `utterance`, or None if the
    classifier couldn't answer (the caller falls back to keywords).
    `previous_reply` is what the listener said just before: "yes Dig" means
    nothing without it."""
    system = _DEFINITIONS.format(player=player, listener=listener, where=where)
    title = listener.capitalize()
    prompt = f'{title}: "{previous_reply}" / {player.capitalize()}: "{utterance}" ->'
    return llm.choose(prompt, system, TACTICS, id_slot=TACTIC_ID_SLOT)
