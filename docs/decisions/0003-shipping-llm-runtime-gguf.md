# ADR 0003 — Shipping LLM runtime: llama.cpp / GGUF, not LiteRT-LM

**Date:** 13 September 2026
**Status:** Accepted
**Context:** PRD §0 (the spike), §11 (tech stack). Answers the go/no-go question the spike exists
for, after on-device testing spanning 2026-09-09 through 2026-09-13.

## Decision

The engine ships on **llama.cpp, running GGUF-quantised models**, not LiteRT-LM / the MediaPipe
LLM Inference API. The model family (Gemma 4 E2B, ADR 0001) is unchanged — only the
runtime/quantisation packaging changes.

## Why

All results below are from the same test device throughout (Poco M4 Pro, MediaTek Helio G96,
Mali-G57 MC2) — see `spike/results/2026-09-09-poco-m4-pro.md` and
`spike/results/2026-09-10-poco-m4-pro-litert-lm.md` for full traces.

- **LiteRT-LM CPU fails both halves of the pass mark.** A ~2s fixed prefill-bucket floor on every
  incremental turn (architectural, not tunable via prompting) already exceeds the ~1s TTFT target
  on its own, and a full 21-minute hot/pocket run showed real thermal degradation (+25-30% latency
  after ~12 minutes).
- **LiteRT-LM GPU clears the thermal half** (flat across a full 21-minute run) **but still fails
  TTFT** — mean 3.28s/turn, no meaningfully better than CPU, because the same prefill-bucket floor
  persists on GPU too. Ruled out a real, still-open upstream Mali/Gemma-4 driver bug as the cause
  (patched and re-tested — no measurable difference).
- **Chased the prefill-bucket floor via a custom export** (smaller 32-token bucket vs. the stock
  128/1024) — a dead end, not because the idea was wrong, but because it surfaced an **~11x
  decode-speed regression** in the public `litert-torch` export pipeline (0.20 vs. 2.27 tok/s),
  confirmed independent of the bucket size via a controlled re-export matching the stock bucket
  set exactly. No fix found in the public tooling. See that results file's 2026-09-12/13 updates.
- **llama.cpp/GGUF**, originally tested as "the pessimistic stand-in" (2026-09-09), was already
  closer to the pass mark than the intended shipping runtime: **1.33s median TTFT** with real
  session/KV-cache reuse via `llama-server`, and **flat latency across a full 18.1-minute
  hot/pocket run** — no thermal degradation at all, in direct contrast to LiteRT-LM CPU's clear
  fail.

The runtime assumed at spike-design time to be the "shipping path" turned out, after real
measurement, to be the worse performer on this hardware on both halves of the pass mark. The
"pessimistic fallback" is the one that's actually closer to passing.

## What this doesn't settle

- **1.33s is still slightly over the ~1s target** — this is "closer, and thermally clean," not a
  confirmed clean pass. Whether it's close enough as-is, or needs further tuning (quantisation,
  thread count, a smaller model), is open — a natural next step, not covered by this decision.
- **Gemma 4 E4B vs. E2B is unchanged as an open question** (ADR 0001) — this decision is about
  runtime, not model size.
- **Device-tier scope:** all evidence is from one mid-range chipset (Helio G96 / Mali-G57 MC2).
  Nothing here confirms the same verdict on other budget-tier hardware.

## Consequences

- PRD §11's tech-stack table updated: LLM runtime is llama.cpp/GGUF, not MediaPipe/LiteRT.
- Phase 1 desktop engine work (brief-builder, voice loop) targets llama.cpp's API and session
  model (persistent `llama-server`-style KV-cache reuse per encounter), not LiteRT-LM's.
- The LiteRT-LM build pipeline, patches, and export tooling built during the spike stay in the
  repo (`.github/workflows/litert-lm-android-build.yml`,
  `.github/workflows/gemma4-litertlm-export.yml`, `spike/patches/`) as a record and in case this
  decision is revisited, but are no longer the active development path.
- The phone spike (PRD §0) is now a **qualified pass-leaning result**: thermal is clean on the
  chosen runtime, TTFT is close but not yet confirmed under the bar. One more focused round of
  GGUF tuning is recommended before calling §0 fully passed — tracked as an open thread, not part
  of this decision.
