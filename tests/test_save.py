import json

from engine.save import load_state, save_state
from engine.scenario import build_cell_and_guard


def test_load_state_returns_a_fresh_scenario_when_no_save_exists(tmp_path):
    scenario = load_state(tmp_path / "no-such-file.json")
    assert scenario.guard.affiliation.value == 40
    assert scenario.door.locked is True


def test_save_and_load_round_trips_every_persisted_field(tmp_path):
    save_path = tmp_path / "save.json"
    scenario = build_cell_and_guard()
    scenario.world.clock.minutes = 6 * 60 + 15
    scenario.door.unlock()
    scenario.guard.affiliation.value = 77
    scenario.guard.remember("player", "hello")
    scenario.guard.remember("guard", "Hmph.")
    scenario.guard.secret_revealed = True
    scenario.guard.add_established_fact("He grew up in Oakhaven.")
    scenario.world.add_established_fact("A single iron grate covers the door.")
    scenario.guard.tactic_counts = {"empathy": 2, "bribe": 1}

    save_state(save_path, scenario)
    loaded = load_state(save_path)

    assert loaded.world.clock.minutes == 6 * 60 + 15
    assert loaded.door.locked is False
    assert loaded.guard.affiliation.value == 77
    assert loaded.guard.memory == ["player: hello", "guard: Hmph."]
    assert loaded.guard.secret_revealed is True
    assert loaded.guard.established_facts == ["He grew up in Oakhaven."]
    assert loaded.world.established_facts == ["A single iron grate covers the door."]
    assert loaded.guard.tactic_counts == {"empathy": 2, "bribe": 1}


def test_load_state_defaults_missing_fields_from_an_older_save_format(tmp_path):
    # Regression (2026-09-17): guard_secret_revealed/guard_established_facts
    # didn't exist before this fix -- a save file written by that older code
    # (or missing keys for any other reason) must still load cleanly, not
    # silently drop the secret-reveal/fact-canonization state machines back
    # to their defaults on every resume.
    save_path = tmp_path / "save.json"
    save_path.write_text(
        json.dumps(
            {
                "clock_minutes": 6,
                "door_locked": True,
                "guard_affiliation": 22,
                "guard_memory": ["player: hi"],
            }
        )
    )

    loaded = load_state(save_path)

    assert loaded.guard.affiliation.value == 22
    assert loaded.guard.secret_revealed is False
    assert loaded.guard.established_facts == []
    assert loaded.world.established_facts == []


def test_resumed_session_keeps_its_time_of_day(tmp_path):
    # With time read live from the clock, a resumed session's briefs reflect
    # the saved time -- the old frozen room.state copy was recomputed from a
    # fresh clock at load and ignored the saved minutes entirely.
    save_path = tmp_path / "save.json"
    scenario = build_cell_and_guard()
    scenario.world.clock.minutes = 6 * 60
    save_state(save_path, scenario)

    assert load_state(save_path).world.clock.time_of_day == "dawn"


def test_scenario_starts_at_its_authored_hour():
    from engine.scenario import SCENE_START_MINUTES

    assert build_cell_and_guard().world.clock.minutes == SCENE_START_MINUTES
