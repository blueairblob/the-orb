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

## Update — same day: real session reuse via `litert_lm_advanced_main`

The single biggest open question from the first pass ("does LiteRT-LM support incremental
per-turn KV-cache reuse the way the GGUF baseline's `llama-server` did?") is resolved: **yes**,
but not through `litert_lm_main` or its `--multi_turns` flag (that flag is declared but never
read by that binary — dead flag, explains the earlier concatenation artifact). The sibling demo
`litert_lm_advanced_main` (also built by the same CI job now) wires `--multi_turns` through the
real `Conversation`/`Session` API (`runtime/engine/litert_lm_lib.cc`): each stdin line becomes a
separate `SendMessage` call on the *same* session, and per-turn benchmark data is logged
separately.

**Protocol:** fed the flattened one-line brief as turn 1, a short player follow-up
("You beg him again to let you out.") as turn 2, `--backend=cpu --num_cpu_threads=4
--max_output_tokens=24`, n=6 full repeats (fresh process each time — this binary doesn't support
looping the same session across process invocations, so each repeat still pays the full turn-1
cold cost; only turn 2 is the "steady-state" measurement).

| Turn | Prefill tokens | Prefill duration (median) | Prefill speed (median) | Decode duration (median, 7 tok) | Decode speed (median) |
|---|---|---|---|---|---|
| 1 (full ~500-token brief) | 501 | 7.53s | 66.4 tok/s | 1.60s | 4.39 tok/s |
| 2 (17-token follow-up) | 17 | **1.81s** | 9.4 tok/s | 1.07s | **6.53 tok/s** |

Turn 2 only reprocessed 17 tokens instead of the full ~518 — **confirmed real KV-cache reuse**,
and remarkably tight across all 6 repeats (prefill duration range 1.78–1.86s, a fraction of
turn-1's variance). Turn 2's decode is also faster than turn-1's, consistent with a warm
executor. A "steady-state TTFT" proxy (turn-2 prefill + turn-2 decode/7, approximating time to
the first output token of an incremental turn) comes out to **~1.96s median**.

**But there's a second bottleneck this uncovers: fixed prefill shape/batching.** Turn 2's prefill
speed (9.4 tok/s) is *far* below turn 1's (66.4 tok/s) for the same model doing the same kind of
work — a 7x drop in apparent throughput for a 30x smaller input. That's not believable as real
per-token compute cost. `--helpfull` confirms `--prefill_chunk_size` and `--prefill_batch_sizes`
default to unchunked/whole-prompt processing here (`prefill_chunk_size=-1`, "Only supported by
the dynamic executor" — not what's running), and the delegate logs name the compiled subgraph
`prefill_128` — strongly suggesting the exported `.litertlm` model has a **statically-shaped
prefill signature bucketed at (at least) 128 tokens**. If so, a 17-token incremental turn still
pays compute proportional to a full 128-token bucket (17/1.81s ≈ 9.4 "tok/s" against the *nominal*
count, but 128/1.81s ≈ 71 tok/s against the *padded* count — consistent with turn 1's real
throughput). Not confirmed against the model export config itself, but the numbers line up too
well to be coincidence — see Open threads.

**Revised reading:** the session/cache-reuse mechanism is not the blocker it looked like after the
first pass — it works, and works consistently. The remaining gap to the ~1s pass mark for a real
incremental turn is now most plausibly this **fixed prefill-bucket floor** (~1.8s regardless of
how short the new turn's text is), not a cold-full-reprocess problem. That's a more tractable,
more specific target than "no session support" would have been.

## The brief used

Generated fresh via `uv run python3 -c "from engine.scenario import build_cell_and_guard; from
engine.brief import build_guard_brief; ..."` — same scenario as the 2026-09-09 run, same call
path, output captured to `guard_brief.txt` and pushed to the device rather than passed as a shell
argument (avoids quoting/escaping the em-dashes and nested quotes in the real brief text). Not
reproduced in full here since it's identical in structure to the one already in
`2026-09-09-poco-m4-pro.md` — only the specific mood/history values differ run to run.

## Verdict against the pass mark

**Closer than the first pass suggested, but still over the ~1s bar, and — surprisingly — not
clearly ahead of the pessimistic GGUF baseline on real incremental-turn latency.** With real
session reuse confirmed (see Update above), the honest steady-state number for LiteRT-LM CPU on
this device is **~1.96s** per incremental turn, against the GGUF/llama-server baseline's **1.33s
median** from 2026-09-09. Both numbers are desk-bound/single-sample-protocol in different ways
(GGUF: real 18-min hot/pocket run, n=192; LiteRT-LM: desk-bound n=6) so this isn't a fully settled
comparison, but it means the PRD §0 research's "shipping runtime has headroom above the GGUF
floor" hypothesis is **not yet confirmed** — raw prefill throughput clearly favors LiteRT-LM
(52.5–66 vs ~14–18 tok/s), but a fixed prefill-bucket floor (~1.8s regardless of how short the
new turn is, see Update) appears to be eating that advantage for the short, incremental turns a
real guard conversation is made of. Decode speed, the other half of end-to-end latency, is
roughly comparable-to-favoring LiteRT-LM (6.53 vs 3.87 tok/s mean) — so the gap is specifically in
prefill-floor overhead, not raw generation speed.

Thermal/hot-pocket behavior for LiteRT-LM: **not tested this session** — see Open threads. Given
the ~1.96s steady-state number, a hot/pocket run is worth doing regardless of whether the
prefill-bucket question gets resolved first — it exercises a different axis (sustained thermal
load) that this desk-bound session doesn't touch.

## Gotchas from this run

- **big.LITTLE core layout matters more than raw core count.** MT6781 has 2 performance + 6
  efficiency cores. Using all 8 threads (`--num_cpu_threads=8`) was consistently worse than 4,
  and 2 threads produced the best single reading of the session — spreading work onto the slow
  efficiency cores looks counterproductive here. Worth real tuning once the session-reuse
  question (below) is settled and a stable benchmark protocol exists.
- **`-c opt` barely moved the numbers** (decode 2.31→2.45 tok/s either way) — the earlier
  hypothesis that the first build's slow numbers were a `fastbuild`-vs-`opt` artifact was wrong;
  don't assume it without checking again on a cleaner benchmark.
- **`litert_lm_main`'s `--multi_turns` flag is dead code in that binary** — declared in the shared
  flags file and linked in, but never read by `litert_lm_main.cc`'s own logic, which always sends
  exactly one message. That's why piping a follow-up line after the brief just got concatenated
  into one 518-token prefill ("Total 1 turns") instead of being treated as a second turn. The
  sibling `litert_lm_advanced_main` binary (same repo, `runtime/engine:litert_lm_advanced_main`)
  *does* wire `--multi_turns` through the real session — see the Update above. Worth remembering
  for any future LiteRT-LM CLI work: check which of the two demo binaries actually implements a
  flag before concluding a feature doesn't exist.
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

- [ ] **Confirm/refute the fixed-prefill-bucket hypothesis.** Check the `.litertlm` model's
  exported signature shapes directly (or test with turn-2 inputs of varying length — e.g. 5, 50,
  100, 150 tokens — and see whether prefill duration stays flat until a threshold then jumps) to
  see whether ~1.8s really is a fixed floor around a 128-token bucket, and whether a
  differently-exported model (or a `--prefill_batch_sizes` override, if the *dynamic* executor
  can be selected) could shrink that floor for short incremental turns.
- [ ] Repeat the full 2026-09-09 protocol with `litert_lm_advanced_main` and real session reuse:
  hot/pocket, ~18-20 min, rotating prompts, thermal-drift-by-window table. Now unblocked.
- [ ] Revisit thread-count tuning with a proper batch (n≥10 per setting) once TTFT methodology is
  fixed — the current spot checks are too noisy to act on.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend to see if the 30.8s one-time init
  amortizes the way the flag's description implies.
- [ ] Compare against Q4_0 vs Q4_K_M on the GGUF side (carried over from 2026-09-09, still open).
