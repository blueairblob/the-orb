"""Multi-label follow-up to the tactic spike (no new model calls — it re-reads
the spike's own trace.jsonl, whose responses carry each call's top_logprobs).

Two findings drove the multi-label build (see README.md, "Follow-up"):

1. The spike's "confidence" was skewed. It multiplied the probabilities of
   *every* generated token, including an end-of-answer token that sits near
   0.65 even when the label is certain — so every score was deflated by
   about a third (labels the model was ~100% sure of scored ~0.62). The
   honest measure is the probability of the label's *first* token.
2. The first token's top_logprobs are the model's whole distribution over
   readings, from the same single call. All ten labels start with a
   different letter, so any token maps to at most one label by prefix.

Run:  uv run python experiments/2026-09-18-tactic-classifier/multilabel_analysis.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from engine.guard import GARRICK_SUSCEPTIBILITY
from engine.tactics import TACTICS

HERE = Path(__file__).parent


def readings(row: dict) -> dict[str, float]:
    """Label -> probability, from the first token's top_logprobs, mapped by
    prefix and renormalised over the labels (the raw distribution also
    carries non-label tokens like '**' or 'greeting')."""
    first = row["raw"]["choices"][0]["logprobs"]["content"][0]["top_logprobs"]
    dist: dict[str, float] = {}
    for alt in first:
        token = alt["token"].strip().lower()
        matches = [label for label in TACTICS if token and label.startswith(token)]
        if len(matches) == 1:
            dist[matches[0]] = dist.get(matches[0], 0.0) + math.exp(alt["logprob"])
    total = sum(dist.values())
    return {label: p / total for label, p in dist.items()} if total else {}


def main() -> None:
    rows = [
        json.loads(line)
        for line in (HERE / "trace.jsonl").read_text().splitlines()
        if json.loads(line)["variant"] == "zero_shot"
    ]
    print("Skew check (chosen label: first-token probability vs the spike's confidence):")
    for row in rows[:8]:
        first = readings(row).get(row["label"], 0.0)
        print(f"  {row['label']:<9} first={first:.2f} spike={row['confidence']:.2f}  {row['line'][:48]}")

    print("\nMeanings per threshold (gold sets list acceptable labels, not every meaning,")
    print("so 'outside gold' overstates errors — judge the printed lines by eye):")
    for threshold in (0.05, 0.1, 0.15, 0.2, 0.3):
        multi = extra_ok = outside = harmful = 0
        for row in rows:
            meanings = {k for k, v in readings(row).items() if v >= threshold}
            gold = set(row["gold"])
            multi += len(meanings) > 1
            extra_ok += len((meanings & gold) - {row["label"]})
            wrong = meanings - gold
            outside += len(wrong)
            harmful += sum(
                1 for w in wrong
                if GARRICK_SUSCEPTIBILITY.get(w, 0) < 0
                and max(GARRICK_SUSCEPTIBILITY.get(g, 0) for g in gold) >= 0
            )
        print(f"  {threshold:.2f}: {multi}/43 lines multi-label, {extra_ok} extra correct meanings, "
              f"{outside} outside gold, {harmful} penalising a non-hostile line")

    print("\nLines with more than one meaning at 0.10:")
    for row in rows:
        ranked = sorted(((p, k) for k, p in readings(row).items() if p >= 0.1), reverse=True)
        if len(ranked) > 1:
            print("  " + " + ".join(f"{k} {p:.2f}" for p, k in ranked) + f"  | {row['line']}")


if __name__ == "__main__":
    main()
