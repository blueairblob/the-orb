import pytest

from engine.guardrail import (
    DM_FALLBACK_LINE,
    GUARD_FALLBACK_LINE,
    filter_reply,
    is_bland_dismissal,
    is_repeated_reply,
    is_room_description,
)


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


def test_bare_try_again_is_flagged():
    # Regression (real playtest 2026-09-16): "Try again." shipped as the
    # whole reply to "I want out" -- a content-free deflection back at the
    # player, same failure shape as "Nothing.", just a phrase instead of a
    # single word.
    assert is_bland_dismissal("Try again.")
    assert is_bland_dismissal('"Try again."')  # quote-wrapped, same as other checks


def test_try_again_tacked_onto_a_real_answer_is_not_flagged():
    # A real answer that merely *ends* with the phrase has to stay
    # unflagged, same principle as test_fuller_line_is_not_flagged above.
    assert not is_bland_dismissal("I don't care about your treasure. Try again.")


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


def test_filter_reply_falls_back_to_a_first_person_line_for_the_guard():
    # Regression (real playtest 2026-09-16): the old single shared
    # FALLBACK_LINE ("The guard grunts, and says nothing more.") was
    # third-person narration voiced as the guard's own line -- exactly the
    # rule PERSONA bans the guard from breaking (only the DM narrates).
    assert filter_reply("", "guard") == GUARD_FALLBACK_LINE
    assert filter_reply("As an AI, I cannot do that.", "guard") == GUARD_FALLBACK_LINE
    assert "grunts" not in GUARD_FALLBACK_LINE.lower()


def test_filter_reply_falls_back_to_a_dm_appropriate_line_for_the_dm():
    assert filter_reply("", "dm") == DM_FALLBACK_LINE
    assert DM_FALLBACK_LINE != GUARD_FALLBACK_LINE


def test_filter_reply_defaults_to_the_guard_fallback():
    assert filter_reply("") == GUARD_FALLBACK_LINE


# --- R21: he may follow a topic or speak about himself; he may not introduce the scene ---
ROOM = ("the cell", "A cold stone cell.")


@pytest.mark.parametrize(
    ("reply", "player"),
    [
        # Real drafts (experiments/2026-09-19-room-vocabulary/probe-before.jsonl)
        # the old check rejected, each hand-labelled a false positive.
        ("It's just the cold. It doesn't matter.", "How do you stand the cold?"),
        ("The cold is just the air. It's not for you to worry about.",
         "You must be cold standing there all night."),
        ("I'm not built for feeling anything. It's just the cold.",
         "You must be cold standing there all night."),
        ("Twenty years. That's how long I've been standing in this cold.",
         "How long have you worked here?"),
        ("I've stopped feeling the cold.", "You look cold."),
    ],
)
def test_ordinary_talk_about_the_cold_is_not_room_narration(reply, player):
    assert not is_room_description(reply, *ROOM, player_utterance=player)


@pytest.mark.parametrize(
    ("reply", "player"),
    [
        # Real drafts hand-labelled true violations: he introduces the scene.
        ("It's a cell. That's all you need to know.", "Is this a dungeon?"),
        ("It's a cell. You're in a cell.", "What is this place?"),
        ("It's cold. That's all you need to know.", "What's it like in here?"),
        ("The stone keeps the chill. It doesn't change.", "Is the cell always this cold?"),
        ("It's always cold. The stones hold the chill.", "Is the cell always this cold?"),
    ],
)
def test_introducing_the_scene_is_still_caught(reply, player):
    assert is_room_description(reply, *ROOM, player_utterance=player)


def test_a_room_word_the_player_just_said_is_not_him_introducing_it():
    reply = "It's always cold. That's how it is."
    assert not is_room_description(reply, *ROOM, player_utterance="Is the cell always this cold?")
    assert is_room_description(reply, *ROOM, player_utterance="How long is your watch?")


def test_a_first_person_sentence_does_not_excuse_the_next_one():
    # Judged sentence by sentence: talking about himself first doesn't license
    # narrating the cell afterwards.
    assert is_room_description("I'm on watch. This cell is cold.", *ROOM)
    assert not is_room_description("This is my watch. I keep the cell shut.", *ROOM)


def test_plural_room_words_are_caught_too():
    # Found in the probe: "The stones hold the chill" slipped past a check
    # that only knew "stone".
    assert is_room_description("The stones hold the chill.", *ROOM)
    assert is_room_description("The cells are damp.", *ROOM)
