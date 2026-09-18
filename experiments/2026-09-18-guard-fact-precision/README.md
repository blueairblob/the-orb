# 2026-09-18 — Guard fact-extraction precision (REVIEW.md R14)

**Question:** R10 made the guard's fact extraction *extractive* (copy his words verbatim, the
engine verifies them) to stop invented canon. The R5 live replay then showed it over-recording:
11 "facts" in 30 turns, mostly junk ("Still locked." ×3, "Show it to me.", "Garrick.", the promise
"Ten minutes. Fine."). Fed back as canon, those junk facts drove repetition loops, amplified by
R12, which lets restating canon past the anti-echo check. Can a tightened prompt cut the junk
without losing real facts?

**Method:** `pairs.json` holds 35 (question, reply) pairs: the 30 replay turns (27 non-facts, 3
borderline remarks about his brother that are acceptable either way) plus 5 known-good personal
facts from earlier live runs (Blackwood, Oakhaven, his brother dying). Each pair runs the real
engine path (extraction call, then the verbatim check) under each prompt. `eval.py` runs it;
`trace.jsonl` logs every call.

## Results

| Prompt | Real facts recorded | Junk recorded |
|---|---|---|
| current (R10: "copy the words that state a fact") | 5 / 5 | **8 / 27** |
| candidate: his name listed as known + explicit exclusions (refusals, orders, reactions, the door/lock/cell, promises/deals, moods) | 3 / 5 | **0 / 27** |
| candidate 2: + "where he comes from or grew up" and "still counts if he adds a remark" | 3 / 5 | **0 / 27** |

The two candidates missed *different* real facts (the first missed both hometown answers; the
second caught Blackwood but missed "He died out there"). That says the remaining misses are model
noise at the boundary, not something another wording tweak will reliably fix.

## Decision

**Ship candidate 2** (the more complete definition), accepting ~2 in 5 real facts missed on their
first telling. The same principle as R1: a missed fact is recoverable (earlier live runs showed a
fact being recorded when the guard retells it), but junk canon isn't. It's fed back into every
brief, loops, and can turn a promise into binding "fact".

Caveat: 5 positives is a tiny sample (each miss moves recall by 20 points). Recall is worth
re-measuring on a larger set if automated playtesting (REVIEW R7) arrives.
