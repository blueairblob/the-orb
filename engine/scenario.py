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
            name="the guard",
            description="A bored, gruff dungeon guard.",
            location=room,
        )
    )
    room.state["time_of_day"] = world.clock.time_of_day
    return CellAndGuard(world=world, room=room, door=door, guard=guard)
