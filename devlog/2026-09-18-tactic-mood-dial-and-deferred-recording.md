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

## Update — R13: the actor now voices the director's judgement (`25931b3`)

`Guard.react_to` records the resolved move and what it earned. The guard brief adds one
engine-worded line just before his current mood ("# Just now they offered you a bribe. It sits
badly with you — you won't give them what they want for it."), bucketed from the actual delta.

On the same 30-line replay, all five bribes are now refused in his own voice ("Treasure is a
waste of my time.", "Gold buys nothing here."), where before he said "Show it to me." three times.
He never parroted the line back.

The one warm reaction ("It truly reaches you") got "I don't care." That's one sample, but it
matches the 2026-09-15 finding that concrete gruff examples beat abstract instructions: negative
reactions agree with the persona, positive ones fight it.

The replay also showed *why* the mood barely moves (R15). The classifier often reads real sympathy
correctly but with low confidence (0.28), and the 0.4 floor turns it neutral. The floor was built
for harmful misreads, which were all hostile labels, and keyword lists already own hostility
precisely. The proposal (ignore model threat/insult labels, lower the floor for positive ones) is
logged under R15 for the user to decide, since it sets how winnable Garrick is.

## Update — R15 becomes a switch: easy vs hard (`1e57c6c`, `--new` in the next commit)

The user's call on "is Garrick too hard to win?" was: gamify it. So there's a switch to play both,
rather than a guessed tuning.

- **hard (default):** unchanged. The classifier's labels count for or against the player, above
  a 0.4 confidence floor.
- **easy:** the classifier can only *credit* the player. Model labels that would lower the mood
  are ignored (only the keyword lists penalise), and crediting labels count from 0.2.
- Launched with `orb-engine --difficulty easy|hard --new` (or `ORB_DIFFICULTY`, also honoured by
  the web rig).

Terminal playtests now write transcripts (R6), with the difficulty and every turn's tactic and
mood change, so sessions can be compared afterwards.

**Same 30-line replay:** hard 40 → 44, easy 40 → 52. Neither unlocks, because that playtest leaned
on bribes and questions. On easy he still refuses bribes in his own voice ("Gold doesn't buy
freedom.") even though they cost nothing.

One limitation surfaced: each line gets one label, so a line that does two things scores only one.
"Wow, look I am really sorry. How did it happen?" was labelled *question*, and the apology earned
nothing on either difficulty. A candidate for later: multi-label, or ranking empathy above
question.

## Update — multi-label readings; a skewed confidence score found and fixed

The user wanted multi-label: "even a dim human would take more than one meaning, though would act
on the question first if asked."

The same single classifier call already carries the model's whole distribution over readings (the
first token's top_logprobs, mapped to labels by prefix), so this cost no extra latency.

Looking at those logprobs revealed a mistake of mine in the R5 spike and build, logged as **R17**
and fixed. Confidence had been the product of every generated token's probability, including an
end-of-answer token near 0.65, so certain labels scored ~0.62. Every floor was stricter than
written. The first-token probability is now the measure.

**The rules:**
- Every reading above the credit floor adds its value.
- A model reading may penalise only when it's dominant; the spike's harmful misreads were all
  diffuse.
- Keyword hostility always counts.
- The reaction line names every move, and tells him to answer a question first.
- Hard: credit from 0.25, penalise from 0.5. Easy: credit from 0.1, never penalise.

**Same replay:** hard 40 → 45, easy 40 → 64. Easy is now winnable-looking. Hard's extra harshness
is partly misreadings: "yes Dig" and "help for 10 minutes" were read as bribes, and "your brother
was a good man" as an insult, all at ≥ 0.5. A stricter hard penalty floor is noted under R15 for
after the user's own playtests.
