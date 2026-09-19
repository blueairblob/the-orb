# 2026-09-19 — Why asking his name shipped "Enough talk." (R19)

## Context

R19, found in the R18 comparison: asking the guard his name (the most natural first question)
often got the fallback line "Enough talk." The user picked it to fix next ("r19").

## Investigation: measure first

A probe (`experiments/2026-09-19-name-question/probe.py`) asked each line in a fresh session, three
times, logging every draft the engine saw. The name question, six ways: **14 of 18 turns ended in
the fallback**, and 16 of 18 first drafts were a verbatim copy of his own example
`"What's your name?" -> "Garrick. Now hush."`, for *every* phrasing, including "Tell me your name".
His other example prompts copied rarely (2 of 9) and their retries always escaped; control lines
never copied.

So the bug was one example, not the check. "Garrick. Now hush." is the singularly correct answer,
so the model treated the whole line as the answer. It also explained something odd from
2026-09-14: the verbatim-example check's *only* documented incident was this exact one. That
day's devlog had already predicted the fix: *"if it's common, the underlying voice-examples
themselves may need rewriting... rather than just catching it after the fact."* I'd considered
filtering examples by word overlap with the player's line, but "What do they call you?" shares no
words with "name", so it would only half-fix it.

## Fix and result

Replaced the identity example, per mood band, with a personal question no one asks verbatim
("Do they pay you well?"), keeping three prompt shapes per band. Same probe: **0 of 18 fallbacks**,
0 of 18 first-draft copies, his name in 15 of 18 replies (the other 3, "I'm the guard…" to "Who are
you?", are fine). A test pins that no example prompt is the name question.

## The risk I checked: tone

Those examples exist to make his mood audible, and I'd replaced one of three per band. A blind
side-check (old vs new example set, shuffled X/Y, judged for warmth before unblinding):

- Round 1 (5 lines): old 2, new 1, ties 2. Slightly leaning old, and I could see why: the old warm
  example carried an explicit warm signal ("Friends call me that").
- I reworded the new one to restore it ("Not enough, friend. It's kind of you to ask.") rather
  than argue from 5 lines, and re-tested on 10 fresh lines: old 2, new 3, ties 5.
- Combined: **old 4, new 4, ties 7.** No evidence of harm. Small and single-rater, so not proof.

## Two things found on the way

- **R21.** The tone check's cold-related lines ended in the fallback, and I verified why: the
  room-description check flags any reply containing "cold" or "stone" (the room is "A cold stone
  cell."), including "I've stopped feeling the cold", a personal remark. Logged, not fixed here.
- **R22, my own mistake.** The repo's `.gitignore` deliberately skips `experiments/*/*.jsonl`, so
  the traces behind the tactic-classifier and fact-precision experiments were never committed,
  though my commit messages said "full trace committed". `multilabel_analysis.py` couldn't run from
  a fresh clone. Force-added the curated evidence and noted the rule in `REVIEW.md`.

## Open threads (REVIEW.md)

R20 (his reply direction should follow what the player did, not what counted toward mood) and R21
(the room-description false positives) are both small and understood. R21 is the more visible to a
player: asking about the cold is a natural thing to do in a cell.
