# 2026-09-18 — The mood dial learns tactics (R5), replies stop waiting (R4), and junk canon (R14)

## Context

The R5 design talk ended with "go for the quick spike, but research first"
(`experiments/2026-09-18-tactic-classifier/`), then "build it with R4 as drafted", using the
reaction table I drafted from Garrick's backstory.

## What was built

- **R5, the mood dial reads tactics** (`ef573c8`). This follows Façade's discourse-act pattern: a
  classifier (`engine/tactics.py`, the spike's zero-shot prompt byte for byte, grammar-constrained,
  confidence from logprobs, its own KV slot) labels *what kind of move* the player made. Garrick's
  authored susceptibility table (`GARRICK_SUSCEPTIBILITY`) sets the number, via `Guard.react_to`.
  - Keyword hostility lists override the model: they were precise in the spike and caught its one
    confident error.
  - Labels below 0.4 confidence count as neutral: every harmful spike error sat below that.
  - Repeating a winning tactic lands at half the last each time (Gotcha #15).
  - If there's no classification at all, the old keyword heuristic takes over.
  - `GemmaHarness.choose()` and a third slot (`--parallel 3`, ctx 6144).
- **R4, the reply before fact recording** (`ef573c8`). `play_turn` returns the reply and
  `Turn.finish()` records facts afterwards. `run_loop` overlaps it with delivering the reply and
  joins before saving; the web rig sends the reply first. `run_turn` keeps its synchronous
  contract.

## The live replay: working as designed, but three problems

I replayed the user's real 30-line 2026-09-16 playtest through the new loop against the live model:

- The classifier did its job: it labelled all five bribes, both sympathy lines (+6, then +3 as
  repeats decayed) and the innocence argument (+4).
- **Median 12.1 s to reply**, with 4.3 s of fact recording now after the reply instead of before.
- **His mood only went 40 → 50** (the old heuristic ends at 49). Garrick's table makes bribes −1
  and questions/requests 0, and that playtest leaned on both. → **R15**, the user's tuning call.
- **His replies contradicted the engine**: each bribe scored −1 while he answered "Show it to me."
  three times. The brief never tells him how he took the move, so players can't learn what works.
  → **R13**.
- **Junk canon**: 11 "facts" recorded, mostly junk ("Still locked." ×3, "Show it to me.", his own
  name, the promise "Ten minutes. Fine."). R10's extractive prompt (earlier today) copied almost
  anything, and R12 let restated canon through the anti-echo check, so junk facts looped.
  → **R14**, a regression I introduced today.

## R14 — fixed by measurement, not guesswork (`b3e45ab`)

`experiments/2026-09-18-guard-fact-precision/`: 35 real (question, reply) pairs, two prompt
iterations.

| Prompt | Real facts | Junk |
|---|---|---|
| R10's | 5/5 | 8/27 |
| Tightened (his name known; refusals, orders, reactions, the door, promises and moods excluded) | 3/5 | 0/27 |

I shipped the tightened prompt on today's R1 principle: a missed fact is recoverable (a retelling
gets recorded), but junk canon loops. The two iterations missed *different* real facts, so the
remaining misses are model noise, not a wording problem.

## Commands

```bash
uv run pytest -q    # 120 -> 141 passed
uv run python experiments/2026-09-18-tactic-classifier/spike.py
uv run python experiments/2026-09-18-guard-fact-precision/eval.py [current|candidate|candidate2]
```

## Open threads (all in REVIEW.md)

- **R13 (Open):** voice the engine's reaction in the guard's brief, so a bribe is met with "I don't
  want your gold" rather than "Show it to me".
- **R15 (Open, user's call):** is Garrick too hard to win? Best judged after R13, since feedback
  changes how players play.
- **R16 (Open):** his fact block inserts newest-first mid-brief, which invalidates the prompt cache
  whenever it grows. Unmeasured latency.
- The classifier's own share of the 12.1 s time-to-reply wasn't isolated in the loop.
