"""R19 side-check: did swapping the identity example for a personal-question
example weaken mood tone? At "ready to help" (mood 92) and "gruff" (mood 40),
the same lines are answered with the OLD example set and the NEW one; replies
are shuffled under X/Y labels so warmth can be judged without knowing which is
which. Writes tone_check.jsonl (with the key) and prints only the blind sheet.

Run:  uv run python experiments/2026-09-19-name-question/tone_check.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from engine import brief
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard

HERE = Path(__file__).parent
OLD_IDENTITY = {
    "hostile": '- Player: "What\'s your name?" -> You: "Doesn\'t concern you."',
    "gruff and suspicious": '- Player: "What\'s your name?" -> You: "Garrick. Now hush."',
    "wary but listening": '- Player: "What\'s your name?" -> You: "Garrick. Been a while since anyone bothered to ask."',
    "warming": '- Player: "What\'s your name?" -> You: "Garrick. First time in a while someone\'s meant it."',
    "ready to help": '- Player: "What\'s your name?" -> You: "Garrick. Friends call me that, if you\'d believe it."',
}
NEW = {band: lines for band, lines in brief.BAND_VOICE_EXAMPLES.items()}
OLD = {band: (OLD_IDENTITY[band], *lines[1:]) for band, lines in NEW.items()}
# Round 1 (5 lines, both bands) was inconclusive, leaning slightly to the old
# examples at "ready to help", whose old example carried an explicit warm signal
# ("Friends call me that"). The new warm-band example was reworded to restore it,
# then re-tested on 10 fresh lines, warm band only (round 2).
LINES = ["What's the weather like outside?", "Do you like this work?", "Have you eaten today?",
         "Is the cell always this cold?", "You seem tired.", "I appreciate you listening.",
         "What do you do when it's quiet?", "Any news from outside?", "Do you sleep on watch?",
         "It must be lonely out here."]
MOODS = {"ready to help": 92}


def main() -> None:
    rng = random.Random(7)
    rows = []
    with GemmaHarness() as llm:
        for band, mood in MOODS.items():
            for line in LINES:
                pair = {}
                for condition, examples in (("old", OLD), ("new", NEW)):
                    brief.BAND_VOICE_EXAMPLES = examples
                    scenario = build_cell_and_guard()
                    scenario.guard.affiliation.value = mood
                    pair[condition] = play_turn(scenario, llm, line).reply
                order = ["old", "new"]
                rng.shuffle(order)
                rows.append({"band": band, "line": line, "X": order[0], "Y": order[1],
                             "X_reply": pair[order[0]], "Y_reply": pair[order[1]]})
    brief.BAND_VOICE_EXAMPLES = NEW
    (HERE / "tone_check.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    for r in rows:
        print(f"[{r['band']}] {r['line']!r}\n   X: {r['X_reply']!r}\n   Y: {r['Y_reply']!r}")


if __name__ == "__main__":
    main()
