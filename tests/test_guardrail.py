from engine.guardrail import is_bland_dismissal, is_repeated_reply, is_room_description


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


def test_padded_dismissal_is_flagged():
    # Regression (real playtest 2026-09-14): "Nothing worth mentioning." and
    # "Nothing matters now." both dodged genuine substantive questions
    # ("What did you do before you became a guard?") without answering them
    # — structurally the same hedge as a bare "Nothing.", just padded, and
    # just as content-free. This corrects the old assumption below (an
    # earlier version of this test asserted "Nothing worth saying." should
    # NOT be flagged) — there's no text-only way to tell that phrase apart
    # from the two real failures above; treating all three the same is the
    # more honest reading of what "bland" actually means here.
    assert is_bland_dismissal("Nothing worth mentioning.")
    assert is_bland_dismissal("Nothing matters now.")
    assert is_bland_dismissal("Nothing worth saying.")


def test_fuller_line_is_not_flagged():
    # PRD §3's Yoda principle wants real sparseness — a line that merely
    # *contains* a banned word, or goes on with enough real content, must
    # not be treated the same as a bare/padded non-answer.
    assert not is_bland_dismissal("Another word. Nothing here.")
    assert not is_bland_dismissal("Nothing you'll ever get from me, prisoner.")
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


def test_room_description_is_flagged():
    # Regression (real playtest 2026-09-14): "This is a cell. It's cold." /
    # "It's a cell. That's all you need to know." both broke PERSONA's own
    # "never describe the room" rule.
    assert is_room_description("This is a cell. It's cold.", "the cell")
    assert is_room_description("It's a cell. That's all you need to know.", "the cell")


def test_room_description_catches_description_vocabulary_too():
    # Regression (real playtest 2026-09-14, after the name-only version of
    # this check shipped): "It's stone and damp." names no room-type word
    # ("cell") but still describes it via the room's own description
    # vocabulary — the room-name-only check missed this one.
    assert is_room_description(
        "It's stone and damp. That's all you need to know.",
        "the cell",
        "A cold stone cell.",
    )


def test_room_description_generalises_past_this_one_scenario():
    assert is_room_description("You're standing in a dungeon, fool.", "a dungeon")


def test_unrelated_line_is_not_flagged_as_room_description():
    assert not is_room_description("Hmph. Fine.", "the cell")
    assert not is_room_description("We're both prisoners here, in a way.", "the cell")
