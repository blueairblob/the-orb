# engine/ — Phase 1 Python engine

The deterministic core (PRD §3, §4, §11). The cell-and-guard proof of concept (PRD §8) runs
end to end, in text mode.

Build order (PRD §24, steps 1–4):
1. ✅ Desktop Python environment; pieces talking. (`pyproject.toml`, `uv`, `experiments/harness/`.)
2. ✅ Evaluate Evennia — **decided: build fresh**, not on Evennia. See
   [ADR 0002](../docs/decisions/0002-evennia-evaluation.md).
3. ✅ Object model — base class, state, relationships, capabilities, existence, position
   (`world.py`), plus the guard's Character Engine (`guard.py`) and the brief-builder
   (`brief.py`) that hangs off both.
4. ✅ Smallest possible voice loop (`loop.py`) — **text-mode**, not real STT/TTS. This host has
   no audio hardware at all (no ALSA devices), so a live mic/speaker loop is physically
   impossible here. `voice.py` defines the protocol the real Android on-device backend will
   implement during the Phase 2 phone port; `voice_text.py` is the only backend so far.

## Modules

| File | What it is |
|---|---|
| `world.py` | `Thing`/`Room`/`Door`/`World`/`WorldClock` — the object model (PRD §4), plain Python, no ORM. |
| `guard.py` | `Guard`, `MoodDial` — the Character Engine (PRD §12). `adjust_mood_from_text` is a first sketch of PRD §12's open "what moves the dial?" question, not a final answer. |
| `brief.py` | Walks the object graph into the turn's markdown brief (PRD §4, §7 step 4). |
| `guardrail.py` | Last-resort output filter before a reply is spoken (PRD §17). |
| `voice.py` | The `Voice` protocol — `listen()`/`speak()`. Swap the backend, not the loop. |
| `voice_text.py` | Text-mode `Voice`: `input()`/`print()`. |
| `llm.py` | The engine's LiteRT-LM client (moved here from `experiments/harness/`, which now reuses it — talking to the model is core engine responsibility, not dev tooling). |
| `scenario.py` | Builds the v0.1 world: one cell, one door, one guard (PRD §8). |
| `save.py` | JSON save/load (PRD §11: "keep it dumb and reliable"). |
| `loop.py` | The core loop (PRD §7) and the `orb-engine` CLI entry point. |

Run it: `uv run orb-engine` (needs the model — `uv run orb-harness setup` first if not already
done). Tests (`../tests/`) run the deterministic logic against a stub LLM — no model download
needed: `uv run pytest`.

Non-negotiables live in `../CLAUDE.md`. The engine owns the truth; the LLM only speaks.
