# 2026-09-09 — Running the real engine loop against the phone

## Context

After today's spike work (see `2026-09-09-spike-llm-alive-on-poco-m4-pro.md`), a different
question: what does the actual harness — `engine/loop.py`'s `run_turn`, DM/guard routing, the
mood dial, the retry-on-bland guardrail, memory — feel like end to end with `poco-m4-pro` as the
backend, instead of raw curl benchmarking? `engine/llm.py`'s `GemmaHarness` is hard-pinned to
desktop LiteRT-LM (by design — it's the real shipping runtime), so there's no existing way to
point the real loop at a llama.cpp server. Wrote a throwaway adapter rather than touching
`engine/llm.py` or `experiments/harness/` (both deliberately LiteRT-LM-only) — lives in scratch,
not the repo, since this was a one-off "what does this feel like" check, not new tooling anyone
asked for.

## What was done

A small `PhoneLlamaCppClient` implementing `engine/loop.py`'s `LLMClient` protocol
(`.ask(prompt, system_message, sampler_config) -> result.response`) against the phone's
OpenAI-compatible `llama-server` endpoint, mirroring `engine/llm.py`'s own
`DEFAULT_SAMPLER_CONFIG_KWARGS` / `RETRY_SAMPLER_CONFIG_KWARGS` so the comparison wasn't
sampling-biased either way. Ran the real `build_cell_and_guard()` scenario through 8 scripted
player lines covering all three DM routes (dialogue, narration via "I look around", refusal via
"I cast a spell") plus a kind line, a verbatim repeat of it, a rude line, and a thank-you — enough
to exercise the mood dial in both directions and the repeat guardrail.

## Outcome

**Character held up.** Garrick stayed clipped and in-character throughout, including under
repeated pleading to open the door — matches the brief's explicit instruction that the door isn't
his to open in words. The DM's narration and refusal replies stayed in-world with no rules
exposition ("The air remains still. The door is still shut.").

**The mood dial matched `engine/guard.py`'s arithmetic exactly, every turn**, checked by hand
against the actual deltas: 40→35, 35→28, 28→24, 24→27. First real end-to-end confirmation that
the engine's own logic is correct against a live remote model, not just passing in isolation.

**Felt latency is materially worse than the hot-run's TTFT number, and there's a clear reason
why.** Per-turn wall time ranged 5.7s–26.5s (avg ~17s) vs. the hot run's 1.33s TTFT median. Real
play switches system prompts every turn (guard brief vs. DM-narration brief vs. DM-refusal
brief), so none of them get the prefix-cache reuse (`LCP similarity`) that flattered the hot
run's numbers — that run hammered one fixed brief 192 times in a row. Real play also waits for
the full reply, not just the first token, and the bland/repeat guardrail can silently trigger a
second full model call on a given turn. **The 1.33s TTFT figure in `spike/results/` is real but
optimistic relative to how an actual conversation will feel** — worth remembering before treating
it as *the* number for the whole experience. Not a contradiction of that result, just a different
thing being measured.

## Findings

- **`adjust_mood_from_text` has no negation handling** (already flagged as a first-sketch
  heuristic in `engine/guard.py`'s own docstring, not a surprise) — "I didn't mean to **hurt**
  anyone" gets scored as a threat purely because the literal word "hurt" is present. Confirmed
  live, not just theoretically.
- **Real routing bug found:** `dm.classify_utterance` checks `ENVIRONMENT_QUERY_PATTERNS` as bare
  substrings, and `"look"` is one of them. "Have you ever thought about **looking** the other
  way?" — clearly guard dialogue, a persuasion attempt — matched `"look"` inside "look**ing**" and
  got misrouted to the DM as an environment query instead of reaching the guard at all. Not fixed
  here (design is locked, this wasn't the point of the session) — just recorded.

## Open threads

- [x] `dm.classify_utterance`'s substring match on `ENVIRONMENT_QUERY_PATTERNS` needs a word
  boundary — fixed same day: split into `ENVIRONMENT_QUERY_WORDS` (word-set match, like
  `UNGROUNDED_WORDS`) and `ENVIRONMENT_QUERY_PHRASES` (substring match, safe for multi-word
  phrases). Regression test added in `tests/test_dm.py`; full suite green (47 passed).
- [ ] If per-turn latency in real play matters for future tuning, worth a hot-run variant that
  rotates through the three actual system prompts (guard/DM-narration/DM-refusal) rather than one
  fixed brief, to get a TTFT number that reflects real cache-miss behavior rather than the
  best case.
