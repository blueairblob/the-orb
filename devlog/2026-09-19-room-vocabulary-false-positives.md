# 2026-09-19 — The room-description check rejected ordinary speech (R21)

## Context

R21, found in the R19 tone check: lines about the cold sometimes ended in the fallback "Enough
talk.". I'd verified the mechanism in isolation (`is_room_description("I've stopped feeling the
cold.")` was True, because the room is "A cold stone cell."), but not how much damage it did.

## Measure first, and it wasn't what I expected

A 36-turn probe (cold-related lines, place questions, controls) recorded every draft and whether the
room check fired: **23 of 36 turns, 11 fallbacks.** But 8 of those 11 were place questions ("What
is this place?", "Is this a dungeon?"), and there the check was *right*: the guard was being asked
to narrate the scene, which PERSONA reserves for the DM. So this wasn't one bug. It was two:

1. Place questions were reaching the guard at all → route them to the DM (the DM stays central, per
   the standing feedback).
2. Ordinary talk about the cold was rejected as narration → change what counts as "introducing
   the scene."

## The rule, and how it was judged

He may *follow* a topic the player raised and speak about *himself*; he may not *introduce* the
scene. So a room word counts only if the player didn't just say it, and it's in a sentence with no
first-person reference (sentence by sentence). Before changing anything I hand-labelled every
distinct flagged draft (TV / FP / BORDER, `labels.json`), then scored the rule offline against
them: true violations blocked stayed at **24/24** while false positives blocked went **5/5 → 1/5**.
The first version leaked one true violation ("The stones hold the chill": plural), so I added crude
plural tolerance.

Routing: anchored place-question phrasings only. Bare "this place" / "in here" / "cell" stay
dialogue, since real lines like "I hate this place and I hate you" and "put me back in my cell?"
are addressed to him; tests pin both directions.

## Live result (fresh samples + 4 lines not used in the design)

| Same 36 lines | Before | After |
|---|---|---|
| Room check fired | 23 | 2 |
| Fallbacks | 11 | 1 |
| Place questions answered by the DM | 0/12 | 12/12 |

The 12 new-line turns: the check fired once, correctly (he volunteered "It's a cell. It's cold."),
no fallbacks.

## What's left, honestly

- **Known residual:** "It's freezing in here" → "Stop complaining about the cold" still falls
  back sometimes: the player said *freezing*, not *cold*. A synonym list would fix it but is
  scenario-specific vocabulary in a generic guardrail; left as a known limitation.
- The offline evaluation isn't out-of-sample (I designed the rule while looking at those drafts);
  the live re-probe is, but small (12 turns). Single rater.
- The DM now answers place questions with fresh narration each time ("Stone walls press in… A
  heavy wooden door blocks the exit"), which invents door details; the scene-fact ledger (R1)
  is what keeps that consistent, and I haven't re-checked it against this new traffic.

## Process note

Force-added the probe traces this time and confirmed they staged: last round I'd found that
`.gitignore` had silently skipped earlier traces (R22).
