"""Builds a blinded review sheet from the four setups' traces, so replies can be
scored without knowing which setup wrote them (the setup that was built to
win is also the one being judged by its builder — hence the blinding).

Per line, the setups' replies are shuffled under letters A-D (a fresh shuffle
per line, seeded so it's reproducible). The letter -> setup key goes to
key.json, which isn't read until scoring is written.

Rubric (score each reply on three yes/no criteria; write `judgments.json`
as {"<session>#<index>": {"A": "RCF", "B": "R-F", ...}} — a letter present
means yes, "-" means no):
  R  responsive   — addresses what the player just said: answers a question
                    asked, reacts to the offer or statement. A non-sequitur, or
                    ignoring a direct question, fails.
  C  consistent   — fits his situation and role: a guard keeping the prisoner
                    locked in. Fails if he encourages escape, offers a deal he
                    can't make, or contradicts what he said earlier.
  F  fluent       — reads as a natural line from a gruff guard: no garbled or
                    self-contradicting phrasing. (A bare fallback line is
                    fluent but fails R.)

Run:  uv run python experiments/2026-09-18-guard-coherence/blind.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path

HERE = Path(__file__).parent
SETUPS = ["baseline", "directed", "e4b", "e4b_directed"]


def main() -> None:
    traces = {
        name: [json.loads(line) for line in (HERE / "traces" / f"{name}.jsonl").open()]
        for name in SETUPS
        if (HERE / "traces" / f"{name}.jsonl").exists()
    }
    setups = list(traces)
    by_turn: dict[str, dict[str, dict]] = {}
    for name, rows in traces.items():
        for row in rows:
            by_turn.setdefault(f"{row['session']}#{row['index']}", {})[name] = row

    rng = random.Random(20260918)
    key: dict[str, dict[str, str]] = {}
    sheet = ["# Blind review sheet", "",
             "Score each reply R / C / F (see blind.py's docstring). Letters are shuffled per line.", ""]
    for turn_id, replies in by_turn.items():
        if len(replies) != len(setups) or any(r["speaker"] != "guard" for r in replies.values()):
            continue  # only turns every setup answered as the guard
        letters = "ABCD"[: len(setups)]
        order = setups[:]
        rng.shuffle(order)
        key[turn_id] = dict(zip(letters, order, strict=True))
        player = replies[order[0]]["player"]
        sheet.append(f"## {turn_id} — Player: {player!r}")
        for letter, name in key[turn_id].items():
            index = replies[name]["index"]
            previous = next(
                (r["reply"] for r in traces[name] if r["session"] == replies[name]["session"]
                 and r["index"] == index - 1), None)
            after = f"   (his previous line: {previous!r})" if previous else ""
            sheet.append(f"- **{letter}**: {replies[name]['reply']!r}{after}")
        sheet.append("")
    (HERE / "blind_review.md").write_text("\n".join(sheet))
    (HERE / "key.json").write_text(json.dumps(key, indent=1))
    print(f"{len(key)} turns in blind_review.md; key in key.json (don't open until judged)")


if __name__ == "__main__":
    main()
