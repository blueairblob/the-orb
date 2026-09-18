from engine.dm import (
    build_narration_brief,
    build_refusal_brief,
    build_scene_fact_extraction_prompt,
    classify_utterance,
)
from engine.scenario import build_cell_and_guard


def narration_for(scenario, scene_facts=()):
    return build_narration_brief(
        scenario.room, scenario.door, scenario.guard, scenario.premise, scene_facts,
        clock=scenario.world.clock,
    )


def test_classifies_ungrounded_actions_as_refusal():
    assert classify_utterance("I cast a spell on the guard") == "refusal"
    assert classify_utterance("I draw my sword") == "refusal"
    assert classify_utterance("I drink a potion") == "refusal"


def test_classifies_environment_queries_as_narration():
    assert classify_utterance("What does this cell look like?") == "narration"
    assert classify_utterance("Describe my surroundings") == "narration"
    assert classify_utterance("Where am I?") == "narration"


def test_ordinary_dialogue_defaults_to_guard():
    assert classify_utterance("Please, let me out") == "dialogue"
    assert classify_utterance("You're an idiot") == "dialogue"


def test_environment_query_words_dont_false_positive_inside_longer_words():
    # Regression (devlog 2026-09-09): "look" as a bare substring matched
    # inside "looking", misrouting real guard dialogue to the DM.
    assert classify_utterance("Have you ever thought about looking the other way?") == "dialogue"


def test_look_as_appearance_verb_stays_dialogue():
    # Regression (real playtest 2026-09-14): "look" as a whole word still
    # false-positived on its *other* sense -- "you look cold", an appearance
    # copula addressed at the guard (also his own VOICE_EXAMPLES line in
    # brief.py), got misrouted to narration.
    assert classify_utterance("You look cold out here.") == "dialogue"
    assert classify_utterance("You look tired.") == "dialogue"


def test_look_as_perception_command_still_routes_to_narration():
    assert classify_utterance("Let me look around.") == "narration"
    assert classify_utterance("Can I take a look?") == "narration"


def test_combat_flavoured_threats_stay_dialogue_not_refusal():
    # Aggressive dialogue toward the guard is handled by the guard's own
    # mood heuristic, not routed to a DM refusal — only clearly nonexistent
    # objects/abilities are grounded here (see engine/dm.py).
    assert classify_utterance("I will attack you") == "dialogue"
    assert classify_utterance("Let's fight") == "dialogue"


def test_refusal_brief_names_the_attempted_action():
    scenario = build_cell_and_guard()
    brief = build_refusal_brief(scenario.room, "I cast a fireball")

    assert "I cast a fireball" in brief
    assert "Dungeon Master" in brief


def test_narration_brief_describes_scene_not_guard_dialogue():
    scenario = build_cell_and_guard()
    brief = narration_for(scenario)

    assert "locked" in brief
    assert "Do not speak as the guard" in brief
    assert scenario.premise in brief


def test_narration_brief_feeds_back_scene_facts():
    # PRD §22 Gotcha #3's own flagship example is a DM detail -- whatever the
    # DM already improvised about the place has to come back as fact.
    scenario = build_cell_and_guard()
    facts = ["A single iron grate covers the door."]

    brief = narration_for(scenario, facts)

    assert "already described" in brief
    assert "A single iron grate covers the door." in brief


def test_refusal_brief_feeds_back_scene_facts():
    scenario = build_cell_and_guard()

    brief = build_refusal_brief(
        scenario.room, "I cast a spell", ["Water drips somewhere in the corner."]
    )

    assert "Water drips somewhere in the corner." in brief


def test_dm_briefs_omit_the_facts_section_when_there_are_none():
    scenario = build_cell_and_guard()

    narration = narration_for(scenario)
    refusal = build_refusal_brief(scenario.room, "I cast a spell")

    assert "already described" not in narration
    assert "already described" not in refusal


def test_scene_fact_extraction_prompt_treats_the_authored_room_as_known():
    # The room's own description counts as already established, so the base
    # scene isn't re-recorded in new words every turn; the engine-owned
    # door lock and guard mood are explicitly excluded (PRD §3).
    scenario = build_cell_and_guard()

    prompt = build_scene_fact_extraction_prompt(
        scenario.room,
        ["A single iron grate covers the door."],
        "describe the room",
        "Stone walls, a drip in the corner.",
    )

    assert scenario.room.description in prompt
    assert "A single iron grate covers the door." in prompt
    assert "Stone walls, a drip in the corner." in prompt
    assert "door is locked" in prompt
    assert "NONE" in prompt


def test_narration_brief_reads_the_live_clock():
    scenario = build_cell_and_guard()
    scenario.world.clock.minutes = 12 * 60

    assert "It is day." in narration_for(scenario)
