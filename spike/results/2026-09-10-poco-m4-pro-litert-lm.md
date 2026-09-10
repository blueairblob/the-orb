# Spike result — `poco-m4-pro` — 2026-09-10 — LiteRT-LM (the actual shipping runtime)

## Device

- **Model:** Poco M4 Pro (5G) — `2201117PG` (`fleur`)
- **Chipset:** MediaTek MT6781 (Helio G96) — 2 big + 6 little cores (`arm_big_little`; see
  Gotchas for why this matters)
- **Android:** 13
- **Runtime:** `litert_lm_main`, built from `google-ai-edge/LiteRT-LM@main` (2026-09-10), Bazel
  `--config=android_arm64 -c opt`
- **Model:** `litert-community/gemma-4-E2B-it-litert-lm` (`gemma-4-E2B-it.litertlm`, ~2.6GB,
  mixed 2/4/8-bit per the model card — same model family as the GGUF baseline, different quant
  packaging)
- **Backends tested:** CPU (XNNPACK delegate) and GPU (OpenCL delegate, real driver — not the
  software Vulkan fallback that sank the GPU attempt in the 2026-09-09 llama.cpp session)

This is the follow-up to the 2026-09-09 result (`2026-09-09-poco-m4-pro.md`), which explicitly
flagged llama.cpp/GGUF as "the pessimistic stand-in, not the shipping path" and listed testing
against LiteRT-LM directly as the top open thread.

## Conditions — narrower than the 2026-09-09 run, read before comparing

**This is not a hot/pocket sustained-load test.** It's desk-bound, screen-on, single-shot
invocations over an adb connection tunnelled through Termux's sshd over Tailscale (the phone's
wireless-debugging pairing port isn't reachable directly from this cloud host — only from the
phone's own loopback via SSH). Getting a real 18-minute unplugged/in-pocket run with this runtime
is still open — see Open threads.

**The build host problem:** this OCI dev host is aarch64, and Google ships Android NDK host
toolchains only for linux-x86_64/macOS/Windows — the documented `bazel build
--config=android_arm64` step cannot run here. Worked around with a `workflow_dispatch` GitHub
Actions job (`.github/workflows/litert-lm-android-build.yml`) on a free x86_64 runner; the
resulting binary is a genuine `ELF ... ARM aarch64 ... interpreter /system/bin/linker64` — the
build host's own architecture doesn't matter for the target artifact. Two build fixes along the
way: `npm install -g @bazel/bazelisk` hit `EACCES` on the hosted runner (switched to downloading
the bazelisk binary directly); the first successful build used Bazel's default `fastbuild`
(unoptimized) — added `-c opt`, though see Results, it barely moved the needle.

## Results

### CPU backend, real engine-generated brief (n=8, `--num_cpu_threads=4`)

Same brief as the 2026-09-09 run's methodology: `engine.brief.build_guard_brief` against the
v0.1 cell-and-guard scenario, ~490 tokens (a shade longer than the earlier ~350-token version —
the scenario picked up more state since). `--max_output_tokens=24` per run, desk-bound, plugged.

| Stat | TTFT | Prefill speed | Decode speed |
|---|---|---|---|
| Median | 10.15s | 52.5 tok/s | 3.4 tok/s |
| Min | 9.98s | 47.3 tok/s | 1.35 tok/s (run 1 — cold outlier) |
| Max | 11.70s | 53.5 tok/s | 3.5 tok/s |

**Prefill throughput is genuinely strong** — 52.5 tok/s median, well above the GGUF baseline's
~14–18 tok/s prefill on the same device. **But TTFT is ~10s, an order of magnitude over both the
~1s pass mark and the GGUF baseline's 1.33s median.** The reason is not the runtime being slow at
the model math — it's architectural, see Gotchas: `litert_lm_main` is a single-shot CLI with no
persistent session, so every invocation reprocesses the *entire* ~490-token brief from a cold
start. The GGUF baseline's 1.33s used a persistent `llama-server` that reused the KV cache for the
static persona/system block across requests (confirmed via its `selected slot by LCP similarity`
log line) — this comparison is not apples-to-apples until LiteRT-LM is driven the same way.

### GPU backend (OpenCL, real Mali driver), single run, same brief

| Metric | Value |
|---|---|
| Init Executor (one-time, includes shader compile) | 30.8s |
| Time to first token | 9.04s |
| Prefill speed | 59.9 tok/s |
| Decode speed | 2.52 tok/s |

Modestly faster prefill than CPU, decode roughly comparable-to-worse (single sample, not a
batch — don't read too much into it). The 30.8s one-time init is real but a red herring for
production: `--cache_compiled_shaders_only` exists specifically to amortize this across app
launches, untested here.

### Thread-count sensitivity (short synthetic prompt, exploratory, high variance — not the
primary result)

Spot checks at `--num_cpu_threads` 0 (auto/default), 2, 4, 8 on a short ~21-token prompt showed
the *default (0) is not the fastest setting* — explicit thread counts beat it every time — but
individual readings at the same thread count varied by up to 2.4x between back-to-back runs
(e.g., `--num_cpu_threads=2` produced both the best single decode reading of the whole session,
4.98 tok/s, and one of the worst, 2.07 tok/s). Not enough signal to name an optimal thread count
from this; the n=8 real-brief batch above (at threads=4, chosen as a reasonable middle value
before this variance was fully apparent) is the trustworthy number, not the single-shot spot
checks.

## The brief used

Generated fresh via `uv run python3 -c "from engine.scenario import build_cell_and_guard; from
engine.brief import build_guard_brief; ..."` — same scenario as the 2026-09-09 run, same call
path, output captured to `guard_brief.txt` and pushed to the device rather than passed as a shell
argument (avoids quoting/escaping the em-dashes and nested quotes in the real brief text). Not
reproduced in full here since it's identical in structure to the one already in
`2026-09-09-poco-m4-pro.md` — only the specific mood/history values differ run to run.

## Verdict against the pass mark

**Not yet gradeable against the ~1s TTFT bar, and it would be misleading to call it "worse than
GGUF" from these numbers.** The 10s TTFT is a real measurement of what `litert_lm_main` (the
demo CLI) does today, but it is not a measurement of what the shipping architecture would do in
an actual app, which would hold a persistent session and reuse the KV cache for the static
persona block exactly as the GGUF/llama-server test did. Prefill throughput — the number that
*is* comparable between the two runtimes regardless of session/caching architecture — favors
LiteRT-LM by roughly 3x (52.5 vs ~14–18 tok/s). That's evidence *for* the "actual shipping runtime
has headroom above the GGUF floor" hypothesis from the PRD §0 research, even though the
end-to-end TTFT number from this session can't be used directly yet.

Thermal/hot-pocket behavior for LiteRT-LM: **not tested this session** — see Open threads.

## Gotchas from this run

- **big.LITTLE core layout matters more than raw core count.** MT6781 has 2 performance + 6
  efficiency cores. Using all 8 threads (`--num_cpu_threads=8`) was consistently worse than 4,
  and 2 threads produced the best single reading of the session — spreading work onto the slow
  efficiency cores looks counterproductive here. Worth real tuning once the session-reuse
  question (below) is settled and a stable benchmark protocol exists.
- **`-c opt` barely moved the numbers** (decode 2.31→2.45 tok/s either way) — the earlier
  hypothesis that the first build's slow numbers were a `fastbuild`-vs-`opt` artifact was wrong;
  don't assume it without checking again on a cleaner benchmark.
- **The demo CLI (`litert_lm_main`) is not the production integration surface.** Its `--multi_turns`
  flag was tested (fed a follow-up line after the brief via piped stdin) and did *not* do
  incremental turn-by-turn prefill — it concatenated everything into one 518-token prefill and
  reported "Total 1 turns". Real turn-to-turn session/cache reuse, if the runtime supports it at
  all, lives in LiteRT-LM's Engine/Session C++ (or Python/Kotlin binding) API, not this benchmark
  binary. This is the single most important open question left by this session.
- **Wireless debugging's pairing service only listens on the phone's local Wi-Fi interface**, not
  the Tailscale interface — pairing had to be done by SSH-tunnelling through Termux's sshd (itself
  reachable over Tailscale) back to the phone's own `127.0.0.1:<pairing-port>`. The main
  `adb connect` port worked the same way. Both the pairing port and the main connect port change
  every time Wireless debugging is toggled — don't expect either from a previous session to still
  work.
- **adb itself needed a workaround on this host**: Google's official `platform-tools` zip is
  x86_64-only (same problem as the NDK). Ubuntu's `adb` apt package does ship a real arm64 build,
  but installing it needs `sudo`, which wasn't available non-interactively. Downloaded the arm64
  `.deb`s with `apt-get download` (no root required) and extracted them with `dpkg-deb -x` into
  `~/android-tools/adb-local`, setting `LD_LIBRARY_PATH` to the extracted `android/` lib dir —
  works fully unprivileged.
- **Android wireless-debugging pairing codes are short-lived** — burned one during
  back-and-forth before getting the tunnel set up; the retry with a freshly generated code worked
  immediately.

## Open threads

- [ ] **Resolve the session/KV-cache-reuse question.** Either find a LiteRT-LM CLI flag/mode that
  does real incremental per-turn prefill, or write a small harness against the actual
  Engine/Session API (C++ or the Python bindings) that holds one session across turns. Without
  this, TTFT numbers from `litert_lm_main` will always overstate real per-turn latency for a
  guard conversation, where the persona/system block is static turn-to-turn by design (PRD §4).
- [ ] Once session reuse works, repeat the full 2026-09-09 protocol: hot/pocket, ~18-20 min,
  rotating prompts, thermal-drift-by-window table.
- [ ] Revisit thread-count tuning with a proper batch (n≥10 per setting) once TTFT methodology is
  fixed — the current spot checks are too noisy to act on.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend to see if the 30.8s one-time init
  amortizes the way the flag's description implies.
- [ ] Compare against Q4_0 vs Q4_K_M on the GGUF side (carried over from 2026-09-09, still open).
