# 2026-09-19 — Why asking his name ships "Enough talk." (REVIEW.md R19)

**Symptom.** Asking the guard his name, the most natural first question, often got the fallback
line "Enough talk." (the user's first playtest; 3 of 4 setups in the R18 experiment).

**Probe** (`probe.py`): each line asked in a fresh session, 3 times, logging every draft the engine
saw. Name question phrased six ways (18 turns), lines matching his other example prompts, and
control lines matching none.

| | Before | After |
|---|---|---|
| Name question → fallback | **14 / 18** | **0 / 18** |
| First draft was a verbatim example copy | 16 / 18 | 0 / 18 |
| Other example prompts → fallback | 0 / 9 (copied 2 / 9, retry always escaped) | 0 / 12 |
| Control lines → fallback | 0 / 9 | 0 / 9 |

**Root cause.** His few-shot example `"What's your name?" -> "Garrick. Now hush."` is the
*singularly correct* answer, so the model treated the whole line as the answer, for *every*
phrasing ("Tell me your name", "hey what is your name"). The engine's anti-copy check (built
2026-09-14, and the only incident it was ever built for was this one) rejected the copy, the retry
copied again, and the fallback shipped. The 2026-09-14 devlog predicted this: *"if it's common,
the underlying voice-examples themselves may need rewriting (less 'obviously singularly correct'
answers) rather than just catching it after the fact."* Filtering examples by word overlap would
only half-fix it ("What do they call you?" shares no words with "name").

**Fix.** Replace the identity example, per mood band, with a personal question no one asks
verbatim ("Do they pay you well?"), keeping three prompt shapes per band. He now answers with
fresh, in-voice lines ("Garrick. That's all you need to know.", "I am Garrick. Now stop wasting my
time."), and names himself on 15 / 18; the other 3 ("Who are you?" → "I'm the guard…") are also fine.
The new example still gets copied when someone asks its exact prompt (3 / 3 first drafts), but the
retry escaped every time (0 fallbacks), which is the well-behaved version.

## Side-check: did swapping the example weaken mood tone? (`tone_check.py`)

Same lines answered with the old and new example sets at "ready to help" (mood 92); replies
shuffled under X / Y and judged for warmth *before* unblinding.

- Round 1 (5 lines): old 2, new 1, ties 2. The old warm example carried an explicit warm signal
  ("Friends call me that"), which mine lacked.
- The new warm-band example was reworded to restore it ("Not enough, friend. It's kind of you to
  ask."). Round 2 (10 fresh lines): old 2, new 3, ties 5.
- **Combined 15 lines: old 4, new 4, ties 7.** No detectable warmth loss. That's small, blind,
  single-rater evidence of no harm, not proof.

## Found on the way (REVIEW.md R21)

Two of the tone-check lines about the *cold* ended in the fallback. `is_room_description` treats
every word of the room's description ("A cold stone cell.") as room vocabulary, so any reply
containing "cold" or "stone" is flagged: including "I've stopped feeling the cold", a personal
remark exactly like his own examples.
