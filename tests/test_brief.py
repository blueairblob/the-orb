from engine.brief import build_guard_brief
from engine.scenario import build_cell_and_guard


def test_brief_reflects_current_state():
    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 90
    scenario.guard.remember("player", "please let me out")
    scenario.guard.remember("guard", "No.")

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)

    assert "locked" in brief
    assert "ready to help" in brief
    assert "please let me out" in brief
    assert "No." in brief
    assert scenario.guard.name in brief
    assert scenario.premise in brief
    assert scenario.guard.backstory in brief


def test_brief_reflects_unlocked_door():
    scenario = build_cell_and_guard()
    scenario.door.unlock()

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)

    assert "unlocked" in brief


def test_secret_withheld_below_trust_threshold():
    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 40

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)

    assert scenario.guard.secret not in brief


def test_secret_available_once_trust_is_earned():
    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 90

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)

    assert scenario.guard.secret in brief
