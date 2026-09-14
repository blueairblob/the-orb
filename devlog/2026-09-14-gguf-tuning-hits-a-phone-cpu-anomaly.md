# 2026-09-14 — Trying to close out the spike with GGUF tuning, hitting a phone-specific CPU anomaly instead

## Context

ADR 0003 flagged the GGUF baseline's 1.33s median TTFT as "close but not confirmed under the ~1s
bar" — a live open thread. This session tried to close it: apply the same session/prefix-cache
technique validated on desktop the day before (`devlog/2026-09-13-engine-onto-llama-cpp.md`) to the
real phone, plus general tuning, to see if a clean pass was reachable.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Test via direct curl/Python against `llama-server`'s HTTP API, tunnelled from OCI, rather than running Python inside Termux | Termux has no `python3`/`jq`/`node` installed — confirmed directly, not assumed. An SSH local port-forward (`-L 18091:127.0.0.1:8091`) let existing OCI-side Python tooling drive the test instead | Install Python in Termux — extra setup for a one-off test, not worth it |
| Always resend the full brief as the system message on every turn, not just turn 1 | The real engine (`engine/llm.py`) does this — PRD §4 rebuilds the brief fresh each turn, it doesn't accumulate raw history. A first version of the test script omitted the system message after turn 1 (wrongly assuming session state would "remember" it), which broke character entirely and made prefix-cache reuse look broken. Fixing this was a test-script bug fix, not a runtime finding | — |
| Stop chasing the CPU anomaly once Edge Gallery confirmed the device itself is fine | Real time already spent (multiple rounds: memory pressure, reboot, CPU frequency, core pinning, backend reinstall) without resolving it, and Termux's llama.cpp path can't reach the real Mali GPU regardless of the throttle's root cause — so even solving it wouldn't unlock GPU-class performance for this specific deployment path | Keep digging on-device — rejected for now, real but open-ended cost; logged as an open thread instead |

## Commands

```bash
# [APPLIED] Confirmed no scripting runtime in Termux, then used a local SSH tunnel instead
ssh -o BatchMode=yes phone "which python python3 jq node"   # -> nothing found
ssh -o BatchMode=yes -f -N -L 18091:127.0.0.1:8091 phone    # tunnel, then drive it from OCI's own Python
```

```bash
# [APPLIED] The finding that mattered: real CPU throttle, confirmed not assumed
ssh phone "cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq"
# -> 500000 x6 (little cores), 774000 x2 (big cores) -- vs cpuinfo_max_freq of 2000000/2050000
# After plugging in: big cores -> 2050000 (max), little cores stayed at 500000
```

```bash
# [APPLIED] Isolated the anomaly from our own HTTP/session code entirely
llama-bench -m gemma-4-E2B-it-Q4_0.gguf -p 512 -n 64 -t 4        # ~4.66 pp / 2.78 tg t/s (Vulkan/llvmpipe)
llama-bench -m gemma-4-E2B-it-Q4_0.gguf -p 512 -n 64 -t 4 -ngl 0 # ~4.08 pp / 2.76 tg t/s (no change)
pkg uninstall -y llama-cpp-backend-vulkan && apt autoremove -y && pkg install -y llama-cpp
llama-bench -m gemma-4-E2B-it-Q4_0.gguf -p 512 -n 64 -t 4        # ~4.00 pp / 2.93 tg t/s, backend: CPU
# -> same order of magnitude every time, ~10x below this exact device's own LiteRT-LM CPU numbers
```

## Outcome

Never got a trustworthy re-measurement of GGUF/llama.cpp on the phone this session — every
configuration (server flags, `id_slot`+`cache_prompt`, thread count 2/4/8, core-pinning to the
full-clock big cores via `taskset`, forcing `-ngl 0`, a completely clean package reinstall)
converged on the same ~4-5 tok/s prefill / ~2.8-3 tok/s decode via `llama-bench`, a clean,
server-independent measurement. That's roughly 10x below this same device's own LiteRT-LM CPU
prefill numbers (~52 tok/s) from the 2026-09-10 investigation.

Ruled out, with direct evidence for each: memory pressure (reboot cleared swap entirely, no
change), background system load (settled over ~13 minutes, no change), Vulkan-backend
misselection (forcing CPU explicitly and reinstalling without the Vulkan package at all: no
change), and thread/core-count tuning (2 full-clock cores were *worse* than 8 throttled ones).
What's real and confirmed: the little CPU cores are locked at 500MHz (25% of their 2000MHz max)
regardless of charging state — a genuine, reproducible hardware/OS-level fact, not fully
sufficient on its own to explain the numbers (full-clock big cores didn't fix it either).

**The decisive step was empirical, not more configuration guessing:** at the user's suggestion,
opened Google's own Edge Gallery app (LiteRT-LM/MediaPipe LLM Inference API — the same runtime
this project already evaluated, not a different one) running Gemma E2B on the real Mali GPU, same
phone, same moment. ~4 second response — consistent with, not better than, this project's own
already-recorded LiteRT-LM GPU number (3.28s mean/turn, ADR 0003). That single data point resolved
the investigation: the device itself is fine, and today's llama.cpp numbers reflect something
specific and broken in Termux's CPU-only path right now (the confirmed throttle, plus something
else even full clock didn't fix), not a device-wide fault or a flaw in ADR 0003's underlying data.

**Decision: keep the existing 2026-09-09 baseline (1.33s median TTFT) as the trusted llama.cpp
number.** It was captured before this CPU anomaly appeared, isn't contradicted by anything found
today, and re-deriving a number under today's confirmed-anomalous conditions would be worse
evidence, not better. ADR 0003 is unaffected.

## Open threads

- [ ] **Why are the little cores locked at 500MHz even while charging, and why did full-clock big
  cores still only give ~4-5 t/s?** Real, reproducible, unexplained — worth a fresh look with more
  time. Possibly relevant beyond this one benchmark if it affects real background CPU work on this
  device generally, not just llama.cpp.
- [ ] Termux's llama.cpp can only reach the software Vulkan (`llvmpipe`) fallback on this device —
  confirmed no real Mali GPU access is possible from that sandbox. If GPU-class llama.cpp
  performance ever matters, it would need a different deployment path than Termux entirely (e.g.
  a native Android build linking the real Mali driver, mirroring what the LiteRT-LM investigation
  already had to do) — not a small follow-up, flagging for awareness only.
- [ ] The GGUF quantisation-comparison thread (Q4_0 vs Q4_K_M, open since 2026-09-09) is still
  untouched — blocked behind this session's device anomaly rather than addressed.
