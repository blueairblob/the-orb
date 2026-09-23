"""R23: where should reply *direction* stop trusting a reading? Mood credits
from 0.1 on Easy; a spurious question=0.10 on a statement then steered his
words to "answer what they asked". Each line is hand-labelled with the moves
that are *really* there (should steer direction) vs the classifier's noise;
we then read every label's probability and find the floor that best keeps the
real secondary moves while dropping the noise.

Run:  uv run python experiments/2026-09-23-reply-direction/floor_probe.py
Writes floor_readings.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.llm import GemmaHarness
from engine.tactics import classify_tactic

HERE = Path(__file__).parent
PREVIOUS = "Keep talking."
# (line, real moves that should steer his reply)
CASES = [
    ("hi anyone there", {"other"}),                                  # a greeting, not a question
    ("I'm sure your brother was a good man.", {"empathy"}),          # a statement, not a question
    ("You seem like a decent guard.", {"flattery"}),
    ("I'm sorry about your brother.", {"empathy"}),
    ("I'm sorry. How did it happen?", {"empathy", "question"}),      # genuine compound
    ("Do you have any family?", {"question"}),
    ("Why won't you let me out?", {"question"}),
    ("Please, I'm begging you, and my children need me.", {"plea"}),
    ("You're good at your job, and I'm innocent.", {"flattery", "argument"}),
    ("Look, I have gold and I didn't even do it.", {"bribe", "argument"}),
    ("hmm", {"other"}),
    ("What's it like working nights? Must be lonely.", {"question", "empathy"}),
]
RUNS = 2


def main() -> None:
    with GemmaHarness() as llm, (HERE / "floor_readings.jsonl").open("w") as out:
        for line, truth in CASES:
            merged: dict[str, float] = {}
            for _ in range(RUNS):
                readings = classify_tactic(llm, line, PREVIOUS) or {}
                for k, v in readings.items():
                    merged[k] = max(merged.get(k, 0.0), v)
            out.write(json.dumps({"line": line, "truth": sorted(truth), "readings": merged}) + "\n")
            top = sorted(merged.items(), key=lambda kv: -kv[1])[:5]
            mark = lambda k: "*" if k in truth else " "
            print(f"{line!r:52s} " + "  ".join(f"{mark(k)}{k}={v:.2f}" for k, v in top))
    print("\n(* = a move that should steer his reply)")


if __name__ == "__main__":
    main()
