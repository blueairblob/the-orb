#!/usr/bin/env python3
"""Properly-paced hot/pocket feeder for litert_lm_advanced_main --multi_turns.

Fixes the 2026-09-11 stdin-pacing artifact: piping the whole input file at
once (`cat file | adb shell ...`) let the async pipeline coalesce most
queued turns into far fewer actually-timed inference calls than lines fed.
This script sends one line, waits for that turn's reply AND the next
"Please enter the prompt" cue to reappear (proving the previous turn is
fully done), then sends the next line — properly serialized.

Usage:
    python3 paced_hotpocket.py --minutes 20 --out /path/to/log.jsonl
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20.0)
    ap.add_argument("--out", default="/tmp/paced_hotpocket.jsonl")
    ap.add_argument("--turn-timeout", type=float, default=30.0)
    ap.add_argument("--max-turns", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=123)
    args = ap.parse_args()

    random.seed(args.seed)
    brief = flatten_brief()

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
        timeout=args.turn_timeout,
        env={**os.environ, "LD_LIBRARY_PATH": LD_LIBRARY_PATH},
    )
    child.logfile = open(args.out + ".raw.log", "w")

    records = []
    deadline = time.time() + args.minutes * 60

    def send_and_wait(text, label):
        # Caller must already have consumed the PROMPT_CUE that precedes this
        # send (either the initial one, or the one left by the previous
        # send_and_wait call) - do NOT re-expect it here, that would wait for
        # a *second* occurrence that only appears after this turn completes,
        # deadlocking against the sendline below.
        t0 = time.time()
        child.sendline(text)
        idx = child.expect_exact([PROMPT_CUE, pexpect.EOF, pexpect.TIMEOUT])
        t1 = time.time()
        rec = {
            "label": label,
            "text": text,
            "wait_seconds": round(t1 - t0, 3),
            "timestamp": t1,
            "expect_result": idx,
        }
        records.append(rec)
        print(f"[{len(records):4d}] {label:8s} {rec['wait_seconds']:6.2f}s  {text[:40]!r}")
        return idx

    print("Waiting for the initial prompt cue...")
    child.expect_exact(PROMPT_CUE, timeout=60)

    print("Sending brief (turn 1, expect a long wait)...")
    idx = send_and_wait(brief, "brief")
    if idx != 0:
        print("Brief turn did not return cleanly, aborting. idx=", idx)
        child.close(force=True)
        with open(args.out, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return

    n = 0
    while time.time() < deadline and n < args.max_turns:
        text = random.choice(UTTERANCES)
        idx = send_and_wait(text, f"turn{n+1}")
        n += 1
        if idx != 0:
            print("Non-clean turn, stopping loop. idx=", idx)
            break

    # End the multi-turn loop cleanly. The trailing PROMPT_CUE from the last
    # send_and_wait call has already been consumed - just send the blank
    # line that ends RunMultiTurnConversation's loop and wait for exit.
    try:
        child.sendline("")
        child.expect(pexpect.EOF, timeout=60)
    except Exception as e:
        print("Cleanup expect failed (non-fatal):", e)
    child.close(force=True)

    with open(args.out, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Wrote {len(records)} records to {args.out}")
    print(f"Raw transcript: {args.out}.raw.log")


if __name__ == "__main__":
    main()
