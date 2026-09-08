"""Desktop web testing rig (dev-host tooling, not the shipping shell — see
`experiments/web/README.md`).

Wires a browser page (`static/index.html`) with a real microphone/speaker,
via the Web Speech API, to the real engine (`engine/loop.py`). This host has
no audio hardware at all, so it can only verify the protocol and static
serving from here — the live voice/visual experience needs a real browser.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from engine.llm import GemmaHarness, is_model_ready
from engine.loop import LLMClient, build_intro, run_turn
from engine.save import save_state
from engine.scenario import CellAndGuard

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    llm: LLMClient,
    scenario: CellAndGuard,
    save_path: Path,
    transcript_path: Path | None = None,
) -> FastAPI:
    """Builds the app against injected dependencies, so tests can supply a
    stub LLM/scenario instead of loading the real 2.4 GB model.

    `transcript_path`, if given, gets one JSON line per turn appended to it —
    a durable, uncapped dialogue capture (unlike `guard.memory`, which only
    keeps the last dozen lines for the brief) for pulling a session's full
    transcript back out after the fact."""
    app = FastAPI()

    # This is a fast-iterating dev rig, not a deployed site — a stale
    # cached copy of orb.js/style.css silently masking real edits (no
    # request even reaches the server to reveal the mismatch) is a much
    # worse failure mode than the bandwidth this would ever save. Without
    # this, Chrome's heuristic caching serves static files from disk across
    # reloads with zero request logged (confirmed against the devlog: a
    # tab reloaded 4x showed 0 requests for either file).
    @app.middleware("http")
    async def _no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    def _state_message() -> dict:
        return {
            "type": "state",
            # Raw value + band both sent: PRD §12's "never a raw number"
            # rule is about the LLM's brief, not this nonverbal visual
            # channel — continuous input makes for smoother orb animation.
            "mood": scenario.guard.mood.value,
            "band": scenario.guard.mood.band,
            "door_locked": scenario.door.locked,
        }

    def _log_transcript(entry: dict) -> None:
        if transcript_path is None:
            return
        with transcript_path.open("a") as f:
            f.write(json.dumps({"ts": time.time(), **entry}) + "\n")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        intro = build_intro(scenario.premise)
        await websocket.send_json({**_state_message(), "intro": intro, "speaker": "dm"})
        _log_transcript({"speaker": "dm", "text": intro, "mood": scenario.guard.mood.value})

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if message.get("type") != "utterance":
                    continue
                utterance = str(message.get("text", "")).strip()
                if not utterance:
                    continue

                await websocket.send_json({"type": "thinking"})
                reply, speaker, outcome = await asyncio.to_thread(
                    run_turn, scenario, llm, utterance
                )
                save_state(save_path, scenario)
                _log_transcript(
                    {
                        "player": utterance,
                        "speaker": speaker,
                        "reply": reply,
                        "mood": scenario.guard.mood.value,
                        "band": scenario.guard.mood.band,
                        "outcome": outcome,
                    }
                )
                await websocket.send_json(
                    {
                        **_state_message(),
                        "type": "reply",
                        "text": reply,
                        "speaker": speaker,
                        "outcome": outcome,
                    }
                )
        except WebSocketDisconnect:
            pass

    # Mounted last: a websocket/HTTP route registered above always matches
    # before this catch-all static mount.
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


def main() -> None:
    import os

    from engine.loop import DEFAULT_SAVE_PATH
    from engine.save import load_state

    if not is_model_ready():
        print(
            "Model not imported yet. Run `orb-harness setup` first.", file=sys.stderr
        )
        sys.exit(1)

    DEFAULT_SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    scenario = load_state(DEFAULT_SAVE_PATH)

    # One capture file per server run — full, uncapped dialogue history for
    # pulling a session's transcript back out later (see create_app's
    # docstring). Separate from DEFAULT_SAVE_PATH, which only round-trips
    # enough state (mood, last dozen lines) to resume a scene.
    import datetime

    transcript_dir = DEFAULT_SAVE_PATH.parent / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = transcript_dir / f"{datetime.datetime.now():%Y%m%d-%H%M%S}.jsonl"

    # Defaults to localhost-only. Set ORB_WEB_HOST to bind elsewhere — e.g. a
    # Tailscale interface IP, so the page is reachable from another device
    # on the tailnet without exposing it on any public interface.
    host = os.environ.get("ORB_WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("ORB_WEB_PORT", "8000"))

    with GemmaHarness() as llm:
        app = create_app(llm, scenario, DEFAULT_SAVE_PATH, transcript_path)
        print(f"Serving on http://{host}:{port}/")
        print(f"Logging full transcript to {transcript_path}")
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
