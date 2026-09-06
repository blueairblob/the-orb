import dataclasses

from engine.loop import run_loop, run_turn
from engine.scenario import build_cell_and_guard


@dataclasses.dataclass
class StubResult:
    response: str


class StubLLM:
    """A fake LLM client: echoes a fixed in-character line, so engine-logic
    tests never need the real model."""

    def __init__(self, reply: str = "Silence."):
        self.reply = reply
        self.calls: list[tuple[str, str | None]] = []

    def ask(self, prompt: str, system_message: str | None = None) -> StubResult:
        self.calls.append((prompt, system_message))
        return StubResult(response=self.reply)


class ScriptedVoice:
    """A fake voice: plays back a scripted list of player lines, records
    what was spoken back."""

    def __init__(self, lines: list[str]):
        self._lines = iter(lines)
        self.spoken: list[str] = []

    def listen(self) -> str:
        try:
            return next(self._lines)
        except StopIteration:
            raise EOFError from None

    def speak(self, text: str) -> None:
        self.spoken.append(text)


def test_run_turn_updates_mood_and_memory():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="Hmph. Fine.")

    reply, outcome = run_turn(scenario, llm, "please, my friend")

    assert reply == "Hmph. Fine."
    assert outcome is None
    assert scenario.guard.mood.value > 40
    assert "player: please, my friend" in scenario.guard.memory
    assert "guard: Hmph. Fine." in scenario.guard.memory
    assert llm.calls[0][0] == "please, my friend"


def test_kind_conversation_reaches_unlock():
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    # Varied phrasing avoids the repeat penalty, which would otherwise cancel
    # out most of the kindness delta (see test_repeating_the_same_line_is_penalised).
    kind_lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]

    outcome = None
    for line in kind_lines:
        _, outcome = run_turn(scenario, llm, line)
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
        _, outcome = run_turn(scenario, llm, line)
        if outcome:
            break

    assert outcome == "lockout"


def test_run_loop_ends_session_on_unlock(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM(reply="...")
    lines = [f"please, my friend, thank you kindly ({i})" for i in range(15)]
    voice = ScriptedVoice(lines)
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert scenario.door.locked is False
    assert any("free" in line for line in voice.spoken)
    assert save_path.is_file()


def test_run_loop_quits_on_command(tmp_path):
    scenario = build_cell_and_guard()
    llm = StubLLM()
    voice = ScriptedVoice(["hello", "quit"])
    save_path = tmp_path / "save.json"

    run_loop(scenario, llm, voice, save_path)

    assert len(llm.calls) == 1
