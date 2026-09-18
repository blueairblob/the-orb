"""Guard fact-extraction precision (REVIEW.md R14): does the extractive prompt
from R10 record junk ("Still locked.", "Show it to me.", "Garrick.") as
canon, and does a tightened prompt fix that without losing real facts?

Pairs: the 30 (question, reply) turns from the 2026-09-18 live replay (nearly
all non-facts) plus 5 known-good personal facts from earlier live runs.
Each pair runs through the full engine path — extraction call, then the
engine's own verbatim check — for the current prompt and the candidate.

Run:  uv run python experiments/2026-09-18-guard-fact-precision/eval.py
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.brief import build_fact_extraction_prompt
from engine.llm import GemmaHarness
from engine.loop import _extract_new_fact, _is_quoted_from
from engine.scenario import build_cell_and_guard

HERE = Path(__file__).parent


def candidate_prompt(guard, player_utterance: str, guard_reply: str) -> str:
    existing = "\n".join(f"- {fact}" for fact in guard.established_facts) or "(nothing yet)"
    return (
        f"# Already established about {guard.name}\n"
        f"- His name is {guard.name}.\n{existing}\n\n"
        "# What was just said\n"
        f"Player: {player_utterance}\n"
        f"{guard.name}: {guard_reply}\n\n"
        "# Task\n"
        f"Did {guard.name} just reveal a NEW, lasting fact about his own life that isn't "
        "already listed above — his past, his family, people he knows, places he's been, "
        "something that happened to him? These do NOT count: refusals, orders or threats; "
        "reactions to the prisoner or to what they said; anything about the door, the lock, "
        "the cell or what happens next; promises, deals or offers; moods and opinions of the "
        "moment. If he revealed such a fact, copy the words from his reply that state it "
        "exactly, word for word — change nothing. If not, reply with exactly: NONE"
    )


def candidate2_prompt(guard, player_utterance: str, guard_reply: str) -> str:
    """Iteration 2: candidate missed both hometown answers ("Blackwood. A
    quiet place.") -- name origins explicitly, and say a fact still counts
    when a brief remark comes with it."""
    return candidate_prompt(guard, player_utterance, guard_reply).replace(
        "his past, his family, people he knows, places he's been, something that happened to him?",
        "where he comes from or grew up, his past, his family, people he knows, places he's "
        "been, something that happened to him? It still counts if he adds a remark with it.",
    )


PROMPTS = {
    "current": build_fact_extraction_prompt,
    "candidate": candidate_prompt,
    "candidate2": candidate2_prompt,
}


def main() -> None:
    import sys

    selected = sys.argv[1:] or list(PROMPTS)
    pairs = json.loads((HERE / "pairs.json").read_text())
    trace = (HERE / "trace.jsonl").open("a")
    summary = {}
    with GemmaHarness() as llm:
        for name in selected:
            build = PROMPTS[name]
            recorded_ok = recorded_junk = missed = 0
            for pair in pairs:
                guard = build_cell_and_guard().guard
                quote = _extract_new_fact(llm, build(guard, pair["question"], pair["reply"]))
                recorded = bool(quote and _is_quoted_from(quote, pair["reply"]))
                want = pair["want_fact"]
                if recorded and want is False:
                    recorded_junk += 1
                if recorded and want is True:
                    recorded_ok += 1
                if not recorded and want is True:
                    missed += 1
                row = {"prompt": name, **pair, "quote": quote, "recorded": recorded}
                trace.write(json.dumps(row) + "\n")
                trace.flush()
                mark = "JUNK" if recorded and want is False else ("MISS" if want is True and not recorded else "ok  ")
                print(f"[{name}] {mark} recorded={recorded!s:<5} quote={quote!r:<40} | {pair['reply']}", flush=True)
            summary[name] = {
                "real_facts_recorded": f"{recorded_ok}/5",
                "real_facts_missed": missed,
                "junk_recorded": f"{recorded_junk}/27",
            }
    results_path = HERE / "results.json"
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    results_path.write_text(json.dumps({**results, **summary}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
