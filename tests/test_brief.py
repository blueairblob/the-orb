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
    assert "you may let a fragment" in brief  # not-yet-revealed framing -- secret_revealed is False


def test_secret_shows_already_revealed_framing_once_flag_is_set():
    # engine/loop.py's real call order: secret_revealed only flips *after*
    # a turn's brief is built (see Guard.maybe_reveal_secret) -- this tests
    # the brief side of that independently of mood, since once revealed it
    # stays revealed even if mood later drops.
    scenario = build_cell_and_guard()
    scenario.guard.mood.value = 20  # would normally withhold the secret entirely
    scenario.guard.secret_revealed = True

    brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)

    assert scenario.guard.secret in brief
    assert "already let this slip" in brief
    assert "you may let a fragment" not in brief  # the one-time offer, not the ongoing fact


def test_brief_shows_a_mood_appropriate_voice_example():
    # Regression (real playtest 2026-09-15): mood climbed from 40 to 62 over
    # a genuinely warm session, but every reply stayed equally cold -- one
    # extra example bolted onto the always-shown gruff static set (a first
    # attempt at fixing this, kept in git history) measurably didn't work
    # either. Each band now gets its own full example set instead.
    scenario = build_cell_and_guard()

    scenario.guard.mood.value = 92  # "ready to help"
    warm_brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)
    assert "Friends call me that" in warm_brief
    assert "Now hush" not in warm_brief  # the gruff-band example, not shown here

    scenario.guard.mood.value = 40  # "gruff and suspicious"
    default_brief = build_guard_brief(
        scenario.guard, scenario.door, scenario.room, scenario.premise
    )
    assert "Now hush" in default_brief
    assert "Friends call me that" not in default_brief


def test_anti_promise_examples_shown_at_every_mood():
    # The one rule that has to hold at *every* band, including "ready to
    # help" -- exactly the band where a promise would be most tempting to
    # generate. Unconditional, unlike the band-specific voice examples above.
    scenario = build_cell_and_guard()
    for mood in (5, 40, 62, 92):
        scenario.guard.mood.value = mood
        brief = build_guard_brief(scenario.guard, scenario.door, scenario.room, scenario.premise)
        assert "I promise nothing" in brief
