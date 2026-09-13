# The Orb

An **audio-first, AI-narrated roleplay engine** — showcased through a family-friendly fantasy
escape adventure, but the real product is the reusable engine underneath.

> **The one-liner:** an interactive podcast — you listen, you speak, the story answers.
> Hands-free, eyes-free. Playable on a commute, a dog walk, or whilst chopping onions.

The engine is a **harness**: it constrains a general-purpose model down into a specific,
reliable, bounded role. Conventional game code owns the world's *brain* (state, rules, memory);
the LLM owns only its *mouth* (the words). That split is the whole idea.

---

## Status

**The cell-and-guard proof of concept (PRD §8) runs end to end, in text mode, on the desktop.**
Object model, guard Character Engine, brief-builder, guardrail, and core loop are all built
(`engine/`) and exercised against the real Gemma 4 E2B model via `orb-engine`. Both terminal
states — talk your way to an unlock, or push the guard to a lockout — are reachable.

What's still **not** built is real voice. This desktop dev host has no audio hardware at all, so
`engine/voice.py` defines a swappable protocol and only a text-mode backend exists so far — the
real Android on-device STT/TTS backend is Phase 2, on a device that actually has a microphone
and a speaker.

The **one piece of genuine uncertainty** is the hardware spike (§0) — does a small model run
acceptably on a warm mid-range Android phone? That question is now **resolved as a qualified
pass-leaning result, on the runtime the engine will actually ship on** (`poco-m4-pro`, MediaTek
Helio G96):

- **LiteRT-LM (the runtime originally assumed to ship) fails.** CPU fails both halves outright
  (~2s fixed prefill-bucket floor over the ~1s TTFT bar, *and* +25-30% thermal latency growth over
  21 minutes). GPU clears the thermal half cleanly but still fails TTFT (~3.2s/turn, same
  prefill-bucket floor). Chased the floor via a custom re-export with a smaller bucket — a dead
  end: it surfaced an unrelated ~11x decode-speed regression in the public `litert-torch` export
  pipeline, confirmed independent of the bucket via a controlled re-export. No fix found. NPU is
  not a usable lever either way (gated behind a separate vendor program, and this chip's AI block
  isn't aimed at LLM workloads regardless).
- **llama.cpp/GGUF — originally tested only as "the pessimistic stand-in" — is closer to passing
  than the runtime that was supposed to ship**, and is now the chosen runtime
  ([ADR 0003](docs/decisions/0003-shipping-llm-runtime-gguf.md)): **1.33s median TTFT** with real
  session/KV-cache reuse, and **flat latency across a full 18.1-minute hot/pocket run** — no
  thermal degradation at all.
- **Still open:** 1.33s is close to the ~1s bar but not yet confirmed under it — one more focused
  round of GGUF tuning (quantisation, thread count) is the natural next step before calling §0 a
  clean pass rather than "pass-leaning."

Everything built so far is desktop engine logic, deliberately kept separate from the spike (see
`CLAUDE.md`, "This dev host vs the phone"). Full detail, raw traces, and the open-threads list:
`spike/results/2026-09-09-poco-m4-pro.md` (the GGUF baseline) and
`spike/results/2026-09-10-poco-m4-pro-litert-lm.md` (LiteRT-LM, and why it was dropped).

Current decisions locked:

- **Spike benchmark model: Gemma 4 E2B** (ADR 0001) — model family unchanged; only the runtime
  packaging changed (see below).
- **Shipping LLM runtime: llama.cpp / GGUF, not LiteRT-LM.** See
  [ADR 0003](docs/decisions/0003-shipping-llm-runtime-gguf.md).
- **Prototype language: Python**, desktop-first. The phone shell is a deliberately separate,
  later phase.
- **World model: build fresh, not on Evennia.** Evaluated hands-on and declined — its object
  model is inseparable from a Django+Twisted multiplayer server stack. See
  [ADR 0002](docs/decisions/0002-evennia-evaluation.md).

## Repo map

| Path | What's here |
|---|---|
| `docs/PRD.md` | **The canonical PRD (v0.8).** Single source of truth. Read this first. |
| `docs/decisions/` | Architecture Decision Records — one file per locked decision. |
| `docs/archive/` | Superseded working docs (e.g. the completed cleanup action plan). |
| `spike/` | The go/no-go hardware benchmark. `spike/README.md` defines the pass mark and how to log results. |
| `engine/` | Phase 1 Python engine — object model, guard, brief-builder, core loop. Runs (text-mode voice). |
| `experiments/` | Model / prompt / brief experiments run on the dev host. One dated folder per experiment. |
| `demos/` | Recorded runs worth keeping — transcripts, audio, notes. |
| `devlog/` | Living journal of development sessions — decisions, commands, outcomes, open threads, dated. |
| `tests/` | Engine-logic tests, run against a stub LLM — no model download needed. |

## Where to start

1. Read `docs/PRD.md` — §0 (the spike), §3 (director/actor), §4 (object model) are the load-bearing ones.
2. Read `CLAUDE.md` — the working brief for AI-assisted development on this repo.
3. Read `spike/README.md` — the first real task.

## Licence notes

- **Game rules:** built on the **D&D 5e SRD** under **CC-BY-4.0** (attribution only, commercial
  use permitted). Branded IP is off-limits — invent original creatures, places, names. See PRD §16.
- **Model:** Gemma 4 is provided under **Apache 2.0** — a change from earlier Gemma generations'
  custom Gemma Terms of Use (confirmed on the model card: `license: apache-2.0`, linking to plain,
  unmodified Apache 2.0 text at ai.google.dev/gemma/docs/gemma_4_license). Google still layers a
  separate Prohibited Use Policy / intended-use statement on top of that base license — review it
  before redistribution, it's not a blanket "no restrictions."
- **This repo's own code and content:** licence to be chosen by the owner.
