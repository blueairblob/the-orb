from engine.world import Door, Room, Thing, World, WorldClock


def test_capabilities_are_the_rules():
    wall = Thing(id="wall", name="a stone wall")
    assert not wall.has_capability("takeable")

    torch = Thing(id="torch", name="a torch", capabilities={"takeable"})
    assert torch.has_capability("takeable")


def test_destroy_crosses_the_existence_threshold():
    torch = Thing(id="torch", name="a torch", exists=True)
    torch.destroy()
    assert torch.exists is False
    assert torch.location is None


def test_door_starts_locked_and_can_be_unlocked():
    door = Door(id="door", name="the door")
    assert door.locked is True
    door.unlock()
    assert door.locked is False
    door.lock()
    assert door.locked is True


def test_room_contents_reflects_location():
    world = World()
    room = world.add(Room(id="cell", name="the cell"))
    other_room = world.add(Room(id="yard", name="the yard"))
    torch = world.add(Thing(id="torch", name="a torch", location=room))
    world.add(Thing(id="rock", name="a rock", location=other_room))

    assert room.contents(world) == [torch]


def test_world_clock_time_of_day_bands():
    clock = WorldClock(minutes=0)
    assert clock.time_of_day == "night"
    clock.advance(9 * 60)
    assert clock.time_of_day == "day"


def test_world_fact_ledger_is_newest_first_and_deduped():
    world = World()
    assert world.add_established_fact("A single iron grate covers the door.") is True
    assert world.add_established_fact("Water drips somewhere in the corner.") is True
    assert world.add_established_fact("  a single IRON grate covers the door.  ") is False
    assert world.add_established_fact("   ") is False

    assert world.established_facts == [
        "Water drips somewhere in the corner.",
        "A single iron grate covers the door.",
    ]


def test_near_identical_retelling_is_not_recorded_twice():
    # Regression (real backend, 2026-09-18): exact-match dedupe recorded
    # both of these as separate canon.
    world = World()
    world.add_established_fact("A shadow shifts just beyond the bars")

    assert world.add_established_fact("A shadow shifts just beyond the iron bars") is False
    assert world.established_facts == ["A shadow shifts just beyond the bars"]


def test_a_genuine_extension_of_a_fact_is_still_recorded():
    world = World()
    world.add_established_fact("Garrick grew up in Oakhaven.")

    assert world.add_established_fact(
        "Garrick grew up in Oakhaven, where he learned to keep quiet."
    ) is True
