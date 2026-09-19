"""Scores a room-description rule against labels.json, offline and
deterministic, on the drafts recorded in probe-before.jsonl (each draft is
scored against the player line that produced it).

  TV should be flagged; FP should not be; BORDER doesn't count either way.

Run:  uv run python experiments/2026-09-19-room-vocabulary/evaluate.py
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

from engine.guardrail import is_room_description

HERE = Path(__file__).parent
ROOM, DESC = "the cell", "A cold stone cell."


def flagged(text: str, player: str) -> bool:
    if "player_utterance" in inspect.signature(is_room_description).parameters:
        return is_room_description(text, ROOM, DESC, player_utterance=player)
    return is_room_description(text, ROOM, DESC)


def main() -> None:
    labels = json.loads((HERE / "labels.json").read_text())
    pairs = []  # (draft text, player line) for every flagged-by-the-old-rule draft
    for row in map(json.loads, (HERE / "probe-before.jsonl").open()):
        for _kind, text, room_flag in row["drafts"]:
            if room_flag and text in labels:
                pairs.append((text, row["line"]))
    tally = {"TV": [0, 0], "FP": [0, 0], "BORDER": [0, 0]}  # [flagged, total]
    for text, player in pairs:
        label = labels[text]
        tally[label][1] += 1
        tally[label][0] += flagged(text, player)
    tv, fp, border = tally["TV"], tally["FP"], tally["BORDER"]
    print(f"{len(pairs)} drafts the old rule flagged (with multiplicity)")
    print(f"  true violations still blocked : {tv[0]}/{tv[1]}")
    print(f"  false positives still blocked : {fp[0]}/{fp[1]}   (want 0)")
    print(f"  borderline blocked            : {border[0]}/{border[1]}   (either is fine)")
    for text, player in pairs:
        label = labels[text]
        if (label == "TV" and not flagged(text, player)) or (label == "FP" and flagged(text, player)):
            print(f"  WRONG [{label}] {text!r}  <- {player!r}")


if __name__ == "__main__":
    main()
