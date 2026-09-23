# 2026-09-23 — Reply direction follows what the player did (R20)

## Context

Picking the project back up after a gap: the newest open finding was R20. On Easy the classifier
can never penalise, so a clear bribe ("You have time to help me get gold") resolved to `other`
for the mood — fine, that's what Easy is for — but `describe_intent` read the *same* resolved
tactics, so he also lost the "turn the offer down" directive and said "Gold is dead. Keep
talking." Mood and reply are two questions that had been answered as one.

## The fix, and the flaw in my first version

Split them: `Guard.last_move` stays what counted toward mood; new `Guard.last_did` is what the
player did, and `describe_intent` reads that. My first cut had direction hear a penalising
reading from Easy's credit floor (0.1), which is the natural reading of R20's own wording.

Before shipping it I remembered *why* Easy drops penalising labels at all (`Difficulty`'s
docstring: the harmful spike errors were kind lines read as hostile, diffusely) and measured
instead of assuming. `probe.py`, 3 runs per line, identical each time: the reported bribe was
**0.95-0.96**, dominant — but "I'm sure your brother was a good man." read `insult=0.10`, exactly
the credit floor. My version would have had him coldly shut down a kind remark. Direction now
hears a penalising reading only when dominant (Hard's 0.5 floor). Hard is unchanged.

## Live result

Real Gemma 4 E2B, full brief, Easy, 3 tries per line: bribe lines turned down **9/9** ("I'm a
watchman. I'm not for sale."), sympathy got the sympathy directive, insults still got shut down,
and no kind line got a hostile directive. Full table in
`experiments/2026-09-23-reply-direction/README.md`. 190 tests pass.

## Two slips worth keeping

- My `verify.py` first crashed: `build_guard_brief` needs `clock=` since R2 and I called it the
  old way. Trivial, but it cost a full server spawn to find out.
- The `.jsonl` evidence needed `git add -f` (R22's standing rule) — I remembered because R22 was
  literally my own past mistake.

## Left open

- **R23 (new):** the same probe shows weak *crediting* readings (~0.10) steering direction on
  Easy — "I'm sure your brother was a good man." also got `question`, so he was told to "Answer
  what they asked" about a statement. R20's "hi anyone there" (other 0.77 + question 0.22) is the
  same family. Whether direction wants a higher floor for weak readings is a separate call.
- R20's other note, "Look I can help" read as a request: the probe shows `bribe=0.50, request=0.37`
  — a genuinely ambiguous line sitting on Hard's penalty floor. Not touched.
- R15 still awaits the user's own playtests on Easy vs Hard.
