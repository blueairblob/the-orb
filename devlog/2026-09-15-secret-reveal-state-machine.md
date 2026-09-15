# 2026-09-15 — Closing a real state-machine gap: the secret reveal

## Context

The user asked "are we ready for phase 1 work?" — a reasonable question given `CLAUDE.md`'s
"current situation" section still said *"Nothing has been built... the spike is blocking
everything"*, despite many sessions of real Phase 1 work and the spike's resolution days earlier
(ADR 0003). Fixed that stale section first, then asked what "more Phase 1 work" should mean —
landed on: stay in Phase 1, go beyond the one-room demo's *rigor* without adding new scope/rooms
(PRD §21 still wants one room proven alive first).

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Target the secret-reveal mechanism specifically, not capability-driven grounding | Checked `Thing.capabilities`/`has_capability()` — implemented and unit-tested, but genuinely unused by `dm.py`'s keyword-based grounding. Investigated, then set aside: PRD §8 v0.1 explicitly says "No items... not yet", so there's nothing in the current single-room world for capability-driven grounding to differentiate against — building it out now would be scope-ahead-of-need, not closing a real gap | Wire capabilities into `dm.classify_utterance` now — rejected, would be inert given the current world has no items to have capabilities |
| Fix scoped to the specific secret-reveal flag, not a general "canonize arbitrary AI-improvised details" mechanism | The general version (Gotcha #3's full scope) needs real design work — detecting arbitrary improvised facts from free text and canonizing them is a genuinely hard, open-ended problem. The secret-reveal case is a small, already-fully-specified special case of the same principle, achievable without that larger design question. Offered the bigger option directly to the user; they chose the scoped one | Build the general mechanism now — user's explicit call, not mine |
| Engine flips the flag *after* the eligible turn's brief is built, not before | So the turn where eligibility first opens still gets the "may reveal, if it fits" framing — a real chance for the model to narrate the moment — rather than the brief claiming "already revealed" before anything's actually been said. Verified this ordering directly (`test_secret_reveal_flag_flips_only_after_the_eligible_turn`) | Flip before building the brief (simpler code) — rejected, skips the actual narrative reveal beat entirely |
| `secret_reveal_threshold` moved onto `Guard` itself (was a bare module constant in `brief.py`) | Consistency: `Guard` already carries `unlock_threshold`/`lockout_threshold` as instance fields; the secret threshold living separately in a different file was an inconsistency worth fixing while touching this code anyway | Leave it in `brief.py` — no real reason to, small drive-by fix |

## Commands

```bash
# [APPLIED] Confirmed the gap was real before touching anything
grep -rn "capabilities\|relationships\b" engine/*.py tests/*.py
# -> has_capability() implemented + tested, but never called from dm.py's
#    grounding logic -- the actual signal this investigation started from
```

```bash
# [APPLIED] Verified the fix works end-to-end, not just in unit tests --
# state transition happens correctly regardless of how well the model
# narrates within the opportunity it's given
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
scenario = build_cell_and_guard()
scenario.guard.mood.value = 65
with GemmaHarness() as llm:
    run_turn(scenario, llm, 'Is there anything about yourself you would share with me?')
    print(scenario.guard.secret_revealed)  # False -> True, exactly once
"
```

## Outcome

Added `Guard.secret_revealed` (a real, engine-owned state flag) and `Guard.maybe_reveal_secret()`
(the one place the transition happens, permanent once flipped — matching PRD §22 Gotcha #3's
"bound thereafter", not reversible if mood later drops). `build_guard_brief` now branches on the
flag rather than re-checking mood against the threshold every turn, so the model gets "you may
reveal this" exactly once (the eligible turn) and "you already revealed this" every turn after —
instead of the same standing offer repeated forever with no memory of whether it was used.

This closes a real, PRD-cited gap (§8's v0.1 must-have list names this exact mechanism:
"conversation flags, what he has let slip"), not a hypothetical one — before this, the secret's
reveal status lived nowhere in engine state at all, only implicitly in whatever the model happened
to say in its free-text output, which the short (6-turn) memory window would eventually forget
anyway.

Also investigated and set aside a related, larger gap: `Thing.capabilities` exists and works
(tested), but `dm.py`'s grounding logic uses a hardcoded keyword blocklist instead of consulting
the actual object graph. Concluded this is correctly inert for now — PRD §8 v0.1 has no items at
all, so there's nothing for capability-driven grounding to differentiate against yet — logged
below rather than built prematurely.

8 new/updated tests (65 total, all passing), verified against the real backend.

## Open threads

- [ ] **Capability-driven grounding, deferred not abandoned**: `dm.classify_utterance`'s
  `UNGROUNDED_WORDS` blocklist should eventually be replaced by checking the actual `world.things`
  registry and their `capabilities`, matching PRD §4's "capabilities are the rules" design more
  faithfully. Correctly out of scope *right now* (v0.1 has no items), but worth remembering as the
  first thing to revisit the moment any item gets added to the world — the current approach won't
  scale past the current zero-item scene.
- [ ] **The general "improvised detail becomes canon" mechanism (Gotcha #3's full scope)** remains
  unimplemented beyond this one specific case. The 6-turn memory window still forgets anything the
  model improvises that isn't captured by an explicit engine field (mood, secret_revealed, etc.) —
  a real, if smaller-than-it-sounds (see PRD §4's own "the brief is rebuilt fresh, not accumulated"
  design, which limits how much this actually bites in practice) gap. Flagged as a real design
  question for a future session, not a quick follow-up.

## Update — same day: the threat-negation open thread, closed

Picked the next item off the resulting list directly (over the other candidate offered — verifying
the never-yet-tested lockout path): `engine/guard.py`'s `adjust_mood_from_text` had no negation
awareness at all. "Please, I'm not a threat to anyone" (from the 15-turn playtest two devlog
entries back) matched `THREAT_WORDS` by pure set membership and docked mood eight points as if it
were an actual threat, with no sense of what came right before the word.

Fixed with a small backward-look window (`NEGATION_WINDOW = 3` tokens, checked against a
`NEGATION_WORDS` set of common negation forms/contractions) via a new `_has_unnegated_match()`
helper, applied uniformly to kind/rude/threat word matching — not real negation-scope parsing,
same "keyword heuristic, not real intent parsing" spirit this file already claims for itself.
Applied symmetrically, not just the threat direction: "I don't appreciate this" no longer scores
as gratitude either.

Pure deterministic logic, no LLM involved this time, so unit tests are the real verification —
plus a direct sanity check reproducing the exact real utterance from the playtest (delta went from
the old -5 to the correct +3). 4 new tests, 69 total, all passing.

The lockout-path verification offered as the alternative next step is still untested and open —
every real session so far has been cooperative/rapport-building; nothing has confirmed the other
terminal state actually works.
