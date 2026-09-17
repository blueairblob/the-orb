# 2026-09-17 — Two small, already-flagged gaps closed

## Context

Both items were noticed during 2026-09-16's real playtest sessions but deliberately deferred at
the time to keep each fix focused (save.py: flagged as an open thread in the fact-canonization
devlog; "Try again.": flagged alongside the fallback-line fix). User picked "close the small known
gaps" over "keep playtesting" or "build the ambient-narration future direction" as today's next step.

## Fix 1: `engine/save.py` didn't persist `secret_revealed` or `established_facts`

Both are engine-owned, PRD §22 Gotcha #3 "bound thereafter" state — same category as
`guard_affiliation`/`guard_memory`, which were already persisted. Without this, resuming a saved
session could silently re-offer an already-revealed secret, or forget a fact the guard is
supposed to stay bound to. `load_state` defaults both when absent, so an older save file (or one
simply missing the keys) still loads cleanly rather than erroring.

No dedicated `tests/test_save.py` existed before this — save/load only had indirect coverage
(`test_loop.py` checking `save_path.is_file()`, never its contents). Added one, covering: full
round-trip of every persisted field, the no-file-yet default case, and an older-format/missing-keys
default case.

```bash
# [APPLIED] Real backend: reveal the secret in a live session, save, reload,
# confirm the reloaded guard's brief reflects it rather than re-offering the reveal
uv run python3 -c "
from pathlib import Path
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
from engine.save import save_state, load_state
from engine.brief import build_guard_brief
scenario = build_cell_and_guard()
scenario.guard.affiliation.value = 70
with GemmaHarness() as llm:
    run_turn(scenario, llm, 'What was the name of the town you grew up in?')
save_state(Path('/tmp/orb-save-test.json'), scenario)
reloaded = load_state(Path('/tmp/orb-save-test.json'))
brief = build_guard_brief(reloaded.guard, reloaded.door, reloaded.room, reloaded.premise)
assert 'already let this slip' in brief
"
```

(Hit an unrelated snag running this: an orphaned `llama-server` from an earlier `timeout`-killed
test command was still holding port 8091, since the killed parent never reached its `GemmaHarness`
context manager's cleanup. Killed the stray PID and reran — worth remembering that a hard
`timeout` on a script using `GemmaHarness` can orphan its subprocess.)

## Fix 2: `guardrail.is_bland_dismissal` missed a bare "Try again."

Same real playtest, same shape of bug as `BLAND_DISMISSALS`'s existing single words (nothing/
silence/quiet) — "Try again." is a content-free deflection back at the player, just a phrase
instead of a word, so the existing set-membership check never caught it. Added
`BLAND_DISMISSAL_PHRASES` with an exact-match check (not the first-word/padding logic the
single-word set uses) — deliberately narrow: a real answer that merely *ends* with the phrase
("I don't care about your treasure. Try again.") has to stay unflagged, same principle already
established for "nothing" appearing mid-sentence in a real answer.

Pure deterministic text logic, no LLM involved — unit tests are the real verification here, same
as the threat-negation fix from 2026-09-15.

## Outcome

6 new tests (96 total, all passing), two commits, both fixes verified — one against the real
backend (save/load), one via unit tests (guardrail is pure logic, same precedent as the
negation-window fix).

## Open threads

None new. Remaining known future directions unchanged: capability-driven grounding and the
Control axis (deferred until a concrete need), ambient/proactive DM narration driven by world time
and NPC schedule (noted 2026-09-17, ../2026-09-16-improvised-detail-canonization.md's sibling
entries have the fuller history).
