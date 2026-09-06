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


def test_repeating_the_same_line_is_penalised():
    guard = make_guard()
    guard.remember("player", "open the door")
    delta = guard.adjust_mood_from_text("open the door")
    assert delta < 0


def test_memory_is_capped():
    guard = make_guard()
    for i in range(20):
        guard.remember("player", f"line {i}")
    assert len(guard.memory) == 12


def test_thresholds():
    guard = make_guard(mood=80)
    assert guard.check_thresholds() == "unlock"

    guard = make_guard(mood=5)
    assert guard.check_thresholds() == "lockout"

    guard = make_guard(mood=50)
    assert guard.check_thresholds() is None
