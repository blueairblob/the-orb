from engine.brief import build_guard_brief
from engine.scenario import build_cell_and_guard


def test_brief_reflects_current_state():
    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 90
    scenario.guard.remember("player", "please let me out")
    scenario.guard.remember("guard", "No.")

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room)

    assert "locked" in brief
    assert "ready to help" in brief
    assert "please let me out" in brief
    assert "No." in brief


def test_brief_reflects_unlocked_door():
    scenario = build_cell_and_guard()
    scenario.door.unlock()

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room)

    assert "unlocked" in brief
