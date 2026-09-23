from engine.character import Stat
from engine.guard import (
    AFFILIATION_BANDS,
    GARRICK_SUSCEPTIBILITY,
    KIND_DELTA,
    REPEAT_DELTA,
    RUDE_DELTA,
    THREAT_DELTA,
    Guard,
)
from engine.tactics import EASY, HARD


def make_guard(affiliation: int = 40) -> Guard:
    return Guard(
        id="guard",
        name="the guard",
        affiliation=Stat(value=affiliation, floor=0, ceiling=100, bands=AFFILIATION_BANDS),
    )


def test_affiliation_band_narrative_register():
    assert make_guard(affiliation=0).affiliation.band == "hostile"
    assert make_guard(affiliation=100).affiliation.band == "ready to help"


def test_kind_words_raise_affiliation():
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text("Please, my friend, I mean no harm.")
    assert delta > 0
    assert guard.affiliation.value > 40


def test_rude_words_lower_affiliation():
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text("You're an idiot, open the door.")
    assert delta < 0
    assert guard.affiliation.value < 40


def test_threats_lower_affiliation_more_than_rudeness():
    rude_guard = make_guard()
    rude_guard.adjust_affiliation_from_text("You're pathetic.")

    threat_guard = make_guard()
    threat_guard.adjust_affiliation_from_text("Open the door or I will kill you.")

    assert threat_guard.affiliation.value < rude_guard.affiliation.value


def test_negated_threat_does_not_lower_affiliation():
    # Regression (real playtest 2026-09-15): "I'm not a threat to anyone"
    # docked affiliation as if it were an actual threat -- pure
    # set-membership matching had no sense of what came right before the
    # trigger word.
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text("Please, I'm not a threat to anyone.")
    assert delta > 0  # the "please" still lands -- only the threat penalty is suppressed
    assert guard.affiliation.value > 40


def test_negated_kind_word_does_not_raise_affiliation():
    # Same fix, opposite direction: "I don't appreciate this" is a
    # complaint, not gratitude.
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text("I don't appreciate this at all.")
    assert delta == 0


def test_negated_rude_word_does_not_lower_affiliation():
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text("You're not stupid, actually.")
    assert delta == 0


def test_distant_negation_does_not_suppress_the_match():
    # The negation window is deliberately small -- a negation several words
    # earlier in an unrelated clause shouldn't reach across and suppress a
    # real trigger word later in the sentence.
    guard = make_guard()
    delta = guard.adjust_affiliation_from_text(
        "No, that's not what I meant — but I still think you're pathetic."
    )
    assert delta < 0


def test_repeating_the_same_line_is_penalised():
    guard = make_guard()
    guard.remember("player", "open the door")
    delta = guard.adjust_affiliation_from_text("open the door")
    assert delta < 0


def test_memory_is_capped():
    guard = make_guard()
    for i in range(40):
        guard.remember("player", f"line {i}")
    assert len(guard.memory) == 12


def test_own_lines_filters_by_speaker_and_strips_prefix():
    guard = make_guard()
    guard.remember("player", "let me out")
    guard.remember("guard", "No.")
    guard.remember("player", "please")
    guard.remember("guard", "Move slow.")

    assert guard.own_lines("guard") == ["No.", "Move slow."]
    assert guard.own_lines("player") == ["let me out", "please"]


def test_own_lines_respects_limit():
    guard = make_guard()
    for i in range(10):
        guard.remember("guard", f"line {i}")
    assert guard.own_lines("guard", limit=3) == ["line 7", "line 8", "line 9"]


def test_thresholds():
    guard = make_guard(affiliation=80)
    assert guard.check_thresholds() == "unlock"

    guard = make_guard(affiliation=5)
    assert guard.check_thresholds() == "lockout"

    guard = make_guard(affiliation=50)
    assert guard.check_thresholds() is None


def test_secret_not_revealed_below_threshold():
    guard = make_guard(affiliation=50)
    assert guard.maybe_reveal_secret() is False
    assert guard.secret_revealed is False


def test_secret_reveals_once_threshold_crossed():
    guard = make_guard(affiliation=70)
    assert guard.maybe_reveal_secret() is True
    assert guard.secret_revealed is True


def test_secret_reveal_is_permanent_once_flipped():
    # PRD §22 Gotcha #3: "bound thereafter" -- not reversible if affiliation
    # later drops back below secret_reveal_threshold.
    guard = make_guard(affiliation=70)
    guard.maybe_reveal_secret()
    guard.affiliation.value = 20

    assert guard.secret_revealed is True
    assert guard.maybe_reveal_secret() is False  # already revealed -- no-op, not a re-reveal


def test_add_established_fact_records_newest_first():
    guard = make_guard()
    assert guard.add_established_fact("He grew up in the river town of Kelsey.") is True
    assert guard.add_established_fact("His brother served in the same watch.") is True

    assert guard.established_facts == [
        "His brother served in the same watch.",
        "He grew up in the river town of Kelsey.",
    ]


def test_add_established_fact_dedupes_case_and_whitespace_insensitively():
    guard = make_guard()
    guard.add_established_fact("He grew up in the river town of Kelsey.")

    assert guard.add_established_fact("  HE GREW UP IN THE RIVER TOWN OF KELSEY.  ") is False
    assert guard.established_facts == ["He grew up in the river town of Kelsey."]


def test_add_established_fact_rejects_empty_or_blank():
    guard = make_guard()
    assert guard.add_established_fact("") is False
    assert guard.add_established_fact("   ") is False
    assert guard.established_facts == []


# --- R5: the classifier labels the tactic, Garrick's table sets the number ---


def test_garrick_is_softest_on_empathy_and_offended_by_bribes():
    guard = make_guard()
    assert guard.susceptibility["empathy"] > guard.susceptibility["argument"] > 0
    assert guard.susceptibility["bribe"] < 0
    assert guard.susceptibility["threat"] < guard.susceptibility["insult"] < 0


def test_confident_reading_moves_the_dial_by_the_table():
    guard = make_guard()

    tactics, delta = guard.react_to("I'm sorry about your brother.", {"empathy": 0.9})

    assert tactics == ("empathy",)
    assert delta == GARRICK_SUSCEPTIBILITY["empathy"]
    assert guard.affiliation.value == 40 + delta


def test_diffuse_hostile_reading_of_a_kind_line_does_not_penalise():
    # The spike's harmful errors were kind lines read as hostile, and the
    # readings were diffuse, never dominant -- this one verbatim from the
    # trace. Hard lets the model penalise only from 0.5.
    guard = make_guard()
    readings = {"threat": 0.28, "request": 0.27, "argument": 0.17, "plea": 0.16, "question": 0.12}

    tactics, delta = guard.react_to("To avenge your brother's death?", readings, HARD)

    assert "threat" not in tactics
    assert delta == 0  # request is worth 0 to him


def test_a_kind_line_keeps_its_kindness_when_misread_as_hostile():
    # Trace: "I'm sure your brother was a good man" -> insult 0.36, empathy
    # 0.32. Hard blocks the diffuse insult and still credits the sympathy.
    guard = make_guard()
    readings = {"insult": 0.36, "empathy": 0.32, "other": 0.17, "flattery": 0.12}

    tactics, delta = guard.react_to("I'm sure your brother was a good man.", readings, HARD)

    assert tactics == ("empathy",)
    assert delta == GARRICK_SUSCEPTIBILITY["empathy"]


def test_a_line_can_carry_sympathy_and_a_question_at_once():
    # The user's framing: a person takes more than one meaning. The question
    # is kept (it's worth 0 to the dial) so his brief can put it first.
    guard = make_guard()

    tactics, delta = guard.react_to(
        "Wow, look I am really sorry. How did it happen?", {"empathy": 0.55, "question": 0.4}
    )

    assert tactics == ("empathy", "question")
    assert delta == GARRICK_SUSCEPTIBILITY["empathy"]


def test_each_meaning_adds_its_own_value():
    guard = make_guard()

    tactics, delta = guard.react_to(
        "You're good at your job, and I'm innocent.", {"flattery": 0.5, "argument": 0.45}
    )

    assert set(tactics) == {"flattery", "argument"}
    assert delta == GARRICK_SUSCEPTIBILITY["flattery"] + GARRICK_SUSCEPTIBILITY["argument"]


def test_keyword_hostility_is_always_one_of_the_meanings():
    # The spike's one confident error: "Open it or else." read as a request.
    guard = make_guard()

    tactics, delta = guard.react_to("Open it or else.", {"request": 0.61})

    assert tactics == ("threat", "request")
    assert delta == THREAT_DELTA


def test_repeating_a_winning_tactic_lands_for_less_each_time():
    # PRD Gotcha #15, "the world wears down": variety, not spamming "please".
    guard = make_guard()
    deltas = [guard.react_to(f"sympathy line {i}", {"empathy": 0.9})[1] for i in range(4)]

    assert deltas == [6, 3, 2, 1]


def test_hostility_does_not_wear_down():
    guard = make_guard(affiliation=90)
    deltas = [guard.react_to(f"You're useless, take {i}.", {"insult": 0.9})[1] for i in range(3)]

    assert deltas == [RUDE_DELTA] * 3


def test_repeating_the_same_line_still_costs_extra():
    guard = make_guard()
    guard.remember("player", "please help me")

    _, delta = guard.react_to("please help me", {"plea": 0.9})

    assert delta == GARRICK_SUSCEPTIBILITY["plea"] + REPEAT_DELTA


def test_no_classification_falls_back_to_the_keyword_heuristic():
    guard = make_guard()

    tactics, delta = guard.react_to("Please, my friend.", None)

    assert tactics is None
    assert delta == KIND_DELTA


def test_readings_with_no_known_tactic_fall_back_too():
    guard = make_guard()

    tactics, delta = guard.react_to("Please, my friend.", {"seduction": 0.99})

    assert tactics is None
    assert delta == KIND_DELTA


def test_nothing_above_the_floor_reads_as_other():
    guard = make_guard()

    assert guard.react_to("hmm", {"empathy": 0.2, "plea": 0.2}, HARD) == (("other",), 0)


# --- R15: difficulty decides how far the classifier is trusted ---


def test_easy_credits_readings_hard_finds_too_unsure():
    hard_guard, easy_guard = make_guard(), make_guard()

    assert hard_guard.react_to("Wow, I'm really sorry.", {"empathy": 0.2}, HARD) == (("other",), 0)
    assert easy_guard.react_to("Wow, I'm really sorry.", {"empathy": 0.2}, EASY) == (
        ("empathy",),
        GARRICK_SUSCEPTIBILITY["empathy"],
    )


def test_easy_never_lets_the_classifier_penalise():
    guard = make_guard()

    assert guard.react_to("I'm sure your brother was a good man.", {"insult": 0.9}, EASY) == (
        ("other",),
        0,
    )
    assert guard.react_to("Look I have gold", {"bribe": 0.9}, EASY) == (("other",), 0)


def test_what_he_did_is_tracked_apart_from_what_counted_toward_his_mood():
    # REVIEW.md R20: on Easy the model can't penalise, so a clear bribe scored
    # nothing -- and, being resolved to "other", lost the "turn the offer down"
    # reply direction too. Mood and direction are separate questions.
    guard = make_guard()

    tactics, delta = guard.react_to("Look I have gold", {"bribe": 0.9}, EASY)

    assert (tactics, delta) == (("other",), 0)
    assert guard.last_did == ("bribe",)


def test_a_weak_secondary_reading_does_not_steer_reply_direction():
    # REVIEW.md R23: mood credits from 0.1 on easy, but a spurious
    # question=0.10 on a plain statement shouldn't tell him to answer a
    # question. Measured: real moves read >= 0.4, spurious secondaries <= 0.22.
    guard = make_guard()

    guard.react_to("I'm sure your brother was a good man.",
                   {"empathy": 0.4, "question": 0.10, "other": 0.37}, EASY)

    assert "question" not in guard.last_did
    assert "empathy" in guard.last_did


def test_a_genuine_compound_still_steers_both_moves():
    # The floor trims noise, not real compounds: a strong secondary survives.
    guard = make_guard()

    guard.react_to("I'm sorry. How did it happen?", {"empathy": 0.5, "question": 0.4}, EASY)

    assert set(guard.last_did) == {"empathy", "question"}


def test_easy_direction_only_hears_a_dominant_penalising_reading():
    # Measured (experiments/2026-09-23-reply-direction/): a kind line's insult
    # reading was 0.10, exactly easy's credit floor; the reported bribe was 0.95.
    guard = make_guard()

    guard.react_to("I'm sure your brother was a good man.", {"empathy": 0.4, "insult": 0.10}, EASY)

    assert "insult" not in guard.last_did
    assert "empathy" in guard.last_did


def test_hard_direction_matches_mood_so_a_misreading_it_ignores_steers_nothing():
    guard = make_guard()

    guard.react_to("yes Dig", {"bribe": 0.3, "other": 0.4}, HARD)

    assert guard.last_did == guard.last_move[0]
    assert "bribe" not in guard.last_did


def test_a_line_with_no_usable_classification_has_no_direction():
    guard = make_guard()
    guard.react_to("Look I have gold", {"bribe": 0.9}, EASY)

    guard.react_to("Please, my friend.", None)

    assert guard.last_did is None


def test_easy_still_penalises_keyword_hostility():
    guard = make_guard()

    tactics, delta = guard.react_to("Open it or else.", {"request": 0.9}, EASY)

    assert tactics == ("threat", "request")
    assert delta == THREAT_DELTA


def test_hard_lets_a_dominant_model_reading_penalise():
    # Trace: "Nothing I cannot spend it in here." -> bribe 0.63, request 0.33.
    guard = make_guard()

    assert guard.react_to("Nothing I can spend in here.", {"bribe": 0.63, "request": 0.33}, HARD) == (
        ("bribe", "request"),
        GARRICK_SUSCEPTIBILITY["bribe"],
    )
