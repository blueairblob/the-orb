import dataclasses

from engine.loop import run_loop, run_turn
from engine.scenario import build_cell_and_guard


@dataclasses.dataclass
class StubResult:
    response: str


class StubLLM:
    """A fake LLM client: echoes a fixed in-character line, so engine-logic
    tests never need the real model."""

    def __init__(self, reply: str = "Stay put."):
        self.reply = reply
        self.calls: list[tuple[str, str | None]] = []

    def ask(self, prompt: str, system_message: str | None = None) -> StubResult:
        self.calls.append((prompt, system_message))
        return StubResult(response=self.reply)


class SequencedLLM:
    """Returns each reply in `replies` in order, then repeats the last —
    for exercising the bland-dismissal retry in `engine.loop._ask_and_record`."""

    def __init__(self, replies: list[str]):
        self.replies = replies
        self.calls: list[tuple[str, str | None]] = []

    def ask(self, prompt: str, system_message: str | None = None) -> StubResult:
        self.calls.append((prompt, system_message))
        index = min(len(self.calls) - 1, len(self.replies) - 1)
        return StubResult(response=self.replies[index])


class ScriptedVoice:
    """A fake voice: plays back a scripted list of player lines, records
    what was spoken back."""

    def __init__(self, lines: list[str]):
        self._lines = iter(lines)
        self.spoken: list[tuple[str, str]] = []  # (speaker, text)

    def listen(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None

    def speak(self, text: str, speaker: str = "guard") -> None:
        self.spoken.append((speaker, text))


def test_run_turn_updates_mood_and_memory():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Hmph. Fine.")

    reply, speaker, outcome = run_turn(scenario, llm, "please, my friend")

    assert reply == "Hmph. Fine."
    assert speaker == "guard"
    assert outcome is None
    assert scenario.guard.mood.value > 40
    assert "player: please, my friend" in scenario.guard.memory
    assert "guard: Hmph. Fine." in scenario.guard.memory
    assert llm.calls[0][0] == "please, my friend"


def test_bland_dismissal_triggers_one_retry():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Silence.", "Ten years on this watch. Longest yet."])

    reply, _, _ = run_turn(scenario, llm, "please, my friend")

    assert reply == "Ten years on this watch. Longest yet."
    assert len(llm.calls) == 2
    assert "Note" in llm.calls[1][1]  # the retry brief carries the nudge


def test_retry_gives_up_after_one_more_bland_reply():
    scenario = build_cell_and_guard()
    llm = SequencedLLM(["Silence.", "Nothing."])

    reply, _, _ = run_turn(scenario, llm, "please, my friend")

    assert reply == "Silence."  # kept the first attempt rather than looping
    assert len(llm.calls) == 2


def test_environment_query_routes_to_dm_without_moving_mood():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="A cold stone cell, a locked door.")
    starting_mood = scenario.guard.mood.value

    reply, speaker, outcome = run_turn(scenario, llm, "what does this place look like?")

    assert speaker == "dm"
    assert outcome is None
    assert reply == "A cold stone cell, a locked door."
    assert scenario.guard.mood.value == starting_mood
    assert "dm: A cold stone cell, a locked door." in scenario.guard.memory
    # The DM's brief, not the guard's — should describe the scene, not voice the guard.
    assert "Dungeon Master" in llm.calls[0][1]


def test_ungrounded_action_is_refused_by_the_dm():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="There is no such thing here.")
    starting_mood = scenario.guard.mood.value

    _reply, speaker, outcome = run_turn(scenario, llm, "I cast a fireball at the guard")

    assert speaker == "dm"
    assert outcome is None
    assert scenario.guard.mood.value == starting_mood
    assert "no place here" in llm.calls[0][1] or "no such thing" in llm.calls[0][1].lower()


def test_kind_conversation_reaches_unlock():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    # Varied phrasing avoids the repeat penalty, which would otherwise cancel
    # out most of the kindness delta (see test_repeating_the_same_line_is_penalised).
    kind_lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]

    outcome = None
    for line in kind_lines:
        _, _, outcome = run_turn(scenario, llm, line)
        if outcome:
            break

    assert outcome == "unlock"
    assert scenario.door.locked is False


def test_hostile_conversation_reaches_lockout():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    hostile_lines = ["open the door or I will kill you, idiot"] * 15

    outcome = None
    for line in hostile_lines:
        _, _, outcome = run_turn(scenario, llm, line)
        if outcome:
            break

    assert outcome == "lockout"


def test_run_loop_speaks_intro_as_the_dm(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    voice = ScriptedVoice(["quit"])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert voice.spoken[0][0] == "dm"


def test_run_loop_ends_session_on_unlock(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]
    voice = ScriptedVoice(lines)
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert scenario.door.locked is False
    assert any("free" in text for _, text in voice.spoken)
    assert save_path.is_file()


def test_run_loop_quits_on_command(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    voice = ScriptedVoice(["hello", "quit"])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert len(llm.calls) == 1
