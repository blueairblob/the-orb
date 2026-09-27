# Inky's Gym character prototype — a bash re-implementation of the Orb's engine

**Reference only. No engine change is proposed here.** This folder is a drop from the
sibling project `inkys_gym`, which — while evaluating small local models for Hermes'
CPU-only fallback role — grew a bash/`jq` re-implementation of the Orb's own
director/actor machinery. That was scope drift for the gym (its remit is exercising
models for a role, not acting), so the character work was moved here, where the Orb
already owns these concepts in Python. It is kept as a **cross-implementation
reference and a log of findings** that happen to confirm several of the Orb's own
design bets on a *different* language, harness, and model host.

Everything below was run against **Gemma 4 E2B** (the Orb's shipping model, ADR 0003)
via `llama.cpp`, plus smaller candidates (Qwen3.5 0.8B "Inky", Spark-X2.5 1.7B/4B),
on a CPU-only OCI ARM64 box. Small samples throughout (typically 3 runs) — read these
as directional, not proven.

## What's here

| Path | What it is | Orb equivalent |
|---|---|---|
| `sheets/inky-janitor.json` | terse persona + mood dial + per-band voice examples | a `Character` sheet |
| `sheets/inky-janitor-actor.json` | the improvise-freely "actor" sheet used for the canon work | — |
| `prototype/exercise/character.sh` | brief-builder + rolling memory + mood + guardrail loop | `engine/brief.py`, `engine/character.py` |
| `prototype/lib/canon.sh` | persistent fact ledger: extract, dedupe, topic-word lookup, contradiction check | `engine/save.py` + brief recall |
| `prototype/lib/repeat.sh` | fuzzy self-repeat detector (`near_repeat`) | `engine/guardrail.py` |
| `prototype/tests/*.sh` | offline + model-backed unit tests for the two libs | — |
| `results/*.txt` | raw transcripts cited below | — |

## Findings, and how they map onto the Orb

### 1. The Character-Engine pattern ports, but has a coherence floor
A character sheet walked into a fresh system brief every turn (persona + 2–3 hard
rules + a short *verbatim* memory of recent lines) is the same shape as `brief.py`.
It produced coherent, in-character replies on **Gemma 4 E2B** every turn — and
incoherent output (non-sequiturs, verbatim loops, emoji tics) on a 0.8B model, which
no amount of sheet-trimming or sampling tightening rescued. **Confirms:** the Orb's
"the model needs to be obedient and consistent, not clever" holds — but there is a
size floor below which even obedience collapses; 0.8B is under it, ~2B (Gemma E2B) is
over it. The gym also independently re-derived the Orb's finding that a *wider* memory
window makes small models *more* repetitive, not less.

### 2. A harness-side anti-repeat guardrail works — for verbatim, not tonal, sameness
`repeat.sh`/`character.sh` port `guardrail.is_repeated_reply` + the retry-then-fallback
path (retry at a *higher* temperature, since a low-temp resample reproduces the same
bad line). Exact-match catches verbatim loops cleanly. It does **not** catch *tonal*
sameness (every reply opening the same way but not word-identical). Later work added a
**fuzzy** check (`near_repeat`, `results/2026-09-24-near-repeat.txt`): a reply repeats
if a ≥5-word sentence overlaps an earlier one by ≥0.75 word-set Jaccard, or the whole
reply overlaps by ≥0.5 (thresholds from 12 labelled T1/T5 pairs; clear copies scored
0.89–1.00 per sentence, distinct answers ≤0.50). Live it made turn-5 answers distinct
3/3 vs 2/3 without losing the underlying facts. **Relevant to `guardrail.py`** if the
Orb ever sees near-copy (not exact) repetition from the guard — the thresholds and the
"keep a reworded retry over falling back to a canned line" rule are the transferable bits.
Also re-found the Orb's own same-day bug: a fallback line written in third person is a
persona violation.

### 3. Per-band mood *directives* don't move observable tone — examples might
The mood dial (a `Stat` with bands + deltas, negation-aware; = the Orb's `Stat` +
`Guard.affiliation`) drove tone correctly at the mechanism level — bands and crossings
verified directly at both extremes on both models. **But observable tone barely moved,
even on Gemma**, and reweighting the per-band *directive text* (even with "this
overrides your general nature") did nothing (A/B table in `FINDINGS` §4). This
**directly re-confirms `brief.py`'s decision to remove per-band directives because
instruction text loses to concrete examples.** The untried lever — the one the Orb's
note says actually works — is exaggerating the per-band *examples* themselves.

### 4. "Improvised detail becomes canon" is the hard part, and mostly a lookup problem
This is PRD §22 Gotcha #3 / `save.py`, re-implemented as `canon.sh`. Findings that may
inform the Python side:
- **The reported failure (a fact stated, then re-asked, gets a different answer) is
  fixed by putting the model's own relevant facts back in front of it** — and the win
  came from *recall*, not from the contradiction check (which rarely fired). So the
  brief-side recall is doing the work; a heavy consistency judge is secondary.
- **Recall must be semantic, not word-shared.** v1 only matched when the question
  shared a word with the fact ("rounds at three" never surfaced for a "quiet" question).
  v2 added extractor-emitted topic words + rarity weighting + a "when/what time" →
  pull time-bearing facts rule, which closed the reported misses (`canon-tests.txt`, 23/23).
- **Check clock times by rule, not by model.** A 2B judge cleared consistent replies
  6/6 but caught only 4/6 contradictions — and both misses were *different clock times*,
  exactly the case that matters. A deterministic time rule + the judge got it to 11/12.
- **Normalise numbers/times before dedupe.** "after 2 a.m." vs "after two in the
  morning" were stored as two facts; worse, the digit-dropping dedupe silently discarded
  a genuinely *conflicting* later fact ("after 4 a.m.") as a duplicate. Number-word→digit
  and clock-phrase normalisation (~30 lines of `jq`, no embedding model) fixed both
  (`canon-normalise-tests.txt`, 31/31). Deliberately **not** solved: true paraphrases
  sharing no words ("wipes down conduits" / "cleans the pipes") — the one place an
  embedding model would earn its keep; measure how often it actually happens in a real
  ledger first. Embedding models were rejected here because they're weak on numbers
  (rating "after 2 a.m." ≈ "after 4 a.m."), which is exactly wrong for a continuity ledger.
- **A small extractor stores junk** (filler, moods-as-facts, behaviours-as-facts). Needs
  a parser/junk filter; the greedy first version discarded real facts and had to be
  anchored to the end of the fact.

## Bottom line for the Orb
Nothing here asks the engine to change. Three of its locked decisions were independently
re-confirmed on a different stack (size-floor obedience, memory-window repetition,
examples-beat-instructions). The canon work is the richest transferable material if the
Python `save.py`/brief-recall path is ever revisited: **semantic recall is the lever,
clock-time contradictions want a deterministic rule, and number/time normalisation is a
cheap dependency-free win** — with an explicit, measured note on when (and only when) an
embedding model would be worth adding.
