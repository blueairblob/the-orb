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

from engine import guardrail
from engine.brief import build_brief
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


def run_turn(
    scenario: CellAndGuard, llm: LLMClient, player_utterance: str
) -> tuple[str, str | None]:
    """Runs one turn end to end. Returns (spoken_reply, outcome), where
    outcome is 'unlock', 'lockout', or None."""
    guard: Guard = scenario.guard
    # Check for a repeat against prior turns before this one joins memory.
    guard.adjust_mood_from_text(player_utterance)
    guard.remember("player", player_utterance)
    scenario.world.clock.advance(TURN_MINUTES)

    outcome = guard.check_thresholds()
    if outcome == "unlock":
        scenario.door.unlock()

    brief = build_brief(guard, scenario.door, scenario.room)
    result = llm.ask(player_utterance, system_message=brief)
    reply = guardrail.filter_reply(result.response)
    guard.remember("guard", reply)
    return reply, outcome


def run_loop(
    scenario: CellAndGuard, llm: LLMClient, voice: Voice, save_path: Path
) -> None:
    voice.speak(INTRO)
    while True:
        try:
            utterance = voice.listen()
        except EOFError:
            break
        if utterance.strip().lower() in {"quit", "exit"}:
            break
        if not utterance.strip():
            continue

        reply, outcome = run_turn(scenario, llm, utterance)
        voice.speak(reply)
        save_state(save_path, scenario)

        if outcome == "unlock":
            voice.speak("(The door creaks open. You're free.)")
            break
        if outcome == "lockout":
            voice.speak("(The guard storms off. Your only way out just left.)")
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
