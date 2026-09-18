from engine.tactics import TACTIC_ID_SLOT, TACTICS, classify_tactic


class RecordingChooser:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def choose(self, prompt, system_message, options, id_slot=None):
        self.calls.append((prompt, system_message, options, id_slot))
        return self.answer


def test_classifier_asks_for_one_of_the_tactics_on_its_own_slot():
    chooser = RecordingChooser(("bribe", 0.9))

    result = classify_tactic(chooser, "Look I have gold", "He was. Now stop wasting my time.")

    assert result == ("bribe", 0.9)
    prompt, system, options, slot = chooser.calls[0]
    assert options == TACTICS
    assert slot == TACTIC_ID_SLOT  # own KV slot: the static definitions stay cached
    # The previous reply is in the prompt -- "yes Dig" means nothing without it.
    assert prompt == 'Guard: "He was. Now stop wasting my time." / Prisoner: "Look I have gold" ->'
    assert '"I\'m not a threat" is not a threat' in system  # the negation guidance


def test_classifier_passes_through_a_failed_call():
    assert classify_tactic(RecordingChooser(None), "hello", "What?") is None


def test_static_definitions_are_identical_across_calls():
    # Only the per-turn prompt changes; a byte-identical system message is
    # what lets llama.cpp reuse the cached prefix.
    chooser = RecordingChooser(("other", 1.0))
    classify_tactic(chooser, "one", "a")
    classify_tactic(chooser, "two", "b")

    assert chooser.calls[0][1] == chooser.calls[1][1]
