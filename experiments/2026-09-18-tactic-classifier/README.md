# 2026-09-18 — Tactic-classifier spike (REVIEW.md R5)

**Question:** can Gemma 4 E2B, already loaded for narration, label *what kind of move* a player's
line is (empathy, a bribe, a threat…) accurately and fast enough to decide the guard's mood
*before* he replies? Today that job is done by keyword lists, which missed most of the real
persuasion in the 2026-09-16 playtest.

## Prior art (researched first, not reinvented)

- **Façade** (Mateas & Stern) maps player text to *discourse acts* (praise, criticize, flirt,
  ally…); a separate drama manager decides what each act does to each character. That's the shape
  used here: *the classifier labels the act; the character's own table decides the effect.* It
  also took them ~6,800 hand-written template rules to make keyword-style NLU work, which is why
  our keyword list was never going to catch up.
  [Natural Language Understanding in Façade](https://eis.ucsc.edu/papers/MateasSternTIDSE04.pdf)
- **Tactic labels** adapted from persuasion research: *Persuasion for Good* (Wang et al. 2019;
  logical appeal, emotional appeal/empathy, credibility…) and Cialdini's principles (reciprocity
  → bribe, liking → flattery). [Persuasion for Good](https://arxiv.org/pdf/1906.06725),
  [Survey of computational persuasion](https://arxiv.org/html/2505.07775v1)
- **llama.cpp's own mechanics**: a GBNF `grammar` forces the answer to be exactly one label, and
  `logprobs` gives a confidence score from the same call.
  [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## Method

- `dataset.json`: 43 real player lines addressed to the guard (two 2026-09-16 playtests, the hostile
  lockout run, the negation regressions), each with the guard's previous line for context and every
  label a reasonable annotator would accept. Hand-labelled by Claude Opus 5; single annotator, so
  treat accuracy as indicative.
- 10 labels: empathy, flattery, bribe, plea, request, argument, threat, insult, question, other.
- Two prompt variants: **zero-shot** (label definitions only) and **few-shot** (definitions plus 10
  examples written separately from the test set). Temperature 0, grammar-constrained, the static
  prompt cached in its own llama.cpp slot, so each call only processes the new line.
- Baseline: the current keyword heuristic (`Guard.adjust_affiliation_from_text`): does it register
  the line at all?
- `spike.py` runs it; `trace.jsonl` logs every call (full request/response, timings);
  `results.json` holds the summary.

## Results (this host: OCI ARM64, CPU-only)

| | Keyword baseline | Gemma zero-shot | Gemma few-shot |
|---|---|---|---|
| Lines that should move the mood and did register | **10 / 26** | — | — |
| Accuracy (label in the accepted set) | — | **88%** (38/43) | 91% (39/43) |
| Warm latency per line (median) | ~0 | **1.8 s** | 2.4 s |
| First (cold) call | — | 5.8 s | 7.4 s |

The keyword baseline missed every bribe, the innocence argument, the flattery and most of the
sympathy. It never pushed the mood the *wrong* way on any line, though: it's precise but misses
most lines.

**Confidence is an effective safety signal.** The dangerous model errors (a kind line labelled as
hostile, which would *punish* sympathy) were all low-confidence: "To avenge your brother's
death?" → threat (0.15), "I'm sure your brother was a good man" → insult (0.21). With a floor of
0.4, below which the line counts as neutral, zero-shot accuracy on the kept lines is 95% (38/42
kept).

**One confident error**: "Open it or else." → request (0.61). The keyword list catches it ("or
else"), which suggested a hybrid.

### Hybrid: keyword override for hostility + model labels + confidence floor

| Variant | Accuracy | Set aside as neutral | Wrong non-neutral labels |
|---|---|---|---|
| **Zero-shot, floor 0.4** | **93% (40/43)** | 4 | 1, harmless: "Can you help me please, what is your name?" → request (gold: plea) |
| Few-shot, floor 0.4 | 91% (39/43) | 3 | 2 |

With the hybrid there are **no harmful errors**: no kind line punished, no hostile line rewarded.

**Few-shot isn't worth it.** Its examples make the cached prefix longer, and every new token
attends to the whole prefix, so each call gets slower (2.4 s vs 1.8 s). It bought no accuracy once
the hybrid rules were applied.

## Verdict

The approach works. The recommended build is **zero-shot labels + a keyword override for hostility
+ a 0.4 confidence floor**, feeding a per-character susceptibility table that the engine owns.

Latency is the real cost: about **+1.8 s per guard turn on this host**. On the phone it's
unmeasured (the phone's prefill is faster than this cloud CPU; see ADR 0003). There are two ways
to pay for it:

1. **REVIEW R4** (speak first, extract facts after) removes ~2.5–3.5 s from every turn's critical
   path, so R4 + R5 together would still be *faster* than today.
2. A follow-up spike could fold the label into the narration call itself (the Oracle one-pass
   "decide, then narrate" shape), avoiding the second prefill entirely, at the cost of labelling
   under the persona prompt. Not tested.
