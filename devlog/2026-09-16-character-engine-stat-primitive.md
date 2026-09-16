# 2026-09-16 — Generalizing the mood dial into a reusable Character Engine primitive

## Context

A spin-off from the same day's improvised-detail canonization work: could the guard's `MoodDial`
(a one-off 0-100 trust/suspicion dial) be expressed as proper D&D-style character stats — a
number with a base, a floor, a ceiling — and could there be more than one of them (mood, trust,
animosity/friendliness)? Before designing anything, asked for research: is there a normalized map
of human character that psychology or game-AI already uses, rather than inventing axes freehand.

Found three distinct, well-established frameworks depending on what's being modeled:

- **Big Five (OCEAN) / HEXACO** — stable personality *traits* (who a character is).
- **PAD (Pleasure-Arousal-Dominance, Mehrabian)** — moment-to-moment *affect* (how they feel right now).
- **The interpersonal circumplex (Leary/Wiggins)** — *relational stance toward a specific other
  person*, two orthogonal axes: Affiliation (warmth <-> hostility) and Control (dominance <->
  submission).

The circumplex was the closest match to what the guard's dial actually is — it's not a general
personality trait or a free-floating mood, it's specifically "how does Garrick feel about *this
prisoner*," which is exactly the circumplex's scope. It also directly resolved the "mood vs. trust
vs. animosity/friendliness" question from the original ask: those are one axis (Affiliation), not
three separate numbers that would just move in lockstep.

## Decisions

| Decision | Rationale |
|---|---|
| Rename `mood` -> `affiliation`, one stat not three | Trust and animosity/friendliness are the same circumplex axis; redundant numbers add complexity with no behavioral payoff |
| Keep the existing 0-100 resolution, don't rescale to 1-5/1-10 | `KIND_DELTA`/`RUDE_DELTA`/`THREAT_DELTA` were already empirically tuned against real playtests (2026-09-14/15 devlogs); raw numbers are never shown to the player either way (PRD §12: only the narrative band is voiced), so a D&D-style small range buys authoring flavor at the cost of a re-tuning pass, for zero gameplay difference |
| Build `Stat` as the reusable primitive now; defer the Control axis and any generic multi-NPC container | Same "wait for a second concrete case" discipline already applied to `Thing.capabilities` — with one NPC built, there's nothing yet to differentiate a container's shape against, and Control has no scene that needs it to gate or flavor anything yet |
| `experiments/web/server.py`'s wire-format JSON keys stay `"mood"`/`"band"` | Disposable dev-tooling shell (CLAUDE.md: engine and shell stay separate); `orb.js`'s whole visual language (hue, restlessness) is already built around that name, renaming it buys nothing for engine rigor |

## Commands

```bash
# [APPLIED] Surveyed every reference before touching anything, to catch the
# full blast radius of the rename (save.py's persisted field, dm.py's brief,
# the web debug server, every test) rather than finding it mid-refactor
grep -rn "mood\|MoodDial" --include="*.py" engine/ tests/ experiments/
```

```bash
# [APPLIED] Full suite + lint after the rename
uv run pytest -q       # 87 passed
uv run ruff check engine/ tests/ experiments/
```

```bash
# [APPLIED] Real backend verification: does everything gated on the renamed
# field still actually work end-to-end, not just import cleanly?
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
scenario = build_cell_and_guard()
scenario.guard.affiliation.value = 70
with GemmaHarness() as llm:
    run_turn(scenario, llm, 'What was the name of the town you grew up in?')
    print(scenario.guard.affiliation.band, scenario.guard.secret_revealed,
          scenario.guard.established_facts)
"
# -> affiliation band/value, secret-reveal, and the fact-canonization
#    ledger (same-day work) all still fire correctly through the rename
```

## Outcome

New `engine/character.py` — no guard-specific vocabulary in it, the actual "Character Engine core"
PRD §12 gestures at:

- **`Stat`**: bounded value with per-character `floor`/`ceiling`/`base` (a narrow ceiling *is* "a
  generally untrusting character," not a special case needing extra fields) and a pluggable
  `bands` ladder — the class itself has no opinion on what "warming" or "commanding" means, that
  vocabulary belongs to whichever NPC/axis defines it.
- **`has_unnegated_match`**: the negation-aware trigger-word matching mechanism (moved out of
  `guard.py`, generalized — the actual trigger-word sets stay NPC-specific).

`Guard.mood: MoodDial` became `Guard.affiliation: Stat`; `adjust_mood_from_text` became
`adjust_affiliation_from_text`. Propagated through `brief.py`, `dm.py`, `loop.py`, `save.py`.
Verified against the real backend, not just import-checked: affiliation value/band, secret-reveal,
and the same-day fact-canonization ledger all still work correctly through the renamed field.

10 tests split into a new `tests/test_character.py` (generic `Stat`/`has_unnegated_match`
coverage, framed without guard vocabulary) with the guard-specific tests updated in place.
87 total, all passing.

## Open threads

- **The Control axis (dominance <-> submission)** is real per the circumplex research but
  deliberately not built — no scene currently needs a guard who postures differently (commanding
  vs. placating) as a mechanic. Revisit if a concrete narrative need shows up, same as capability-
  driven grounding.
- **A generic multi-NPC stat container** (e.g. a `dict[str, Stat]` on a shared base class) is
  still not built — `Guard` just has a typed `affiliation` field, same shape as the old `mood`.
  Revisit the moment a second NPC exists to prove the container's shape against.
- **Noticed, not touched**: `engine/save.py` doesn't persist `secret_revealed` or
  `established_facts` — an existing gap, unrelated to this rename, not investigated further here.
