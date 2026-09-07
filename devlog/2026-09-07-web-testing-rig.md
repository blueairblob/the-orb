# 2026-09-07 — Desktop web testing rig: real voice + the orb

## Context

You added two orb visual prototypes to `experiments/orb_graphic/` (`demo0.html` — three discrete
mood states, colour-ripple transitions; `demo1.html` — mic-volume-reactive particle sphere) and
asked whether we could experiment via desktop web before a phone is involved. Good instinct: a
browser has a real mic and speaker via the Web Speech API, which this headless OCI host doesn't.

## Decisions

- **Dev-host testing rig, not a shell decision.** You called the orb "the main app view," which
  read like it might be reopening PRD §11's React-Native-later call — checked explicitly via
  `AskUserQuestion` before building anything. Confirmed: this stays a testing rig under
  `experiments/web/`, same status as `experiments/harness/`. React Native vs. web-as-shell stays
  open, to be revisited on its own if it comes up again.
- **FastAPI + one WebSocket endpoint**, not polling — the orb's "thinking" animation needs a
  message the instant the player's utterance is received, before the ~1s+ model latency, and
  polling would either miss that moment or need its own complexity to fake it.
- **The blocking LiteRT-LM call runs via `asyncio.to_thread`** inside the WebSocket handler — it's
  a synchronous native call; without this it would freeze the whole event loop for the duration of
  every reply.
- **`create_app(llm, scenario, save_path)` factory, not module-level globals** — lets
  `tests/test_web_server.py` inject a stub LLM and exercise the full protocol without downloading
  or loading the real 2.4 GB model. Same testability discipline as `engine/loop.py`'s `run_turn`.
- **Orb redesigned, not copy-pasted.** One `orb.js` module driven by an explicit
  `{moodValue, phase, micVolume}` state, `phase` being `idle | listening | thinking | speaking`.
  Mood is a continuous 0–100 HSL interpolation across the guard's five narrative bands (replacing
  demo0's 3-button discrete picker), colour-ripple technique kept from demo0, mic-reactivity kept
  from demo1. Documented explicitly in code: PRD §12's "never a raw number" rule is about the
  LLM's brief, not this nonverbal visual channel — sending the continuous value here is correct,
  not a violation, but worth flagging so it isn't miscited later.
- **Push-to-click mic, not always-on listening** — sidesteps PRD Gotcha #11 (accidental commands
  picked up by an open mic) even in a test rig, and a plain-text debug fallback lives behind a
  `⋯` toggle so the whole thing is testable without working speech, on any browser.

## What we did

1. `uv add fastapi "uvicorn[standard]"` — clean ARM64 wheel resolution, including `uvloop`.
2. Built `experiments/web/server.py` (the WebSocket protocol: `state` → `thinking` → `reply`,
   wrapping `engine.loop.run_turn` unchanged), `static/index.html` + `style.css` (orb canvas, mic
   button, collapsible debug panel), and `static/orb.js` (the renderer + WebSocket client + Web
   Speech API wiring — described above).
3. `tests/test_web_server.py` — three tests against `create_app` with a stub LLM: the
   state/thinking/reply message sequence, malformed/empty messages being ignored rather than
   crashing the socket, and static files actually serving. Caught a real bug this way: the reply
   message's `**_state_message()` spread was placed *after* `"type": "reply"` in the dict literal,
   so the spread's own `"type": "state"` silently overwrote it — every reply was mislabeled as a
   state message. Fixed by spreading first, explicit fields last.
4. `uv run pytest` — 23 passed (20 from yesterday + 3 new). `uv run ruff check` — one import-order
   nit, auto-fixed.
5. Started the real server (`uv run orb-web`), confirmed `/`, `/orb.js`, `/style.css` all serve
   (200s in the uvicorn log), then drove one real turn over the WebSocket with a small Python
   script (not a browser — this host can't run one): sent "Please, my friend, I mean you no
   harm.", got back `state`(40) → `thinking` → `reply`(mood 43, band "wary but listening", text
   "Silence. Keep quiet.") in the right order, against the real model. Stopped the server and
   cleared the save file afterward for a clean mood-40 start on your first real browser test.

## Outcomes

Protocol and static serving are verified from here, end to end, against the real engine and real
model. What's **not** yet verified — and can't be, from this host — is the actual browser
experience: does `SpeechRecognition` behave, does the orb's colour/phase read as intended, does
the guard's reply actually get spoken. That's the next step, on your machine.

## Open threads

- **You need to open `http://127.0.0.1:8000/` (or a tunnelled equivalent) in Chrome or Edge** and
  try it live — mic permission, speech recognition accuracy, whether the orb's four phases
  (idle/listening/thinking/speaking) feel distinct and right. Flag anything off and we iterate on
  `orb.js` specifically, not the protocol.
- If this host is remote from your machine, the server's port needs to reach you — SSH tunnel or
  a security-list rule, whichever fits your setup. Didn't assume which; ask if unsure.
- The "speaking" orb animation is an acknowledged stand-in (rhythmic pulse, not real
  `speechSynthesis` amplitude — browsers don't expose that easily). Worth revisiting if it looks
  wrong once you can actually watch it.
- `SpeechRecognition` browser support (Chrome/Edge only, cloud-backed) is a real constraint, not a
  bug — documented in `experiments/web/README.md` rather than worked around.
