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

The **one piece of genuine uncertainty** remains the hardware spike (§0) — does a small model run
acceptably on a warm mid-range Android phone? That question is still open and still gates the
on-device deployment decision; everything built so far is desktop engine logic, deliberately kept
separate from it (see `CLAUDE.md`, "This dev host vs the phone").

Current decisions locked:

- **Spike benchmark model: Gemma 4 E2B** (`litert-community/gemma-4-E2B-it-litert-lm`, `.litertlm`).
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
- **Model:** Gemma is provided under the **Gemma Terms of Use** (not Apache 2.0). Review before
  redistribution.
- **This repo's own code and content:** licence to be chosen by the owner.
