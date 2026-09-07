# experiments/web/ — desktop web testing rig

A **dev-host testing rig**, same spirit as `experiments/harness/` — not a decision about the
shipping shell (PRD §11 still names React Native for Phase 2). This wires a real browser page
(mic + speaker via the Web Speech API, the orb visual) to the real engine
(`engine/loop.py`, `engine/llm.py`), so real voice interaction and visual feedback can be tested
together on this desktop host, before a phone is involved.

## Why this exists

This OCI host has no audio hardware at all (`engine/voice.py` is text-mode only because of it).
A browser *does* have a real mic and speaker. This rig lets the actual guard conversation
(`engine/scenario.py`'s cell-and-guard, PRD §8) be driven by real speech and heard aloud, with the
orb changing colour and motion to match the guard's mood dial — much closer to the real product
feel than typing into a terminal, without needing a phone yet.

## Running it

```bash
uv run orb-harness setup   # if you haven't already — needs the model imported
uv run orb-web
```

Then open `http://127.0.0.1:8000/` in **Chrome or Edge** (see caveat below). Click the mic button,
speak, and the guard should reply — spoken aloud, with the orb's colour tracking its mood.

If this host is remote from your own machine, you'll need the port reachable from your browser —
either an SSH tunnel (`ssh -L 8000:localhost:8000 <host>`) or the port opened on this box's
firewall/security list. Ask if you're not sure which applies here.

## Known limitations — read before judging the voice quality

- **`SpeechRecognition` is Chrome/Edge-only**, and it's **cloud-backed** (often literally Google's
  own speech service under the hood) — not the on-device STT the phone will eventually use.
  Firefox/Safari support is patchy to absent. A plain text-input fallback lives in the collapsible
  debug panel (top-right `⋯`) for testing without speech at all.
- **`speechSynthesis` (TTS)** uses whatever voice the browser/OS provides — a placeholder, not the
  eventual character voice (PRD §8/§15's "later" tier is Coqui TTS).
- The orb's "speaking" animation is a **rhythmic stand-in**, not synced to real audio amplitude —
  browsers don't expose `speechSynthesis` output to the Web Audio API for analysis.
- This is still **not** the §0 phone spike. Nothing here measures on-device thermal performance;
  see `../../spike/README.md`.

## Files

| File | What it is |
|---|---|
| `server.py` | FastAPI + one WebSocket endpoint. `create_app(llm, scenario, save_path)` is the testable factory (see `../../tests/test_web_server.py`); `main()` wires it to the real model and save file. |
| `static/index.html` | The page: orb canvas, mic button, collapsible debug panel. |
| `static/orb.js` | The orb renderer (mood → colour, phase → motion) + WebSocket client + Web Speech API wiring. Redesigned from `../orb_graphic/demo0.html` and `demo1.html` into one module driven by explicit state, not a copy-paste of either. |
| `static/style.css` | Styling for the above. |

Saves to the same file `orb-engine` uses (`~/.orb/cell-and-guard-save.json`) — either front end
can resume the other's session.
