# 2026-09-19 — The guard's incoherence is a direction problem, not a capacity one (R18)

## Context

The user played the game on Easy and reported the guard "a bit incoherent in rationale — do we
need a rethink, as users will get bored quick if IQ is not improved." The transcript showed it:
"I need to get out" → "Try harder." (a guard encouraging his prisoner to escape), and asked what
he meant, he doubled down. I diagnosed a missing *goal*: the brief said how the guard should
*sound* but never what he was trying to *achieve*. But that was a hypothesis, and the alternative
(a 2B model is simply too small) points to a very different fix. So: measure before rebuilding.
The user agreed, including downloading Gemma 4 E4B (5.15 GB).

## What was built

- **`Guard.stance`** (authored in `scenario.py`): what he's doing in this conversation, shown in
  the static part of the brief. **`Guard.reply_intents`** (`GARRICK_REPLY_INTENTS`): what he does
  with each kind of move. `brief.describe_intent` picks the directives from the classified
  tactics: a question first ("act on the question first if asked"), then the strongest other
  move, at most two, "other" only when alone. Character data, like his mood table; empty data is
  the old undirected actor, kept reachable so the two could be compared. (`e8d2a49`)
- **The experiment**: four setups (E2B or E4B, undirected or directed) × 40 real player lines
  (the user's 10 + 30 from their earlier playtest), on Easy.
- **Blind scoring.** The setup I'd built was the one I'd be judging, so the replies were
  shuffled per line under letters and I scored them before opening the key.

## The one methodological wobble

The rubric started as R (responsive), C (consistent), F (fluent). Reading the blinded replies, I
saw those don't capture the actual complaint: an incoherent *rationale*. I added **M** ("makes
sense to a player") before unblinding and recorded that in the README. It's still a post-hoc
criterion, from a single rater who built one of the setups, which is why the scoring is committed
and the caveats are written down.

## Results (all four criteria must pass; n = 40)

| Setup | All 4 | Median s to reply |
|---|---|---|
| E2B directed | **90%** | 10.0 |
| E4B directed | 82% | 16.2 |
| E2B undirected (before) | 60% | 13.0 |
| E4B undirected | 58% | 14.5 |

Directed beats undirected on 14 turns and loses on 2 (p = 0.004). E4B alone: 8 better, 9 worse.
Direction helps both models; the bigger model adds nothing on top of it.

**Correction to something I told the user:** I'd said E4B would be "roughly twice as slow."
Measured, it's about +10% undirected and +60% against directed E2B. Not the reason to skip it, but
with no quality gain there's no reason to pay it either. (Baseline's raw latency was contaminated
by the E4B file being copied on the same disk; the README says so.)

## Outcome

The rethink the user asked for is a **rethink of how the actor is directed, not of the engine or
the model.** The directed actor is now the default; E2B stays. The E4B file (5.15 GB) is left in
`~/.orb/models/gemma-4-e4b/` in case it's wanted for something this didn't measure.

## What still fails (4 of 40) and what it exposed

- "Oi whats your name Guard" → the fallback "Enough talk." again (3 of 4 setups; the user hit it
  in their first playtest too). His real answer was fine; the engine's own anti-copy check
  rejected it. → **R19**.
- His reply direction is derived from what counted toward his *mood*, so on Easy (where the model
  can't penalise) a bribe reading was dropped and he lost the "turn the offer down" intent.
  → **R20**.

## Open threads (REVIEW.md)

R19 and R20 are both small and well-understood, and R19 hits the very first question most players
ask. R7 (automated playtesting) would make experiments like this one much cheaper: this took
about two hours of wall-clock, mostly model time.
