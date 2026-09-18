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
        "guard_affiliation": scenario.guard.affiliation.value,
        "guard_memory": scenario.guard.memory,
        # Noticed missing during the 2026-09-16 fact-canonization/Stat work
        # (devlog) but out of scope for that fix — both are engine-owned,
        # PRD §22 Gotcha #3 "bound thereafter" state, same as the fields
        # above; leaving them out meant a resumed session could silently
        # re-litigate an already-revealed secret or forget an established
        # fact the guard is supposed to stay bound to.
        "guard_secret_revealed": scenario.guard.secret_revealed,
        "guard_established_facts": scenario.guard.established_facts,
        "world_established_facts": scenario.world.established_facts,
    }
    path.write_text(json.dumps(data, indent=2))


def load_state(path: Path) -> CellAndGuard:
    """Builds a fresh cell-and-guard scenario, then overlays saved state."""
    scenario = build_cell_and_guard()
    if not path.is_file():
        return scenario

    data = json.loads(path.read_text())
    scenario.world.clock.minutes = data.get("clock_minutes", scenario.world.clock.minutes)
    if not data.get("door_locked", True):
        scenario.door.unlock()
    scenario.guard.affiliation.value = data.get(
        "guard_affiliation", scenario.guard.affiliation.value
    )
    scenario.guard.memory = data.get("guard_memory", [])
    scenario.guard.secret_revealed = data.get(
        "guard_secret_revealed", scenario.guard.secret_revealed
    )
    scenario.guard.established_facts = data.get(
        "guard_established_facts", scenario.guard.established_facts
    )
    scenario.world.established_facts = data.get(
        "world_established_facts", scenario.world.established_facts
    )
    return scenario
