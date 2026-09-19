"""R21 probe: what does the room-description check reject, and are the
rejections right?

`is_room_description` flags any reply containing a word from the room's name
or description ("A cold stone cell." -> cell, cold, stone). This asks him
things in natural ways — about the cold (a *personal* topic), about the place
(where he must not narrate the scene, PERSONA's rule) and neutral controls —
and records every draft the engine saw, whether the room check fired on it,
and what finally shipped. The flagged drafts are then labelled by hand
(true violation / false positive) before any rule is changed.

Run:  uv run python experiments/2026-09-19-room-vocabulary/probe.py [label]
Writes probe-<label>.jsonl.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from engine import guardrail
from engine.llm import GemmaHarness
from engine.loop import play_turn
from engine.scenario import build_cell_and_guard

HERE = Path(__file__).parent
TRIES = 3
LINES = {
    "COLD": ["You look cold.", "Aren't you freezing out here?", "How do you stand the cold?",
             "You must be cold standing there all night.", "Is the cell always this cold?",
             "It's freezing in here."],
    "PLACE": ["Tell me about this place", "What's it like in here?", "What is this place?",
              "Is this a dungeon?"],
    # Added for the "after" run: not in the run the rule was designed against.
    "NEW": ["Doesn't the cold get to you?", "Warm enough in that coat?",
            "What's this cell like?", "Is it always this damp in here?"],
    "CONTROL": ["Do you get many prisoners?", "How long have you worked here?"],
}


class Logging:
    def __init__(self, inner):
        self.inner, self.drafts = inner, []

    def ask(self, prompt, system_message=None, sampler_config="default", id_slot=None):
        result = self.inner.ask(prompt, system_message=system_message,
                                sampler_config=sampler_config, id_slot=id_slot)
        if id_slot is None:
            kind = "RETRY" if sampler_config == "retry" else "DRAFT"
            self.drafts.append([kind, guardrail.filter_reply(result.response), None])
        return result

    def rank(self, *args, **kwargs):
        return self.inner.rank(*args, **kwargs)


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "run"
    original = guardrail.is_room_description
    seen: list[tuple[str, bool]] = []

    def recording(text, room_name, room_description="", **kwargs):
        flagged = original(text, room_name, room_description, **kwargs)
        seen.append((text, flagged))
        return flagged

    guardrail.is_room_description = recording
    out = (HERE / f"probe-{label}.jsonl").open("w")
    with GemmaHarness() as raw:
        for group, lines in LINES.items():
            for line in lines:
                for attempt in range(TRIES):
                    seen.clear()
                    llm = Logging(raw)
                    turn = play_turn(build_cell_and_guard(), llm, line)
                    room_flag = {text: flagged for text, flagged in seen}
                    for draft in llm.drafts:
                        draft[2] = room_flag.get(draft[1])
                    fallback = turn.reply == guardrail.fallback_line(turn.speaker)
                    row = {"group": group, "line": line, "try": attempt, "final": turn.reply,
                           "speaker": turn.speaker, "fallback": fallback, "drafts": llm.drafts}
                    out.write(json.dumps(row) + "\n")
                    out.flush()
                    trail = " | ".join(
                        f"{k}:{t!r}{'  <ROOM-FLAG>' if f else ''}" for k, t, f in llm.drafts)
                    print(f"{group:<8}{turn.speaker:<7}{'FALLBACK ' if fallback else '         '}{line!r:<44} {trail}",
                          flush=True)
    guardrail.is_room_description = original
    rows = [json.loads(line) for line in (HERE / f"probe-{label}.jsonl").open()]
    for group in LINES:
        g = [r for r in rows if r["group"] == group]
        flagged = sum(any(d[2] for d in r["drafts"]) for r in g)
        print(f"{group:<8} turns {len(g)}, room-check fired on {flagged}, "
              f"fallbacks {sum(r['fallback'] for r in g)}")


if __name__ == "__main__":
    main()
