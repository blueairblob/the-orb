from engine.brief import (
    build_fact_extraction_prompt,
    build_guard_brief,
    format_guard_fact,
    guard_fact_quote,
)
from engine.scenario import build_cell_and_guard


def brief_for(scenario):
    return build_guard_brief(
        scenario.guard, scenario.door, scenario.room, scenario.premise,
        clock=scenario.world.clock,
    )


def test_brief_reflects_current_state():
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = 90
    scenario.guard.remember("player", "please let me out")
    scenario.guard.remember("guard", "No.")

    brief = brief_for(scenario)

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

    brief = brief_for(scenario)

    assert "unlocked" in brief


def test_secret_withheld_below_trust_threshold():
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = 40

    brief = brief_for(scenario)

    assert scenario.guard.secret not in brief


def test_secret_available_once_trust_is_earned():
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = 90

    brief = brief_for(scenario)

    assert scenario.guard.secret in brief
    assert "you may let a fragment" in brief  # not-yet-revealed framing -- secret_revealed is False


def test_secret_shows_already_revealed_framing_once_flag_is_set():
    # engine/loop.py's real call order: secret_revealed only flips *after*
    # a turn's brief is built (see Guard.maybe_reveal_secret) -- this tests
    # the brief side of that independently of mood, since once revealed it
    # stays revealed even if mood later drops.
    scenario = build_cell_and_guard()
    scenario.guard.affiliation.value = 20  # would normally withhold the secret entirely
    scenario.guard.secret_revealed = True

    brief = brief_for(scenario)

    assert scenario.guard.secret in brief
    assert "already let this slip" in brief
    assert "you may let a fragment" not in brief  # the one-time offer, not the ongoing fact


def test_brief_omits_established_facts_section_when_none_recorded():
    scenario = build_cell_and_guard()

    brief = brief_for(scenario)

    assert "already told them" not in brief


def test_brief_feeds_back_established_facts_newest_first():
    scenario = build_cell_and_guard()
    scenario.guard.add_established_fact("He grew up in the river town of Kelsey.")
    scenario.guard.add_established_fact("His brother served in the same watch.")

    brief = brief_for(scenario)

    assert "already told them" in brief
    assert "He grew up in the river town of Kelsey." in brief
    assert "His brother served in the same watch." in brief
    assert brief.index("His brother served in the same watch.") < brief.index(
        "He grew up in the river town of Kelsey."
    )


def test_fact_extraction_prompt_lists_no_facts_yet():
    scenario = build_cell_and_guard()

    prompt = build_fact_extraction_prompt(scenario.guard, "what's your name?", "Garrick. Hush.")

    assert "(nothing yet)" in prompt
    assert "what's your name?" in prompt
    assert "Garrick. Hush." in prompt
    assert "NONE" in prompt


def test_fact_extraction_prompt_lists_existing_facts():
    scenario = build_cell_and_guard()
    scenario.guard.add_established_fact("He grew up in the river town of Kelsey.")

    prompt = build_fact_extraction_prompt(scenario.guard, "where are you from?", "Kelsey.")

    assert "He grew up in the river town of Kelsey." in prompt
    assert "(nothing yet)" not in prompt


def test_brief_shows_a_mood_appropriate_voice_example():
    # Regression (real playtest 2026-09-15): mood climbed from 40 to 62 over
    # a genuinely warm session, but every reply stayed equally cold -- one
    # extra example bolted onto the always-shown gruff static set (a first
    # attempt at fixing this, kept in git history) measurably didn't work
    # either. Each band now gets its own full example set instead.
    scenario = build_cell_and_guard()

    scenario.guard.affiliation.value = 92  # "ready to help"
    warm_brief = brief_for(scenario)
    assert "Friends call me that" in warm_brief
    assert "Now hush" not in warm_brief  # the gruff-band example, not shown here

    scenario.guard.affiliation.value = 40  # "gruff and suspicious"
    default_brief = brief_for(scenario)
    assert "Now hush" in default_brief
    assert "Friends call me that" not in default_brief


def test_anti_promise_examples_shown_at_every_mood():
    # The one rule that has to hold at *every* band, including "ready to
    # help" -- exactly the band where a promise would be most tempting to
    # generate. Unconditional, unlike the band-specific voice examples above.
    scenario = build_cell_and_guard()
    for mood in (5, 40, 62, 92):
        scenario.guard.affiliation.value = mood
        brief = brief_for(scenario)
        assert "I promise nothing" in brief


def test_guard_fact_is_composed_from_the_question_and_his_own_words():
    # The guard's answers are terse and lean on the question -- "Oakhaven. A
    # quiet place." only means "my hometown" next to what was asked.
    fact = format_guard_fact(" What town did you grow up in? ", " Oakhaven. A quiet place. ")

    assert fact == 'Asked "What town did you grow up in?", you said: "Oakhaven. A quiet place."'


def test_guard_fact_extraction_prompt_asks_for_a_verbatim_copy():
    scenario = build_cell_and_guard()

    prompt = build_fact_extraction_prompt(scenario.guard, "where are you from?", "Kelsey.")

    assert "word for word" in prompt
    assert "third-person" not in prompt


def test_brief_reads_the_live_clock_not_a_frozen_copy():
    # REVIEW.md R2: time of day used to be copied into room.state once at
    # scenario build and never updated, so the brief showed the same time
    # forever no matter how far the clock ticked.
    scenario = build_cell_and_guard()
    assert "It is night." in brief_for(scenario)

    scenario.world.clock.minutes = 6 * 60  # 6am
    assert "It is dawn." in brief_for(scenario)
    assert "time_of_day" not in scenario.room.state  # no duplicate to go stale


def test_guard_fact_quote_inverts_format_guard_fact():
    fact = format_guard_fact("Where from?", "Blackwood. A quiet place.")

    assert guard_fact_quote(fact) == "Blackwood. A quiet place."
    assert guard_fact_quote("He grew up in Kelsey.") is None  # older, free-form fact


def test_guard_fact_prompt_treats_his_name_as_already_known():
    # R14: the untightened prompt recorded "Garrick." -- his own name -- as a
    # new fact about himself.
    scenario = build_cell_and_guard()

    prompt = build_fact_extraction_prompt(scenario.guard, "what's your name?", "Garrick.")

    assert f"His name is {scenario.guard.name}." in prompt


def test_guard_fact_prompt_rules_out_non_facts():
    # R14: 8 of 27 non-fact turns got recorded ("Still locked.", "Show it to
    # me.", the promise "Ten minutes. Fine."), and fed back as canon they drove
    # repetition loops. The categories that caused it are named as excluded.
    scenario = build_cell_and_guard()

    prompt = build_fact_extraction_prompt(scenario.guard, "q", "r")

    for excluded in ("refusals", "the door, the lock", "promises", "reactions to the prisoner"):
        assert excluded in prompt
