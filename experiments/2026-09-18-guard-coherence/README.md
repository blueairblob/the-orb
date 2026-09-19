# 2026-09-18 — Is the guard's incoherence direction or capacity? (REVIEW.md R18)

**Question.** A real Easy playtest showed an incoherent guard ("I need to get out" → "Try harder.";
asked what he meant, he doubled down). Is that missing *direction* (nothing tells the actor what
his reply should achieve, which the engine can fix cheaply), or missing model *capacity* (which
only a bigger model fixes)?

**Setups** (`run.py`), each replaying the same 40 real player lines through a fresh Easy session,
run exactly as a real session runs (`play_turn` then `finish`):

| Setup | Model | Actor |
|---|---|---|
| `baseline` | Gemma 4 E2B | undirected: today's brief before R18 (empty stance and intents) |
| `directed` | Gemma 4 E2B | **stance + engine-chosen reply intents** (`Guard.stance`, `GARRICK_REPLY_INTENTS`) |
| `e4b` | Gemma 4 E4B (5.15 GB) | undirected |
| `e4b_directed` | Gemma 4 E4B | directed |

Lines: the user's 10 from their Easy session + 30 from their 2026-09-16 playtest.

**Scoring.** Blind: `blind.py` shuffles the four replies per line under letters A-D and hides
the setups; I scored each reply *before* opening `key.json`. Criteria: **R** responsive, **C**
consistent with his role and earlier lines, **F** fluent, **M** makes sense to a player.
*M was added after I had read the blinded replies and before unblinding*, because R/C/F don't
capture the user's actual complaint, an incoherent rationale. A reply must pass all four.
`judgments.json` is the scoring; `score.py` unblinds and aggregates.

## Results (n = 40 turns per setup)

| Setup | Responsive | Consistent | Fluent | Sensible | **All 4** | Median s to reply* |
|---|---|---|---|---|---|---|
| **directed** (E2B) | 92% | 100% | 98% | 90% | **90%** | **10.0** |
| e4b_directed | 92% | 98% | 100% | 82% | 82% | 16.2 |
| baseline (E2B) | 85% | 88% | 98% | 60% | 60% | 13.0 (24.0 raw) |
| e4b | 80% | 85% | 92% | 70% | 58% | 14.5 |

\* Baseline's raw median (24.0 s) is an artifact: its first 10 turns ran at 27 s while the E4B
file was being copied on the same disk; its last 30 turns are 13.0 s. Timings are single runs on
a shared CPU-only host; read them as rough.

Paired sign tests on the all-4 pass/fail, per turn:
- **directed beats baseline: 14 turns better, 2 worse (p = 0.004).**
- E4B vs baseline: 8 better, 9 worse (p = 1.0). **A bigger model alone does nothing.**
- E4B + directed vs E2B + directed: 4 better, 7 worse (p = 0.55). **No sign E4B adds anything on top.**
- Direction also helps E4B (e4b_directed vs e4b: 15 better, 5 worse, p = 0.04): it's the lever on
  either model.

On the user's own 10 lines, directed answers "I need to get out" with "The door stays locked. It's
my watch." (undirected: "The door is locked. You want to get out."), and "I have gold" with "Gold
buys nothing here." (undirected: `"Gold." I just have to wait.`).

## Verdict

**It's a direction problem, not a capacity problem.** Telling the actor what he's doing and what
his reply should achieve moved coherent replies from 60% to 90%; doubling the model moved them
from 60% to 58%. Directed E2B is also the fastest setup, so there's no reason to switch models.
The directed actor is now the default (`scenario.py` stance, `guard.py` intents).

Correction to my earlier estimate: E4B is not "roughly twice as slow" here. It's about +10% on
undirected briefs and +60% against directed E2B (16.2 s vs 10.0 s). Not a reason to skip it, but
with no quality gain it isn't worth it either.

## Caveats

- **One rater**, and the builder of the winning setup: mitigated by blinding, not removed. The
  scoring is committed (`judgments.json`) so anyone can rescore.
- n = 40, one sample per line; the model samples at temperature 0.6, so a rerun would differ.
- M was added post hoc (before unblinding, after seeing replies).
- 30 of the 40 lines come from one earlier playtest; all runs are on Easy.
- E4B may still be better at things this doesn't measure (richer prose, longer memory).

## What's still wrong in the winning setup (4 of 40)

1. **"hi anyone there" → "You're here. Now stop talking."** A greeting classified as
   other + question got the question directive and a bad answer.
2. **"Oi whats your name Guard" → "Enough talk."** The safe fallback: he copies the name example
   from his own few-shot examples, the engine rejects the copy twice, and the fallback ships. It
   happened in 3 of 4 setups, and in the user's own first playtest before that.
3. **"Look I can help" → "The door stays locked."** Read as a request, so he refused something
   nobody asked for.
4. **"You have time to help me get gold" → "Gold is dead. Keep talking."** Classified as
   `other`: on Easy the model can't penalise, so the bribe reading was dropped, and with it the
   "turn the offer down" intent. His reply direction should come from what the player *did*, not
   from what counted toward the mood dial.
