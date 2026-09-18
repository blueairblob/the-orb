# 2026-09-18 — The DM's improvisations become canon too (REVIEW R1)

## Context

First finding acted on from the first formal review (`REVIEW.md`, 2026-09-18, reviewer Claude
Opus 5). R1: "improvised detail becomes canon" (PRD §22 Gotcha #3, 🔴) had been built for the
guard only (`devlog/2026-09-16-improvised-detail-canonization.md`). But the PRD's own example of
the problem is a DM detail ("what's over the wall?"). The DM's refusal and narration paths
returned before any extraction ran, and its briefs had no record of what it had already
described, so nothing stopped it saying "darkness is absolute" one turn and describing moonlit
carvings the next.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Scene canon lives on `World`, not the room or the guard | It describes the place, and there's one ledger per scene. The guard's facts are about himself, a different subject | On `Room` (fine for v0.1, but facts can be about "beyond the wall", not the room itself) |
| Same Oracle-pattern extraction call as the guard, with its own prompt | Proven pattern (2026-09-16); the DM's subject matter needs different inclusion rules | Keyword scan: rejected, same reasons as before |
| The authored room description counts as already known; door lock and guard mood are excluded | Otherwise the base scene gets re-recorded in new words every turn, and prose would compete with engine state (PRD §3) | — |
| **Extractive, engine-verified** — the model must quote the sentence verbatim, and `loop._is_quoted_from` rejects anything that isn't in the narration | Live testing caught the first (paraphrasing) version recording "The iron door is etched with faint, swirling patterns", which the DM never said. A missed fact is recoverable; a false one corrupts canon for good. "Agents propose, engine disposes" | Trust the extraction model: this is what failed |
| Transient events excluded in the prompt; the brief says "never contradict, but don't repeat unless relevant" | Live testing recorded "A shadow shifts just beyond the bars" as canon, and the DM then re-narrated it every turn | — |
| Shared `add_fact` drops near-identical retellings (word-set overlap ≥ 0.8) | Live testing recorded "…beyond the bars" and "…beyond the iron bars" separately (overlap 0.875). A genuine extension of a fact (0.5) must stay distinct | Semantic dedupe: needs embeddings, out of scope (R11) |
| No extraction call when the reply is a fallback line | The engine's own words; nothing improvised to record, so it saves a model call | — |

Also fixed a latent bug found while refactoring: extraction answers were passed through
`guardrail.filter_reply`, which replaces an empty reply with the speaker's fallback line. So an
empty extraction answer would have been recorded as the fact "Enough talk.". The guardrail is now
used as a predicate there (reject whatever it would have replaced), not as a filter.

## Commands

```bash
uv run pytest -q          # 110 passed
uv run ruff check engine/ tests/
```

```bash
# [APPLIED] Real backend, 6 DM turns, run three times as the design changed
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
scenario = build_cell_and_guard()
turns = ['describe the room', 'what do I see on the walls?',
         'describe my surroundings again, what is by the door?',
         'what do I see on the walls again?', 'I cast a fireball at the door',
         'describe the room once more']
with GemmaHarness() as llm:
    for t in turns:
        reply, speaker, _ = run_turn(scenario, llm, t)
        print(speaker, reply, scenario.world.established_facts)
"
```

## Outcome

| Run | Result |
|---|---|
| 1 (paraphrasing prompt) | Missed the carvings entirely; **recorded a detail the DM never said** |
| 2 (verbatim quote + engine check) | No invented facts. Carvings recorded later and the DM stayed consistent ("The rough carvings remain unchanged."). But a transient shadow was recorded and then parroted, and near-duplicates piled up |
| 3 (transient exclusion, "don't repeat" wording, near-duplicate merge) | Carvings recorded on first mention; the shadow correctly skipped; later turns consistent with every recorded fact ("the iron bar holds fast", carvings "worn smooth" again); no repetition tic; every fact a verbatim quote |

14 new tests (110 total), covering the world ledger, near-duplicate merging, scene facts in both DM
briefs, the extraction prompt's exclusions, loop wiring, rejection of an invented fact, tolerance
for case and quote differences, the empty-answer bug, no extraction on fallback lines, and save
persistence.

## Open threads

Logged in `REVIEW.md`:

- **R10 (Open):** the guard's extraction still paraphrases, so it can't be checked verbatim and
  carries the same invention risk the DM path just showed. It needs its own grounding check.
- **R11 (Deferred):** meaning-level duplicates aren't merged; a scene fact can indirectly describe
  the door's lock (a problem only once play continues past an unlock).
- **R4 (Open, now wider):** DM turns now pay the extraction latency too.
