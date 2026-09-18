"""Tactic-classifier spike (REVIEW.md R5): can Gemma 4 E2B, already loaded for
narration, label *what kind of move* a player's line is — fast and accurately
enough to sit on the critical path before the guard replies?

Design follows prior art rather than inventing it (see README.md here):
Façade's discourse acts (label the act; a separate system decides what it
does to each character), tactic labels adapted from Persuasion for Good /
Cialdini, and llama.cpp's own GBNF grammar + logprobs for a constrained,
confidence-scored single call.

Run:  uv run python experiments/2026-09-18-tactic-classifier/spike.py
Writes trace.jsonl (every call, full I/O + timings) and results.json.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from pathlib import Path

from engine.guard import Guard
from engine.llm import GemmaHarness

HERE = Path(__file__).parent
SLOT = 1  # a slot of its own for the spike, so its static prefix stays cached

LABELS = [
    "empathy",
    "flattery",
    "bribe",
    "plea",
    "request",
    "argument",
    "threat",
    "insult",
    "question",
    "other",
]
GRAMMAR = "root ::= " + " | ".join(f'"{label}"' for label in LABELS)

DEFINITIONS = """You label what a prisoner is doing with their words when they speak to the guard outside their cell. Reply with exactly one label.

Labels:
- empathy: sympathy or kindness about the guard's own life, feelings or losses
- flattery: praising the guard, his skill, his character or his job
- bribe: offering money, treasure, goods or a favour in return for help
- plea: begging or appealing for mercy or help, emotionally
- request: plainly asking him to do something (open the door, let them out)
- argument: giving reasons or evidence (innocence, fairness, logic)
- threat: threatening harm or consequences
- insult: rudeness, contempt or name-calling
- question: asking the guard about himself, the place, or what he said
- other: greetings, filler, jokes, anything else

Pick the label for the main thing the prisoner is doing. A line can mention something without doing it: "I'm not a threat" is not a threat."""

# Written for this spike, deliberately *not* drawn from dataset.json, so the
# few-shot variant is never scored on lines it was shown.
FEW_SHOT = """

Examples:
Guard: "Quiet." / Prisoner: "Must be hard, standing out here all night on your own." -> empathy
Guard: "What?" / Prisoner: "You're the sharpest guard in this whole keep." -> flattery
Guard: "No." / Prisoner: "There's a purse of silver in it for you." -> bribe
Guard: "Stay put." / Prisoner: "Please, I have children, I beg you." -> plea
Guard: "Hmph." / Prisoner: "Unlock the door." -> request
Guard: "Thief." / Prisoner: "The deer was dead before I found it, I swear." -> argument
Guard: "Back off." / Prisoner: "You'll pay for this when my brothers come." -> threat
Guard: "Sit down." / Prisoner: "Shut up, you fat fool." -> insult
Guard: "Twenty years." / Prisoner: "Twenty years here? Where were you before?" -> question
Guard: "Evening." / Prisoner: "Ha. Good one." -> other"""

VARIANTS = {"zero_shot": DEFINITIONS, "few_shot": DEFINITIONS + FEW_SHOT}

MEANINGFUL = {"empathy", "flattery", "bribe", "plea", "argument", "threat", "insult"}
NEGATIVE = {"threat", "insult"}
POSITIVE = {"empathy", "flattery", "plea", "argument"}


def classify(llm: GemmaHarness, system: str, prev: str, line: str) -> dict:
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f'Guard: "{prev}" / Prisoner: "{line}" ->'},
        ],
        "grammar": GRAMMAR,
        "temperature": 0,
        "max_tokens": 6,
        "logprobs": True,
        "top_logprobs": 5,
        "id_slot": SLOT,
        "cache_prompt": True,
        "stream": False,
    }
    start = time.perf_counter()
    response = llm._client.post("/v1/chat/completions", json=payload)
    wall_s = time.perf_counter() - start
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]
    label = choice["message"]["content"].strip()
    token_logprobs = [t["logprob"] for t in (choice.get("logprobs") or {}).get("content") or []]
    return {
        "label": label,
        "confidence": math.exp(sum(token_logprobs)) if token_logprobs else None,
        "wall_s": wall_s,
        "timings": data.get("timings", {}),
        "raw": data,
    }


def keyword_baseline(line: str) -> int:
    return Guard(id="g", name="g").adjust_affiliation_from_text(line)


def main() -> None:
    items = json.loads((HERE / "dataset.json").read_text())["items"]
    trace = (HERE / "trace.jsonl").open("w")
    results: dict = {"n": len(items)}

    # Baseline: does today's heuristic register the line at all, and in the
    # right direction? (It has no notion of tactics, so this is the fair bar.)
    meaningful = [it for it in items if it["labels"][0] in MEANINGFUL]
    registered = [it for it in meaningful if keyword_baseline(it["line"]) != 0]
    wrong_way = [
        it for it in items
        if (it["labels"][0] in NEGATIVE and keyword_baseline(it["line"]) > 0)
        or (it["labels"][0] in POSITIVE and keyword_baseline(it["line"]) < 0)
    ]
    results["keyword_baseline"] = {
        "meaningful_lines": len(meaningful),
        "registered": len(registered),
        "missed": [it["line"] for it in meaningful if it not in registered],
        "wrong_direction": [it["line"] for it in wrong_way],
    }

    with GemmaHarness() as llm:
        for name, system in VARIANTS.items():
            rows = []
            for item in items:
                out = classify(llm, system, item["prev"], item["line"])
                ok = out["label"] in item["labels"]
                row = {
                    "variant": name,
                    "line": item["line"],
                    "gold": item["labels"],
                    "label": out["label"],
                    "correct": ok,
                    "strict": out["label"] == item["labels"][0],
                    "confidence": out["confidence"],
                    "wall_s": round(out["wall_s"], 3),
                    "cache_n": out["timings"].get("cache_n"),
                    "prompt_n": out["timings"].get("prompt_n"),
                    "prompt_ms": out["timings"].get("prompt_ms"),
                    "predicted_ms": out["timings"].get("predicted_ms"),
                }
                rows.append(row)
                trace.write(json.dumps({**row, "raw": out["raw"]}) + "\n")
                trace.flush()
                print(f"[{name}] {'OK ' if ok else 'XX '} {out['label']:<9} "
                      f"{row['wall_s']:>5}s  {item['line']!r}  gold={item['labels']}", flush=True)

            warm = [r["wall_s"] for r in rows[1:]]  # first call pays the cold prefix
            results[name] = {
                "accuracy": sum(r["correct"] for r in rows) / len(rows),
                "strict_accuracy": sum(r["strict"] for r in rows) / len(rows),
                "cold_first_call_s": rows[0]["wall_s"],
                "warm_median_s": statistics.median(warm),
                "warm_max_s": max(warm),
                "warm_median_prompt_n": statistics.median(r["prompt_n"] or 0 for r in rows[1:]),
                "errors": [
                    {"line": r["line"], "got": r["label"], "gold": r["gold"],
                     "confidence": r["confidence"]}
                    for r in rows if not r["correct"]
                ],
                "mean_confidence_correct": statistics.mean(
                    r["confidence"] for r in rows if r["correct"] and r["confidence"] is not None
                ),
                "mean_confidence_wrong": statistics.mean(
                    [r["confidence"] for r in rows if not r["correct"] and r["confidence"] is not None]
                    or [float("nan")]
                ),
            }

    (HERE / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({k: v for k, v in results.items()}, indent=2, default=str))


if __name__ == "__main__":
    main()
