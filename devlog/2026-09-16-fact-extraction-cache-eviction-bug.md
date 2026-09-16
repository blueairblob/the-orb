# 2026-09-16 — Real playtest catches a self-inflicted latency regression

## Context

User played the guard directly in the terminal (`uv run orb-engine`) for the first time since
today's fact-canonization work landed, and reported ~10 second gaps between every single turn —
not just the first — plus asked whether this was just an inherent property of the model
("Google E2B"). Worth a real answer, not a guess, given this session's whole rigor pattern has
been "verify against the real backend, don't assume."

## Investigation

Timed a cold `llm.ask()` call directly: 14.1s wall time, of which 13.2s was time-to-first-token —
almost entirely prefill of the ~557-token brief (42.6 tok/s prefill on this CPU-only ARM64 host,
no GPU). That alone explains a slow *first* turn. But a second, identical narration call in the
same harness session came back in 72ms (`cache_n: 556` — llama.cpp's prefix cache reusing almost
the entire prompt) — so the design ADR 0003 committed to (fixed `id_slot`, `cache_prompt: true`)
does work when nothing else touches that slot in between.

Reproduced the actual per-turn call sequence `run_turn` makes (narration, then today's new
fact-extraction call) and checked `timings.cache_n` at each step:

```
narration 1  cache_n=0    prompt_n=557
extraction   cache_n=2    prompt_n=130
narration 2  cache_n=1    prompt_n=556   <- same brief prefix as narration 1, but no reuse at all
```

Root cause confirmed: `GemmaHarness` hardcoded `id_slot=0` for *every* call, and llama.cpp's
prefix cache is per-slot — one live KV sequence at a time. The fact-extraction call (added earlier
today, a short, structurally unrelated prompt) was running on the same slot as narration, right
between one turn's narration and the next turn's narration — evicting the cached brief prefix on
every single turn. The mechanism that was supposed to make turn 2 onward fast was being reset
every turn by code added the same day, before anyone had actually played a multi-turn session
against it. Confirmed the server had spare slots available (`/slots` showed 4, llama.cpp's
implicit default) that were never being used.

## Fix

Gave `GemmaHarness` a second slot (`--parallel 2`, explicit rather than relying on the implicit
default) and an `id_slot` parameter on `ask()` (default: the instance's usual slot 0).
`engine/loop.py`'s `_maybe_record_new_fact` now passes a dedicated `FACT_EXTRACTION_ID_SLOT` (1),
so the two prompt shapes never contend for the same cache.

## Verification

```bash
# [APPLIED] A 4-turn stable-band conversation, checking timings.cache_n per turn
uv run python3 -c "
from engine.llm import GemmaHarness
from engine.scenario import build_cell_and_guard
from engine.brief import build_guard_brief
scenario = build_cell_and_guard()
with GemmaHarness() as llm:
    for line in ['hello there', 'how are you keeping?', 'quiet night, is it?', 'has it been a long watch?']:
        brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)
        r = llm.ask(line, system_message=brief)
        print(r.raw_response['timings'])
        scenario.guard.adjust_affiliation_from_text(line)
        scenario.guard.remember('player', line); scenario.guard.remember('guard', r.response)
"
```

Result: turn 1 cold (`cache_n=0`, 12.8s prefill); turns 2-4 reused 406/429/450 of ~600 cached
tokens, prefill dropping to ~6.2-6.6s — roughly half the cold cost, sustained turn to turn rather
than resetting every time.

## Outcome

Real bug, real fix, real numbers — not a claim about "the model being slow." Two things remain
true and are worth being direct about, since the user asked specifically:

1. **This CPU-only ARM64 cloud host is not representative of the shipping target.** ~40 tok/s
   prefill / ~4-13 tok/s decode with no GPU is genuinely slow compared to what the phone spike
   measured (ADR 0003, `spike/results/`) — CLAUDE.md already flags "desktop will flatter latency,"
   but this box is a *cloud* CPU, not even a fast desktop GPU — if anything it may undersell real
   phone performance rather than flatter it. Not investigated further here; noted so it's not
   mistaken for representative.
2. **A band-crossing turn still forces a large re-prefill.** `brief.py` deliberately places the
   current mood band's voice examples early in the prompt, right after `PERSONA` (a considered
   quality decision, devlog 2026-09-15: a single always-shown example set measurably produced
   flat, band-inappropriate tone). Since that block changes whenever affiliation crosses a
   threshold, it invalidates the cache from that point forward on exactly those turns. Real,
   understood, **not fixed here** — moving band examples later in the prompt would trade some of
   their proven effectiveness for cache stability, a tradeoff that deserves its own discussion
   rather than a silent reorder.

87 tests passing (test doubles updated to accept/record the new `id_slot` kwarg).

## Open threads

- Whether the band-examples-vs-cache-stability tradeoff is worth revisiting is an open question,
  not decided here.
- Separately noticed while testing: the guard's own reply "Try again." (a real, in-character but
  fairly content-free line) isn't caught by `guardrail.is_bland_dismissal` (only
  nothing/silence/quiet trigger a retry) — a minor gap, not investigated further, flagged for
  whenever guardrail tuning comes up again.
