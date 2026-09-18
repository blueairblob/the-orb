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

**The cell-and-guard proof of concept (PRD §8) runs end to end, in text mode, on the desktop, on
the engine's real shipping runtime, and has been through several real (not synthetic) playtest
sessions against it.** Object model, guard Character Engine, brief-builder, guardrail, and core
loop are all built (`engine/`) and run against the real Gemma 4 E2B model via `orb-engine` and
`llama.cpp`/GGUF ([ADR 0003](docs/decisions/0003-shipping-llm-runtime-gguf.md)). Both terminal
states — talk your way to an unlock, or push the guard to a lockout — are confirmed reachable in
real play, not just unit tests. State-machine rigor (PRD §22 Gotcha #3, "improvised detail becomes
canon") is built: the guard's secret-reveal and any fact he spontaneously invents both become
real, engine-owned state, persisted across saves, fed back into every future brief so he stays
consistent with his own earlier word. See `devlog/` (2026-09-14 through 2026-09-17) for the full
trail of real playtest findings and fixes.

**Not yet done, and the actual next milestone**: everything above has been proven on this desktop
host, in text mode — PRD §24's roadmap step 5, "port to a real mid-range phone, feel the true
latency in the real loop," hasn't happened. The hardware spike (§0, below) benchmarked the raw
model in isolation on-device; the actual engine+loop has never run there. Real voice (Google
STT/TTS) is unbuilt for the same reason — this host has no audio hardware, so `engine/voice.py` is
a swappable protocol with only a text-mode backend so far. Both are explicitly Phase 2
(`CLAUDE.md`), not a Phase 1 gap.

**The hardware spike (§0)** — does a small model run acceptably on a warm mid-range Android phone?
— is a **qualified pass-leaning result, on one physical test device** (`poco-m4-pro`, MediaTek
Helio G96) — **read that scope limit as load-bearing, not a formality: everything below is one
device's behaviour, not a claim about Android phones generally.**

- **LiteRT-LM (the runtime originally assumed to ship) failed the pass mark on both backends** —
  CPU on thermal and TTFT both, GPU on TTFT alone — and a real attempt to fix its TTFT floor hit an
  unrelated, unfixable upstream export bug. Full story:
  `spike/results/2026-09-10-poco-m4-pro-litert-lm.md`.
- **llama.cpp/GGUF is the chosen runtime instead** ([ADR 0003](docs/decisions/0003-shipping-llm-runtime-gguf.md)):
  **1.33s median TTFT**, real session/KV-cache reuse, **flat latency across a full 18.1-minute
  hot/pocket run** (no thermal degradation). Close to the ~1s bar, not confirmed under it.
- **A 2026-09-14 attempt to close that gap via on-device tuning hit a device-specific CPU anomaly**
  (this one phone's CPU stuck at ~10x below its own earlier numbers) rather than producing a
  tuning result — cross-checked and resolved (the device itself is fine; it was specific to one
  runtime's CPU path that day), but no improved number came out of it. **The 1.33s figure above is
  still the one to trust** — not because it's been reconfirmed, but because nothing since has
  contradicted it. Full story: `spike/results/2026-09-09-poco-m4-pro.md` (2026-09-14 Update).

Everything built so far is desktop engine logic, deliberately kept separate from the spike (see
`CLAUDE.md`, "This dev host vs the phone").

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
| `REVIEW.md` | Formal project review log — dated, reviewer-attributed step-backs listing gaps against the PRD and missed opportunities, with per-finding status. |
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
