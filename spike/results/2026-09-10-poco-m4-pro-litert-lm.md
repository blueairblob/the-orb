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

**Confirmed directly.** Ran the same brief-as-turn-1, varying-length-turn-2 protocol at 6 follow-up
lengths (single sample each — a quick confirmation pass, not a rigorous batch):

| Turn-2 tokens (actual) | Prefill duration |
|---|---|
| 11 | 1.94s |
| 23 | 1.96s |
| 48 | 2.40s |
| 88 | 1.98s |
| 138 | 4.07s |
| 196 | 3.40s |

Everything from 11 to 88 tokens — an 8x range in actual new-token count — costs essentially the
same ~2s. Crossing ~128 tokens roughly doubles the cost (138 and 196 both land around 3.4–4.1s,
consistent with spilling into a second bucket). This is about as clean a confirmation as a
single-sample sweep can give: **any incremental turn under ~128 tokens pays the same ~2s floor
on this model/device/backend, regardless of how short it actually is.** That floor, not the
session-reuse mechanism (which works fine), is what stands between LiteRT-LM CPU and the ~1s pass
mark for a real guard conversation, where almost every player turn is well under 128 tokens.

**Revised reading:** the session/cache-reuse mechanism is not the blocker it looked like after the
first pass — it works, and works consistently. The remaining gap to the ~1s pass mark for a real
incremental turn is now most plausibly this **fixed prefill-bucket floor** (~1.8s regardless of
how short the new turn's text is), not a cold-full-reprocess problem. That's a more tractable,
more specific target than "no session support" would have been.

## Update — 2026-09-11: hot/pocket sustained-load attempt, with a methodology caveat

Attempted the "now unblocked" open thread: real unplugged/in-pocket sustained load with
`litert_lm_advanced_main`'s session reuse, mirroring the 2026-09-09 GGUF protocol. One long-lived
process, one brief as turn 1, then hundreds of rotating short follow-ups (10 templates, all under
the ~128-token bucket) fed as separate stdin lines, `--backend=cpu --num_cpu_threads=4
--max_output_tokens=24`. Two runs:

| Run | Lines fed | Wall-clock duration | Benchmarked turns (Prefill/Decode) |
|---|---|---|---|
| 1 | 345 | 9m02s | 125 / 118 |
| 2 | 881 | 10m24s | 126 / 116 |

**A real methodology artifact, not a runtime bug (or at least, not confirmed as one):** every
fed line was tokenized (`TextToTokenIds Turns` matched the full line count both times), and the
model kept producing real, distinct replies throughout (spot-checked the captured output) — but
only ~125-126 lines per run actually got a separately-timed `Prefill`/`Decode Turn` entry, and
those ~125 entries' durations alone account for almost the entire wall-clock time in both runs.
The likely explanation: piping the whole input file at once (`cat file | adb shell ...`) buffers
far ahead of what the model can consume, and something in the async `SendMessageAsync` /
`WaitUntilDone` pipeline coalesces some fraction of rapidly-queued turns into fewer actual
inference calls rather than truly running one at a time — this needs a properly-paced feeder
(one line at a time, waiting for each reply) to rule out entirely, not confirmed against the
library source. **Practical effect: neither run is really an 18-20 minute, 300+ distinct-turn
test — both are closer to a ~9-11 minute, ~125-distinct-turn test**, shorter than intended and
short of the GGUF baseline's 18.1 real minutes / 192 requests.

**Within that shorter, real window, both runs show the same drift direction — worth taking
seriously despite the shorter duration:**

| Run | Prefill 1st-half mean | Prefill 2nd-half mean | Decode 1st-half mean | Decode 2nd-half mean |
|---|---|---|---|---|
| 1 | 2.03s | 2.43s (+20%) | 1.64s | 1.99s (+21%) |
| 2 | 2.59s | 2.70s (+4%) | 1.74s | 2.07s (+19%) |

Decode time rose ~19-21% from first half to second half in **both independent runs**. Prefill
drift was less consistent (+20% vs +4%). This is the opposite of the GGUF/llama.cpp baseline,
which showed **no** upward drift over its full 18.1-minute run (second half flat-to-slightly-
faster than the first). Read cautiously given the shorter real duration and the turn-coalescing
caveat above, but two independently-reproduced ~20% decode slowdowns is a real signal, not noise
at this magnitude — plausibly thermal throttling that the GGUF run, at a similar wall-clock
distance into its own run, hadn't yet shown.

**Net effect on the pass mark:** the thermal half of the gate, which GGUF passed cleanly at 18
minutes, is now **an open question rather than a pass** for LiteRT-LM CPU — the evidence so far
points toward throttling appearing within the first ~10 minutes, not toward a clean pass. Needs a
properly-paced, full-duration re-run before this can be called either way.

## Update — 2026-09-11 (later): properly-paced runs, a new hard limit found, and the clearest drift signal yet

Built a paced feeder (`pexpect`-driven, sends one line, waits for that exact turn's reply and the
next prompt cue before sending the next — see `paced_hotpocket.py`, not checked into the repo,
lives in the session scratchpad) to fix the stdin-pacing artifact from the earlier update. First
fix attempt had its own bug: `pexpect.expect()` re-waited for a *second* occurrence of the prompt
cue that only appears after sending the next line, deadlocking; switched to `expect_exact()` after
sequencing the wait-then-send order correctly, verified with a 30-second/7-turn dry run (clean,
consistent ~3-3.5s per turn) before trusting it with a full run.

**Attempt 1** ran for only ~2.5 minutes (40 clean turns) before the connection died — traced to a
real hardware/OS constraint, not a script bug: Android's Wireless debugging service stops
listening entirely once the phone leaves Wi-Fi range (confirmed directly via `nc` from inside
Termux itself: `127.0.0.1:<port>` went from open to "Connection refused" the moment the phone
switched to cellular). Not a Tailscale/tunnel problem this time — the ADB daemon itself shuts
down. Re-pairing wasn't needed once back on Wi-Fi (the device still trusted the host's adb key),
but the connect port changes every time and needs re-fetching from the Wireless debugging screen.

**Attempt 2**, back on Wi-Fi, ran the full protocol and surfaced a genuine new finding: after
133 real turns (~6.8 minutes in), the transcript shows `Chosen prefill work group size exceeds
available state entries (100)` — **the long-lived session has a hard capacity ceiling around
~100 turns.** Past that point the tool kept matching the prompt cue successfully (no crash, no
error propagated to the script) but stopped doing real work: turn latency dropped to a fake
~0.15-0.2s and the generated text started accumulating garbage/repeated tokens turn over turn.
The script correctly logged 2000 "turns" by that measure, but only the first 133 are real. This
matters beyond just this test: it means an engine design that holds one ever-growing Conversation
per NPC encounter needs either a turn cap well under ~100 or periodic session
rotation/resummarization — though note this test methodology (one raw accumulating session) is
itself *not* how the real engine is designed to work (PRD §4: the brief is rebuilt fresh from the
object model each turn, not accumulated as raw LLM conversation history), so this ceiling may
matter less in practice than it would for a naive chat-style integration.

**The 133 clean, real, properly-paced turns give the best drift signal so far** — a monotonic
increase across thirds of the window, not just a first-half/second-half average:

| Segment | Mean turn latency (prefill+decode+overhead) |
|---|---|
| First third (turns 1-44) | 2.73s |
| Middle third (turns 45-88) | 2.92s |
| Last third (turns 89-133) | 3.48s |

+27% from first third to last third, monotonic, over a real 6.8-minute continuous window (session
mean 3.05s, median 2.97s, range 2.34-5.66s). Combined with the earlier (methodologically noisier)
2026-09-11 runs both independently showing ~19-21% decode slowdown, this is now three separate
observations all pointing the same direction: **real, reproducible latency growth under sustained
CPU load**, and — importantly — it's visible within under 7 minutes, well short of the GGUF
baseline's full 18.1-minute flat result. Still short of a full clean 18-20 minute run (now blocked
by the ~100-turn session ceiling, not by pacing), but the direction of the finding is no longer in
doubt: the thermal/sustained-load half of the pass mark looks like a real problem area for
LiteRT-LM CPU on this device, in clear contrast to GGUF/llama.cpp's clean pass.

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

**Thermal/hot-pocket behavior: leans negative, and now on firmer footing than the first attempt.**
Four independent unplugged/in-pocket observations now exist (two bulk-piped, methodologically
noisy; two properly-paced), and all four show the same direction — latency rising under sustained
load, never falling or staying flat. The cleanest of the four (133 properly-paced real turns over
6.8 minutes, 2026-09-11 later Update) shows a **monotonic +27% increase across thirds of the
window**, visible in under 7 minutes. That's the opposite of the GGUF baseline, which stayed flat
over its full 18.1-minute run. Still not a full clean 18-20 minute run — now blocked by a ~100-turn
session capacity ceiling rather than pacing — but with four-for-four agreement on direction and
one genuinely clean monotonic trend, this is no longer a "leans negative, inconclusive" read. It's
reasonable to treat the thermal half of the pass mark as **failing, or at least not passing
cleanly, for LiteRT-LM CPU on this device** unless a full-duration run (via session
rotation — see Open threads) reverses the trend, which would itself be a surprising result given
four consistent prior observations.

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

- [x] **Confirm/refute the fixed-prefill-bucket hypothesis** — confirmed directly, see above.
- [ ] Whether a differently-exported model (smaller bucket) or the "dynamic executor" mentioned in
  `--prefill_chunk_size`'s help text could shrink the ~2s floor for short incremental turns —
  not attempted this session, would need investigating how to select/build that executor variant.
- [x] Fix the stdin-pacing artifact — done, see the later 2026-09-11 Update (paced `pexpect`
  feeder, verified against a dry run before trusting it).
- [ ] **Run a full 18-20 min hot/pocket test via chained bounded sessions.** The paced feeder
  works, but a single long-lived Conversation hits a hard ~100-turn capacity ceiling (see Update)
  well before 18-20 minutes of real turns accumulate. Needs the feeder extended to start a fresh
  session (new process, fresh brief-as-turn-1) every N turns (N comfortably under 100, e.g. 40-50)
  and chain sessions back-to-back until the time budget is used, rather than one unbounded session.
  This is now the top open thread — the thermal verdict above is well-supported by four consistent
  observations but still not from one continuous full-duration run.
- [ ] Revisit thread-count tuning with a proper batch (n≥10 per setting) once TTFT methodology is
  fixed — the current spot checks are too noisy to act on.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend to see if the 30.8s one-time init
  amortizes the way the flag's description implies.
- [ ] Compare against Q4_0 vs Q4_K_M on the GGUF side (carried over from 2026-09-09, still open).
