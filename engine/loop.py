"""The core loop (PRD §7): the smallest possible voice loop, one cell, one
guard (PRD §8, roadmap §24 step 4) — "you speak, the engine decides, it
speaks back."

Voice is text-mode on this host (see `engine/voice.py` for why); everything
else here is exactly what ships. `llm` is typed against a small protocol so
`run_turn` can be tested without the real model (`tests/test_loop.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

from engine import dm, guardrail
from engine.brief import build_guard_brief
from engine.guard import Guard
from engine.llm import GemmaHarness, is_model_ready
from engine.save import load_state, save_state
from engine.scenario import CellAndGuard
from engine.voice import Voice
from engine.voice_text import TextVoice

DEFAULT_SAVE_PATH = Path.home() / ".orb" / "cell-and-guard-save.json"
TURN_MINUTES = 1
INTRO = (
    "You wake up on cold stone. Through the bars, a guard stands watch. "
    "The only way out is to talk your way past him."
)


class LLMResult(Protocol):
    response: str


class LLMClient(Protocol):
    def ask(self, prompt: str, system_message: str | None = None) -> LLMResult: ...


RETRY_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was a bare dismissal ('Nothing.', 'Silence.', "
    "'Quiet.') — resist it. Give a short line that's actually *about* "
    "something: your mood, your history, or what was just said."
)


def _ask_and_record(
    llm: LLMClient, guard: Guard, prompt: str, brief: str, speaker: str
) -> str:
    result = llm.ask(prompt, system_message=brief)
    reply = guardrail.filter_reply(result.response)

    # The engine directs: a flat non-answer gets one retake with a nudge,
    # rather than shipping it or silently rewriting what the actor said.
    if guardrail.is_bland_dismissal(reply):
        retry_result = llm.ask(prompt, system_message=brief + RETRY_NUDGE)
        retry_reply = guardrail.filter_reply(retry_result.response)
        if not guardrail.is_bland_dismissal(retry_reply):
            reply = retry_reply

    guard.remember(speaker, reply)
    return reply


def run_turn(
    scenario: CellAndGuard, llm: LLMClient, player_utterance: str
) -> tuple[str, str, str | None]:
    """Runs one turn end to end. Returns (spoken_reply, speaker, outcome),
    where speaker is 'dm' or 'guard' and outcome is 'unlock', 'lockout', or
    None. Routes to the DM (PRD §12: "the DM wearing a different hat") for
    scene narration and grounding refusals; the guard only ever speaks his
    own dialogue — see `engine/dm.py`."""
    guard: Guard = scenario.guard
    scenario.world.clock.advance(TURN_MINUTES)
    route = dm.classify_utterance(player_utterance)

    if route == "refusal":
        guard.remember("player", player_utterance)
        brief = dm.build_refusal_brief(scenario.room, player_utterance)
        reply = _ask_and_record(llm, guard, player_utterance, brief, "dm")
        return reply, "dm", None

    if route == "narration":
        guard.remember("player", player_utterance)
        brief = dm.build_narration_brief(scenario.room, scenario.door, guard, scenario.premise)
        reply = _ask_and_record(llm, guard, player_utterance, brief, "dm")
        return reply, "dm", None

    # Default: dialogue directed at the guard.
    # Check for a repeat against prior turns before this one joins memory.
    guard.adjust_mood_from_text(player_utterance)
    guard.remember("player", player_utterance)

    outcome = guard.check_thresholds()
    if outcome == "unlock":
        scenario.door.unlock()

    brief = build_guard_brief(guard, scenario.door, scenario.room, scenario.premise)
    reply = _ask_and_record(llm, guard, player_utterance, brief, "guard")
    return reply, "guard", outcome


def run_loop(
    scenario: CellAndGuard, llm: LLMClient, voice: Voice, save_path: Path
) -> None:
    voice.speak(INTRO, speaker="dm")
    while True:
        try:
            utterance = voice.listen()
        except EOFError:
            break
        if utterance.strip().lower() in {"quit", "exit"}:
            break
        if not utterance.strip():
            continue

        reply, speaker, outcome = run_turn(scenario, llm, utterance)
        voice.speak(reply, speaker=speaker)
        save_state(save_path, scenario)

        if outcome == "unlock":
            voice.speak("(The door creaks open. You're free.)", speaker="dm")
            break
        if outcome == "lockout":
            voice.speak("(The guard storms off. Your only way out just left.)", speaker="dm")
            break


def main() -> None:
    if not is_model_ready():
        print(
            "Model not imported yet. Run `orb-harness setup` first.", file=sys.stderr
        )
        sys.exit(1)

    save_path = DEFAULT_SAVE_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    scenario = load_state(save_path)

    with GemmaHarness() as llm:
        run_loop(scenario, llm, TextVoice(), save_path)


if __name__ == "__main__":
    main()
