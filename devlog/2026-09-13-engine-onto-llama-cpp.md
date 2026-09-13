# 2026-09-13 — Swapping the engine's LLM backend onto llama.cpp/GGUF

## Context

ADR 0003 (locked earlier the same day) settled the phone spike's runtime question: ship on
llama.cpp/GGUF, not LiteRT-LM. The engine itself hadn't caught up — `engine/llm.py`'s
`GemmaHarness` (used by both the real core loop, `engine/loop.py`, and the dev CLI,
`experiments/harness/`) was a thin wrapper around `litert_lm`'s Python API. This session did the
actual swap.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Keep the `GemmaHarness` name and `PromptResult`/`.ask()` contract exactly as-is | `engine/loop.py`, `experiments/harness/cli.py`, and `tests/test_loop.py` (which stubs the `LLMClient` Protocol) all needed zero logic changes as a result — confirmed by running the full test suite unmodified | Rename to something backend-neutral — rejected, the name refers to the model (Gemma), not the runtime, and renaming would ripple through every call site for no functional gain |
| Model: `google/gemma-4-E2B-it-qat-q4_0-gguf` (official Google QAT GGUF) | Same model ADR 0001 already chose, officially quantised, no conversion step needed — confirmed via the HF API that this repo exists and ships a single ~3.3GB text-model GGUF (`gemma-4-E2B_q4_0-it.gguf`) plus a separate mmproj file we don't need | A community quant (bartowski/unsloth) — passed on since an official QAT quant was available |
| `GemmaHarness` spawns and owns its own `llama-server` subprocess, not a pre-existing one | Preserves the old self-contained "just works" UX (`with GemmaHarness(): ...`) — this host already runs three unrelated `llama-server` instances for other projects, on other ports, so "assume one is running" wasn't viable anyway | Expect an externally-managed server, harness as pure HTTP client — simpler code, but breaks the existing UX contract and needs a new manual setup step |
| `/v1/chat/completions` (OpenAI-compatible) over `/completion` | Confirmed directly (`curl` against a running server) that both endpoints expose the same `timings` object; chat/completions gets Gemma's jinja chat-template rendering for free via `--jinja` | `/completion` + manually rendering the template via `/apply-template` — more moving parts for no benefit once chat/completions was confirmed to carry timings too |
| Fixed `id_slot` per `GemmaHarness` instance + `cache_prompt: true` on every call | `engine/brief.py`'s `build_guard_brief` already puts the fully-static block (persona, voice examples, scene, drives, backstory) first and the dynamic tail (recent memory, mood) last — llama.cpp's automatic longest-common-prefix matching reuses that static prefix turn-to-turn for free, **without** needing to redesign the brief or accumulate raw conversation history (which would contradict PRD §4's "rebuild fresh" design) | Redesign brief.py around an accumulating session — rejected outright, contradicts the PRD; not needed anyway once LCP-prefix reuse was confirmed to work with the existing fresh-rebuild design |
| `--reasoning off` on the spawned server | **Found live, not assumed:** Gemma 4's chat template defaults to a chain-of-thought "thinking" pass. A first real test with a 96-token budget came back with `content: ""` — the entire budget got consumed by `reasoning_content`. `llama-server --help` documents `--reasoning [on\|off\|auto]`; `off` fixed it immediately (verified: `content: "I'm here."`, `finish_reason: "stop"`) | `--reasoning-budget 0` (what this host's other pre-existing servers already use) — equivalent effect, `off` is more explicit for a use case that never wants a thinking channel at all |
| DRY sampling (`dry_multiplier`, `dry_allowed_length=2`, `dry_penalty_last_n=256`) as the replacement for litert-lm's `NoRepeatNgramConfig` | Nearest llama.cpp equivalent to a hard "no repeated 3-gram" constraint, aimed at the same failure mode (verbatim repetition of the guard's own recent lines, which are embedded in the brief) | Not validated against real transcripts yet — flagged as needing the same empirical tuning process `brief.py`'s own docstring already documents for prompting, not assumed correct on paper |

## Commands

```bash
# [APPLIED] Dependency swap, via uv so the lock file stays in sync
uv remove litert-lm
uv remove --group dev httpx
uv add "httpx>=0.27" "huggingface-hub>=0.25"
```

```bash
# [APPLIED] Confirmed timings + cache_prompt semantics directly against a
# running (unrelated) llama-server on this host before writing any code
curl -s -X POST http://127.0.0.1:45072/completion \
  -H "Content-Type: application/json" \
  -d '{"prompt":"...","n_predict":8,"id_slot":0,"cache_prompt":true}'
# -> timings.cache_n went from 0 (no cache_prompt) to a real nonzero count
```

```bash
# [APPLIED] The bug that mattered most this session
curl -s -X POST http://127.0.0.1:8092/v1/chat/completions -d '{...,"max_tokens":96}'
# -> content: "", reasoning_content: "*** User input: \"Hello\" ***..." (truncated by max_tokens)
# Fixed by adding --reasoning off to the llama-server launch args.
```

```bash
# [APPLIED] Full end-to-end verification
uv run orb-harness setup --yes                                    # downloads the GGUF
uv run orb-harness prompt "Hello" --system "You are a terse guard."  # real reply + sane timings
printf "Please, I mean no harm.\nI just want to talk.\nWhat's your name?\nexit\n" \
  | uv run orb-engine                                              # full scripted playthrough
uv run pytest -q                                                   # 47 passed, unmodified
```

## Outcome

Full rewrite of `engine/llm.py`'s `GemmaHarness` internals (model download via `huggingface_hub`,
server subprocess lifecycle, `/v1/chat/completions` calls with streaming for real TTFT
measurement, `PromptResult` field mapping from llama.cpp's `timings` object). Zero changes needed
to `engine/loop.py`, `experiments/harness/cli.py`'s logic, or `tests/test_loop.py` — only a few
docstrings/help strings in the CLI got updated to describe the new backend accurately. All 47
existing tests pass unmodified.

Ran a real scripted 3-turn playthrough end-to-end (`uv run orb-engine` with piped stdin) and read
the server's own log rather than trusting the harness's numbers blindly: **turn 1 evaluated the
full ~600-token brief cold (14.36s, 41.8 tok/s); turns 2 and 3 only needed 176-179 fresh tokens
each** (a ~70% reduction) — real, measured confirmation that the fixed-`id_slot` +
`cache_prompt: true` approach gets genuine prefix-cache reuse out of `brief.py`'s existing
rebuild-fresh-each-turn design, no rearchitecting required. Replies were coherent and in-character
("Try.", "Talk? You'll get what you want.", "Garrick. Now hush." — the last one a verbatim reuse of
a `VOICE_EXAMPLES` few-shot line rather than a fresh line, a prompting-quality note for later, not
a backend bug).

The `--reasoning off` finding is the one worth remembering hardest: without it, the engine would
have silently produced `content: ""` for every single reply once the token budget ran out on
thinking rather than an answer, and nothing in the wiring code itself would look wrong. Found by
testing a real call rather than assuming the swap "should just work" once talking to the right
endpoint.

## Open threads

- [ ] DRY sampling's anti-repetition behaviour hasn't been validated against real transcripts the
  way `brief.py`'s prompting has — worth watching for the same verbatim-repetition failure modes
  documented there (devlog 2026-09-08) before trusting it's an equivalent fix.
- [ ] The verbatim reuse of a `VOICE_EXAMPLES` line in the test playthrough above is worth a closer
  look — not a regression from this swap (the same risk existed with litert-lm), but now's a
  natural point to notice it.
- [ ] `--ctx-size 4096` and `--threads 4` are reasonable defaults carried over from this host's
  other llama-server instances and the spike's own thread-count finding, not independently tuned
  for this engine's actual brief sizes — fine for now, revisit if it matters.
- [ ] No automated test covers the real llama.cpp wiring itself (only the stubbed `LLMClient`
  Protocol) — reasonable for now (needs a real model + server), but worth a real integration test
  once CI/hardware makes that practical.
