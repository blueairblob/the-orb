# 2026-09-16 — The safety net itself broke the DM/guard voice split

## Context

Same real terminal playtest that caught the fact-extraction cache-eviction bug also caught this:
the guard was heard saying *"The guard grunts, and says nothing more."* — as his own line, twice
in one session. User: "the guard sometimes talks in the third person like the DM should be doing."

## Investigation

That exact string is `guardrail.FALLBACK_LINE`, the last-resort safe line `_ask_and_record`
(`engine/loop.py`) ships when a reply fails guardrail checks twice in a row (bland dismissal,
verbatim self-repeat, voice-example reuse, room-description leak). It's third-person narration —
nobody had noticed, because no test ever asserted anything about its *voice*, only that it got
returned in the right failure scenarios. It directly breaks PRD §12's own DM/guard split (the DM
narrates in third person; the guard only ever speaks his own first-person dialogue) — from the
one place in the whole engine specifically meant to be the *safe*, never-wrong fallback.

Worse: `filter_reply()` (also using this one shared line for empty replies, fourth-wall breaks,
and over-length replies) is called for both DM and guard turns, and `_ask_and_record`'s
retry-failure fallback is reachable from a DM self-repeat too (own-lines checks aren't guard-only)
— so the bug could in principle have gone the other way too: a guard-voiced line reaching the DM.

## Fix

Split into two fallback lines, speaker-aware:

- `GUARD_FALLBACK_LINE = "Enough talk."` — first-person, matches his established terse voice.
- `DM_FALLBACK_LINE = "The moment passes without another word."` — third-person, scene-neutral
  enough to never misdescribe whatever the DM was actually narrating.

`filter_reply(text, speaker="guard")` and `engine/loop.py`'s retry-failure fallback (which already
had `speaker` in scope everywhere it's called) both pick the right one now.

## Verification

```bash
uv run pytest -q   # 91 passed
uv run ruff check engine/ tests/
```

```bash
# [APPLIED] Real backend: reproduce the exact exchange from the transcript
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
scenario = build_cell_and_guard()
with GemmaHarness() as llm:
    print(run_turn(scenario, llm, 'Oi whats your name Guard')[:2])
"
# -> ('Enough talk.', 'guard') -- same real trigger, correct voice now
```

## Outcome

4 new tests: direct `guardrail.filter_reply` coverage for both speakers (`test_guardrail.py`), plus
a `run_turn`-level test proving a DM self-repeat falls back to the DM's line, not the guard's
(`test_loop.py`) — closing the "could go the other way too" risk noted above, not just the
observed direction. 91 tests total, all passing.

## Open threads

None new. Same minor, still-unfixed observation from the cache-eviction devlog entry: the guard's
real line "Try again." isn't caught by `is_bland_dismissal` (only nothing/silence/quiet trigger a
retry) — noted there, not investigated further.
