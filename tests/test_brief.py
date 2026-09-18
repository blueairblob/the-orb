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


# --- R13: the brief tells him how he took the player's move ---


def test_brief_voices_his_reaction_to_a_bribe():
    # REVIEW.md R13: each bribe scored -1 while he answered "Show it to me.",
    # because nothing told him he'd taken it badly.
    scenario = build_cell_and_guard()
    scenario.guard.react_to("Look I have gold", {"bribe": 0.9})

    brief = brief_for(scenario)

    assert "Just now they offered you a bribe." in brief
    assert "you won't give them what they want for it" in brief


def test_reaction_scales_with_what_the_move_actually_earned():
    scenario = build_cell_and_guard()
    scenario.guard.react_to("I'm sorry about your brother.", {"empathy": 0.9})
    assert "It truly reaches you" in brief_for(scenario)

    scenario.guard.react_to("You're pathetic.", {"insult": 0.9})
    assert "It stings" in brief_for(scenario)

    scenario.guard.react_to("I will hurt you.", {"threat": 0.9})
    assert "It makes you angry." in brief_for(scenario)


def test_worn_out_tactic_is_voiced_as_worn_out():
    # Gotcha #15 made visible: the third time the same flattery lands at 0.
    scenario = build_cell_and_guard()
    for i in range(3):
        scenario.guard.react_to(f"You're a fine guard ({i}).", {"flattery": 0.9})

    assert "doesn't move you any more" in brief_for(scenario)


def test_no_reaction_line_for_questions_or_before_any_move():
    scenario = build_cell_and_guard()
    assert "Just now they" not in brief_for(scenario)

    scenario.guard.react_to("Do you have family?", {"question": 0.9})
    assert "Just now they" not in brief_for(scenario)


def test_reaction_line_sits_just_before_his_current_mood():
    # Near the end of the brief: the highest-attention position, closest to
    # where generation starts (same reasoning as RULE_REMINDER).
    scenario = build_cell_and_guard()
    scenario.guard.react_to("Look I have gold", {"bribe": 0.9})
    brief = brief_for(scenario)

    assert brief.index("Just now they") < brief.index("# Right now you feel")
    assert brief.index("Just now they") > brief.index("# Your private history")


def test_reaction_names_every_move_and_puts_a_question_first():
    # The user: a person "would take more than one meaning, though would act
    # on the question first if asked".
    scenario = build_cell_and_guard()
    scenario.guard.react_to(
        "Wow, look I am really sorry. How did it happen?", {"empathy": 0.55, "question": 0.4}
    )

    line = next(ln for ln in brief_for(scenario).splitlines() if ln.startswith("# Just now"))

    assert "showed real sympathy for you and your life" in line
    assert line.endswith("They asked you something too — answer that first.")


def test_several_moves_are_joined_naturally():
    scenario = build_cell_and_guard()
    scenario.guard.react_to("You're good at your job, and I'm innocent.", {"flattery": 0.5, "argument": 0.45})

    assert "Just now they flattered you and argued their case to you." in brief_for(scenario)


# --- R18: the engine directs what his reply does ---


def test_brief_states_what_he_is_doing_in_the_conversation():
    # R18: a real Easy playtest had "I need to get out" -> "Try harder." -- the
    # brief said how to sound but never what he was trying to achieve.
    scenario = build_cell_and_guard()

    brief = brief_for(scenario)

    assert "# What you're doing here" in brief
    assert scenario.guard.stance in brief
    assert brief.index("# What you're doing here") < brief.index("# Your private history")


def test_an_undirected_guard_gets_no_stance_and_no_intent():
    # Empty stance + empty intents is the pre-R18 actor, kept reachable so
    # directed vs undirected can be compared (experiments/2026-09-18-guard-coherence/).
    scenario = build_cell_and_guard()
    scenario.guard.stance = ""
    scenario.guard.reply_intents = {}
    scenario.guard.react_to("I need to get out", {"request": 0.9})

    brief = brief_for(scenario)

    assert "What you're doing here" not in brief
    assert "What you do now" not in brief


def test_a_request_is_met_with_a_plain_refusal_directive():
    scenario = build_cell_and_guard()
    scenario.guard.react_to("I need to get out", {"request": 0.9})

    assert "# What you do now: Say plainly that the door stays locked and why" in brief_for(
        scenario
    )


def test_a_pure_question_gets_an_answer_directive_though_no_reaction_line():
    # "what do you mean 'try harder'?" -- he doubled down instead of answering.
    scenario = build_cell_and_guard()
    scenario.guard.react_to("what do you mean try harder?", {"question": 0.9})
    brief = brief_for(scenario)

    assert "Just now they" not in brief
    assert "# What you do now: Answer what they asked, plainly" in brief


def test_a_question_is_dealt_with_before_the_other_move():
    # The user: "would act on the question first if asked".
    scenario = build_cell_and_guard()
    scenario.guard.react_to("I'm sorry. How did it happen?", {"empathy": 0.5, "question": 0.4})

    line = next(ln for ln in brief_for(scenario).splitlines() if ln.startswith("# What you do now"))

    assert line.index("Answer what they asked") < line.index("Let it reach you a little")


def test_no_more_than_two_directives():
    scenario = build_cell_and_guard()
    scenario.guard.react_to(
        "sorry, how? I have gold and I'm innocent",
        {"empathy": 0.3, "question": 0.3, "bribe": 0.2, "argument": 0.2},
    )

    line = next(ln for ln in brief_for(scenario).splitlines() if ln.startswith("# What you do now"))

    assert line.count(" Then: ") == 1


def test_other_is_only_a_directive_when_nothing_else_was_said():
    scenario = build_cell_and_guard()
    scenario.guard.react_to("Funny. Do you get many prisoners?", {"other": 0.5, "question": 0.4})
    line = next(ln for ln in brief_for(scenario).splitlines() if ln.startswith("# What you do now"))
    assert "React to what they said" not in line

    scenario.guard.react_to("hmm", {"other": 0.9})
    line = next(ln for ln in brief_for(scenario).splitlines() if ln.startswith("# What you do now"))
    assert "React to what they said" in line


def test_no_intent_before_any_move_and_none_when_classification_failed():
    scenario = build_cell_and_guard()
    assert "What you do now" not in brief_for(scenario)

    scenario.guard.react_to("Please, my friend.", None)  # keyword fallback: no tactics
    assert "What you do now" not in brief_for(scenario)
