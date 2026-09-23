# 2026-09-23 — A floor so weak readings don't steer his reply (R23)

## Context

R23 was a finding I raised the same afternoon while fixing R20: after splitting reply direction
(`last_did`) from the mood reading (`last_move`), direction still read *every* tactic the mood
credited. On Easy the mood credits from 0.1 — deliberately generous, so faint persuasion still
registers — so a spurious `question=0.10` on the plain statement "I'm sure your brother was a
good man." told him to "answer what they asked" about nothing.

## Measure the floor, don't guess it

The instinct is to pick a number. Instead I hand-labelled twelve lines with the moves that are
*really* there and read every label's probability (`floor_probe.py`). The gap was clean: real
moves ≥ 0.40 (usually ≥ 0.8), spurious secondaries ≤ 0.22, genuine compounds ("I'm sorry. How did
it happen?" question=0.40; "Nothing I can spend in here" bribe=0.63/request=0.33) ≥ 0.33. So
`DIRECTION_FLOOR = 0.3`, applied to reply direction only, on top of the mood credit floor.

The probe also settled something I'd half-assumed: **the classifier is dominant-label in
practice.** Most compound lines collapse to one label ("You're good at your job, and I'm innocent."
→ flattery=0.99, argument=0.00). So the floor trims noise, not real compounds — the multi-label
machinery (R15/R17) earns its keep on the minority of lines that genuinely split.

## Half of the original complaint was not a bug

R20's note bundled "hi anyone there → answer-the-question directive" with the statement case. But
in the real opening context "hi anyone there" reads `question=0.37–0.48` (and "anyone there?" →
0.95, "is someone there" → 0.98). A presence-query genuinely *is* a question; "answer them" is a
fair directive, and the replies ("You're in the way. Keep talking.") aren't broken. Catching it
would need the floor above 0.4 — which would drop the genuine compounds at 0.33–0.40 and undo the
R18/R15 coherence. So I left it, and said so in the review status rather than quietly cranking a
number until one borderline line looked right at the cost of real ones.

## Verified

`verify_r23.py`, real Gemma 4 E2B, full brief, Easy: the brother statement gets the empathy
directive both tries; a real question still gets answered. 192 tests pass.
