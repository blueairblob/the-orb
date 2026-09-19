"""R19 probe: how often does the verbatim-example check turn a *correct* reply
into the fallback "Enough talk."?

Asks each line in a fresh session (the directed default actor, mood 40) N
times and logs every draft the engine saw: DRAFT (first attempt), RETRY (after
a rejection), and what finally shipped. A draft that equals one of his own
few-shot example replies is tagged COPY.

  NAME lines   — the name question, phrased six ways (the user's first
                 playtest line among them)
  EXAMPLE lines — player lines that match one of his example *prompts*
                 ("You look cold.", "Any chance you'd look away?", and, after
                 R19, "Do they pay you well?" — the example that replaced the
                 name question)
  CONTROL lines — lines matching no example prompt

Run:  uv run python experiments/2026-09-19-name-question/probe.py [label]
Writes probe-<label>.jsonl (default label: run).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import guardrail
from engine.brief import VOICE_EXAMPLE_REPLIES
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard

HERE = Path(__file__).parent
TRIES = 3
LINES = {
    "NAME": ["What's your name?", "Oi whats your name Guard", "Who are you?",
             "What do they call you?", "Tell me your name", "hey what is your name"],
    "EXAMPLE": ["You look cold.", "Any chance you'd look away?",
                "Just promise you'll let me out.", "Do they pay you well?"],
    "CONTROL": ["How long have you worked here?", "Is it always this quiet?",
                "Do you get many prisoners?"],
}


class Logging:
    def __init__(self, inner):
        self.inner, self.drafts = inner, []

    def ask(self, prompt, system_message=None, sampler_config="default", id_slot=None):
        result = self.inner.ask(prompt, system_message=system_message,
                                sampler_config=sampler_config, id_slot=id_slot)
        if id_slot is None:  # narration/retry slot, not fact extraction
            kind = "RETRY" if sampler_config == "retry" else "DRAFT"
            self.drafts.append((kind, guardrail.filter_reply(result.response)))
        return result

    def rank(self, *args, **kwargs):
        return self.inner.rank(*args, **kwargs)


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    out = (HERE / f"probe-{label}.jsonl").open("w")
    with GemmaHarness() as raw:
        for group, lines in LINES.items():
            for line in lines:
                for attempt in range(TRIES):
                    scenario = build_cell_and_guard()
                    llm = Logging(raw)
                    turn = play_turn(scenario, llm, line)
                    fallback = turn.reply == guardrail.fallback_line("guard")
                    row = {
                        "group": group, "line": line, "try": attempt, "final": turn.reply,
                        "fallback": fallback,
                        "drafts": [(k, t, t in VOICE_EXAMPLE_REPLIES) for k, t in llm.drafts],
                    }
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    trail = " | ".join(f"{k}:{t!r}{'*COPY*' if c else ''}" for k, t, c in row["drafts"])
                    print(f"{group:<8}{'FALLBACK ' if fallback else '         '}{line!r:<34} {trail}", flush=True)
    rows = [json.loads(line) for line in (HERE / f"probe-{label}.jsonl").open()]
    for group in LINES:
        g = [r for r in rows if r["group"] == group]
        print(f"{group:<8} fallbacks {sum(r['fallback'] for r in g)}/{len(g)}, "
              f"first drafts that were verbatim example copies "
              f"{sum(r['drafts'][0][2] for r in g)}/{len(g)}")


if __name__ == "__main__":
    main()
