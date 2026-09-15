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
from engine.brief import VOICE_EXAMPLE_REPLIES, build_guard_brief
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

# A generic "don't repeat yourself" framing (REPEAT_NUDGE) does not work for
# this specific failure — tested directly against the real backend (real
# playtest 2026-09-14): asked "what's your name?" at retry-level sampling
# (temperature=1.0) *with* REPEAT_NUDGE appended, the model gave the exact
# VOICE_EXAMPLES line back 4/4 times. It has to be told, specifically, that
# the offending text *is* one of the examples — that framing alone fixed it
# 4/4 times in the same test. Worded differently from REPEAT_NUDGE on
# purpose: "something you've already said" is false here (the guard never
# actually said this before), which risks confusing the model about what
# it's even being asked to avoid.
VOICE_EXAMPLE_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to answer with the exact words shown in the "
    "examples above — resist it. Those show your voice, not your actual "
    "line. Say something different that still sounds like you."
)

# Same situation as VOICE_EXAMPLE_NUDGE: PERSONA already states this rule,
# RULE_REMINDER already restates it right before generation, and neither
# was enough on its own (real playtest 2026-09-14: "Tell me about this
# place" named the room 4/4 times even with a nudge naming the problem
# directly, same as the voice-example case) — so this also falls back to
# guardrail.FALLBACK_LINE on a second failure rather than retrying forever.
ROOM_DESCRIPTION_NUDGE = (
    "\n\n# Note\n"
    "Your instinct just now was to describe the cell or your surroundings "
    "— resist it, that's the Dungeon Master's to narrate, not yours to say. "
    "React to what they actually asked without naming or describing where "
    "you are."
)

_NUDGES = {
    "bland": BLAND_NUDGE,
    "self_repeat": REPEAT_NUDGE,
    "voice_example": VOICE_EXAMPLE_NUDGE,
    "room_description": ROOM_DESCRIPTION_NUDGE,
}

# Failure modes that measurably don't reliably escape via resampling alone
# and so fall back to a safe line on a second failure rather than shipping a
# second bad reply. Bland dismissals aren't in this set — retry does
# reliably improve on them (test_retry_gives_up_after_one_more_bland_reply
# keeps that established, still-true behavior as-is). self_repeat *was*
# exempted on the same assumption, but two real sessions (2026-09-15) each
# hit a genuine double failure ("Begging doesn't work." / "Hunger is a
# powerful thing.", both shipped twice verbatim) — tested directly
# afterward: retry+REPEAT_NUDGE only escapes a self-repeat about half the
# time, common enough to explain both. A verbatim self-echo reads just as
# broken to a player as a copied voice-example line; treat it the same way.
_FALLS_BACK_ON_RETRY_FAILURE = {"voice_example", "room_description", "self_repeat"}


def _ask_and_record(
    llm: LLMClient,
    guard: Guard,
    prompt: str,
    brief: str,
    speaker: str,
    room_name: str | None = None,
    room_description: str = "",
) -> str:
    own_lines = guard.own_lines(speaker)
    # Voice examples and the room-description rule only apply to the guard
    # (brief.py's few-shot block, PERSONA's own-surroundings ban) — checking
    # them for a DM line, whose whole job is describing the scene, would be
    # meaningless. room_name is None for DM calls for the same reason.
    voice_examples = list(VOICE_EXAMPLE_REPLIES) if speaker == "guard" else []

    def _failure(reply: str) -> str | None:
        if guardrail.is_bland_dismissal(reply):
            return "bland"
        if guardrail.is_repeated_reply(reply, own_lines):
            return "self_repeat"
        if guardrail.is_repeated_reply(reply, voice_examples):
            return "voice_example"
        if room_name is not None and guardrail.is_room_description(
            reply, room_name, room_description
        ):
            return "room_description"
        return None

    result = llm.ask(prompt, system_message=brief)
    reply = guardrail.filter_reply(result.response)

    # The engine directs: a flat non-answer, a verbatim echo of a past line,
    # or a verbatim copy of a voice-example line gets one retake with a
    # nudge naming the specific problem, rather than shipping it or silently
    # rewriting what the actor said. sampler_config="retry" matters as much
    # as the nudge text — a resample at the same (fairly low) default
    # temperature is close enough to deterministic that it can reproduce the
    # exact bad reply it was meant to escape (devlog: happened with multiple
    # failure modes in real sessions).
    failure = _failure(reply)
    if failure is not None:
        retry_result = llm.ask(
            prompt, system_message=brief + _NUDGES[failure], sampler_config="retry"
        )
        retry_reply = guardrail.filter_reply(retry_result.response)
        retry_failure = _failure(retry_reply)
        if retry_failure is None:
            reply = retry_reply
        elif failure in _FALLS_BACK_ON_RETRY_FAILURE:
            # Unlike bland dismissals (which do reliably escape on retry —
            # see test_retry_gives_up_after_one_more_bland_reply for that
            # established, intentional "keep the first attempt" behavior),
            # these measurably don't (see _FALLS_BACK_ON_RETRY_FAILURE's own
            # comment above) — shipping the same bad reply twice is worse
            # than the guardrail's own last-resort line.
            reply = guardrail.FALLBACK_LINE

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

    # Brief reflects secret_revealed as it stood *before* this turn, so the
    # turn eligibility first opens still gets the "may reveal" framing — a
    # real chance to narrate the moment — rather than skipping straight to
    # "already revealed" before it's ever actually been said. Flipped for
    # future turns only after this one's brief and reply are done.
    brief = build_guard_brief(guard, scenario.door, scenario.room, scenario.premise)
    reply = _ask_and_record(
        llm,
        guard,
        player_utterance,
        brief,
        "guard",
        room_name=scenario.room.name,
        room_description=scenario.room.description,
    )
    guard.maybe_reveal_secret()
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
