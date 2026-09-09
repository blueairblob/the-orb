# 2026-09-09 — Spike: the LLM half comes alive on real hardware (`poco-m4-pro`)

## Context

The LLM half of the PRD §0 spike — the go/no-go gate that can kill the on-device premise.
Driving Termux on the target phone (`poco-m4-pro`) from the OCI ARM host (`huey`) over the
Tailscale mesh, running Gemma 4 E2B through llama.cpp. Two things surfaced that had to be fixed
before any measurement could be trusted: Gemma 4 kept emitting a reasoning trace we don't want in
the voice path, and the Tailscale/Termux link freezes intermittently. Neither is the spike pass
itself — that still needs time-to-first-token and a hot run — but both were blocking clean
measurement.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Disable Gemma 4 thinking with `--reasoning off` | Under `--jinja`, `--reasoning-budget 0` and `enable_thinking:false` were flaky on Gemma 4 (silently no-op on some builds; budget sometimes only *hides* the trace while still paying decode cost) | `--reasoning-budget 0`; `--chat-template-kwargs '{"enable_thinking":false}'` |
| Keep the multimodal build, drop the projector with `--no-mmproj` | Text-only wouldn't generate faster (encoders idle on text turns; decode speed is set by the LM weights) but the projector still costs RAM on a memory-constrained phone | Sourcing a text-only GGUF build |
| Keep Google/Termux STT; do **not** feed audio natively into E2B | Native audio-in would put transcription in the model's on-device hot path and throw away free, deterministic STT | E2B native audio modality |
| `mosh` + `tmux` over raw SSH for the OCI→phone link | SSH is one TCP connection that silently dies on sleep/roam/IP-shift → terminal hang. Mosh is UDP with local echo and re-syncs after drops; tmux decouples "terminal froze" from "job died" | Raw SSH with keepalives only |

## Commands

```bash
# [APPLIED] Disable Gemma 4 thinking under --jinja (this is what worked)
./build/bin/llama-cli -hf bartowski/google_gemma-4-E2B-it-GGUF:Q4_K_M \
  -fa auto -c 0 --jinja --reasoning off
# Confirm: startup template-init log line ends `thinking = 0` (not `1`)
```

```bash
# [RECOMMENDED — not yet applied] Drop the unused vision/audio projector to reclaim RAM
# (no tok/s change; RAM only)
./build/bin/llama-server -hf ggml-org/gemma-4-E2B-it-GGUF:Q4_0 --port 8081 \
  --jinja --reasoning off --no-mmproj
```

```bash
# [RECOMMENDED — not yet applied] Stabilise the OCI→phone link
# Phone (Termux):
pkg install mosh tmux
# OCI host (huey):
sudo apt install mosh
# Connect over Tailscale, pointing mosh at Termux's SSH port 8022:
mosh --ssh="ssh -p 8022" u0_382@<tailscale-ip>
# Run the actual work inside tmux so a dropped session doesn't kill llama-server:
tmux new -s orb      # detach Ctrl-b d ; reattach: tmux attach -t orb
```

```bash
# [RECOMMENDED — not yet applied] SSH keepalives as fallback (huey ~/.ssh/config)
# Host phone
#     HostName <tailscale-ip>
#     Port 8022
#     User u0_382
#     ServerAliveInterval 20
#     ServerAliveCountMax 3
#     TCPKeepAlive yes
# Mirror on phone in $PREFIX/etc/ssh/sshd_config: ClientAliveInterval 20 / ClientAliveCountMax 3
```

```bash
# [RECOMMENDED — not yet applied] Diagnose link path: direct vs DERP relay
tailscale ping <phone>
```

## Outcome

The LLM half of the spike is **alive on real mid-range hardware**. Gemma 4 E2B (Q4_K_M,
bartowski) runs on `poco-m4-pro`, CPU-only via llama.cpp, with the thinking trace cleanly
disabled. First measured numbers:

| Metric | Observed |
|---|---|
| Generation | ~4.7–4.8 tok/s |
| Prompt (prefill) | ~14–18 tok/s (varies with prompt length) |

Generation sits at the **top of the 2–5 tok/s floor** the PRD §0 research predicted — reassuring
precisely because this is the pessimistic lane (CPU-only, GGUF, Termux, no MTP). It's a floor,
not a ceiling; the shipping path (LiteRT-LM, GPU/NPU, MTP) has headroom above it. An external
`android-edge-ai-devops-notes.md` working file was updated with all of the above (new §2
subsections on disabling thinking, dropping the projector, and the measured results) — not
checked into this repo; captured here instead per the devlog convention.

**This is not the spike pass.** The gate turns on TTFT and thermals, neither of which is measured
yet. No file has been added to `spike/results/` for this run — see Open threads.

## Gotchas & notes

- **`--jinja` overrides "off by default."** The chat template's `enable_thinking` variable governs
  Gemma 4 thinking — not the model card's `<|think|>` token — and the template default can be
  *on*. Always set it explicitly and confirm via the `thinking = 0` line in the startup log.
- **`--reasoning-budget 0` can be a trap.** On some builds it only hides the reasoning trace
  rather than stopping generation, so you keep paying the decode/battery cost. Prefer
  `--reasoning off`. This area of llama.cpp is churny with open regressions.
- **`-hf` auto-loads the mmproj.** The bartowski build reports `modalities: text, vision, audio`;
  the projector rides along unless you pass `--no-mmproj`. Text-only ≠ faster decode — but the
  projector is real resident RAM.
- **MIUI/HyperOS kills background VPNs.** Termux being battery-Unrestricted with a wake-lock is
  not enough — **Tailscale needs the same treatment** (Unrestricted + Autostart + locked in
  recents), or the tunnel freezes even when Termux is healthy.
- **Two different "freezes."** Freeze *during inference* = thermal throttling (CPU pinned, clocks
  clamped, shell goes gluey) — a perf-domain problem. Freeze *when idle/mid-keystroke* =
  network/Doze — the mosh/tmux/battery fix. Diagnose which before chasing it.
- **Direct vs DERP.** `tailscale ping` reveals whether the link is direct or relayed via DERP. On
  cellular CGNAT it'll likely relay (jitterier); home Wi-Fi has a better shot at direct. MIUI
  killing Tailscale also breaks its ability to hold a direct path.

## Open threads

- [x] Capture time-to-first-token on a realistic §4-style brief — done, see update below and
  `spike/results/2026-09-09-poco-m4-pro.md` (median 1.33s, real engine-generated brief).
- [x] Re-run hot: 15–20 min sustained inference, in-pocket — done (18.1 min, 192 requests, 0
  hangs after the wake-lock fix). No thermal throttling signature found.
- [x] Wire the sparse in-character system prompt (Yoda principle) — used the real
  `build_guard_brief` output for the hot run, not a hand-written stand-in.
- [x] Apply `mosh` + `tmux` + Tailscale battery-unrestriction — done (see update below); still
  want confirmation the link holds for a multi-hour session, which hasn't been tested yet.
- [ ] Compare Q4_0 (QAT) vs Q4_K_M for quality/speed on `poco-m4-pro`.
- [ ] Confirm whether `termux-speech-to-text` runs on-device or falls back to network recognition.
- [ ] Build the glue script: `termux-speech-to-text` → POST to local `llama-server` →
  `termux-tts-speak`.
- [x] Once TTFT + hot-run numbers exist, write the dated result file in `spike/results/` per
  `spike/README.md`'s format — done, `spike/results/2026-09-09-poco-m4-pro.md`.
- [x] Test the GPU backend — attempted; only software Vulkan (`llvmpipe`) is reachable through
  Termux's loader, not the real Mali ICD, and it's much slower, not faster. Closed for now, see
  update below. Getting the real Mali driver discovered is a separate follow-up, not done here.
- [ ] **Test against LiteRT-LM directly — the actual shipping runtime, not llama.cpp/GGUF. Start
  here next session.** Scoped same day (end of session), not yet started:
  - Needs Bazel + Android NDK r28b+ on this host (`ANDROID_NDK_HOME`) — a real cross-compile
    toolchain, not something Termux can do.
  - `git clone google-ai-edge/LiteRT-LM`, then
    `bazel build --config=android_arm64 //runtime/engine:litert_lm_main` — a from-source C++
    build, could be slow/heavy.
  - Deployment is **`adb`, not SSH/Termux** — `adb push` the binary + `.litertlm` model (+
    prebuilt `prebuilt/android_arm64/*.so` for the GPU backend) to `/data/local/tmp/`, then
    `adb shell` to run with `--backend=cpu|gpu|npu`. No `adb` access is set up yet — either USB
    debugging or wireless adb (`adb connect <tailscale-ip>:5555`, unconfirmed whether wireless
    debugging is even enabled on `poco-m4-pro`).
  - Docs: [build-and-run.md](https://github.com/google-ai-edge/LiteRT-LM/blob/main/docs/getting-started/build-and-run.md),
    [LiteRT-LM CLI](https://developers.google.com/edge/litert-lm/cli).
  - This is the one that actually settles the §0 verdict — llama.cpp/GGUF is the pessimistic
    stand-in, not the shipping path.

## Update — same day: connection fixed, first real TTFT numbers

Picked back up later the same day to act on the connection open thread before trusting any more
TTFT readings.

**Fixed:** `tailscale ping poco-m4-pro` was going via DERP relay (London), with jitter up to 4.3s
on a single ping — enough to make any TTFT number meaningless. `tailscale netcheck` on the OCI
side showed a clean NAT (`MappingVariesByDestIP: false`, 1.9ms to the London DERP), so the OCI
host wasn't the problem. Two changes on the phone side — confirmed already on home Wi-Fi, and
Tailscale set to Unrestricted battery / Autostart — and the link came up **direct** (19–65ms, no
relay). Also installed `tmux` + `iproute2` in Termux (mosh was already present) and moved
`llama-server` into a detached `tmux -s orb` session so it survives a dropped SSH/mosh connection
— confirmed useful immediately, since a plain `echo` over SSH stayed reliable but a heavier
command (`ip addr show`) hung and dropped the connection mid-session at least twice this session.

**First TTFT batch (n=4, direct link, desk-bound, plugged in):** 3.73s, 1.46s, 1.48s, then a
full hang — client waited 60s for nothing, server log showed the task cancelled ~2.3s in. The
drop happens somewhere in the path even with Tailscale Unrestricted on Wi-Fi (next suspect: phone
Wi-Fi radio power-saving, distinct from the already-diagnosed cellular/Doze issue) — not fully
solved.

**Second TTFT batch (n=12, same conditions, 15s per-request timeout, 5 rotating prompts):**
0/12 hangs.

| Stat | Value |
|---|---|
| Mean | 1.559s |
| **Median** | **0.946s** |
| Min | 0.446s |
| Max | 5.764s |
| stdev | 1.569s |

Bimodal: the first two requests were slow (5.76s, 3.83s — likely Wi-Fi radio wake or cache still
settling right after the tmux restart), then it dropped and mostly held under ~1.4s, several
samples under 0.6s. Caveat: `llama-server` reuses KV cache across requests by prompt-prefix
similarity (log: `selected slot by LCP similarity`) — the shared system/persona block was cached
across all 12 requests, which is realistic for actual play (the guard's persona is static turn to
turn even as state changes) but does mean these weren't fully independent cold measurements.

**Reading this honestly:** the median (0.946s) is under the §0 pass mark for the first time, and
the connection fix is real and reproducible. But this is still desk-bound, plugged in, with a
short synthetic prompt, and the link has now dropped a request outright at least once even after
the Wi-Fi/battery fix. None of this is the recorded verdict — see Open threads above, unchanged.

## Update — same day: the actual hot/pocket run, and a recorded verdict

Went straight for the real §0 gate condition: unplugged, in-pocket, ~18 minutes, real
engine-generated brief (`engine.brief.build_guard_brief`, ~350 tokens — not synthetic), 192
back-to-back requests. Full writeup, numbers, and the pass-mark verdict are now recorded in
`spike/results/2026-09-09-poco-m4-pro.md` per `spike/README.md`'s format — this entry just covers
what happened operationally.

**First attempt failed immediately.** The moment the phone was pocketed and the screen locked,
the whole Termux process tree died — not a network freeze, the `tmux` server itself was gone
(`operator(): cleaning up before exit...` in the llama-server log). This happened *despite*
Tailscale already being Unrestricted/Autostart from earlier — necessary but not sufficient.
Fixed with `termux-wake-lock` before relaunching. `MemAvailable` was only ~1.1GB of 7.9GB total
at the time, plausibly a contributing factor (low-memory killer on top of Doze) — worth checking
before the next run.

**Second attempt, clean: 192/192 requests succeeded, 0 hangs.** Headline results:

- **No thermal throttling signature over 18.1 real minutes, unplugged, in-pocket.** Second half
  of the run (mean 1.40s TTFT) was flat-to-slightly-better than the first half (1.65s). This is
  the actual thermal half of the §0 gate, and it passes clean at this quant/config (CPU-only
  `Q4_0`, `--no-mmproj`).
- **TTFT median 1.33s** against the ~1s pass mark, using the real brief for the first time —
  close but consistently over (only 4.7% of warm requests landed at/under 1s). Earlier same-day
  batches showing sub-1s medians were on short synthetic prompts; this is the more honest number.
- Full device specs, brief text, sample replies, and the split verdict (thermal: pass;
  TTFT: not yet, but close, and CPU-only-GGUF is the pessimistic lane not the shipping path) are
  in the results file, not duplicated here.

This is the first entry in `spike/results/` — the LLM half of PRD §0 now has real, recorded
evidence behind it instead of an open thread.

**mosh confirmed ready.** Both ends already had it installed (`mosh` client on `huey`,
`mosh-server` on the phone from earlier this session) — no install step needed. Couldn't drive it
end-to-end from here since `mosh` requires a real tty (`tcgetattr: Inappropriate ioctl for
device` when run non-interactively — expected, it's built for an interactive human terminal, not
a scripted one). Bootstrapped `mosh-server new -s` by hand over SSH instead to confirm the
server-side handshake works: it claimed UDP port 60003 (default range) and detached cleanly, then
was killed again as a throwaway test. Since this rides inside the already-confirmed direct
Tailscale link, there's no separate NAT/firewall hurdle for the UDP port. Connect with:
`mosh --ssh="ssh -p 8022" u0_382@100.105.178.99`, then `tmux attach -t orb` for the running
`llama-server` session. This closes that open thread for interactive use; one-shot commands run
from this host still just use keepalive-flagged SSH, which has been reliable throughout.

## Update — same day: tried the GPU backend, learned why it's not simple

Also fixed the `dm.classify_utterance` routing bug found during the real-loop test (see
`2026-09-09-real-loop-against-the-phone.md`) — word-boundary fix, regression test added, full
suite green (47 passed). Then tried closing the TTFT gap by testing the GPU (open thread, and
PRD §0 explicitly wants CPU *and* GPU measured). Findings, in order:

1. **A prebuilt Termux package exists** — `llama-cpp-backend-vulkan` (pulls in `llama-cpp` and a
   `vulkan-loader` stack) — so no source rebuild was needed, contrary to the earlier assumption
   that this would require compiling `llama.cpp` with `-DGGML_VULKAN=ON` by hand.
2. **The device does have a real vendor Vulkan driver for this exact chipset**
   (`/vendor/lib64/hw/vulkan.mt6781.so`, `vulkan.mali.so`) — but Termux's Vulkan loader didn't
   find it. Running the packaged `llama-server` with `-ngl 99` against port 8082 (alongside the
   working CPU server on 8081, to compare without disturbing it) showed the detected device was
   `Vulkan0 : llvmpipe` — Mesa's **software** rasterizer, not the Mali GPU. `mesa-vulkan-icd-swrast`
   got pulled in as a dependency and is what's actually being used.
3. **Software Vulkan is much worse, not better.** The model was still stuck on "warming up" after
   3+ minutes — the CPU backend completes a cold load + first reply in ~15–25s. Killed it rather
   than wait longer.
4. **Running two full model instances at once crashed the phone.** The moment the Vulkan test was
   killed and the baseline was re-checked, both Tailscale and SSH went dark for ~3–4 minutes —
   total connectivity loss, not just a port timeout. `MemAvailable` had been ~1.1GB before this;
   after recovery it was 4.3GB, consistent with an OOM sweep reaping both `llama-server`
   processes (and the `tmux` server managing them) while leaving Termux's `sshd` alive — plausible
   given a 2B-param model process is a much fatter OOM-killer target than a lightweight shell.
   Real operational finding: **don't run two model instances concurrently on this device** — even
   the working CPU baseline got taken down as collateral.
5. **Installing the Vulkan package broke the working CPU binary.** `~/llama.cpp/build/bin/llama-server`
   turned out to be dynamically linked against Termux's *shared* `libggml*.so` / `libllama*.so`
   (`readelf -d` showed `NEEDED` entries for them, not static linking) — so it was never really a
   private build. `pkg install llama-cpp-backend-vulkan` overwrote those shared libraries with the
   package's own versions, and the old binary then hard-crashed on startup
   (`GGML_ASSERT(params.speculative.draft.n_gpu_layers < 0) failed`) even with no
   speculative-decoding flags passed. Fixed by switching to the system-installed `llama-server`
   (same package, matching libs) instead of the stale path — confirmed working again with a real
   reply ("Guard.") over the API.

**Verdict on GPU, for now: closed, not pursued further today.** Getting the real Mali ICD
discovered by Termux's Vulkan loader (rather than falling back to `swrast`) is a separate,
deeper yak-shave — not a same-session flag flip. CPU-only remains the number on record.
