"""Guard coherence comparison (REVIEW.md R18): does the incoherence the user saw
in their Easy playtest come from a missing *direction* (fixable cheaply in the
engine) or from model *capacity* (needs a bigger model)?

Four setups, each replaying the same 40 real player lines through a fresh
session on Easy (as the user played), exactly as a real session runs
(play_turn, then finish):

  baseline       Gemma 4 E2B, the undirected actor (empty stance + intents) — today
  directed       Gemma 4 E2B, stance + engine-chosen reply intents (R18)
  e4b            Gemma 4 E4B, undirected
  e4b_directed   Gemma 4 E4B, directed

Run:  uv run python experiments/2026-09-18-guard-coherence/run.py baseline directed
Writes traces/<setup>.jsonl (one line per turn, full detail).
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from engine import guardrail
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard
from engine.tactics import EASY

HERE = Path(__file__).parent
SETUPS = {
    "baseline": ("gemma-4-e2b", False),
    "directed": ("gemma-4-e2b", True),
    "e4b": ("gemma-4-e4b", False),
    "e4b_directed": ("gemma-4-e4b", True),
}


class Counting:
    """Wraps the model to count a turn's retry calls (a retry = the first
    draft failed a quality check)."""

    def __init__(self, inner):
        self.inner = inner
        self.retries = 0

    def ask(self, prompt, system_message=None, sampler_config="default", id_slot=None):
        if sampler_config == "retry":
            self.retries += 1
        return self.inner.ask(prompt, system_message=system_message,
                              sampler_config=sampler_config, id_slot=id_slot)

    def rank(self, *args, **kwargs):
        return self.inner.rank(*args, **kwargs)


def run_setup(name: str) -> None:
    model_id, directed = SETUPS[name]
    lines = json.loads((HERE / "lines.json").read_text())
    out = (HERE / "traces" / f"{name}.jsonl").open("w")
    with GemmaHarness(model_id=model_id) as raw:
        for session, session_lines in lines.items():
            scenario = build_cell_and_guard()
            scenario.difficulty = EASY
            if not directed:
                scenario.guard.stance = ""
                scenario.guard.reply_intents = {}
            llm = Counting(raw)
            for index, line in enumerate(session_lines):
                llm.retries = 0
                start = time.perf_counter()
                turn = play_turn(scenario, llm, line)
                reply_s = time.perf_counter() - start
                turn.finish()
                row = {
                    "setup": name, "session": session, "index": index, "player": line,
                    "reply": turn.reply, "speaker": turn.speaker,
                    "tactics": list(turn.tactics) if turn.tactics else None,
                    "mood": scenario.guard.affiliation.value,
                    "fallback": turn.reply == guardrail.fallback_line("guard"),
                    "retries": llm.retries, "reply_s": round(reply_s, 1),
                }
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(f"[{name}] {session[:4]}#{index:<2} {row['reply_s']:>5}s "
                      f"{'FALLBACK ' if row['fallback'] else ''}{turn.reply!r}  <- {line}", flush=True)
                if turn.outcome:
                    break
    rows = [json.loads(line) for line in (HERE / "traces" / f"{name}.jsonl").open()]
    guard_rows = [r for r in rows if r["speaker"] == "guard"]
    print(f"[{name}] guard turns {len(guard_rows)}, fallbacks {sum(r['fallback'] for r in guard_rows)}, "
          f"retries {sum(r['retries'] for r in guard_rows)}, "
          f"median reply {statistics.median(r['reply_s'] for r in guard_rows)}s")


if __name__ == "__main__":
    for setup in sys.argv[1:] or list(SETUPS):
        run_setup(setup)
