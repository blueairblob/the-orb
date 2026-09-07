from engine.dm import build_narration_brief, build_refusal_brief, classify_utterance
from engine.scenario import build_cell_and_guard


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
    brief = build_narration_brief(scenario.room, scenario.door, scenario.guard)

    assert "locked" in brief
    assert "Do not speak as the guard" in brief
