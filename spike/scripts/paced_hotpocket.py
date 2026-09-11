#!/usr/bin/env python3
"""Properly-paced, session-chained hot/pocket feeder for
litert_lm_advanced_main --multi_turns.

History (see spike/results/2026-09-10-poco-m4-pro-litert-lm.md and the
matching devlog for the full story):
- v1 piped a whole input file at once (`cat file | adb shell ...`); the
  async pipeline coalesced most queued turns into far fewer actually-timed
  inference calls than lines fed. Fixed by sending one line at a time and
  waiting for that exact turn's reply before sending the next.
- v2 (this file, single-session) found a hard session capacity ceiling:
  a long-lived Conversation breaks down after ~100 turns ("Chosen prefill
  work group size exceeds available state entries (100)"), after which the
  tool silently stops doing real work while still reporting success.
- v3 (this version): chains multiple bounded sessions (fresh process, fresh
  brief-as-turn-1, comfortably under the ~100-turn ceiling) back-to-back
  until the time budget is used, so a full 18-20+ minute run is possible
  without hitting the ceiling.

Usage:
    python3 paced_hotpocket.py --minutes 20 --turns-per-session 45 \
        --out /path/to/log.jsonl
"""
import argparse
import json
import os
import random
import sys
import time

import pexpect

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, REPO_ROOT)

ADB = os.environ.get(
    "ADB_PATH",
    os.path.expanduser(
        "~/android-tools/adb-local/usr/lib/android-sdk/platform-tools/adb"
    ),
)
LD_LIBRARY_PATH = os.environ.get(
    "ADB_LD_LIBRARY_PATH",
    os.path.expanduser("~/android-tools/adb-local/usr/lib/aarch64-linux-gnu/android"),
)
PROMPT_CUE = "Please enter the prompt (or press Enter to end): "

UTTERANCES = [
    "You beg him again to let you out.",
    "Please, just five minutes outside the cell.",
    "You ask if he ever gets lonely out here.",
    "You tell him the food was terrible again tonight.",
    "You ask what happens tomorrow at first light.",
    "You remind him you never actually poached anything.",
    "You ask about his brother, carefully, watching his face.",
    "You go quiet, then just say his name softly.",
    "You ask if the captain ever checks on him.",
    "You tell him you are cold too, through the door.",
]


def flatten_brief():
    """Generates a real brief via the actual engine (not a stale static copy),
    matching how the object model would produce it, then flattens it to one
    line since the remote REPL reads one turn per stdin line."""
    from engine.brief import build_guard_brief
    from engine.scenario import build_cell_and_guard

    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 60
    scenario.guard.remember("player", "please let me out")
    scenario.guard.remember("guard", "No.")
    text = build_guard_brief(
        scenario.guard, scenario.door, scenario.room, scenario.premise
    )
    return " ".join(text.split("\n"))


def spawn_session(turn_timeout, log_path):
    cmd = (
        f'{ADB} shell -tt "cd /data/local/tmp && '
        f"LD_LIBRARY_PATH=/data/local/tmp ./litert_lm_advanced_main "
        f"--backend=cpu --num_cpu_threads=4 "
        f"--model_path=/data/local/tmp/model.litertlm "
        f'--multi_turns=true --benchmark=true --max_output_tokens=24"'
    )
    child = pexpect.spawn(
        "/bin/bash",
        ["-c", cmd],
        encoding="utf-8",
        timeout=turn_timeout,
        env={**os.environ, "LD_LIBRARY_PATH": LD_LIBRARY_PATH},
    )
    child.logfile = open(log_path, "w")
    return child


def send_and_wait(child, records, session_idx, text, label):
    # Caller must already have consumed the PROMPT_CUE that precedes this
    # send (either the initial one, or the one left by the previous
    # send_and_wait call) - do NOT re-expect it here, that would wait for a
    # *second* occurrence that only appears after this turn completes,
    # deadlocking against the sendline below.
    t0 = time.time()
    child.sendline(text)
    idx = child.expect_exact([PROMPT_CUE, pexpect.EOF, pexpect.TIMEOUT])
    t1 = time.time()
    rec = {
        "session": session_idx,
        "label": label,
        "text": text,
        "wait_seconds": round(t1 - t0, 3),
        "timestamp": t1,
        "expect_result": idx,
    }
    records.append(rec)
    print(
        f"[s{session_idx:03d} #{len(records):5d}] {label:8s} "
        f"{rec['wait_seconds']:6.2f}s  {text[:40]!r}"
    )
    return idx


def end_session_cleanly(child):
    try:
        child.sendline("")
        child.expect(pexpect.EOF, timeout=60)
    except Exception as e:
        print("Cleanup expect failed (non-fatal):", e)
    child.close(force=True)


def run_one_session(session_idx, brief, turns_per_session, deadline, turn_timeout,
                     out_base, records):
    """Returns "ok", "brief_failed", or "startup_failed" - the caller uses
    this to detect a broken connection (e.g. the phone drops off wifi again
    mid-run) rather than spinning through --max-sessions instantly."""
    log_path = f"{out_base}.session{session_idx:03d}.raw.log"
    child = spawn_session(turn_timeout, log_path)
    try:
        print(f"--- session {session_idx}: waiting for initial prompt cue ---")
        try:
            child.expect_exact(PROMPT_CUE, timeout=60)
        except Exception as e:
            print(f"session {session_idx}: never got initial prompt cue: {e}")
            return "startup_failed"

        idx = send_and_wait(child, records, session_idx, brief, "brief")
        if idx != 0:
            print(f"session {session_idx}: brief turn did not return cleanly, "
                  f"abandoning this session. idx={idx}")
            return "brief_failed"

        n = 0
        while n < turns_per_session - 1 and time.time() < deadline:
            text = random.choice(UTTERANCES)
            idx = send_and_wait(child, records, session_idx, text, f"turn{n + 1}")
            n += 1
            if idx != 0:
                print(f"session {session_idx}: non-clean turn, ending session. "
                      f"idx={idx}")
                break
    finally:
        end_session_cleanly(child)
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--turns-per-session", type=int, default=45,
                     help="Kept comfortably under the ~100-turn session "
                          "capacity ceiling found on 2026-09-11.")
    ap.add_argument("--out", default="/tmp/paced_hotpocket.jsonl")
    ap.add_argument("--turn-timeout", type=float, default=30.0)
    ap.add_argument("--max-sessions", type=int, default=200)
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    random.seed(args.seed)
    brief = flatten_brief()

    deadline = time.time() + args.minutes * 60
    records = []
    session_idx = 0
    consecutive_failures = 0

    while time.time() < deadline and session_idx < args.max_sessions:
        session_idx += 1
        status = run_one_session(
            session_idx, brief, args.turns_per_session, deadline,
            args.turn_timeout, args.out, records,
        )
        # Persist progress after every session, not just at the very end -
        # today's connectivity/session-ceiling surprises are reason enough.
        with open(args.out, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"[checkpoint] {len(records)} records across {session_idx} "
              f"session(s), {round((deadline - time.time()) / 60, 2)} min remaining, "
              f"last status={status}")

        if status == "ok":
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                print("3 consecutive failed sessions - likely a dead connection "
                      "(e.g. phone off wifi again), not a transient blip. "
                      "Stopping rather than spinning through --max-sessions.")
                break
            time.sleep(5)  # brief backoff before retrying a fresh session

    print(f"Done. Wrote {len(records)} records across {session_idx} sessions to {args.out}")
    print(f"Per-session raw transcripts: {args.out}.session*.raw.log")


if __name__ == "__main__":
    main()
