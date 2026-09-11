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

## Open threads

- [ ] **Test the GPU backend under the same full-duration protocol** — the CPU thermal fail is
  solid now; GPU (real OpenCL/Mali, already proven to load) and NPU (unavailable on this build,
  see Gotchas) sustained-load behavior could change the picture for LiteRT-LM overall. The
  chained feeder just needs `--backend=gpu` wired through (currently hardcoded to `cpu`).
- [x] Run a full 18-20 min hot/pocket test via chained bounded sessions — done, see Update above.
- [x] Fix the stdin-pacing artifact — done, see earlier Update.
- [x] Confirm/refute the fixed-prefill-bucket hypothesis — confirmed directly, see earlier Update.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend.
- [ ] Properly re-test thread-count sensitivity (n≥10 per setting) — this session's spot checks
  were too noisy (2.4x run-to-run variance at the same setting) to act on.
- [ ] Carried over from 2026-09-09, still untouched: Q4_0 vs Q4_K_M comparison on the GGUF side;
  confirm whether `termux-speech-to-text` is on-device or network; build the
  STT → inference → TTS glue script.
