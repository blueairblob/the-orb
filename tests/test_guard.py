from engine.guard import Guard, MoodDial


def make_guard(mood: int = 40) -> Guard:
    return Guard(id="guard", name="the guard", mood=MoodDial(value=mood))


def test_mood_dial_clamps_to_bounds():
    dial = MoodDial(value=95)
    dial.adjust(20)
    assert dial.value == 100
    dial.adjust(-500)
    assert dial.value == 0


def test_mood_band_narrative_register():
    assert MoodDial(value=0).band == "hostile"
    assert MoodDial(value=100).band == "ready to help"


def test_kind_words_raise_mood():
    guard = make_guard()
    delta = guard.adjust_mood_from_text("Please, my friend, I mean no harm.")
    assert delta > 0
    assert guard.mood.value > 40


def test_rude_words_lower_mood():
    guard = make_guard()
    delta = guard.adjust_mood_from_text("You're an idiot, open the door.")
    assert delta < 0
    assert guard.mood.value < 40


def test_threats_lower_mood_more_than_rudeness():
    rude_guard = make_guard()
    rude_guard.adjust_mood_from_text("You're pathetic.")

    threat_guard = make_guard()
    threat_guard.adjust_mood_from_text("Open the door or I will kill you.")

    assert threat_guard.mood.value < rude_guard.mood.value


def test_negated_threat_does_not_lower_mood():
    # Regression (real playtest 2026-09-15): "I'm not a threat to anyone"
    # docked mood as if it were an actual threat -- pure set-membership
    # matching had no sense of what came right before the trigger word.
    guard = make_guard()
    delta = guard.adjust_mood_from_text("Please, I'm not a threat to anyone.")
    assert delta > 0  # the "please" still lands -- only the threat penalty is suppressed
    assert guard.mood.value > 40


def test_negated_kind_word_does_not_raise_mood():
    # Same fix, opposite direction: "I don't appreciate this" is a
    # complaint, not gratitude.
    guard = make_guard()
    delta = guard.adjust_mood_from_text("I don't appreciate this at all.")
    assert delta == 0


def test_negated_rude_word_does_not_lower_mood():
    guard = make_guard()
    delta = guard.adjust_mood_from_text("You're not stupid, actually.")
    assert delta == 0


def test_distant_negation_does_not_suppress_the_match():
    # NEGATION_WINDOW is deliberately small -- a negation several words
    # earlier in an unrelated clause shouldn't reach across and suppress a
    # real trigger word later in the sentence.
    guard = make_guard()
    delta = guard.adjust_mood_from_text(
        "No, that's not what I meant — but I still think you're pathetic."
    )
    assert delta < 0


def test_repeating_the_same_line_is_penalised():
    guard = make_guard()
    guard.remember("player", "open the door")
    delta = guard.adjust_mood_from_text("open the door")
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
    guard = make_guard(mood=80)
    assert guard.check_thresholds() == "unlock"

    guard = make_guard(mood=5)
    assert guard.check_thresholds() == "lockout"

    guard = make_guard(mood=50)
    assert guard.check_thresholds() is None


def test_secret_not_revealed_below_threshold():
    guard = make_guard(mood=50)
    assert guard.maybe_reveal_secret() is False
    assert guard.secret_revealed is False


def test_secret_reveals_once_threshold_crossed():
    guard = make_guard(mood=70)
    assert guard.maybe_reveal_secret() is True
    assert guard.secret_revealed is True


def test_secret_reveal_is_permanent_once_flipped():
    # PRD §22 Gotcha #3: "bound thereafter" -- not reversible if mood later
    # drops back below secret_reveal_threshold.
    guard = make_guard(mood=70)
    guard.maybe_reveal_secret()
    guard.mood.value = 20

    assert guard.secret_revealed is True
    assert guard.maybe_reveal_secret() is False  # already revealed -- no-op, not a re-reveal
