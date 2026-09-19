# 2026-09-19 — The room-description check rejected ordinary speech (REVIEW.md R21)

**Symptom.** Lines about the cold ("Is the cell always this cold?", "It's freezing in here") often
ended in the fallback "Enough talk.". `is_room_description` treated every word of the room's
description ("A cold stone cell.") as room narration, so any reply containing "cold" or "stone" was
rejected, including "I've stopped feeling the cold".

**Probe** (`probe.py`): 36 lines asked in fresh sessions, 3 tries each (cold-related lines, place
questions, controls), logging every draft, whether the room check fired on it, and what shipped.

## What the check was really doing

| Same 36 lines | Before | After |
|---|---|---|
| Room check fired | 23 turns | 2 |
| Fell back to "Enough talk." | **11** | **1** |
| Place questions answered by the DM | 0 / 12 | **12 / 12** |

Two separate problems were mixed together:

1. **Place questions** ("What is this place?", "What's it like in here?", "Is this a dungeon?")
   caused 8 of the 11 fallbacks. Here the check was *right*: he was being asked to narrate the
   scene, which is the DM's job (PRD §12). The bug was that the question reached him at all.
2. **Ordinary temperature talk** ("It's just the cold", "I've been standing in this cold") was
   rejected as narration.

## Method

Every distinct draft the old check flagged was hand-labelled *before* any rule changed
(`labels.json`): **TV** true violation (he's narrating or naming the place), **FP** false positive
(ordinary speech), **BORDER** (a plain answer to a direct question about the cold; either outcome
is fine). `evaluate.py` scores a rule against those labels, offline and deterministically.

| Rule | True violations blocked | False positives blocked |
|---|---|---|
| Old (any room word) | 24 / 24 | **5 / 5** |
| New (below) | 24 / 24 | **1 / 5** |

## The fix (two parts)

- **The check** (`engine/guardrail.py`): he may *follow* a topic the player raised and speak about
  *himself*, but may not *introduce* the scene. A room word only counts if (a) the player didn't
  just say it and (b) it's in a sentence with no first-person reference, judged sentence by
  sentence ("I'm on watch. This cell is cold." is still caught). Plural tolerance was added after
  the first version let "The stones hold the chill" through.
- **The routing** (`engine/dm.py`): anchored place-question phrasings go to the DM. Bare "this
  place" / "in here" / "cell" stay dialogue, since real lines like "I hate this place and I hate
  you" and "put me back in my cell?" are addressed *to him*.

## Caveats and what remains

- The rule was designed while looking at the same drafts the offline evaluation uses, so that
  number isn't out-of-sample. The live re-probe is: fresh samples, plus 4 lines not used before
  (12 turns: the check fired once, correctly, and none fell back).
- Single rater; 3 samples per line.
- **Known residual:** "It's freezing in here" → "Stop complaining about the cold" still fails
  (the player said *freezing*, so "cold" counts as him introducing it). It's 1 of 5 labelled
  false positives and the one remaining fallback. A synonym list would fix it, but it would be
  scenario-specific vocabulary inside a generic guardrail, so I left it.
- "Do you get many prisoners?" → "Enough to keep the cold at bay" is a genuine figurative use that
  the check retries once (no fallback).
