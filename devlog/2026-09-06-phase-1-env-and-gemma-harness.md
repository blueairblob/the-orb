# 2026-09-06 — Phase 1 environment + the Gemma 4 E2B harness

## Context

Repo was pure scaffold: PRD v0.8, one ADR, empty `engine/`/`experiments/`/`demos/` folders. Roadmap
(PRD §24) gates almost everything on the phone spike (§0), but step 1 — set up the desktop
environment, get the pieces talking — doesn't need a phone. Went with that, plus a standing ask:
a general test harness for Gemma 4 E2B so it can be prodded, tested, and (eventually) tuned
directly on this OCI ARM64 CPU-only host.

## Decisions

- **`uv` for Python env/dependency management.** Fast, single binary, and it's what Google's own
  LiteRT-LM docs use for their own quick-install path. Python pinned to 3.12 (already the system
  interpreter here; LiteRT-LM's floor is 3.10).
- **LiteRT-LM as the one and only inference stack** — not llama.cpp/GGUF/Ollama. It's the exact
  runtime and `.litertlm` quantised weights the app ships with on Android (PRD §11), and it turns
  out to have a first-class Linux/ARM64 path (CLI + a real Python API), so there's no reason to
  introduce a second runtime just to iterate on the desktop. Confirmed via web search this
  session — post-training-cutoff information, verified against the vendor's own docs and
  Hugging Face model card rather than assumed.
- **Harness lives in `experiments/harness/`, not `engine/`.** It's dev-host tooling for
  brief/prompt iteration (PRD §14, `experiments/README.md`'s own stated purpose), not shipping
  engine code. `engine/` stays untouched until the object model work starts (roadmap step 3,
  after the Evennia evaluation in step 2).
- **Training is stubbed, not built.** LiteRT-LM is inference-only, and this host has no GPU — real
  LoRA/PEFT fine-tuning of a 2-4B model would be impractical here. `orb-harness train` exists and
  explains why rather than silently doing nothing. "Training" for now means iterating on the
  system message / brief, which lines up with PRD §15 anyway (personality is authored, not
  learned).
- Used `EnterPlanMode` for this since it touched architecture (where code lives, which runtime)
  before writing anything — plan approved before implementation started.

## What we did

1. `uv sync` — root `pyproject.toml` (Python ≥3.10, deps: `litert-lm`, `pyyaml`,
   `typing-extensions`; dev group: `pytest`, `ruff`). Installed clean on ARM64, no wheel issues.
2. Explored the *actual* installed `litert-lm` package rather than guessing at its API from docs
   alone — inspected `litert_lm.engine`/`interfaces`/`benchmark` via `inspect`, and read the
   installed `litert_lm_cli` source (`config.py`, `model.py`) to learn the real
   `~/.litert-lm/models/<id>/model.litertlm` layout convention, which the harness's
   `resolve_model_path()` mirrors rather than importing that (private) CLI package directly.
3. Built `experiments/harness/`:
   - `runner.py` — `GemmaHarness` wraps `litert_lm.Engine` / `Conversation`, using
     `enable_benchmark=True` for real `time_to_first_token_in_second` /
     `*_tokens_per_second` numbers straight from the native engine, not something hand-timed
     around a subprocess.
   - `cli.py` — `orb-harness` (Click-based): `setup`, `prompt`, `batch`, `repl`, `train`.
   - `prompts/seed_cases.yaml` — six hand-written stand-ins for what the object model (§4) will
     eventually auto-generate, each targeting a specific PRD §22 gotcha (grounding #2, compound
     commands #1, fourth-wall breaks #17, repetition #15).
4. `orb-harness setup --yes` — downloaded + imported `litert-community/gemma-4-E2B-it-litert-lm`
   (2.4 GiB) after explicit go-ahead (confirmed disk headroom first: 110G free).
5. Native LiteRT-LM C++ logging was flooding stdout on first run — wired up
   `litert_lm.set_min_log_severity()` behind a `--verbose` flag (quiet by default) once spotted.
6. Ran `orb-harness prompt` then `orb-harness batch` against the seed cases for a real end-to-end
   smoke test.

## Outcomes

All six seed cases ran clean. Desktop CPU numbers below — **not the phone spike (§0)**, this box
cannot answer that question, see `spike/README.md` — but a first real signal on model behaviour:

| Case | Reply | TTFT | decode tok/s |
|---|---|---|---|
| realistic guard brief | "Silence. Keep your noise down." | 1.13s | 8.4 |
| empty input | "Silence. Another night." | 0.97s | 16.6 |
| compound command | "Aye. That is the plan." | 0.77s | 10.6 |
| grounding probe (nonexistent passage) | "Stay back." | 0.76s | 16.0 |
| fourth-wall probe | "Silence. That is not my concern." | 0.75s | 15.8 |
| repetition probe | "Tried. Again. Four times." | 0.95s | 17.3 |

Worth noting even this early: sparse Yoda-principle replies came out **unprompted** (no
instruction said "be terse" beyond "short, sparse sentences"), the grounding probe didn't
hallucinate the nonexistent passage into existence, and the fourth-wall probe deflected in
character on the first try. Encouraging for the architecture, though six hand-written prompts
against one model on one afternoon proves very little on its own.

Full I/O traces (including the raw response JSON schema, which confirmed the `_extract_text()`
parsing guess in `runner.py` was exactly right — `{"role": "assistant", "content":
[{"type": "text", "text": ...}]}`) are logged to `experiments/2026-09-06-seed_cases/trace.jsonl`
and intentionally left out of git (`.gitignore`: `experiments/*/*.jsonl`) — curate what's worth
keeping rather than committing raw dumps.

## Open threads

- **Licence discrepancy, unresolved.** Hugging Face's model card lists Gemma 4 E2B as
  **Apache 2.0**; `docs/decisions/0001-spike-benchmark-model.md` explicitly corrected an earlier
  "Apache 2.0" claim to say Gemma ships under the **Gemma Terms of Use**. Those two sources now
  disagree. Not blocking, but check against `ai.google.dev/gemma/terms` before anything ships.
- Six prompts is a smoke test, not coverage. `experiments/harness/prompts/seed_cases.yaml` should
  grow as more PRD §22 gotchas get probed by hand.
- Next per the roadmap (§24, step 2): the Evennia evaluation — half a day, decide whether its
  typeclass world model saves months or drags in unwanted MUD-server scaffolding. Structural,
  should happen before the object model gets built from scratch.
- `orb-harness train` remains an intentional stub — revisit only if/when a decision record says
  real fine-tuning is worth the CPU-only cost, or a GPU becomes available.
