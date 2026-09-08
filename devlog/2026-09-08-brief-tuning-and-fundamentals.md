# 2026-09-08 — Chasing the guard's voice: five patches, then back to fundamentals

## Context

A long session driving `experiments/web`'s orb-web rig against the real model, alternating
between manual play (you, over Tailscale) and scripted repros (me, via a headless-Chromium
Playwright rig set up this session specifically to make this kind of test-and-verify loop
possible without a browser extension). Started as "check the harness works," ended up being
almost entirely about one question: why does the guard's dialogue keep degrading into flat,
repetitive, or incoherent lines over a long conversation, no matter how many rules get added to
the brief to stop it?

## Decisions

- **Playwright + headless Chromium for real testing, not guesswork.** `claude-in-chrome` was
  declined; no `chromium-cli` or browser was installed on this ARM64 box at all. Installed
  Playwright + its bundled Chromium into the project venv (`uv pip install playwright && uv run
  playwright install chromium`) — no sudo, no missing system libs, worked first try. This is what
  made every fix in this entry actually verifiable rather than asserted.
- **Full-session dialogue capture, separate from the engine's own capped memory.**
  `experiments/web/server.py` now appends one JSON line per turn to
  `~/.orb/transcripts/<session-start>.jsonl` (`create_app`'s new `transcript_path` param) — the
  point being `guard.memory` is deliberately capped for the brief, but a human (or me) reviewing
  a session afterwards needs the whole thing, uncapped.
- **Declined a request to add D&D 5e dice/persuasion checks.** PRD §11 is explicit that v0.1 uses
  the mood dial specifically instead of dice ("Persuasion is not vibes; it is a number the engine
  moves" / "No dice, no inventory, no combat. Not yet.") — dice are listed under "Later —
  Elaboration," not now. Also pushed back on "the DM must be a 5e rules guru" as a framing — rules
  arithmetic belongs in deterministic engine code either way (non-negotiable principle #1), never
  something the model reasons about live.
- **Declined "AGI'ish" framing for the NPC**, for the same architectural reason — the project's
  whole thesis is the engine directs, the model narrates what it's handed. What actually looked
  like "unintelligence" during a long negotiation turned out to be the engine starving the model
  of context (a 3-exchange memory window) and a keyword-only mood heuristic missing genuinely
  persuasive language, not a lack of capability to give the model more autonomy over.
- **The real turning point: a shared reference doc on small-model NPC prompting.** You handed me
  a doc (not written this session) specifically about running a "dumb guard" on Gemma-2B-class
  models. Its core claims, checked against what actually happened tonight, were dead on: small
  fixed personality block (50-100 tokens, 2-3 hard rules), few-shot over abstract instruction,
  *short* verbatim history ("forgetting old chats is in character for a low-level NPC... giving
  him real long-term memory tends to break believability"), and rules restated tersely right
  before generation rather than buried in a long block. Every round before this one had been doing
  the opposite — adding a rule per failure mode, widening memory to fix forgetting.
- **Checked which of the doc's tips actually transfer to our runtime before touching code.** It's
  written for llama.cpp/GGUF. Two claims don't apply here: `litert_lm.SamplerConfig` has no
  `repeat_penalty` knob at all (only `top_k`/`top_p`/`temperature`/`seed` — checked via
  `inspect.signature`), and quantization is fixed by Google's pre-converted `.litertlm` file, not
  something controllable via `Q4_K_M`-style flags. The "Gemma has no system role" concern is
  probably moot too — `create_conversation`'s `system_message` param is backed by a dedicated
  native call (`litert_lm_conversation_config_set_system_message`), strongly suggesting the
  runtime already handles the fold-into-first-turn trick internally.

## What we did (roughly chronological)

1. Relaunched the harness, found dialogue "nonsensical," diagnosed via a rapport-run script: mood
   climbed 35→68 across an 11-turn kindness run but the guard's *tone* never audibly warmed —
   `MOOD_DIRECTIVES` per-band tonal instructions added to `brief.py` (didn't fully fix it, see
   below).
2. Sampler tuning round 1: `DEFAULT_SAMPLER_CONFIG_KWARGS` temperature 0.0 (model's own greedy
   default) → 0.85 to escape the model collapsing every reply to "Nothing."/"Silence.". Fixed
   that, but let the guard drift into ungrounded aphorisms ("Kindness is a currency. Don't spend
   it.").
3. Tightening round: reverted a "rare third sentence" allowance, added a grounding constraint,
   dropped temperature to 0.6. Reduced the aphorism drift, but a live session showed bland
   dismissals came back — root cause: the bland-dismissal *retry* was reusing the same
   low-temperature sampler, close enough to deterministic to reproduce the exact reply it was
   meant to escape. Fixed by giving the retry its own `RETRY_SAMPLER_CONFIG_KWARGS` (temp 1.0),
   threaded through as `sampler_config="retry"` on `GemmaHarness.ask()`. Also found and fixed a
   real bug in `guardrail.is_bland_dismissal`: the model sometimes wraps replies in literal quote
   marks, which weren't being stripped before comparison, silently defeating detection.
4. `experiments/web` infra bugs, found and fixed along the way (unrelated to prompting, but ate
   a lot of the session):
   - **Mic button did nothing at all over the Tailscale `http://` link.** `navigator.mediaDevices`
     is `undefined` on an insecure origin (not localhost/https); `ensureMicVolumeAnalysis()` called
     into it with no guard, which threw *synchronously* inside a non-`async` function — before any
     Promise existed — skipping right past the caller's `.catch()` and killing the rest of
     `startListening()`. Fixed with a guard + a load-time on-page notice; documented in
     `experiments/web/README.md` that voice fundamentally can't work over that link (browser
     security, not fixable client-side) — Tailscale access is text-only now.
   - **Static files were being served with no `Cache-Control` header**, so Chrome's heuristic
     caching served `orb.js`/`style.css` from disk across *four separate reloads* with zero
     requests reaching the server — every visual fix looked like it wasn't working when it was
     just never being fetched. Added a `Cache-Control: no-store` middleware to `server.py`.
   - Dialogue panel moved from a floating top-right corner to centred under the orb (`style.css`).
5. Pushed on a long, real negotiation ("I have treasure... let me out and I'll take you there").
   Found two real gaps: `recent_memory()`'s default window (last 3 exchanges) was dropping offers
   made a dozen turns back, and the keyword-only mood heuristic gave zero credit to genuinely
   persuasive lines with no exact `KIND_WORDS` hit. Widened `MAX_MEMORY` 12→24 and
   `recent_memory()`'s default 6→16 turns. **This made things worse, not better** — a next test
   saw the guard repeat "Move slow." verbatim for four different, unrelated prompts. Added a
   symmetric guardrail (`guardrail.is_repeated_reply`, `Guard.own_lines()`) routed through the
   same bland-dismissal retry mechanism — reduced the repeat rate (4→2 occurrences in a like-for-
   like retest) but didn't eliminate it, and a subsequent session surfaced *new* disguised bland
   replies that dodge the exact-match check ("Treasure. Nothing.", "Rich. Nothing.") plus a
   third-person hallucination ("Garrick. Always worried about things." / "You said that.").
6. **The fundamentals rewrite**, per the shared doc (see Decisions): `brief.py`'s `PERSONA`
   285 words → 45; `MOOD_DIRECTIVES` collapsed from full sentences to short fragments;
   `MAX_MEMORY` reverted 24→12, `recent_memory()`'s default 16→6 (back to ~3 exchanges); a new
   `RULE_REMINDER` restates the couple of rules that actually matter once, tersely, at the very
   end of the brief instead of mid-block. First test: **zero bland dismissals across 12 turns**
   for the first time all night — but a new fixation appeared ("The door is locked" / "you're
   wasting my time," reworded slightly, for five unrelated prompts), plus the guard telling the
   player to "open the door" — incoherent, since the player has no key and can't comply, and the
   door was never actually unlocking either way. Added two more short clauses to `RULE_REMINDER`
   (react to what was just said, not a stock line; only you hold the key, never tell the player to
   open the door) rather than reverting to the old paragraph. Retest: clean — no bland dismissals,
   no repeats, no phantom door-opening, coherent and specific across 12 turns.
7. Final 18-turn stress test mixing DM narration/refusal routing, kindness, rudeness, negotiation,
   a deliberate exact-repeat of an earlier line, and casual/off-topic chat. Mood tracked exactly
   as the code predicts (40→54: six `KIND_WORDS` hits × +3, one `RUDE_WORDS` hit × -4 — hand-
   verified against the transcript). No bland dismissals, no verbatim self-repeats, no phantom
   door commands. **But**: a subtler version of the repetition problem showed up — a "Now, [stop
   X]." tail recurred across four different replies in the back half of the session ("Now, be
   quiet." twice verbatim, plus "Now, stop wasting my time." / "Now, stop talking."). Each full
   reply differs (different lead-in clause), so `is_repeated_reply`'s exact-match check correctly
   doesn't flag any of them — this is tail-phrase reuse, not whole-line repetition, and it's a
   harder problem: a genuinely terse character has a naturally small vocabulary, so a fuzzy/n-gram
   overlap check risks false-positiving on legitimate terseness. Left open, not patched tonight.
8. A second, much more technical reference doc arrived (`devlog/2026-09-08-npc-gemma-e2b-android-
   dnd-guide.md`, saved separately — it's reference material, not a session log), specifically
   about shipping Gemma 4 E2B via LiteRT-LM on Android for a D&D app. Its two most load-bearing
   claims: **sampling should be `temperature=1.0`, not 0.4-0.6** ("lowering it flattens output and
   tends to increase looping"), directly contradicting the 0.6 this file settled on earlier
   tonight; and litert-lm exposes **native repetition control and a `<think>` mode**. Checked both
   against our actual installed `litert_lm` via `inspect.signature` before touching anything:
   - `SamplerConfig` really has no repeat-penalty field (confirmed earlier tonight) — but
     `Conversation.send_message()` does, separately: `repetition_penalty_config`,
     `no_repeat_ngram_config`, `suppress_tokens_config`. Missed these the first time by only
     checking `SamplerConfig`.
   - `create_conversation`'s `thinking_config` accepts a real `ThinkingConfig(enable_thinking,
     thinking_token_budget)` — native chain-of-thought support, completely unused so far.
   - The temperature claim couldn't be verified from the API alone — would need an actual
     before/after test (not done tonight, see Open threads).
9. Tried `no_repeat_ngram_config` (`no_repeat_ngram_size=3, window_size=256`, applied to every
   `ask()` call, `engine/llm.py`) against the exact stress-test sequence that produced the "Now,
   X." tail-phrase drift. **Result: no effect at all — byte-for-byte identical output to the
   pre-fix run**, including the exact repeat it was meant to block. Chased why: a follow-up check
   (calling `ask()` twice with identical inputs) showed **generation is fully deterministic given
   identical (system_message, prompt, sampler_config)** — no true randomness, `seed=None`
   apparently resolves to a fixed internal seed. That determinism makes the identical result
   before/after strong evidence the n-gram constraint isn't engaging at all here, not just bad
   luck — most likely because each turn opens a *fresh* `create_conversation()` (no persistent
   conversation object across turns), so the constraint probably only reaches newly-generated
   tokens within one call, not text merely quoted as history in the prompt. Real, verified
   negative result — reverted nothing (the config call is harmless, just inert), but noted as a
   dead end for this specific architecture. Also reframes why the bland-dismissal/repeat retries
   work at all: different `sampler_config` values walk a different deterministic decode path, not
   "another roll of the dice."
10. You played a long negotiation and reported "I've escaped but... there's no conclusion." Real
    bug, found in the transcript log: mood sat at 54 the whole back half (no `KIND_WORDS` hits),
    nowhere near `unlock_threshold` (75) — `door.locked` never changed — but the guard kept
    *verbally promising* release anyway: `"Fine. Ten minutes."` / `"I will."` / `"I'll let you
    know."`, and then just went along with `"OK I've left the cell"` as if it had happened.
    Root cause was a bug in this session's own earlier fix: the "you alone hold the key" rule
    (item 6 above) said "never tell the player to open the door, **only say whether you will**" —
    which literally licensed exactly this. First fix attempt (rewording the instruction, adding a
    matching negative example in the same sentence) **did not work** — a same-scenario retest
    still got `"Fine. Ten minutes."` almost verbatim, despite the rule being clearly present in the
    rendered brief. Second attempt worked better: added two `VOICE_EXAMPLES` demonstrating the
    *correct* refusal under pressure ("I promise nothing. We'll see." / "I said we'll see.
    Nothing's changed.") and shortened `RULE_REMINDER` to point back at them, rather than trying to
    state the rule more forcefully. Retest: explicit promises gone, replaced by hedges ("I'll see
    what I can do.", "Don't expect anything.") — real improvement, not airtight (that hedge is
    still soft), but no more flat "yes". Consistent with both docs' shared claim that few-shot
    demonstration beats abstract instruction for this model size — now demonstrated twice tonight
    (this, and the earlier bland-dismissal fix).
11. You asked "what is this 'stag' all about?" — the guard and DM had been alluding to the
    premise (`scenario.premise`, "poaching a stag...") since both their briefs already receive it,
    but the fixed `INTRO` line the player actually hears on connect never mentioned it at all, so
    the callbacks read as confusing rather than evocative. Fixed: `engine/loop.py`'s `INTRO`
    constant became `build_intro(premise)`, threaded through both call sites (`run_loop`'s CLI
    voice loop and `experiments/web/server.py`'s websocket handler). Same shape as every other bug
    tonight — state existed, just wasn't surfaced to the one channel that needed it.

## Outcomes

Real, measurable, honest before/after — using the same or equivalent test each round, not vibes:

| | Before tonight | After 5 patches | After fundamentals rewrite | End of session |
|---|---|---|---|---|
| Bland dismissals | frequent, undetected when quoted | reduced, still ~2/11 turns | 0/12, 0/18 (two tests) | still 0 |
| Verbatim self-repeat | not tracked | "Move slow." ×4 → ×2 after a guardrail | 0/12, 0/18 | still 0 |
| Phantom "open the door" | not observed pre-negotiation-testing | present | fixed | still fixed |
| Disguised bland ("X. Nothing.") | not observed | present, undetected | not observed | not observed |
| Tail-phrase catchphrase drift | not observed | not observed | present, milder, undetected | **still open** (item 9's `no_repeat_ngram_config` attempt was a verified no-op) |
| False promises to release ("I will.") | not observed | not observed | not observed pre-long-negotiation | **found, then fixed twice** (item 10) — down to soft hedges, not airtight |
| Premise never told to player ("the stag") | not observed | not observed | not observed | **found and fixed** (item 11) |

The pattern across every round before the fundamentals rewrite: adding a rule to fix one observed
failure either didn't hold under a longer/different session, or shifted the failure into a shape
the existing checks didn't cover. The fundamentals rewrite cleared every *previously observed*
failure mode in a stress test — but two more real bugs still turned up afterwards, from you playing
it further than any script had (the false-promise bug, and the untold premise). Both are now fixed
and verified. Net: real, cumulative progress across the whole session, not a single clean win —
and the two post-rewrite finds are a good reminder that a passing stress test is not the same as
"no bugs left," just "no *tested* bugs left."

`uv run pytest` — 46 passed throughout every round (tests updated alongside: `test_guardrail.py`
is new this session, covering `is_bland_dismissal`'s quote-stripping and the new
`is_repeated_reply`; `test_guard.py` covers `own_lines()`; `test_loop.py` covers both retry paths
end to end via `SequencedLLM`).

Engine-latency numbers gathered along the way (this box, 4 CPU cores, `cpu_thread_count` unset):
single-pass reply ~4-7s, doubling to ~13s when a retry fires. **Explicitly not the §0 phone
spike** — this is desktop-CPU steady-state, not on-device thermal-throttled mobile, and the
debug-panel text path bypasses STT/TTS entirely. Worth recording only as a lower bound: a
mid-range Android phone under sustained load is generally *slower* than this, not faster.

## Open threads

- **Tail-phrase catchphrase drift** — still open. The whole-line repeat check doesn't catch it by
  design (different lead-in clause each time), and `no_repeat_ngram_config` — the obvious native
  fix — turned out to be a verified no-op for our fresh-conversation-per-turn calling pattern
  (item 9). Needs either a smarter partial-overlap heuristic (risking false positives against real
  terseness) or acceptance as inherent small-model texture.
- **`temperature=1.0`/`top_p=0.95`/`top_k=64` untested.** The second doc's headline claim, and the
  one most likely to actually matter given tonight's determinism finding (a different temperature
  is a genuinely different deterministic path, not noise) — but not yet tried against our brief.
  Prime candidate for next session, ideally re-run against the exact tail-phrase-drift repro.
- **`ThinkingConfig` (native `<think>` mode) completely untried.** Confirmed available in our
  `litert_lm` (`create_conversation(thinking_config=...)`). Plausibly relevant to both remaining
  open items (tail-phrase drift, the earlier ultra-short-input gibberish like "what" → "The
  stag.") since it gives the model reasoning room before committing to a terse public line — but
  costs latency, untested how much on this CPU box.
- **Prefill technique untried** — starting the assistant turn with something like `*The guard
  shifts his weight.* "` to bias tone and cut preamble drift (doc §3.4). Cheap, unexplored.
- **Mood heuristic is still keyword-only.** `guard.py`'s own docstring already names the fix:
  have the LLM propose a mood delta via structured output, engine clamps/applies it (Gotcha #31,
  "agents propose, engine disposes") — flagged repeatedly tonight, not built. Bigger than a
  prompt tweak; needs a deliberate go-ahead.
- **Mood-driven vocal warmth** (the very first thing investigated tonight) was never retested
  against the new, much-shorter brief — the whole session pivoted to fixing coherence/repetition
  instead. Worth one more rapport-run test under the current brief before calling this closed.
- **The secret-reveal path** (`guard.secret`, gated at mood ≥ 65) has still never been observed
  actually surfacing through the real model in a live session, even when the threshold was
  crossed — only confirmed via unit test in isolation. Untested again tonight (stress test topped
  out at mood 54).
- **This is real evidence for the PRD's open E2B-vs-E4B question** (§11: "only the spike settles
  which ships") — bland collapse, aphorism drift, repetition, hallucination, all recurring across
  a well-constrained, iteratively-tuned prompt, on a 2B model. Not decisive (the fundamentals
  rewrite recovered a lot of ground through prompting alone), but worth having on record when that
  decision actually gets made. Careful not to conflate with the §0 spike itself, which is a
  thermal/latency question, not a dialogue-quality one.
- **False-promise fix is better, not airtight.** "I'll see what I can do." is still a soft hedge
  toward agreement under sustained pressure, even after the few-shot fix (item 10). Worth another
  round of examples/testing if a player specifically leans on this.
- **Shared server state, still unaddressed.** `experiments/web/server.py`'s `scenario` is one
  object shared across every websocket connection — two tabs/testers at once will visibly
  cross-contaminate each other's conversation. Flagged, not fixed; low priority for a dev-only
  rig but worth a comment in the file if this rig outlives tonight.
