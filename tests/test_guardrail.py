from engine.guardrail import is_bland_dismissal, is_repeated_reply


def test_bare_dismissal_is_flagged():
    assert is_bland_dismissal("Silence.")
    assert is_bland_dismissal("nothing")
    assert is_bland_dismissal("Quiet!")


def test_quote_wrapped_dismissal_is_still_flagged():
    # Real sessions show the model occasionally wraps its whole reply in
    # quote marks — a bland dismissal shouldn't slip past retry just because
    # of that formatting quirk (devlog: '"Silence."' went unretried before
    # this was fixed).
    assert is_bland_dismissal('"Silence."')
    assert is_bland_dismissal("'Nothing.'")
    assert is_bland_dismissal("“Quiet.”")


def test_fuller_line_is_not_flagged():
    # PRD §3's Yoda principle wants real sparseness — a line that merely
    # starts with a banned word but goes on to say something specific must
    # not be treated the same as a bare non-answer.
    assert not is_bland_dismissal("Nothing worth saying.")
    assert not is_bland_dismissal("Another word. Nothing here.")
    assert not is_bland_dismissal("No.")
    assert not is_bland_dismissal("Fine.")


def test_verbatim_echo_of_own_past_line_is_flagged():
    # devlog: widening the guard's memory window (so he'd stop forgetting a
    # dozen-turn-old offer) had the side effect of making him more likely to
    # literally repeat a past line word-for-word — "Move slow." recurred
    # four times in one real session, for four unrelated prompts.
    assert is_repeated_reply("Move slow.", ["No.", "Move slow."])
    assert is_repeated_reply('"Move slow."', ["Move slow."])  # quotes stripped too


def test_fresh_line_is_not_flagged_as_repeat():
    assert not is_repeated_reply("Move slow.", ["No.", "Fine."])
    assert not is_repeated_reply("Move slow, then.", ["Move slow."])  # not verbatim
    assert not is_repeated_reply("Move slow.", [])
