"""The v0.1 proof of concept scenario (PRD §8): one cell, one door, one guard."""

from __future__ import annotations

import dataclasses

from engine.guard import Guard
from engine.world import Door, Room, World


@dataclasses.dataclass
class CellAndGuard:
    world: World
    room: Room
    door: Door
    guard: Guard
    # Why the prisoner is actually here — world-level canon (PRD §3), fed
    # into both the guard's and the DM's briefs so suspicion/sympathy has
    # something concrete to hang on, not just an abstract "the prisoner."
    premise: str = "poaching a stag from the king's forest, this last hard winter"


def build_cell_and_guard() -> CellAndGuard:
    world = World()
    room = world.add(
        Room(id="cell", name="the cell", description="A cold stone cell.")
    )
    door = world.add(
        Door(id="cell-door", name="the cell door", location=room)
    )
    guard = world.add(
        Guard(
            id="guard",
            name="Garrick",
            description="A bored, gruff dungeon guard, twenty years in the King's Watch.",
            location=room,
            backstory=(
                "Twenty years in the King's Watch, most of it spent freezing outside "
                "cells exactly like this one. His younger brother went into one during "
                "the famine winter, for the same kind of petty theft half the county "
                "was desperate enough to risk that year — and never came out."
            ),
            secret=(
                "He never talks about his brother. Earn real trust and he might let "
                "slip why he can't quite bring himself to hate the people he locks up."
            ),
        )
    )
    room.state["time_of_day"] = world.clock.time_of_day
    return CellAndGuard(world=world, room=room, door=door, guard=guard)
