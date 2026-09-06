# 2026-09-06 — Building the engine: object model, guard, core loop

## Context

Third chunk of work today, right after the Evennia evaluation (ADR 0002) unblocked roadmap step
3. Asked for "the engine built," which turned out to have a real fork in it: how far to take
voice I/O, given step 4 assumes real Google STT/TTS. Used `EnterPlanMode` and two
`AskUserQuestion` checks before writing any code, since both were genuine judgment calls, not
things derivable from the code or PRD alone.

## Decisions

- **Scope: everything, including "real" STT/TTS** — but then a hardware check changed what that
  could mean. `aplay -l` / `arecord -l` aren't even installed, and `/dev/snd` has only the
  software MIDI sequencer/timer — **this OCI host has zero audio hardware**. A live mic/speaker
  loop is physically impossible here regardless of backend (on-device, Google Cloud, anything).
  This mirrors the §0 spike's own host-vs-device split, just for voice instead of thermal
  performance. Landed on: build the full engine with a swappable `Voice` protocol, wire a
  text-mode backend now, defer the real Android on-device backend to the Phase 2 phone port
  (where a mic/speaker actually exist). No engine-loop code changes will be needed then — that's
  the point of the protocol.
- **Object model: plain dataclasses, no ORM** — direct product of ADR 0002. `Thing` carries all
  five PRD §4 layers (state, relationships, capabilities, existence, position) as ordinary
  fields. Distance/direction (§5) deliberately **not built** — v0.1 has no map (§8's explicit
  scope cut).
- **Mood dial: one dial, not two, and a keyword heuristic.** PRD §12 lists "suspicion, warmth" as
  an example but flags "what moves the dial" as **unsketched**. Rather than invent an unverified
  two-dial design, shipped one dial and a small transparent heuristic
  (`guard.adjust_mood_from_text`) as an explicit first sketch, documented as such in code and
  README. The natural v0.2 upgrade — LLM proposes a mood delta via structured output
  (`response_format`/constrained decoding, already present in the installed `litert-lm` package),
  engine clamps and applies it (Gotcha #31: "agents propose, engine disposes") — is flagged, not
  built. Didn't want to block a working loop on an unverified structured-output experiment.
- **Moved the LLM client into `engine/llm.py`**, out of `experiments/harness/runner.py`. Talking
  to the model is core engine responsibility (PRD §7 step 5), not dev-host tooling — fixes the
  dependency direction (`experiments/` now depends on `engine/`, not the reverse) before it had a
  chance to calcify. `experiments/harness/cli.py` now imports `engine.llm`; `runner.py` deleted
  outright, no compat shim (nothing else referenced it).
- Engine memory (`Guard.memory`) is capped at 12 entries and the brief only ever gets the last 6
  — Gotcha #6 discipline (save-state bloat) applied from day one rather than retrofitted later.

## What we did

1. Built `engine/world.py` (`Thing`, `Room`, `Door`, `World`, `WorldClock`), `engine/guard.py`
   (`Guard`, `MoodDial`, the mood heuristic, thresholds), `engine/brief.py` (walks the graph into
   markdown, reusing the persona style already validated in
   `experiments/harness/prompts/seed_cases.yaml`), `engine/guardrail.py` (fourth-wall/empty/
   overlong checks with a safe fallback line), `engine/voice.py` + `voice_text.py`,
   `engine/scenario.py` (the one-cell-one-guard world from §8), `engine/save.py` (plain JSON),
   and `engine/loop.py` (the core loop + `orb-engine` CLI entry point, `run_turn`/`run_loop`
   split so the deterministic logic is testable without the model).
2. Wrote `tests/test_world.py`, `test_guard.py`, `test_brief.py`, `test_loop.py` — the last one
   drives full scripted conversations (kind → unlock, hostile → lockout) through a **stub LLM and
   stub voice**, proving the deterministic engine works in total isolation from the AI (PRD §3's
   whole architectural point). 20 tests, no model download needed, 0.05s.
3. Caught a real bug via testing: the first draft of `run_turn` recorded the player's line to
   memory *before* checking whether it was a repeat, so every line matched itself and the
   "exact-repeat" penalty fired on turn one, every time. Fixed the ordering (check repeat, then
   remember); added a devlog-worthy test note about it since it also meant the original "repeat
   the same kind line 15 times" test design was itself flawed — a real repeated phrase's kindness
   bonus gets mostly cancelled by the repeat penalty by design, so the "reaches unlock" test now
   uses varied phrasing, which is also more representative of how a real player actually talks.
4. `uv sync --reinstall-package the-orb`, `uv run pytest` (20 passed), `uv run ruff check` (clean
   after two rounds of auto-fixable nits — f-strings without placeholders, quoted type hints that
   didn't need quoting given `from __future__ import annotations`).
5. Smoke-tested the real loop against the already-downloaded model:
   `uv run orb-engine`, typed three polite lines, mood climbed 40 → 49 (+3/turn, three kind-word
   hits), guard replies stayed appropriately terse and in-character ("Silence. Keep quiet." →
   "Stay put."). Killed the session with `quit`, restarted, fed one hostile line
   ("idiot... kill you") — **loaded the prior session's mood and memory correctly**, applied
   -12 (rude −4, threat −8), landed at 37, guard replied "Threat." in character.
6. Verified `orb-harness` still works post-refactor (`--help`, `setup --help`) — the `engine.llm`
   move didn't break the existing dev-host tooling.

## Outcomes

The full PRD §7 loop runs, deterministically driven, on real hardware-appropriate constraints:
player line → engine updates mood/memory/clock → threshold check → brief built fresh from
current state → real Gemma 4 E2B reply → guardrail → spoken (printed) → saved to JSON → resumable
across process restarts. Both terminal states (unlock, lockout) are reachable and were reached in
testing. This is §21's success bar in miniature — "does one room feel alive?" — minus the actual
audio, which this host cannot provide.

## Open threads

- **Mood-delta-via-structured-output** is the flagged v0.2 direction for §12's still-open
  question — worth its own experiment once the current heuristic's limits are felt in play
  (it's simplistic on purpose; expect it to need replacing).
- **Android on-device `Voice` backend** is the real Phase 2 task — `voice.py`'s protocol exists
  specifically so that's a new file, not a rewrite of `loop.py`.
- Guardrail (`guardrail.py`) is intentionally minimal — a real fourth-wall-break or fully off-rails
  reply from the model hasn't been observed yet in testing, so the filter is unverified against a
  genuine trip. Worth feeding it adversarial input (PRD §14's spirit) once the automated
  playtesting idea gets built.
- No compound-command parsing or object-reference grounding (Gotchas #1, #2) yet — not needed for
  a pure-dialogue scenario with no takeable items, but will matter the moment the maze (§9) or any
  inventory (§12b) lands.
- Real save-file location is `~/.orb/cell-and-guard-save.json`, outside the repo (correctly —
  it's player state, not project state). No multi-profile support yet (Gotcha #25) — single save
  slot only, fine for now.
