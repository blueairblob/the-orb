"""Unblinds and aggregates judgments.json against key.json and the traces.

judgments.json: {"<session>#<index>": {"A": "RCF", "B": "R-F", ...}} — written
from blind_review.md *before* key.json was opened. Prints, per setup: the
share of replies that were responsive (R), consistent (C), fluent (F) and
sensible to a player (M), the share that passed all four, plus the mechanical numbers from the traces
(fallbacks, retries, median seconds to reply).

Run:  uv run python experiments/2026-09-18-guard-coherence/score.py
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    key = json.loads((HERE / "key.json").read_text())
    judgments = json.loads((HERE / "judgments.json").read_text())
    tally: dict[str, dict[str, int]] = {}
    for turn_id, marks in judgments.items():
        for letter, verdict in marks.items():
            setup = key[turn_id][letter]
            t = tally.setdefault(setup, {"n": 0, "R": 0, "C": 0, "F": 0, "M": 0, "all": 0})
            t["n"] += 1
            for criterion in "RCFM":
                t[criterion] += criterion in verdict
            t["all"] += all(c in verdict for c in "RCFM")

    print(f"{'setup':<14}{'n':>4}{'responsive':>12}{'consistent':>12}{'fluent':>8}{'sensible':>10}{'all 4':>7}"
          f"{'fallbacks':>11}{'retries':>9}{'median s':>10}")
    results = {}
    for setup, t in tally.items():
        rows = [json.loads(line) for line in (HERE / "traces" / f"{setup}.jsonl").open()]
        guard_rows = [r for r in rows if r["speaker"] == "guard"]
        fallbacks = sum(r["fallback"] for r in guard_rows)
        retries = sum(r["retries"] for r in guard_rows)
        median_s = statistics.median(r["reply_s"] for r in guard_rows)
        pct = {c: round(100 * t[c] / t["n"]) for c in ("R", "C", "F", "M", "all")}
        results[setup] = {"n": t["n"], **{f"pct_{c}": v for c, v in pct.items()},
                          "fallbacks": fallbacks, "retries": retries, "median_reply_s": median_s}
        print(f"{setup:<14}{t['n']:>4}{pct['R']:>11}%{pct['C']:>11}%{pct['F']:>7}%{pct['M']:>9}%{pct['all']:>6}%"
              f"{fallbacks:>11}{retries:>9}{median_s:>10}")
    (HERE / "results.json").write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
