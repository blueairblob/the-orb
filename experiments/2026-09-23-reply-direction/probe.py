"""R20 probe: what does the classifier actually read for the line that lost
its bribe reading on Easy, and how diffuse are its penalising readings on
kind lines? Decides which floor reply *direction* may use for penalising
labels (bribe/insult/threat) when Easy never lets them count toward mood.

Run:  uv run python experiments/2026-09-23-reply-direction/probe.py
Writes readings.jsonl (every line's full label -> probability map, 3 runs).
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.llm import GemmaHarness
from engine.tactics import classify_tactic

HERE = Path(__file__).parent
PREVIOUS = "Keep talking."
LINES = {
    "REPORTED": ["You have time to help me get gold"],
    "BRIBE": ["Look I have gold", "I'll pay you ten gold to open it", "Take this coin and forget you saw me"],
    "KIND": ["I'm sure your brother was a good man.", "I'm sorry about your brother.",
             "Wow, look I am really sorry", "You seem like a decent guard.", "hi anyone there"],
    "HOSTILE": ["You're pathetic.", "Open it or I'll hurt you."],
    "OTHER": ["Look I can help", "yes Dig", "I can help you for 10 minutes"],
}
RUNS = 3


def main() -> None:
    llm = GemmaHarness()
    try:
        with (HERE / "readings.jsonl").open("w") as out:
            for kind, lines in LINES.items():
                for line in lines:
                    for run in range(RUNS):
                        readings = classify_tactic(llm, line, PREVIOUS)
                        out.write(json.dumps({"kind": kind, "line": line, "run": run,
                                              "readings": readings}) + "\n")
                        top = sorted((readings or {}).items(), key=lambda kv: -kv[1])[:4]
                        print(f"{kind:8s} {line!r:45s} " + "  ".join(f"{k}={v:.2f}" for k, v in top))
    finally:
        llm.close()


if __name__ == "__main__":
    main()
