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
attempt on 2026-09-09) backends. Headline finding: **prefill throughput clearly beats the GGUF
baseline** (52.5 vs ~14–18 tok/s median), supporting the PRD §0 research's expectation that the
shipping runtime has headroom above the llama.cpp/GGUF floor — but the raw **TTFT numbers from
this session aren't usable yet**, because `litert_lm_main` is a single-shot CLI with no
persistent session, so every invocation reprocesses the full ~490-token brief from cold (10s
TTFT) instead of reusing a cached persona prefix the way the GGUF baseline's `llama-server` did.
Full numbers, caveats, and the thread-count/big.LITTLE notes are in the results file. The build
itself: first attempt failed on `npm install -g @bazel/bazelisk` (`EACCES` on the hosted
runner — switched to downloading the bazelisk binary directly); second attempt succeeded in
~28 min cold, ~7 min with the Bazel cache warm; adding `-c opt` for the third build barely
changed the numbers (the earlier "must be a fastbuild artifact" theory doesn't hold up).

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
- **`litert_lm_main --multi_turns` is not a KV-cache-reuse mechanism** — tested directly (piped a
  follow-up line via stdin after `--input_prompt_file`), and it just concatenated everything into
  one larger single-shot prefill. Don't reach for this flag expecting per-turn incremental
  prefill; real session reuse (if the runtime supports it at all outside a full app integration)
  would need the Engine/Session API directly.
- **GPU backend's first-run cost is real but likely not representative**: 30.8s `Init Executor`,
  presumably OpenCL shader compilation. `--cache_compiled_shaders_only` exists for exactly this
  and is untested — an open thread, not a verdict against GPU.

## Open threads

- [ ] **Solve the session/KV-cache-reuse problem for LiteRT-LM** before any further TTFT
  comparison is meaningful — the single biggest open question from this session. See the results
  file for detail.
- [ ] Once that's solved, run the same 18-20 min hot/pocket protocol used for the GGUF baseline.
- [ ] Test `--cache_compiled_shaders_only` for the GPU backend.
- [ ] Properly re-test thread-count sensitivity (n≥10 per setting) — this session's spot checks
  were too noisy (2.4x run-to-run variance at the same setting) to act on.
- [ ] Carried over from 2026-09-09, still untouched: Q4_0 vs Q4_K_M comparison on the GGUF side;
  confirm whether `termux-speech-to-text` is on-device or network; build the
  STT → inference → TTS glue script.
