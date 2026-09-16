# 2026-09-16 — Closing the last state-machine gap: improvised detail becomes canon

## Context

The remaining open thread from `devlog/2026-09-15-secret-reveal-state-machine.md`: PRD §22
Gotcha #3's full scope (also CLAUDE.md's non-negotiable principle #5) — *"the moment the AI
invents something, the engine writes it to state and feeds it back forever"* — was implemented
only for the one pre-scripted secret-reveal case. Anything else the guard spontaneously invented
(a name, a place, an event from his past) lived only in free text and would eventually age out of
the 6-turn memory window with no engine-owned record of it ever happening.

Asked for a design discussion before building anything. Walked through: what the principle means,
then design questions — until redirected: *"first exercise is to not reinvent the wheel, go and
check the web for how this is done."* Found the open-source "Oracle" LLM-GM engine
(github.com/Cyb3rRon1n/oracle): a two-phase turn — a schema-constrained "decide" call produces
mechanical outcomes plus up to 3 short durable "scene facts," deduped into a persistent per-session
ledger fed back newest-first into later turns, with older facts resurfacing when named again. User:
*"I like the Oracle's approach"* → *"go ahead and build it."*

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Extraction happens *after* narration, not before | Oracle's "decide mechanical outcome, then narrate" split doesn't map cleanly onto a personality reveal — the guard only decides what to invent while performing the line, there's no clean prior mechanical decision to extract from | Mirror Oracle's before-narration decide phase exactly — rejected, no equivalent "mechanical outcome" exists here |
| A focused, separate extraction call judges each turn, not a keyword scan over the reply | This exact trap already broke twice this session (`guardrail.is_bland_dismissal`, `is_room_description` both started as keyword heuristics and needed real-model tuning to stop false-triggering). Free text is not reliably parseable by pattern matching for something as open-ended as "did this contain a new fact" | Regex/keyword scan for name-like or place-like patterns — rejected up front, same failure mode already seen twice |
| No cap on `established_facts` | v0.1 sessions are short (10-30 turns to a terminal state) — the unbounded-ledger bloat problem PRD §22 Gotcha #6 flags as "unsolved" doesn't bite at this scale. Revisit if that changes | Cap at N facts, evict oldest — premature, no evidence it's needed yet |
| `cache_prompt` reuse (already wired in, ADR from the 2026-09-13 backend swap) justifies the extra per-turn LLM call | The extraction prompt shares almost the entire brief as a cached prefix with the narration call that just ran — the added latency is closer to one cheap decode than a second full call | Skip extraction on some turns to save latency — not needed given the cache-reuse justification, added complexity for no measured problem |

## Commands

```bash
# [APPLIED] Full suite + lint after wiring the three files together —
# caught 10 stale call-count assertions across test_loop.py/test_web_server.py
# that assumed one llm.ask() per guard turn; the extraction call adds a second
uv run pytest -q
uv run ruff check engine/ tests/
```

```bash
# [APPLIED] Real backend verification: does a genuinely improvised fact get
# captured, and does the guard stay bound to it in later turns?
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.loop import run_turn
scenario = build_cell_and_guard()
scenario.guard.mood.value = 70
turns = ['What is your name, and where did you grow up?',
         'Do you have a wife or children waiting for you?',
         'What was the name of the town you mentioned?']
with GemmaHarness() as llm:
    for t in turns:
        reply, speaker, outcome = run_turn(scenario, llm, t)
        print(speaker, reply, scenario.guard.established_facts)
"
# -> town name 'Oakhaven' correctly captured on the third turn; 'Garrick'
#    (already-known name) and vague 'wife and kids, they're not here'
#    correctly NOT captured as new canon
```

```bash
# [APPLIED] Bug found by the above: extraction sometimes answers plain "No"
# instead of the prompted-for literal "NONE" -- an exact-match check let
# that slip through as a bogus fact ("- No" recorded as established canon).
# Reproduced directly, fixed with a small tolerance set, re-verified with
# the same script -- confirmed no repeat corruption and continued consistency
# ("Oakhaven" held across two further real-model turns).
```

## Outcome

Three files, working together:

- **`engine/guard.py`**: `Guard.established_facts` (list, newest-first) + `add_established_fact()`
  (dedupes case/whitespace-insensitively, rejects blanks).
- **`engine/brief.py`**: `build_guard_brief` injects the ledger back every turn under "Things
  you've already told them — stay consistent with these"; new `build_fact_extraction_prompt`
  builds the small judge-this-turn prompt (existing facts + the just-said exchange + the
  NONE-or-one-sentence instruction).
- **`engine/loop.py`**: new `_maybe_record_new_fact`, called after `guard.maybe_reveal_secret()`
  in `run_turn`'s guard-dialogue branch — a low-temperature (`FACT_EXTRACTION_SAMPLER_KWARGS`,
  unlike the in-character sampler config) separate `llm.ask()` per guard turn.

Real backend testing caught a genuine bug before it shipped: the model doesn't always say the
exact literal "NONE" the prompt asks for — plain "No" showed up in testing — and an exact-match
check let that get recorded as a fact, corrupting the ledger with garbage shown back to the model
as established canon on every future turn. Fixed with `_NO_NEW_FACT_ANSWERS`, a small tolerance
set in the same "keyword heuristic, not real intent parsing" spirit the rest of this codebase
already uses (`guard.py`'s negation window, `guardrail.py`'s dismissal/repeat checks). This is
exactly the kind of thing stub-only testing would have missed — `StubLLM` always returns a fixed
string, never "No," so the bug was invisible until run against the real model.

Also confirmed directly: a genuinely new fact ("Oakhaven," a town name volunteered on the third
turn of a real conversation) gets captured, injected into the next brief, and the guard stays
bound to it — asked again two turns later, it names the same town rather than inventing a
different one, closing the exact contradiction PRD §22 itself uses as the motivating example
("rolling green hills" then "a dark forest"). Equally important, the extraction correctly declines
to canonize vague non-facts ("wife and kids, they're not here" — no name, no place, nothing to
hold the guard to) and already-known ones (his own name, already established), rather than
over-triggering on every mention of anything personal.

10 new/updated tests (79 total, all passing): `add_established_fact` dedup/ordering/blank-rejection
in `test_guard.py`; brief injection ordering and extraction-prompt content in `test_brief.py`;
orchestration (`run_turn` records a real fact, correctly no-ops on "NONE," and correctly no-ops on
the near-miss "No" regression) plus the ten stale call-count fixes in `test_loop.py`/
`test_web_server.py`.

This closes the last open item from `devlog/2026-09-15-secret-reveal-state-machine.md` — both
named engine-rigor gaps from that session (secret-reveal, general canonization) are now real,
tested, engine-owned state rather than living only in the model's free text.

## Open threads

None specific to this mechanism. The one deferred-not-abandoned item from 2026-09-15 remains open
and unrelated: capability-driven grounding (`dm.classify_utterance`'s keyword blocklist vs. the
actual `Thing.capabilities` object graph), correctly inert until any item exists in the world.
