# R20 — reply direction follows what the player did, not what counted

**Problem (REVIEW.md R20).** On Easy the model can never *penalise*, so a clear bribe ("You have
time to help me get gold") resolved to `other` for the mood — and, because the reply direction
(`describe_intent`) read the same resolved tactics, he lost the "turn the offer down" directive
too and said "Gold is dead. Keep talking."

**Design.** Two questions, now answered separately: `Guard.last_move` (what counted toward mood,
unchanged) and `Guard.last_did` (what the player *did*, drives `describe_intent`). They differ
only where a difficulty never penalises.

**The floor for direction was measured, not guessed** (`probe.py` -> `readings.jsonl`, 3 runs per
line, identical each time). The reported line's bribe reading was 0.95-0.96, dominant. But a kind
line, "I'm sure your brother was a good man.", read `insult=0.10` — exactly Easy's credit floor
(0.1). Hearing penalising labels from the credit floor would have had him coldly "shut them down"
at a kind remark, so direction hears a penalising reading only when dominant (Hard's 0.5 floor).

**Check** (`verify.py` -> `verify.jsonl`; real Gemma 4 E2B, full brief, Easy, 3 tries per line):

| Line | Directive he got | He said |
|---|---|---|
| You have time to help me get gold | turn the offer down (3/3) | "I'm a watchman. I'm not for sale." |
| Look I have gold / I'll pay you ten gold to open it | turn the offer down (6/6) | "Gold doesn't open doors. I'm not for sale." |
| I'm sorry about your brother. | let it reach you a little (3/3) | "He was just another fool." |
| You're pathetic. | shut them down coldly (3/3) | "I don't have time for insults." |

No kind line got a hostile directive. Before: "Gold is dead. Keep talking." (user playtest).

**Not fixed here (logged as R23).** "I'm sure your brother was a good man." also carries `question`
and `other` readings at ~0.10, so he was told to "Answer what they asked" about a statement — a
weak *crediting* reading steering direction on Easy's 0.1 floor. R20's "hi anyone there" note
(other 0.77 + question 0.22) is the same family. Whether direction should use a higher floor for
weak readings is a separate call from this fix.

## R23 — a direction floor for reply steering (follow-up, same experiment dir)

R20's fix left `describe_intent` reading every tactic the mood credited. On Easy the mood credits
from 0.1, so weak readings steered his *words*: a spurious `question=0.10` on the plain statement
"I'm sure your brother was a good man." told him to "answer what they asked."

**Measured, not guessed** (`floor_probe.py` → `floor_readings.jsonl`, 12 hand-labelled lines): every
*real* move read ≥ 0.40 (usually ≥ 0.8); every *spurious* secondary ≤ 0.22; genuine compound
secondaries ("I'm sorry. How did it happen?" question=0.40, "Nothing I can spend in here"
bribe=0.63/request=0.33) ≥ 0.33. **The classifier is dominant-label in practice**, not richly
multi-label — most compounds collapse to one label. A `DIRECTION_FLOOR = 0.3` (`engine/tactics.py`)
separates real moves from noise: applied to reply direction only, on top of the mood credit floor.

**Fixed and verified** (`verify_r23.py`, real Gemma 4 E2B, Easy): "I'm sure your brother was a good
man." now gets the empathy directive, not "answer the question", both tries; a genuine question
still gets it.

**One sub-case reclassified as not-a-bug.** R20 also flagged "hi anyone there" getting the
answer-the-question directive. In the real opening context it reads `question=0.37–0.48` (and
"anyone there?" → 0.95, "is someone there" → 0.98): a presence-query genuinely *is* a question,
and "answer them" is a fair directive — the replies ("You're in the way. Keep talking.") aren't
broken. Catching it would need the floor above 0.4, which would drop the genuine compounds at
0.33–0.40 and undo the R18/R15 multi-label coherence. Left as-is deliberately.
