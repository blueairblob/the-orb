# 2026-09-10 — LiteRT-LM on real hardware, and the aarch64 dev-host build problem

## Context

Picking up the top open thread from 2026-09-09's spike devlog: test against LiteRT-LM directly —
"the actual shipping runtime, not llama.cpp/GGUF." Two separate problems had to be solved before
any measurement was possible: this OCI dev host can't build the Android binary at all (wrong host
architecture), and getting `adb` talking to `poco-m4-pro` from a cloud host with no LAN access to
the phone required stitching together wireless debugging, Tailscale, and an SSH tunnel through
Termux. Full benchmark results are in `spike/results/2026-09-10-poco-m4-pro-litert-lm.md` — this
entry covers what it took operationally to get there.

## Decisions

| Decision | Rationale | Alternatives considered |
|---|---|---|
| Cross-build via a `workflow_dispatch` GitHub Actions job on a free x86_64 runner, rather than building locally | This host is aarch64; Google ships Android NDK host toolchains only for linux-x86_64/macOS/Windows (confirmed via `android/ndk#1440`) — the documented `bazel build --config=android_arm64` step cannot run here. The target binary is Android arm64 regardless of the build host's arch, so any x86_64 machine works | A temporary x86_64 OCI VM (more setup, ongoing cost); a community aarch64-host NDK port or box64/qemu emulation (unofficial, unverified, likely slow for a large C++ build) |
| Use the existing `jibjabjog` (Hermes bot) `gh` auth to push the workflow, rather than switching identities | User's explicit call after I flagged the mismatch (this repo's remote is `blueairblob/the-orb`, but `gh` here is authenticated as the Hermes deployment's bot account) | Switch `gh auth` to a personal account first; use a separate scratch repo under the bot account |
| Extract `adb` from Ubuntu's arm64 `.deb` via `apt-get download` + `dpkg-deb -x`, no `sudo` | Google's `platform-tools-latest-linux.zip` is x86_64-only (same problem as the NDK); `sudo apt-get install` needed a password non-interactively, which wasn't available | Ask the user to run the install themselves (asked once, sudo still needed a real tty even from their own `!`-prefixed command) |
| Tunnel adb pairing/connect through an SSH port-forward into Termux's sshd, targeting the phone's own `127.0.0.1:<port>` | Android's wireless-debugging pairing service only listens on the phone's local Wi-Fi interface (`192.168.0.x`), which this cloud host can't route to directly. Termux's sshd is reachable over Tailscale, and once inside that shell, `127.0.0.1:<port>` on the phone is exactly what the pairing service is bound to | Have the user temporarily join the same LAN as the host (not possible, host is a cloud VM); use a pure-Python adb client library (`adb-shell`) — checked, but it doesn't implement Android 11+'s SPAKE2/TLS wireless-pairing handshake, only the old pre-shared-key protocol |

## Commands

```bash
# [APPLIED] Extract adb without root from Ubuntu's arm64 package
cd /tmp && apt-get download adb android-libbase android-libboringssl android-libcutils \
  android-liblog android-libziparchive
for f in adb android-libbase android-libboringssl android-libcutils android-liblog android-libziparchive; do
  dpkg-deb -x "$(ls ${f}_*.deb)" ~/android-tools/adb-local
done
export LD_LIBRARY_PATH=~/android-tools/adb-local/usr/lib/aarch64-linux-gnu/android
~/android-tools/adb-local/usr/lib/android-sdk/platform-tools/adb version
```

```bash
# [APPLIED] Tunnel through Termux's sshd to reach the wireless-debugging pairing service
# (port numbers change every time Wireless debugging is toggled — get fresh ones from the phone)
ssh -p 8022 -o BatchMode=yes -o ExitOnForwardFailure=yes -f -N \
  -L <pairing-port>:127.0.0.1:<pairing-port> u0_382@100.105.178.99
adb pair 127.0.0.1:<pairing-port> <6-digit-code>

# Same trick for the main connect port
ssh -p 8022 -f -N -L <connect-port>:127.0.0.1:<connect-port> u0_382@100.105.178.99
adb connect 127.0.0.1:<connect-port>
```

```yaml
# [APPLIED] .github/workflows/litert-lm-android-build.yml — key steps
# (full file in the repo; checks out google-ai-edge/LiteRT-LM, not this repo)
- run: bazelisk build --config=android_arm64 -c opt //runtime/engine:litert_lm_main
```

## Outcome

Got a real Android arm64 `litert_lm_main` built and running on `poco-m4-pro`, both CPU (XNNPACK)
and GPU (real OpenCL/Mali driver, not the software Vulkan fallback that sank the equivalent GPU
attempt on 2026-09-09) backends. First pass: prefill throughput clearly beat the GGUF baseline
(52.5 vs ~14–18 tok/s median), but raw TTFT (~10s) looked bad — traced to `litert_lm_main` being
a single-shot CLI with no persistent session, reprocessing the full ~490-token brief from cold
every call. Same-session follow-up: found and built the sibling `litert_lm_advanced_main` binary,
whose `--multi_turns` flag (unlike `litert_lm_main`'s, which is dead code) is wired through the
real `Conversation`/`Session` API. **Confirmed real KV-cache reuse across turns** — a follow-up
turn only reprocessed 17 tokens instead of the full ~500, stable across 6 repeats — giving a real
steady-state TTFT of ~1.96s. That's still over the ~1s pass mark and, unexpectedly, not clearly
ahead of the GGUF baseline's 1.33s hot-run median: the data now points at a **fixed prefill-bucket
floor** (the model's `prefill_128`-named compiled subgraph suggests short turns still pay
close to a full 128-token prefill's compute) as the likely remaining bottleneck, not the
session-reuse question that first looked like the blocker. Full numbers in the results file. The
build itself: first attempt failed on `npm install -g @bazel/bazelisk` (`EACCES` on the hosted
runner — switched to downloading the bazelisk binary directly); second attempt succeeded in
~28 min cold, ~7 min with the Bazel cache warm; adding `-c opt` for the third build barely
changed the numbers (the earlier "must be a fastbuild artifact" theory doesn't hold up); a fourth
build added `litert_lm_advanced_main` alongside the original target, ~same warm-cache build time.

## Gotchas & notes

- **MIUI/HyperOS kills backgrounded Tailscale, again** — same gotcha as 2026-09-09, hit again
  this session. The fix (Unrestricted battery + Autostart) had already been applied, but the
  Tailscale *app* itself still needs to be brought to the foreground at least once per session
  after it's been killed; the systemic fix doesn't make it un-killable, just faster to revive.
- **`gh` on this host is authenticated as the Hermes deployment's bot account (`jibjabjog`), not
  a personal GitHub account**, despite this repo's remote being the user's own
  `blueairblob/the-orb`. Worth remembering for any future task that pushes to this repo from this
  host — flag it rather than assume.
- **`adb-shell` (pure-Python) doesn't support Android 11+ wireless pairing** — only the older
  pre-shared-key `adb connect` protocol. Would have been a much simpler no-sudo, no-NDK-style-arch
  workaround if it had; ruled out after checking its source rather than assuming.
- **`litert_lm_main --multi_turns` is dead code in that specific binary** — declared via the
  shared flags file but never read by `litert_lm_main.cc`'s own logic, so piping a follow-up line
  after `--input_prompt_file` just concatenated everything into one larger single-shot prefill.
  The sibling `litert_lm_advanced_main` binary implements the same flag properly through
  `runtime/engine/litert_lm_lib.cc`'s `RunMultiTurnConversation`, which does real per-turn
  `SendMessage` calls on one `Conversation`. Lesson: check which of LiteRT-LM's two demo binaries
  actually implements a flag before concluding a capability doesn't exist.
- **Fixed prefill-bucket floor, not session support, looks like the real remaining latency
  bottleneck.** A 17-token incremental turn took ~1.8s to prefill — 7x slower "tok/s" than the
  501-token first turn's 66 tok/s, for 30x less nominal work. The delegate logs name the compiled
  subgraph `prefill_128`; the numbers are consistent with the exported model having a
  statically-shaped prefill signature bucketed at 128 tokens, so any turn under that still pays
  close to the full bucket's compute. Not confirmed against the model export itself — see the
  results file's open threads.
- **GPU backend's first-run cost is real but likely not representative**: 30.8s `Init Executor`,
  presumably OpenCL shader compilation. `--cache_compiled_shaders_only` exists for exactly this
  and is untested — an open thread, not a verdict against GPU.

## Update — 2026-09-11: confirmed the bucket floor directly, hot/pocket run undershoots

Swept turn-2 length from 11 to 196 tokens against the same session (single sample per length —
a confirmation pass, not a rigorous batch): 11-88 tokens all cost ~2s regardless of actual length
(an 8x range in real tokens, flat wall-clock time); crossing ~128 tokens roughly doubled it
(138 and 196 tokens both landed at 3.4-4.1s). Confirms the fixed-bucket-floor hypothesis directly
— any incremental turn under ~128 tokens pays the same ~2s floor here, which covers essentially
every real player utterance in a guard conversation.

Then attempted the hot/pocket sustained-load run twice (user unplugged the phone and pocketed it
for both). Both undershot the intended 18-20 minutes: fed 345 then 881 rotating short follow-ups
via `cat file | adb shell`, but only ~125-126 lines per run actually got separately-timed
prefill/decode entries — the rest were tokenized (confirmed via `TextToTokenIds Turns` matching
the full line count) but seemingly coalesced into fewer real inference calls somewhere in the
async pipeline, likely because piping the whole file at once buffers far ahead of what the model
can consume. Net real duration: ~9 and ~11 minutes, not the intended 18-20. Within those shorter
windows, both runs independently showed **decode time rising ~19-21% from first half to second
half** — the opposite of the GGUF baseline's flat 18-minute result. Suggestive of thermal
throttling showing up faster on LiteRT-LM CPU than it did on GGUF, but not confirmed given the
shorter duration and the turn-coalescing artifact. Full numbers and tables in the results file.

## Update — 2026-09-11 (later): paced feeder built, a hard session ceiling found, clearest drift yet

Built `paced_hotpocket.py` (`pexpect`-driven, session scratchpad, not checked in): send one line,
wait for that exact turn's reply and the next prompt cue, then send the next. First version had a
sequencing bug (re-waiting for a cue that only appears after the next send, deadlocking on turn 2)
— fixed by moving the initial wait outside the per-turn function, and switched `expect()` to
`expect_exact()` after a mystifying timeout on a cue that was visibly already in the buffer
(regex vs. literal-match edge case, not fully root-caused, exact-match sidesteps it). Verified
clean with a 30s/7-turn dry run before trusting it with anything longer.

**Attempt 1** died after 2.5 minutes (40 clean turns) — not a script bug: confirmed via `nc` from
inside Termux itself that Android's Wireless debugging service stops listening the moment the
phone leaves Wi-Fi range (`127.0.0.1:<port>` went from open to "Connection refused"). Re-pairing
wasn't needed once back on Wi-Fi (the device still trusted the host's key), just a fresh connect
port from the Wireless debugging screen.

**Attempt 2**, back on Wi-Fi, ran cleanly for 133 real turns (~6.8 minutes) before hitting a new,
real limit: `Chosen prefill work group size exceeds available state entries (100)` — **a
long-lived Conversation session has a hard capacity ceiling around ~100 turns.** Past that, the
tool kept matching the prompt cue successfully (script saw no error) but stopped doing real work —
latency dropped to a fake ~0.15-0.2s and output degenerated into repeated garbage tokens. The
script's own "2000 turns completed" count is misleading; only the first 133 are real.

The 133 real turns gave the cleanest thermal signal of the whole spike: a **monotonic +27%**
latency increase across thirds of the window (2.73s → 2.92s → 3.48s), not just a first/second-half
average. Combined with the two noisier same-day runs (both independently +19-21% decode), that's
four-for-four agreement on direction, in clear contrast to GGUF's flat 18-minute baseline. Full
numbers in the results file, including a note that this ever-growing-session test methodology
isn't quite how the real engine would use the model anyway (PRD §4 rebuilds the brief from the
object model each turn rather than accumulating raw conversation history) — the ~100-turn ceiling
may matter less in practice than it would for a naive chat-style integration, but is a real
constraint worth knowing about regardless.

## Update — 2026-09-11 (final): full 21-minute run settles the thermal question — it's a fail

Extended `paced_hotpocket.py` (now checked in at `spike/scripts/paced_hotpocket.py`, generates
its brief live from `engine.brief`/`engine.scenario` rather than a stale copy) to chain multiple
45-turn sessions back-to-back, comfortably under the ~100-turn ceiling, until a time budget is
used. Ran the full protocol: 21 minutes, unplugged, in-pocket, 7 sessions, all clean (no ceiling
hits, no drops, no errors).

**Result, by 3-minute window (directly comparable to the GGUF baseline's own table):** flat/noisy
for the first ~12 minutes (3.6-4.0s), then a clear **+25-30%** step up for the remaining 9 minutes
(4.5-5.1s) — including session cold-start cost itself nearly doubling (12.3s → 21.1s, session 1
vs session 6). GGUF's 18.1-minute baseline showed no equivalent trend anywhere in its run. Four
earlier, methodologically-caveated observations from earlier this session all pointed the same
direction; this run has none of those caveats.

**This settles the open question:** LiteRT-LM CPU fails the thermal half of the PRD §0 pass mark
on this device, plainly, not just "leans that way." Combined with the already-established ~2s
fixed prefill-bucket floor (over the ~1s TTFT bar on its own), neither half of the gate is met by
LiteRT-LM's CPU backend at this quant/config — a materially more negative conclusion than the PRD
§0 research's working assumption that the shipping runtime would have headroom over the GGUF
floor. Specific to CPU; GPU/NPU sustained-load behavior remains untested and is now the natural
next step before treating this as a verdict on LiteRT-LM as a whole.

## Update — 2026-09-11 (GPU): the CPU thermal fail does not reproduce on GPU

Wired `--backend` through `paced_hotpocket.py` and ran the identical 21-minute chained-session
protocol on GPU (80 turns/session, 4 sessions). First had to reconnect twice more — the
Wireless-debugging port died again between test runs (routine at this point, not a new finding)
and a tunnel process had silently exited on its own between commands.

GPU cold-start time is real but wildly inconsistent independent of anything measured here: three
spot checks the same session read 30.8s, 75.7s, and 9.6s for nominally-comparable cold starts,
despite persistent shader/weight cache files existing on disk (`_mldrift_program_cache.bin`,
`_mldrift_weight_cache.bin`) that don't obviously explain the swing — not root-caused. This run's
own 4 sessions were a tight, fast 8.9-9.6s throughout, for reasons not fully understood either.

**The result itself is unambiguous: no thermal degradation.** By-thirds per-turn latency: 3.23s
→ 3.48s → 3.13s — noisy, not climbing, ending *lower* than the middle. Cold-start cost across the
4 sessions stayed flat (8.9-9.6s, no creep). Directly contrasts with CPU's clear +25-30% climb and
near-doubled cold-start cost over the identical protocol. GPU still doesn't solve the ~1s TTFT
problem (mean 3.28s/turn, not meaningfully better than CPU's early-window numbers) but it does not
carry CPU's additional thermal problem. If the shipping product uses GPU (LiteRT-LM's documented
default) rather than CPU, the sustained-load concern from the CPU runs may simply not apply.

## Open threads

- [ ] **Root-cause GPU's cold-start variance** (9.6s / 30.8s / 75.7s observed for nominally
  comparable cold starts) — matters for real product startup latency even though it doesn't
  affect the sustained-load verdict.
- [x] Test the GPU backend under the same full-duration protocol — done, see Update above.
- [x] Run a full 18-20 min hot/pocket test via chained bounded sessions — done, see earlier Update.
- [x] Fix the stdin-pacing artifact — done, see earlier Update.
- [x] Confirm/refute the fixed-prefill-bucket hypothesis — confirmed directly, see earlier Update.
- [ ] NPU remains unavailable on this build (`kLiteRtStatusErrorInvalidArgument`) — the one
  backend still fully untested.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend.
- [ ] Properly re-test thread-count sensitivity (n≥10 per setting) — this session's spot checks
  were too noisy (2.4x run-to-run variance at the same setting) to act on.
- [ ] Carried over from 2026-09-09, still untouched: Q4_0 vs Q4_K_M comparison on the GGUF side;
  confirm whether `termux-speech-to-text` is on-device or network; build the
  STT → inference → TTS glue script.

## Update — 2026-09-12: chased "GPU should be way better," patched a real upstream bug, and it
wasn't the answer

Prompted by a fair question: published LiteRT-LM numbers make our GPU decode look bad by
comparison — was that a wrong driver, or a bad build? Driver was already ruled out (real Mali
OpenCL, confirmed 2026-09-10). Build was already the stock upstream `--config=android_arm64 -c
opt` with no missing flags. So went looking at the LiteRT-LM issue tracker instead, and found
something real: three independent open reports (google-ai-edge/LiteRT-LM#1850, #2202, #2421) of
Gemma 4 E2B crashing or corrupting output on Mali GPUs specifically, all pointing at the same
root cause — `AdvancedSettings::hint_waiting_for_completion`, a documented OpenCL quality fix for
AMD/Mali GPUs, is auto-enabled by `runtime/engine/engine_settings.cc` only for metadata-tagged
"generic" models. Gemma 4 gets a different, unrelated auto-setting instead (`disable_delegate_
clustering`) and never receives this hint. Confirmed via `gh api` that all three issues are still
open and that no release through v0.17.0 (2026-09-09, essentially what we'd already built)
mentions a fix.

**What we did:**
1. Wrote `spike/patches/gemma4-mali-hint-waiting-for-completion.patch` extending the upstream
   condition to also cover `has_gemma4()`.
2. Wired it into `litert-lm-android-build.yml` via a new `apply_local_patches` input — checkout
   this repo alongside LiteRT-LM, `git apply` before the Bazel build. First attempt silently
   built *unpatched*: `actions/checkout` git-cleans its target directory by default, and the
   LiteRT-LM checkout (no `path:`, targets workspace root) ran after the patches checkout and
   wiped it. Fixed by reordering — LiteRT-LM checkout first, then the patches checkout into a
   `path: orb-patches` subdirectory that nothing cleans afterward.
3. Rebuilt (confirmed via CI log: "Applied patch runtime/engine/engine_settings.cc cleanly"),
   downloaded the artifact, pushed the new `litert_lm_main`/`litert_lm_advanced_main` and all
   `lib*.so` to `/data/local/tmp/` on `poco-m4-pro` over the still-live adb-over-Tailscale
   connection from the 09-11 session (no `pexpect` was installed for `paced_hotpocket.py` this
   time — `uv add --dev pexpect` fixed that).
4. A 3-minute desk-bound sanity run (3 sessions × 20 turns, GPU) looked dramatically better at
   first glance: decode ~5.0-5.8 tok/s vs. the 2026-09-10 single-shot figure of 2.52 tok/s, no
   crashes past the turn-2-4 window the GitHub issues describe.
5. Re-ran the *real* comparison: the identical 21-minute chained-session hot/pocket protocol
   (unplugged, in-pocket, 80 turns/session) used for the original 2026-09-11 GPU result, this
   time with the patched binary.

**The honest result — and a correction to what I told the user mid-session:** pulling the
2026-09-11 unpatched run's own raw per-turn benchmark logs (still on disk from the prior session)
for a proper sustained-vs-sustained comparison showed **no measurable difference**:

| Metric | Unpatched (09-11) | Patched (09-12) |
|---|---|---|
| Decode speed, mean | 4.94 tok/s | 4.89 tok/s |
| Prefill speed, mean | 14.97 tok/s | 15.37 tok/s |
| Cold-start range | 8.9-9.6s | 8.94-9.54s |
| By-thirds latency | 3.23→3.48→3.13s | 3.15→3.45→3.20s |
| Crashes | 0/307 | 0/316 |

The "2.52 tok/s, worse than CPU" figure that kicked off this whole investigation was a single
desk-bound cold sample from 2026-09-10, already flagged in that file as "don't read too much into
it" — the *actual* sustained-load decode speed was already ~4.9 tok/s even unpatched, matching
the patched result almost exactly. I'd reported the 3-minute sanity check's improvement to the
user as if it were the real finding before running the properly-matched comparison; the full
21-minute retest overturned that. Worth remembering: a short isolated sanity check against a
flagged-unreliable baseline is not the same evidence as a matched sustained-load comparison —
don't report the former as a conclusion.

**Actual conclusion:** this device/workload (text-only guard brief, no vision encoder, no
speculative decoding) doesn't trigger the resource-accumulation bug those three issues describe —
plausibly because it carries none of the extra GPU memory pressure the upstream repro configs
had. The literature numbers that set the "way better" expectation (Samsung S26 Ultra, Pixel 8
post-patch) come from meaningfully stronger GPUs than this device's Mali-G57 MC2 (2 cores, budget
tier). Most likely explanation left standing: a hardware-tier ceiling, not a fixable
misconfiguration. Patch stays in the repo — real fix for upstream's own stated intent, harmless,
may matter on other devices/models — but it's not the answer here.

Full write-up and raw traces: `spike/results/2026-09-10-poco-m4-pro-litert-lm.md` (2026-09-12
Update section) and `spike/results/raw/2026-09-12-poco-m4-pro-gpu-patched/`.
