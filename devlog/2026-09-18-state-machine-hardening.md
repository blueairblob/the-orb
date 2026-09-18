# 2026-09-18 — Hardening the state machine: R10, R2 and a canon-vs-anti-echo conflict (R12)

## Context

The user's direction after R1 (DM scene canon): "keep hardening the state machine" (PRD §24
step 6, "continuity is non-negotiable"). I took the open `REVIEW.md` findings about the integrity
of game state in order of risk: R10 (the guard's canon could be invented), then R2 (a frozen
clock). Verifying R10 live surfaced a third, R12, which was fixed in the same round. R4 (latency)
was left for later, since it's a speed issue rather than a state one.

## R10 — the guard's facts are now quoted, verified and composed by the engine

R1 showed the extraction model inventing a DM detail when allowed to paraphrase. The guard's
extraction still asked for a free third-person sentence ("Garrick grew up in Oakhaven") that
nothing could check.

The DM's fix (a verbatim quote) doesn't transfer directly: the guard's answers are terse and lean
on the question. "Blackwood. A quiet place." only means "my hometown" next to "what town did you
grow up in?". So the model now only *points at* the words (copies them verbatim),
`loop._is_quoted_from` verifies they're really in his reply, and `brief.format_guard_fact`
composes the recorded fact from two verbatim pieces:

```
Asked "What was the name of the town you grew up in?", you said: "Blackwood"
```

Nothing the extraction model phrases can enter canon. The second-person framing reads naturally
under the guard brief's existing "Things you've already told them" heading.

**Live (5 turns, affiliation 70):** the town, the brother and his fate were all captured this way,
and a later retelling ("He died out there.") stayed consistent with the earlier one ("He didn't
last the winter."). One turn fell back to "Enough talk.", which led to R12.

## R12 — anti-repetition was fighting canon

Asked "Remind me, where did you grow up?", the guard answered with the fallback line. I reproduced
it three times with every model draft logged:

```
[DRAFT] 'Blackwood. A quiet place.'                 <- the canon answer, word for word
[RETRY] 'Blackwood. Just keep pushing the door.'    <- escaped this time; in the original run it didn't
```

The self-repeat check (Gotcha #15: an identical line "screams machine") rejects the consistent
answer, because it *is* his earlier line. The retry sometimes escapes; when it repeats too, the
engine falls back and refuses to repeat a fact he's on record as having given. That's a
trust-wobble moment (#16) caused by the anti-echo rule overriding the canon rule (#3).

**Fix:** when both attempts are verbatim self-repeats *and* the draft contains his own words from a
recorded fact, the draft ships instead of the fallback. The retry still runs first (fresh wording
is preferred), and an idle echo of a line that isn't canon still falls back exactly as before.
`brief.guard_fact_quote` parses the quote back out of a recorded fact; it sits beside
`format_guard_fact` so the format and its parser can't drift apart.

## R2 — time of day is read from the live clock

`room.state["time_of_day"]` was copied from the clock once, at scenario build, and never updated,
while `run_turn` advanced the clock every turn, so the briefs showed a frozen time forever. A
resumed session was worse: `load_state` rebuilt the copy from a fresh clock *before* overlaying the
saved minutes, so the saved time was ignored completely.

The copy is gone. `build_guard_brief` and `dm.build_narration_brief` take the `WorldClock` as a
keyword-only argument, so no caller can silently omit it, and read `time_of_day` live. The scene
starts at an authored hour (`SCENE_START_MINUTES`, 11pm) rather than the clock's accidental
minute 0. Making time actually *matter* (drowsy at night, the shift change at dawn) is the
NPC-timetable work (R3, still deferred); this fix is its foundation.

## Commands

```bash
uv run pytest -q    # 110 -> 120 passed across the three fixes
uv run ruff check engine/ tests/
```

## Outcome

| Finding | Commit | Verified |
|---|---|---|
| R10 guard canon extractive + engine-composed | `545f6a0` | Live, 5 turns |
| R2 live clock | `77d7ff3` | Tests (pure deterministic logic) |
| R12 canon beats the self-repeat fallback | `b6611e7` | Live reproduction of the trigger (3 runs, drafts logged) + regression test built from it |

## Open threads

- **R5, what actually moves the mood dial**, is the next state-machine item, but it changes the
  core persuasion mechanic (PRD §12 still lists it as an open question), so it's a design
  conversation before code.
- Recorded guard facts can overlap ("…you said: "Blackwood"" twice, from two different
  questions). They're consistent, just redundant; covered by R11(a).
