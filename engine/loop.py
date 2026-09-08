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


def build_intro(premise: str) -> str:
    """The player's very first line — the one thing said before any model
    call happens, so it's the only place that's *guaranteed* to establish
    why they're here. Both `build_guard_brief` and `build_narration_brief`
    already pass `premise` to the model, which happily alludes to it
    ("The stag is gone.") — but until this was dynamic, the player
    themselves was never told, so those callbacks read as confusing rather
    than evocative (devlog: "what is this 'stag' all about?")."""
    return (
        "You wake up on cold stone. Through the bars, a guard stands watch. "
        f"You remember why you're here — {premise}. "
        "The only way out is to talk your way past him."
    )


class LLMResult(Protocol):
    response: str


class LLMClient(Protocol):
    def ask(
        self, prompt: str, system_message: str | None = None, sampler_config: str = "default"
    ) -> LLMResult: ...


BLAND_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was a bare dismissal ('Nothing.', 'Silence.', "
    "'Quiet.') — resist it. Give a short line that's actually *about* "
    "something: your mood, your history, or what was just said."
)

REPEAT_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to repeat something you've already said "
    "word-for-word — resist it. React fresh to *this* line, even if the "
    "sentiment ends up similar."
)


def _ask_and_record(
    llm: LLMClient, guard: Guard, prompt: str, brief: str, speaker: str
) -> str:
    def _needs_retry(reply: str) -> bool:
        return guardrail.is_bland_dismissal(reply) or guardrail.is_repeated_reply(
            reply, guard.own_lines(speaker)
        )

    result = llm.ask(prompt, system_message=brief)
    reply = guardrail.filter_reply(result.response)

    # The engine directs: a flat non-answer or a verbatim echo of a past
    # line gets one retake with a nudge, rather than shipping it or
    # silently rewriting what the actor said. sampler_config="retry" matters
    # as much as the nudge text — a resample at the same (fairly low)
    # default temperature is close enough to deterministic that it can
    # reproduce the exact bad reply it was meant to escape (devlog: happened
    # with both failure modes in real sessions).
    if _needs_retry(reply):
        nudge = BLAND_NUDGE if guardrail.is_bland_dismissal(reply) else REPEAT_NUDGE
        retry_result = llm.ask(
            prompt, system_message=brief + nudge, sampler_config="retry"
        )
        retry_reply = guardrail.filter_reply(retry_result.response)
        if not _needs_retry(retry_reply):
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
    voice.speak(build_intro(scenario.premise), speaker="dm")
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
