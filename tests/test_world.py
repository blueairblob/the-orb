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
