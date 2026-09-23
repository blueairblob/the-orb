"""R20 end-to-end check, real model + full brief, Easy difficulty: for the
line that lost its bribe reading, plus kind/hostile controls, record the
"# What you do now" directive he was actually given and what he said.

Run:  uv run python experiments/2026-09-23-reply-direction/verify.py
Writes verify.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.brief import build_guard_brief
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard
from engine.tactics import EASY

HERE = Path(__file__).parent
TRIES = 3
LINES = {
    "REPORTED": ["You have time to help me get gold"],
    "BRIBE": ["Look I have gold", "I'll pay you ten gold to open it"],
    "KIND": ["I'm sure your brother was a good man.", "I'm sorry about your brother."],
    "HOSTILE": ["You're pathetic."],
}


def main() -> None:
    with GemmaHarness() as llm, (HERE / "verify.jsonl").open("w") as out:
        for group, lines in LINES.items():
            for line in lines:
                for attempt in range(TRIES):
                    scenario = build_cell_and_guard()
                    scenario.difficulty = EASY
                    turn = play_turn(scenario, llm, line)
                    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room,
                                              scenario.premise,
                                              clock=scenario.world.clock)
                    directive = next((ln for ln in brief.splitlines()
                                      if ln.startswith("# What you do now")), None)
                    row = {"group": group, "line": line, "try": attempt, "reply": turn.reply,
                           "speaker": turn.speaker, "did": scenario.guard.last_did,
                           "mood_move": scenario.guard.last_move, "directive": directive}
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    print(f"{group:<8}{line!r:<42} did={row['did']} -> {turn.reply!r}", flush=True)
                    print(f"         {directive}", flush=True)


if __name__ == "__main__":
    main()
