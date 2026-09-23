"""R23 end-to-end: the two lines that got a spurious "answer the question"
directive on Easy no longer do, and a genuine question still does. Real model,
full brief, Easy.

Run:  uv run python experiments/2026-09-23-reply-direction/verify_r23.py
"""

from __future__ import annotations

from engine.brief import build_guard_brief
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard
from engine.tactics import EASY

LINES = [
    ("STATEMENT", "I'm sure your brother was a good man."),
    ("GREETING", "hi anyone there"),
    ("REAL_Q", "Do you have any family?"),
]


def main() -> None:
    with GemmaHarness() as llm:
        for tag, line in LINES:
            for attempt in range(2):
                scenario = build_cell_and_guard()
                scenario.difficulty = EASY
                turn = play_turn(scenario, llm, line)
                brief = build_guard_brief(scenario.guard, scenario.door, scenario.room,
                                          scenario.premise, clock=scenario.world.clock)
                directive = next((ln for ln in brief.splitlines()
                                  if ln.startswith("# What you do now")), "(none)")
                answers_q = "Answer what they asked" in directive
                print(f"{tag:10s} did={str(scenario.guard.last_did):24s} answer-q={answers_q}  -> {turn.reply!r}")
                print(f"           {directive[:130]}")


if __name__ == "__main__":
    main()
