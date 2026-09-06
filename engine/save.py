"""Save state (PRD §8, §11): "one structured JSON file. Human-readable,
debuggable. Keep it dumb and reliable."

Deliberately scoped to what the cell-and-guard scenario actually needs to
resume, not a generic serializer for the whole object graph — that's more
than v0.1 requires (PRD's own discipline: don't build for hypothetical
future scope).
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.scenario import CellAndGuard, build_cell_and_guard


def save_state(path: Path, scenario: CellAndGuard) -> None:
    data = {
        "clock_minutes": scenario.world.clock.minutes,
        "door_locked": scenario.door.locked,
        "guard_mood": scenario.guard.mood.value,
        "guard_memory": scenario.guard.memory,
    }
    path.write_text(json.dumps(data, indent=2))


def load_state(path: Path) -> CellAndGuard:
    """Builds a fresh cell-and-guard scenario, then overlays saved state."""
    scenario = build_cell_and_guard()
    if not path.is_file():
        return scenario

    data = json.loads(path.read_text())
    scenario.world.clock.minutes = data.get("clock_minutes", 0)
    if not data.get("door_locked", True):
        scenario.door.unlock()
    scenario.guard.mood.value = data.get("guard_mood", scenario.guard.mood.value)
    scenario.guard.memory = data.get("guard_memory", [])
    return scenario
