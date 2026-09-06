# The Spike — go / no-go

> **Before a single line of engine code: does a small LLM run acceptably on a mid-range Android
> phone, in a pocket, warm?**

This is the gate in front of the roadmap, not a task on it. Everything else in the PRD assumes the
answer is yes. **Find out first.** (PRD §0.)

## The model

**Gemma 4 E2B**, quantised, `.litertlm` — `litert-community/gemma-4-E2B-it-litert-lm`, run via
LiteRT-LM / the MediaPipe LLM Inference API. (ADR 0001.)

## The procedure

1. Get the quantised model onto a **real mid-range Android** — not a flagship, not an emulator.
2. Run it on **CPU and GPU**. Measure both. GPU is *not* assumed faster on mobile — do not pick a
   backend on faith.
3. Measure **time-to-first-token**, not just tokens/sec. In conversation the first syllable is
   what kills or saves the illusion.
4. **Run it hot.** ~20 minutes, unplugged, in a pocket. The cold 30-second benchmark is a lie.
5. Feed it a **realistic brief** — the kind the object model (§4) will actually generate — and a
   realistically short response.

## The pass mark

> A short, in-character guard reply, spoken, **beginning within roughly a second**, and still
> doing so after **twenty minutes** of use, on a **warm** mid-range phone.

- **Pass →** build the engine.
- **Fail →** the architecture survives, but the deployment story changes (cloud tier, or a bigger
  floor device).

## Note on this dev host

The OCI host **cannot run this spike** — it is a cloud box, and the spike is about on-device
thermal behaviour. Use the host for engine logic, brief quality, and desktop model behaviour; run
this benchmark on a physical phone. (See `../CLAUDE.md`, "This dev host vs the phone".)

## Recording results

One dated file per run in `results/`, e.g. `results/2026-09-DD-<device>.md`, capturing:

- Device (model, chipset, RAM), Android version, quant build, runtime + version.
- Backend (CPU / GPU), time-to-first-token, tokens/sec.
- Cold vs warm (after ~20 min), plugged vs unplugged.
- The brief used and the reply produced (paste both).
- Verdict against the pass mark, and any thermal throttling observed.
