# ADR 0001 — Spike benchmark model: Gemma 4 E2B

**Date:** 6 September 2026
**Status:** Accepted
**Context:** PRD §0 (the spike), §8, §11. Resolves cleanup action-plan decision **A2**.

## Decision

The hardware spike benchmarks **Gemma 4 E2B**, quantised, in `.litertlm` format
(`litert-community/gemma-4-E2B-it-litert-lm`), run via LiteRT-LM / the MediaPipe LLM Inference API.

This decides **only what goes on the test phone this week**, not what ships. The model that ships
is settled by the spike result, not by this record.

## Why

- ~2B effective parameters — small enough to be a defensible on-device choice, in line with the
  PRD's "obedient and consistent, not clever" requirement.
- `.litertlm` + LiteRT-LM is a first-class on-device path for Android with CPU and GPU backends,
  which the spike needs to measure both of (PRD §0).
- Native audio + vision + function calling — not required for the cell-and-guard PoC, but a useful
  latent capability for an audio-first product.

## Alternatives / open

- **Gemma 4 E4B** (bigger sibling) — recorded as an open question: is the extra footprint worth the
  coherence/context gain? Not evaluated until the spike proves the floor.
- **Gemma 3n E2B** — the older on-device model; superseded here but noted to avoid the naming
  collision (both are called "E2B").

## Correction carried from the action plan

The action plan recorded this model's licence as Apache 2.0. That is wrong: Gemma is provided
under the **Gemma Terms of Use** (ai.google.dev/gemma/terms). Corrected here and in the PRD.

## Consequences

- Unblocks roadmap step 0 (the spike).
- PRD §0 / §8 / §11 / roadmap / open-questions updated to name Gemma 4 E2B consistently (v0.8).
