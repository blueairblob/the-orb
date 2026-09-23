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
